"""
Page 3 – News & Sentiment Engine
"""
import asyncio
import html
import re
import streamlit as st
import streamlit.components.v1 as components
from news import fetch_news, NewsItem
from services.instruments import get_nifty200_symbols
from components.ui import page_heading, loading_html


def _run(coro):
    try:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_news():
    from dataclasses import asdict
    symbols_df = _run(get_nifty200_symbols())
    symbols = symbols_df["symbol"].tolist() if not symbols_df.empty else []
    items = _run(fetch_news(symbols))
    # Convert dataclass instances to plain dicts so pickle can serialize them
    return [asdict(item) for item in items], symbols


def _clean(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


_REC_COLOR = {"Strong Buy": "#00c853", "Strong Sell": "#ef4444"}


def _news_card(item: NewsItem) -> str:
    r_color = _REC_COLOR.get(item.recommendation, "#6b7280")
    companies_html = "".join(
        f'<span style="display:inline-block;padding:2px 7px;border-radius:3px;font-size:.62rem;'
        f'font-weight:500;margin:2px 2px 2px 0;background:rgba(59,130,246,.1);'
        f'color:#60a5fa;border:1px solid rgba(59,130,246,.2);">{html.escape(c)}</span>'
        for c in (item.companies or [])[:4]
    )
    headline = html.escape(_clean(item.headline))
    summary = _clean(item.summary or "")
    if len(summary) > 240:
        summary = summary[:240] + "..."
    summary = html.escape(summary)
    pub = html.escape(_clean(item.published or "")[:16])
    source = html.escape(item.source or "")
    rec_bg = "rgba(0,200,83,.08)" if item.recommendation == "Strong Buy" else "rgba(239,68,68,.08)"
    rec_border = "rgba(0,200,83,.2)" if item.recommendation == "Strong Buy" else "rgba(239,68,68,.2)"

    return (
        f'<div style="background:#131722;border:1px solid #1e2433;border-radius:5px;'
        f'border-left:3px solid {r_color};'
        f'padding:14px 16px;margin-bottom:8px;">'
        f'<div style="display:flex;gap:12px;align-items:flex-start;">'
        f'<div style="flex:1;min-width:0;">'
        f'<div style="font-size:.84rem;font-weight:600;color:#ffffff;line-height:1.5;margin-bottom:4px;">{headline}</div>'
        f'<div style="font-size:.74rem;color:#9ca3af;line-height:1.6;">{summary}</div>'
        f'</div>'
        f'<div style="text-align:right;min-width:104px;flex-shrink:0;">'
        f'<div style="display:inline-block;background:{rec_bg};border:1px solid {rec_border};'
        f'border-radius:3px;padding:4px 10px;font-size:.7rem;font-weight:600;color:{r_color};">{item.recommendation}</div>'
        f'<div style="color:#4a5568;font-size:.62rem;margin-top:4px;">{item.confidence*100:.0f}% confidence</div>'
        f'</div></div>'
        f'<div style="margin-top:8px;display:flex;flex-wrap:wrap;align-items:center;gap:3px;">'
        f'{companies_html}'
        f'<span style="margin-left:auto;font-size:.62rem;color:#4a5568;white-space:nowrap;">'
        f'{source} &middot; {pub}</span>'
        f'</div></div>'
    )


def _build_news_html(items) -> str:
    cards = "\n".join(_news_card(item) for item in items)
    return f"""<!DOCTYPE html><html><head>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0b0e17;color:#d1d4dc;font-family:'Inter',system-ui,sans-serif;padding:4px 0}}
::-webkit-scrollbar{{width:4px}}::-webkit-scrollbar-track{{background:#0b0e17}}
::-webkit-scrollbar-thumb{{background:#2d3748;border-radius:4px}}
</style></head><body>{cards}</body></html>"""


def render(slot):
    slot.empty()
    slot.markdown(loading_html("Fetching market sentiment..."), unsafe_allow_html=True)
    news_dicts, symbols = _fetch_news()
    news_items = [NewsItem(**d) for d in news_dicts]
    slot.empty()

    if not news_items:
        st.warning("No news available. Check your internet connection.")
        return

    filtered = [
        n for n in news_items
        if any(s in (_clean(n.headline) + " " + _clean(n.summary or "")).upper() for s in symbols)
    ]
    filtered.sort(key=lambda n: n.confidence, reverse=True)

    if not filtered:
        st.info("No news found for Nifty 200 stocks right now.")
        return

    buy_c  = sum(1 for n in filtered if n.recommendation == "Strong Buy")
    sell_c = sum(1 for n in filtered if n.recommendation == "Strong Sell")
    st.markdown(
        f'<div style="font-size:.68rem;color:#6b7280;margin-bottom:10px;">'
        f'{len(filtered)} articles &nbsp;&middot;&nbsp;'
        f'<span style="color:#00c853">{buy_c} Strong Buy</span>'
        f' &nbsp; <span style="color:#ef4444">{sell_c} Strong Sell</span>'
        f' &nbsp; sorted by confidence</div>',
        unsafe_allow_html=True,
    )
    card_height = min(len(filtered) * 140 + 20, 820)
    components.html(_build_news_html(filtered), height=card_height, scrolling=True)
