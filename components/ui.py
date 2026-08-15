def loading_html(sub: str = "Please wait...") -> str:
    """Returns an HTML string for use with st.markdown (fixed overlay, no iframe)."""
    return f"""
<style>
#qx-loading-overlay {{
    position:fixed;top:0;left:0;width:100vw;height:100vh;
    background:rgba(11,14,23,0.96);z-index:9999;
    display:flex;align-items:center;justify-content:center;
    font-family:'Inter',system-ui,sans-serif;
    pointer-events:none;
}}
#qx-loading-overlay .inner{{
    display:flex;flex-direction:column;align-items:center;justify-content:center;
    text-align:center;gap:0;
}}
#qx-loading-overlay .bars{{
    display:flex;gap:3px;align-items:flex-end;height:32px;
    margin-bottom:12px;
}}
#qx-loading-overlay .bar{{
    width:4px;border-radius:2px;background:#00c853;
    animation:qxbounce 1s ease-in-out infinite;
}}
#qx-loading-overlay .bar:nth-child(1){{animation-delay:0s;height:14px}}
#qx-loading-overlay .bar:nth-child(2){{animation-delay:.12s;height:22px}}
#qx-loading-overlay .bar:nth-child(3){{animation-delay:.24s;height:32px}}
#qx-loading-overlay .bar:nth-child(4){{animation-delay:.36s;height:22px}}
#qx-loading-overlay .bar:nth-child(5){{animation-delay:.48s;height:14px}}
@keyframes qxbounce{{0%,100%{{transform:scaleY(.3);opacity:.2}}50%{{transform:scaleY(1);opacity:1}}}}
#qx-loading-overlay .label{{
    color:#d1d4dc;font-size:.75rem;letter-spacing:.1em;
    text-transform:uppercase;font-weight:600;line-height:1;
}}
#qx-loading-overlay .sub{{
    color:#00c853;font-size:.65rem;margin-top:8px;
    letter-spacing:.02em;font-weight:400;line-height:1;
}}
</style>
<div id="qx-loading-overlay">
  <div class="inner">
    <div class="bars">
      <div class="bar"></div><div class="bar"></div><div class="bar"></div>
      <div class="bar"></div><div class="bar"></div>
    </div>
    <div class="label">QUANTIX</div>
    <div class="sub">{sub}</div>
  </div>
</div>
"""


def page_heading(title: str) -> str:
    return (
        f'<div class="page-heading">{title}</div>'
        f'<div class="page-heading-line"></div>'
    )
