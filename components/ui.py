def loading_html(sub: str = "Please wait...") -> str:
    """Returns an HTML string for use with st.markdown (fixed overlay, no iframe)."""
    return f"""
<style>
#qx-loading-overlay {{
    position:fixed;top:160px;left:0;width:100vw;height:calc(100vh - 160px);
    background:#0b0e17;z-index:9000;
    display:flex;align-items:center;justify-content:center;
    font-family:'Inter',system-ui,sans-serif;
    pointer-events:none;
}}
#qx-loading-overlay .bars{{display:flex;gap:5px;align-items:flex-end;height:44px;margin-bottom:18px}}
#qx-loading-overlay .bar{{width:6px;border-radius:3px;background:#00c853;animation:qxbounce 1.1s ease-in-out infinite}}
#qx-loading-overlay .bar:nth-child(1){{animation-delay:0s;height:18px}}
#qx-loading-overlay .bar:nth-child(2){{animation-delay:.15s;height:30px}}
#qx-loading-overlay .bar:nth-child(3){{animation-delay:.3s;height:44px}}
#qx-loading-overlay .bar:nth-child(4){{animation-delay:.45s;height:30px}}
#qx-loading-overlay .bar:nth-child(5){{animation-delay:.6s;height:18px}}
@keyframes qxbounce{{0%,100%{{transform:scaleY(.4);opacity:.3}}50%{{transform:scaleY(1);opacity:1}}}}
#qx-loading-overlay .label{{color:#d1d4dc;font-size:.82rem;letter-spacing:.14em;text-transform:uppercase;font-weight:700}}
#qx-loading-overlay .sub{{color:#00c853;font-size:.72rem;margin-top:8px;letter-spacing:.04em;font-weight:500}}
</style>
<div id="qx-loading-overlay">
  <div style="text-align:center">
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
