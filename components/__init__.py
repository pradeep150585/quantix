"""
Reusable UI components.
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime
from api.upstox_client import get_client


def render_status_bar():
    client = get_client()
    connected = client.is_connected
    latency = client.latency_ms
    now = datetime.now().strftime("%H:%M:%S")
    dot_class = "connected" if connected else "disconnected"
    conn_text = "Connected" if connected else "Disconnected"
    st.markdown(f"""
    <div class="status-bar">
        <span><span class="status-dot {dot_class}"></span> &nbsp;{conn_text}</span>
        <span>⚡ {latency:.0f}ms</span>
        <span>🕐 {now}</span>
        <span style="margin-left:auto;color:#38bdf8;font-weight:600;">NIFTY SCANNER PRO</span>
    </div>
    """, unsafe_allow_html=True)


def render_index_card(name: str, quote: dict):
    if not quote:
        return
    ltp = quote.get("ltp", 0)
    prev = quote.get("prev_close", 0) or quote.get("close", 0)
    chg = ltp - prev if prev else 0
    pct = chg / prev * 100 if prev else 0
    trend = "bullish" if pct > 0 else ("bearish" if pct < 0 else "neutral")
    color = "#22c55e" if pct > 0 else ("#ef4444" if pct < 0 else "#94a3b8")
    arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "—")
    st.markdown(f"""
    <div class="index-card {trend}">
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:0.8rem;color:#64748b;font-weight:600;">{name}</span>
            <span style="color:{color};font-size:0.78rem;">{arrow} {abs(pct):.2f}%</span>
        </div>
        <div style="font-size:1.2rem;font-weight:700;color:#e2e8f0;margin-top:4px;">
            {ltp:,.2f}
        </div>
        <div style="font-size:0.75rem;color:{color};">{arrow} {chg:+.2f}</div>
    </div>
    """, unsafe_allow_html=True)


def render_market_sentiment(index_quotes: dict) -> str:
    if not index_quotes:
        return "Neutral"
    changes = []
    for name, q in index_quotes.items():
        if name == "INDIA VIX":
            continue
        ltp = q.get("ltp", 0)
        prev = q.get("prev_close", 0) or q.get("close", 0)
        if prev:
            changes.append((ltp - prev) / prev * 100)
    if not changes:
        return "Neutral"
    bullish = sum(1 for c in changes if c > 0)
    bearish = sum(1 for c in changes if c < 0)
    if bullish > len(changes) * 0.6:
        return "Bullish"
    elif bearish > len(changes) * 0.6:
        return "Bearish"
    return "Neutral"


def render_heatmap(data: dict):
    if not data:
        return
    labels, values, colors, parents = [], [], [], []
    for name, q in data.items():
        if name == "INDIA VIX":
            continue
        ltp = q.get("ltp", 0)
        prev = q.get("prev_close", 0) or q.get("close", 0)
        pct = (ltp - prev) / prev * 100 if prev else 0
        labels.append(f"{name}<br>{pct:+.2f}%")
        values.append(abs(pct) + 0.1)
        colors.append(pct)
        parents.append("")

    fig = go.Figure(go.Treemap(
        labels=labels,
        values=values,
        parents=parents,
        marker=dict(
            colors=colors,
            colorscale=[[0, "#7f1d1d"], [0.5, "#1e2d3d"], [1, "#14532d"]],
            cmid=0,
            showscale=False,
        ),
        textfont=dict(color="white", size=11),
        hovertemplate="%{label}<extra></extra>",
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=220,
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def render_candlestick_chart(df: pd.DataFrame, symbol: str, indicators: dict = None):
    if df.empty:
        st.info("No chart data available.")
        return

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        row_heights=[0.6, 0.2, 0.2],
        vertical_spacing=0.02,
    )

    fig.add_trace(go.Candlestick(
        x=df["datetime"], open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing_line_color="#22c55e", decreasing_line_color="#ef4444",
        name="Price",
    ), row=1, col=1)

    if indicators:
        for period, color in [(20, "#38bdf8"), (50, "#f59e0b"), (200, "#a855f7")]:
            key = f"ema{period}"
            if key in indicators:
                fig.add_hline(y=indicators[key], line_dash="dot", line_color=color,
                              annotation_text=f"EMA{period}", row=1, col=1)

    bar_colors = ["#22c55e" if c >= o else "#ef4444"
                  for c, o in zip(df["close"], df["open"])]
    fig.add_trace(go.Bar(
        x=df["datetime"], y=df["volume"],
        marker_color=bar_colors, name="Volume", opacity=0.7,
    ), row=2, col=1)

    from indicators import rsi as calc_rsi
    rsi_vals = []
    for i in range(len(df)):
        sub = df.iloc[:i+1]
        rsi_vals.append(calc_rsi(sub) if len(sub) >= 15 else 50)
    fig.add_trace(go.Scatter(
        x=df["datetime"], y=rsi_vals,
        line=dict(color="#38bdf8", width=1.5), name="RSI",
    ), row=3, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="#ef4444", row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#22c55e", row=3, col=1)

    fig.update_layout(
        title=dict(text=symbol, font=dict(color="#38bdf8", size=14)),
        paper_bgcolor="#0a0e1a",
        plot_bgcolor="#0d1117",
        font=dict(color="#94a3b8", size=11),
        xaxis_rangeslider_visible=False,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#94a3b8")),
        height=550,
        margin=dict(l=0, r=0, t=30, b=0),
    )
    for i in range(1, 4):
        fig.update_xaxes(gridcolor="#1e2d3d", row=i, col=1)
        fig.update_yaxes(gridcolor="#1e2d3d", row=i, col=1)

    st.plotly_chart(fig, width="stretch")


def color_pct(val: float) -> str:
    if val > 0:
        return f'<span class="positive">▲ {val:.2f}%</span>'
    elif val < 0:
        return f'<span class="negative">▼ {abs(val):.2f}%</span>'
    return f'<span class="neutral">— {val:.2f}%</span>'


def rsi_color(val: float) -> str:
    if val >= 70:
        return "#ef4444"
    elif val >= 60:
        return "#f59e0b"
    elif val <= 30:
        return "#22c55e"
    return "#94a3b8"


def format_volume(v: float) -> str:
    if v >= 1e7:
        return f"{v/1e7:.2f}Cr"
    elif v >= 1e5:
        return f"{v/1e5:.2f}L"
    elif v >= 1e3:
        return f"{v/1e3:.1f}K"
    return str(int(v))
