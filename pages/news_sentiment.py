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
::-webkit-scrollbar{{width:2px;height:2px}}
</style></head><body>{cards}</body></html>"""


def render(slot):
    slot.empty()
    slot.markdown(loading_html("Fetching market news..."), unsafe_allow_html=True)
    news_dicts, symbols = _fetch_news()
    news_items = [NewsItem(**d) for d in news_dicts]
    slot.empty()
    st.empty()  # Clear any lingering components

    if not news_items:
        st.warning("No news available. Check your internet connection.")
        return

    from news import _is_stock_or_gold_news
    filtered = [
        n for n in news_items
        if _is_stock_or_gold_news(_clean(n.headline) + " " + _clean(n.summary or ""))
        and (n.companies or any(s in (_clean(n.headline) + " " + _clean(n.summary or "")).upper() for s in symbols))
    ]

    def _sort_key(n):
        order = {"Strong Buy": 0, "Strong Sell": 1}
        return (order.get(n.recommendation, 2), -n.confidence)

    filtered.sort(key=_sort_key)

    if not filtered:
        st.info("No stock or gold news found for Nifty 200 right now.")
        return

    buy_items  = [n for n in filtered if n.recommendation == "Strong Buy"]
    sell_items = [n for n in filtered if n.recommendation == "Strong Sell"]

    buy_c  = len(buy_items)
    sell_c = len(sell_items)

    if buy_items or sell_items:
        banner_parts = []
        if buy_items:
            banner_parts.append(
                f'<span style="background:rgba(0,200,83,.12);color:#00c853;border:1px solid rgba(0,200,83,.3);'
                f'border-radius:4px;padding:6px 14px;font-size:.78rem;font-weight:700;">'
                f'&#9650; STRONG BUY &nbsp; {buy_c} stocks</span>'
            )
        if sell_items:
            banner_parts.append(
                f'<span style="background:rgba(239,68,68,.12);color:#ef4444;border:1px solid rgba(239,68,68,.3);'
                f'border-radius:4px;padding:6px 14px;font-size:.78rem;font-weight:700;">'
                f'&#9660; STRONG SELL &nbsp; {sell_c} stocks</span>'
            )
        st.markdown(
            f'<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px;">{" ".join(banner_parts)}</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<div style="font-size:.68rem;color:#6b7280;margin-bottom:10px;">'
        f'{len(filtered)} articles &nbsp;&middot;&nbsp;'
        f'<span style="color:#00c853">{buy_c} Strong Buy</span>'
        f' &nbsp; <span style="color:#ef4444">{sell_c} Strong Sell</span>'
        f' &nbsp; Stocks &amp; Gold only &middot; Deduplicated &middot; Strong signals first</div>',
        unsafe_allow_html=True,
    )
    card_height = min(len(filtered) * 120 + 20, 600)
    components.html(_build_news_html(filtered), height=card_height, scrolling=True)
