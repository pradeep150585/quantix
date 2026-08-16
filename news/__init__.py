"""
News engine – fetches financial news from RSS feeds, deduplicates,
and performs keyword-based sentiment scoring.
"""
import asyncio
import hashlib
import time
import re
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timedelta
import httpx
import feedparser
from loguru import logger

# Trusted financial RSS feeds — focused on Indian company results & news
RSS_FEEDS = [
    ("ET Markets",          "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms"),
    ("ET Earnings",         "https://economictimes.indiatimes.com/markets/earnings/rssfeeds/2146843.cms"),
    ("Moneycontrol News",   "https://www.moneycontrol.com/rss/results.xml"),
    ("Moneycontrol Markets","https://www.moneycontrol.com/rss/marketreports.xml"),
    ("BS Markets",          "https://www.business-standard.com/rss/markets-106.rss"),
    ("BS Companies",        "https://www.business-standard.com/rss/companies-101.rss"),
    ("LiveMint Markets",    "https://www.livemint.com/rss/markets"),
    ("LiveMint Companies",  "https://www.livemint.com/rss/companies"),
    ("Financial Express",   "https://www.financialexpress.com/market/feed/"),
]

POSITIVE_WORDS = {
    "surge", "rally", "gain", "rise", "jump", "soar", "breakout", "bullish",
    "strong", "beat", "outperform", "upgrade", "buy", "positive", "growth",
    "profit", "record", "high", "boost", "momentum", "upside", "recovery",
    "results", "earnings", "revenue", "dividend", "buyback", "acquisition",
    "expansion", "order", "contract", "win", "launch", "approval",
}
NEGATIVE_WORDS = {
    "fall", "drop", "decline", "crash", "plunge", "bearish", "weak", "miss",
    "underperform", "downgrade", "sell", "negative", "loss", "low", "risk",
    "concern", "warning", "cut", "reduce", "pressure", "slump", "worry",
    "fraud", "penalty", "fine", "probe", "investigation", "default", "debt",
    "recall", "shutdown", "layoff", "resign", "exit",
}

# Keywords that indicate company-specific results/news (not macro)
_COMPANY_NEWS_KEYWORDS = {
    "results", "earnings", "profit", "revenue", "quarterly", "q1", "q2", "q3", "q4",
    "dividend", "buyback", "acquisition", "merger", "order", "contract", "launch",
    "approval", "ipo", "fpo", "rights", "bonus", "split", "board", "agm", "egm",
    "management", "ceo", "cfo", "md", "chairman", "stake", "shareholding",
    "guidance", "outlook", "forecast", "target", "upgrade", "downgrade",
}

# Exclude macro/index/forex/crypto news — only stocks and gold
_EXCLUDE_KEYWORDS = {
    "nifty", "sensex", "index", "market", "rbi", "rbi rate", "inflation", "gdp",
    "rupee", "forex", "dollar", "currency", "bond", "yield", "ipo calendar",
    "ipo listing", "crypto", "bitcoin", "ethereum", "nft", "mutual fund",
    "etf", "commodity", "crude", "natural gas", "silver", "copper",
}


def _is_recent_news(published_str: str) -> bool:
    """Check if news is from today or yesterday."""
    if not published_str:
        return True
    try:
        from email.utils import parsedate_to_datetime
        pub_date = parsedate_to_datetime(published_str).date()
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        return pub_date in (today, yesterday)
    except Exception:
        return True


def _is_stock_or_gold_news(text: str) -> bool:
    """True if article is about stocks or gold (not macro/forex/crypto)."""
    text_lower = text.lower()
    if any(kw in text_lower for kw in _EXCLUDE_KEYWORDS):
        return False
    if "gold" in text_lower:
        return True
    return _is_company_news(text, [])


def _get_primary_company(companies: list[str], headline: str, summary: str) -> str:
    """Extract the primary (first mentioned) company from the article."""
    if not companies:
        return ""
    text = (headline + " " + summary).upper()
    for company in companies:
        if company in text:
            return company
    return companies[0] if companies else ""


@dataclass
class NewsItem:
    id: str
    headline: str
    summary: str
    source: str
    url: str
    published: str
    sentiment: str = "Neutral"
    sentiment_score: float = 0.0
    confidence: float = 0.5
    companies: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    recommendation: str = "Hold"


