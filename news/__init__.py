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
import httpx
import feedparser
from loguru import logger

# Trusted financial RSS feeds
RSS_FEEDS = [
    ("Economic Times Markets", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("Moneycontrol", "https://www.moneycontrol.com/rss/marketreports.xml"),
    ("Business Standard Markets", "https://www.business-standard.com/rss/markets-106.rss"),
    ("LiveMint Markets", "https://www.livemint.com/rss/markets"),
    ("NDTV Profit", "https://feeds.feedburner.com/ndtvprofit-latest"),
    ("Financial Express Markets", "https://www.financialexpress.com/market/feed/"),
]

POSITIVE_WORDS = {
    "surge", "rally", "gain", "rise", "jump", "soar", "breakout", "bullish",
    "strong", "beat", "outperform", "upgrade", "buy", "positive", "growth",
    "profit", "record", "high", "boost", "momentum", "upside", "recovery",
}
NEGATIVE_WORDS = {
    "fall", "drop", "decline", "crash", "plunge", "bearish", "weak", "miss",
    "underperform", "downgrade", "sell", "negative", "loss", "low", "risk",
    "concern", "warning", "cut", "reduce", "pressure", "slump", "worry",
}


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
        for entry in feed.entries[:20]:
            title = entry.get("title", "")
            summary = entry.get("summary", entry.get("description", ""))
            published = entry.get("published", "")
            link = entry.get("link", "")
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
    for batch in results:
        if isinstance(batch, list):
            for item in batch:
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    if symbols:
                        item.companies = _match_companies(item.headline, symbols)
                    all_items.append(item)

    # Sort by most recent (best effort)
    _news_cache = all_items
    _last_fetch = now
    logger.info(f"Fetched {len(all_items)} unique news items")
    return all_items


def get_cached_news() -> list[NewsItem]:
    return _news_cache