_news_cache: list[NewsItem] = []
_last_fetch: float = 0.0
_FETCH_TTL = 60


def _is_company_news(text: str, companies: list[str]) -> bool:
    """True if article is about a specific Indian company (not pure macro)."""
    if companies:  # already matched a Nifty 200 symbol
        return True
    text_lower = text.lower()
    return any(kw in text_lower for kw in _COMPANY_NEWS_KEYWORDS)


def _sentiment(text: str) -> tuple[str, float, float]:
    words = set(re.findall(r"\b\w+\b", text.lower()))
    pos = len(words & POSITIVE_WORDS)
    neg = len(words & NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return "Neutral", 0.0, 0.4
    score = (pos - neg) / total
    confidence = min(0.5 + total * 0.05, 0.95)
    if score > 0.2:
        sentiment = "Positive"
    elif score < -0.2:
        sentiment = "Negative"
    else:
        sentiment = "Neutral"
    return sentiment, round(score, 3), round(confidence, 2)


def _recommendation(sentiment: str, score: float) -> str:
    if score >= 0.6:
        return "Strong Buy"
    elif score >= 0.2:
        return "Buy"
    elif score <= -0.6:
        return "Strong Sell"
    elif score <= -0.2:
        return "Sell"
    return "Hold"


def _extract_keywords(text: str) -> list[str]:
    words = re.findall(r"\b[A-Z][A-Za-z]{3,}\b", text)
    return list(dict.fromkeys(words))[:8]


def _match_companies(text: str, symbols: list[str]) -> list[str]:
    text_upper = text.upper()
    return [s for s in symbols if s in text_upper]


async def _fetch_feed(name: str, url: str, client: httpx.AsyncClient) -> list[NewsItem]:
    try:
        resp = await client.get(url, timeout=10)
        feed = feedparser.parse(resp.text)
        items = []
        for entry in feed.entries[:30]:
            title = entry.get("title", "")
            summary = entry.get("summary", entry.get("description", ""))
            published = entry.get("published", "")
            link = entry.get("link", "")
            
            # Filter to today/yesterday only
            if not _is_recent_news(published):
                continue
            
            text = f"{title} {summary}"
            uid = hashlib.md5(link.encode()).hexdigest()[:12]
            sentiment, score, confidence = _sentiment(text)
            rec = _recommendation(sentiment, score)
            keywords = _extract_keywords(text)
            items.append(NewsItem(
                id=uid,
                headline=title,
                summary=summary[:300],
                source=name,
                url=link,
                published=published,
                sentiment=sentiment,
                sentiment_score=score,
                confidence=confidence,
                keywords=keywords,
                recommendation=rec,
            ))
        return items
    except Exception as e:
        logger.warning(f"Feed fetch error [{name}]: {e}")
        return []


async def fetch_news(symbols: list[str] = None) -> list[NewsItem]:
    global _news_cache, _last_fetch
    now = time.time()
    if _news_cache and (now - _last_fetch) < _FETCH_TTL:
        return _news_cache

    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True) as client:
        tasks = [_fetch_feed(name, url, client) for name, url in RSS_FEEDS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    all_items: list[NewsItem] = []
    seen_ids: set[str] = set()
    seen_companies: dict[str, NewsItem] = {}  # Track latest news per company
    
    for batch in results:
        if isinstance(batch, list):
            for item in batch:
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    if symbols:
                        item.companies = _match_companies(item.headline, symbols)
                    
                    # Filter to stocks/gold only
                    text = item.headline + " " + (item.summary or "")
                    if not _is_stock_or_gold_news(text):
                        continue
                    
                    # Deduplicate by primary company — keep highest confidence
                    primary = _get_primary_company(item.companies, item.headline, item.summary or "")
                    if primary:
                        if primary not in seen_companies or item.confidence > seen_companies[primary].confidence:
                            seen_companies[primary] = item
                    else:
                        all_items.append(item)
    
    # Add deduplicated company news
    all_items.extend(seen_companies.values())
    
    # Sort by most recent (best effort)
    _news_cache = all_items
    _last_fetch = now
    logger.info(f"Fetched {len(all_items)} unique news items (deduplicated by company)")
    return all_items


def get_cached_news() -> list[NewsItem]:
    return _news_cache


def clear_news_cache():
    """Clear the news cache (used when switching pages)."""
    global _news_cache, _last_fetch
    _news_cache = []
    _last_fetch = 0.0
