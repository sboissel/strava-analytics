"""Shared visual theme for the Runner's Dashboard."""

from __future__ import annotations

# Athletic palette: cool mist + pine/coral accents (not purple / cream / terracotta).
BG = "#E8EEF2"
SURFACE = "#F7FAFC"
CARD = "#FFFFFF"
INK = "#152028"
MUTED = "#5B6B75"
LINE = "#D5DEE5"
NAV_ACTIVE = "#E8EAED"
EASY = "#5B9BD5"
HARD = "#E67E22"
MILES = "#3A4A55"
TARGET = "#152028"

# Traffic-light KPI/chart bins (best → worst). Separate from EASY/HARD series colors.
TRAFFIC_GREEN = "#2dc937"  # bright green
TRAFFIC_LIME = "#99c140"  # yellow-green
TRAFFIC_YELLOW = "#e7b416"  # yellow/gold
TRAFFIC_ORANGE = "#db7b2b"  # orange
TRAFFIC_RED = "#cc3232"  # red

# Weekly on-target center (middle of the 18–22 green band).
WEEKLY_MILES_GOAL = 20.0
EASY_TARGET_FRAC = 0.8
EH_BAND_THRESHOLDS = (85, 75, 65, 55)

# Weekly band edges relative to WEEKLY_MILES_GOAL (scaled per grain in miles_color).
_MILES_BAND_EDGES = (10.0, 14.0, 18.0, 22.0, 25.0, 28.0)


def eh_color(easy_pct: float | None) -> str:
    """Traffic-light color for easy-percentage KPIs and tooltips."""
    if easy_pct is None:
        return INK
    if easy_pct >= EH_BAND_THRESHOLDS[0]:
        return TRAFFIC_GREEN
    if easy_pct >= EH_BAND_THRESHOLDS[1]:
        return TRAFFIC_LIME
    if easy_pct >= EH_BAND_THRESHOLDS[2]:
        return TRAFFIC_YELLOW
    if easy_pct >= EH_BAND_THRESHOLDS[3]:
        return TRAFFIC_ORANGE
    return TRAFFIC_RED


def miles_goal(grain: str = "Week") -> float:
    """Extrapolate the 20 mi/week center goal to the selected period grain."""
    if grain == "Day":
        return WEEKLY_MILES_GOAL / 7.0
    if grain == "Month":
        return WEEKLY_MILES_GOAL * (52.0 / 12.0)
    if grain == "Year":
        return WEEKLY_MILES_GOAL * 52.0
    return WEEKLY_MILES_GOAL


def miles_color(miles: float | None, grain: str = "Week") -> str:
    """Color mileage by goal bands, scaled so Day/Month/Year match Week proportions."""
    if miles is None:
        return INK
    scale = miles_goal(grain) / WEEKLY_MILES_GOAL
    lo_red, lo_orange, lo_yellow, hi_green, hi_yellow, hi_orange = (
        edge * scale for edge in _MILES_BAND_EDGES
    )
    if miles < lo_red or miles > hi_orange:
        return TRAFFIC_RED
    if miles < lo_orange or miles > hi_yellow:
        return TRAFFIC_ORANGE
    if miles < lo_yellow or miles > hi_green:
        return TRAFFIC_YELLOW
    return TRAFFIC_GREEN


def _miles_legend_range(lo: int, hi: int) -> str:
    if lo == hi:
        return str(lo)
    return f"{lo}–{hi}"


def _miles_legend_pair(lo1: int, hi1: int, lo2: int, hi2: int) -> str:
    left = _miles_legend_range(lo1, hi1)
    right = _miles_legend_range(lo2, hi2)
    if left == right:
        return left
    return f"{left} or {right}"


def miles_legend_labels(grain: str = "Week") -> list[tuple[str, str]]:
    """Legend (color, label) pairs for mileage goal bands, scaled to the grain."""
    scale = miles_goal(grain) / WEEKLY_MILES_GOAL
    lo_red, lo_orange, lo_yellow, hi_green, hi_yellow, hi_orange = (
        int(round(edge * scale)) for edge in _MILES_BAND_EDGES
    )
    return [
        (TRAFFIC_RED, f"<{lo_red} or >{hi_orange} mi"),
        (
            TRAFFIC_ORANGE,
            f"{_miles_legend_pair(lo_red, lo_orange, hi_yellow, hi_orange)} mi",
        ),
        (
            TRAFFIC_YELLOW,
            f"{_miles_legend_pair(lo_orange, lo_yellow, hi_green, hi_yellow)} mi",
        ),
        (TRAFFIC_GREEN, f"{_miles_legend_range(lo_yellow, hi_green)} mi"),
    ]


FONT_BODY = '"Inter", "Helvetica Neue", Helvetica, Arial, sans-serif'
FONT_DISPLAY = '"Inter", "Helvetica Neue", Helvetica, Arial, sans-serif'

GLOBAL_CSS = f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  .stApp {{
    background:
      radial-gradient(1200px 500px at 10% -10%, #d5e6df 0%, transparent 55%),
      radial-gradient(900px 420px at 100% 0%, #d9e3ec 0%, transparent 50%),
      linear-gradient(180deg, {BG} 0%, #F4F7F9 45%, {BG} 100%);
    color: {INK};
    font-family: {FONT_BODY};
  }}

  .block-container {{
    padding-top: 1.4rem;
    padding-bottom: 2.5rem;
    max-width: 1180px;
  }}

  /* Minimal top bar — keep native sidebar expand/collapse controls */
  header[data-testid="stHeader"] {{
    background: transparent;
  }}
  [data-testid="stToolbar"] {{
    background: transparent !important;
  }}
  [data-testid="stToolbarActions"],
  [data-testid="stDecoration"],
  [data-testid="stStatusWidget"],
  [data-testid="stAppDeployButton"],
  .stDeployButton,
  [data-testid="stHeaderActionElements"],
  #MainMenu,
  footer {{
    display: none !important;
    visibility: hidden !important;
  }}
  [data-testid="stExpandSidebarButton"],
  [data-testid="stSidebarCollapseButton"] {{
    display: inline-flex !important;
    visibility: visible !important;
  }}

  .hero {{
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    margin-bottom: 0.35rem;
  }}
  .hero-kicker {{
    font-family: {FONT_BODY};
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: {EASY};
  }}
  .hero-title {{
    font-family: {FONT_DISPLAY};
    font-weight: 700;
    font-size: clamp(2rem, 3vw, 2.55rem);
    line-height: 1.05;
    color: {INK};
    margin: 0;
  }}

  /* Left sidebar navigation */
  section[data-testid="stSidebar"] {{
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.96) 0%, rgba(247, 250, 252, 0.94) 100%);
    border-right: 1px solid rgba(21, 32, 40, 0.08);
    font-family: {FONT_BODY};
  }}
  section[data-testid="stSidebar"] > div {{
    background: transparent;
  }}
  section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
    padding-top: 1.25rem;
  }}
  section[data-testid="stSidebar"] .block-container {{
    padding-top: 0.5rem;
    padding-left: 0.85rem;
    padding-right: 0.85rem;
  }}
  [data-testid="stSidebarHeader"] {{
    padding: 0.35rem 0.5rem 0.15rem;
  }}
  [data-testid="stSidebarCollapseButton"] button {{
    color: {MUTED} !important;
    border-radius: 8px !important;
  }}
  [data-testid="stSidebarCollapseButton"] button:hover {{
    background: rgba(21, 32, 40, 0.05) !important;
    color: {INK} !important;
  }}
  [data-testid="stExpandSidebarButton"] button {{
    color: {MUTED} !important;
    border-radius: 8px !important;
  }}
  [data-testid="stExpandSidebarButton"] button:hover {{
    background: rgba(21, 32, 40, 0.05) !important;
    color: {INK} !important;
  }}
  [data-testid="stSidebarNav"] {{
    padding-top: 0.35rem;
  }}
  [data-testid="stSidebarNav"]::before {{
    content: "Navigation";
    display: block;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {MUTED};
    padding: 0.35rem 0.85rem 0.55rem;
  }}
  nav[data-testid="stSidebarNavItems"] {{
    gap: 0.2rem;
  }}
  div[kind="header"] {{ gap: 0.4rem !important; }}
  [data-testid="stHeadingWithActionElements"] h1,
  [data-testid="stHeadingWithActionElements"] h2,
  [data-testid="stHeadingWithActionElements"] h3 {{
    font-family: {FONT_DISPLAY} !important;
    color: {INK} !important;
  }}

  /* Sidebar page links (st.navigation → stSidebarNavLink) */
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] a,
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLinkContainer"] a,
  section[data-testid="stSidebar"] div[data-testid="stPageLink-Nav"] a {{
    display: block;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.92rem !important;
    color: {MUTED} !important;
    padding: 0.55rem 0.85rem !important;
    margin-bottom: 0.15rem;
    border: 1px solid transparent !important;
    background: transparent !important;
    text-decoration: none !important;
    transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
  }}
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] a:hover,
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLinkContainer"] a:hover,
  section[data-testid="stSidebar"] div[data-testid="stPageLink-Nav"] a:hover {{
    background: rgba(21, 32, 40, 0.04) !important;
    color: {INK} !important;
  }}
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] a[aria-current="page"],
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLinkContainer"] a[aria-current="page"],
  section[data-testid="stSidebar"] div[data-testid="stPageLink-Nav"] a[aria-current="page"] {{
    background: {NAV_ACTIVE} !important;
    color: {INK} !important;
    border-color: {LINE} !important;
  }}

  /* In-page section navigation (Training Overview sidebar) */
  section[data-testid="stSidebar"] .sidebar-section-nav {{
    margin: -0.15rem 0 0.75rem;
    padding: 0 0 0.35rem;
  }}
  section[data-testid="stSidebar"] .sidebar-section-nav-label {{
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {MUTED};
    padding: 0.15rem 0.85rem 0.4rem;
  }}
  section[data-testid="stSidebar"] .sidebar-section-nav-links {{
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    padding: 0 0.35rem;
  }}
  section[data-testid="stSidebar"] .sidebar-section-nav-links a {{
    display: block;
    border-radius: 10px;
    font-weight: 600;
    font-size: 0.86rem;
    color: {MUTED};
    padding: 0.48rem 0.85rem 0.48rem 1.35rem;
    margin-bottom: 0;
    border: 1px solid transparent;
    background: transparent;
    text-decoration: none;
    transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
  }}
  section[data-testid="stSidebar"] .sidebar-section-nav-links a:hover {{
    background: rgba(21, 32, 40, 0.04);
    color: {INK};
  }}
  section[data-testid="stSidebar"] .sidebar-section-nav-links a:active,
  section[data-testid="stSidebar"] .sidebar-section-nav-links a:focus-visible {{
    background: {NAV_ACTIVE};
    color: {INK};
    border-color: {LINE};
    outline: none;
  }}
  .page-anchor,
  #key-indicators,
  #chart-compliance,
  #chart-mileage {{
    scroll-margin-top: 1.25rem;
  }}

  .panel {{
    background: rgba(255, 255, 255, 0.82);
    border: 1px solid rgba(21, 32, 40, 0.06);
    border-radius: 20px;
    padding: 1.25rem 1.2rem 1.3rem;
    box-shadow: 0 10px 30px rgba(21, 32, 40, 0.04);
    backdrop-filter: blur(10px);
    height: 100%;
  }}
  /* Controls column: widgets can't live inside one HTML .panel. Mark the
     column with .controls-panel and paint ONLY that column — never a bare
     [data-testid=stVerticalBlock]:has(...), which also matches the page-level
     block and draws a full-width white pill under the page title. */
  [data-testid="stColumn"]:has(.controls-panel),
  [data-testid="column"]:has(.controls-panel) {{
    background: rgba(255, 255, 255, 0.82) !important;
    border: 1px solid rgba(21, 32, 40, 0.06) !important;
    border-radius: 20px !important;
    padding: 1.25rem 1.2rem 1.3rem !important;
    box-shadow: 0 10px 30px rgba(21, 32, 40, 0.04) !important;
    backdrop-filter: blur(10px);
  }}
  .controls-title {{
    font-family: {FONT_DISPLAY};
    font-size: 0.95rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    text-transform: none;
    color: {INK};
    margin: 0 0 1.05rem 0;
    line-height: 1.2;
  }}
  .controls-filter-label {{
    font-size: 0.8rem;
    font-weight: 500;
    letter-spacing: 0.01em;
    text-transform: none;
    color: {MUTED};
    margin: 0 0 0.42rem 0;
    opacity: 0.88;
  }}
  /* Tighter vertical stack inside Controls column only (never bare :has(.controls-panel) on stVerticalBlock). */
  [data-testid="stColumn"]:has(.controls-panel) [data-testid="stVerticalBlock"],
  [data-testid="column"]:has(.controls-panel) [data-testid="stVerticalBlock"] {{
    gap: 0.4rem !important;
  }}
  [data-testid="stColumn"]:has(.controls-panel) [data-testid="stElementContainer"],
  [data-testid="column"]:has(.controls-panel) [data-testid="stElementContainer"] {{
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
  }}
  [data-testid="stColumn"]:has(.controls-panel) [data-testid="stSelectbox"],
  [data-testid="column"]:has(.controls-panel) [data-testid="stSelectbox"] {{
    margin-bottom: 0 !important;
  }}
  [data-testid="stColumn"]:has(.controls-panel) div[data-baseweb="select"] > div,
  [data-testid="column"]:has(.controls-panel) div[data-baseweb="select"] > div {{
    background: {SURFACE} !important;
    border: 1px solid {LINE} !important;
    border-radius: 10px !important;
    min-height: 38px !important;
    box-shadow: none !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
  }}
  [data-testid="stColumn"]:has(.controls-panel) div[data-baseweb="select"] > div:focus-within,
  [data-testid="column"]:has(.controls-panel) div[data-baseweb="select"] > div:focus-within {{
    border-color: rgba(91, 155, 213, 0.45) !important;
    box-shadow: 0 0 0 3px rgba(91, 155, 213, 0.1) !important;
  }}
  [data-testid="stColumn"]:has(.controls-panel) div[data-baseweb="select"] span,
  [data-testid="column"]:has(.controls-panel) div[data-baseweb="select"] span {{
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    color: {INK} !important;
  }}
  .controls-meta {{
    margin-top: 0.3rem;
  }}
  .controls-meta-divider {{
    height: 1px;
    background: {LINE};
    opacity: 0.55;
    margin: 0 0 0.65rem 0;
  }}
  .controls-meta .meta-line {{
    display: flex;
    flex-direction: column;
    gap: 0.12rem;
    margin: 0.5rem 0 0;
    line-height: 1.35;
  }}
  .controls-meta .meta-line:first-of-type {{
    margin-top: 0;
  }}
  .controls-meta .meta-line:last-of-type {{
    margin-bottom: 0.65rem;
  }}
  .meta-key {{
    font-size: 0.72rem;
    font-weight: 500;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: {MUTED};
    opacity: 0.85;
  }}
  .meta-val {{
    font-size: 0.88rem;
    font-weight: 600;
    color: {INK};
  }}
  .panel-title {{
    font-family: {FONT_DISPLAY};
    font-size: 1.25rem;
    font-weight: 700;
    color: {INK};
    margin: 0 0 0.25rem 0;
    border-bottom: none !important;
  }}
  .panel-summary {{
    font-size: 0.92rem;
    color: {MUTED};
    margin: 0 0 0.85rem 0;
  }}
  .panel-label {{
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {MUTED};
    margin-bottom: 0.55rem;
  }}

  .meta-line {{
    color: {MUTED};
    font-size: 0.92rem;
    margin: 0.35rem 0 0;
  }}
  .meta-line strong {{
    color: {INK};
    font-weight: 600;
  }}

  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
  }}
  .kpi-card {{
    background: {CARD};
    border: 1px solid transparent;
    border-radius: 16px;
    padding: 1rem 0.75rem 0.95rem;
    text-align: center;
    position: relative;
    overflow: visible;
  }}
  .kpi-card::before {{
    content: "";
    position: absolute;
    inset: 0 0 auto 0;
    height: 3px;
    background: var(--accent, {MILES});
  }}
  .kpi-label {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.28rem;
    font-size: 0.78rem;
    font-weight: 500;
    color: {MUTED};
    margin-bottom: 0.45rem;
  }}
  .kpi-info {{
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 0.95rem;
    height: 0.95rem;
    border-radius: 999px;
    color: {MUTED};
    font-size: 0.68rem;
    font-weight: 600;
    line-height: 1;
    cursor: help;
    opacity: 0.72;
    transition: opacity 0.15s ease, color 0.15s ease;
  }}
  .kpi-info:hover,
  .kpi-info:focus {{
    opacity: 1;
    color: {INK};
    outline: none;
  }}
  .kpi-info:focus-visible {{
    box-shadow: 0 0 0 2px rgba(21, 32, 40, 0.14);
  }}
  .kpi-tooltip {{
    visibility: hidden;
    opacity: 0;
    position: absolute;
    left: 50%;
    bottom: calc(100% + 0.45rem);
    transform: translateX(-50%);
    width: min(15.5rem, 72vw);
    padding: 0.55rem 0.65rem;
    border-radius: 10px;
    border: 1px solid {LINE};
    background: {CARD};
    color: {INK};
    font-family: {FONT_BODY};
    font-size: 0.72rem;
    font-weight: 400;
    line-height: 1.45;
    text-align: left;
    letter-spacing: normal;
    text-transform: none;
    white-space: normal;
    box-shadow: 0 10px 24px rgba(21, 32, 40, 0.12);
    z-index: 20;
    pointer-events: none;
    transition: opacity 0.15s ease, visibility 0.15s ease;
  }}
  .kpi-tooltip strong {{
    display: block;
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: {MUTED};
    margin-bottom: 0.2rem;
  }}
  .kpi-tooltip strong:last-of-type {{
    margin-bottom: 0.05rem;
  }}
  .kpi-tooltip .band-dot {{
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 0.35rem;
    vertical-align: middle;
    flex-shrink: 0;
  }}
  .kpi-info:hover .kpi-tooltip,
  .kpi-info:focus .kpi-tooltip,
  .kpi-info:focus-within .kpi-tooltip {{
    visibility: visible;
    opacity: 1;
  }}
  .kpi-value {{
    font-family: {FONT_DISPLAY};
    font-size: 2rem;
    font-weight: 700;
    line-height: 1;
    color: var(--accent, {INK});
  }}

  /* Selectbox polish */
  div[data-baseweb="select"] > div {{
    background: {CARD} !important;
    border-color: {LINE} !important;
    border-radius: 12px !important;
  }}
  label[data-testid="stWidgetLabel"] p {{
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: {MUTED} !important;
  }}

  .placeholder {{
    background: rgba(255,255,255,0.78);
    border: 1px dashed rgba(21, 32, 40, 0.08);
    border-radius: 20px;
    padding: 2.5rem 1.5rem;
    text-align: center;
    color: {MUTED};
  }}
  .placeholder strong {{
    display: block;
    font-family: {FONT_DISPLAY};
    font-size: 1.35rem;
    color: {INK};
    margin-bottom: 0.4rem;
  }}

  /* Kill Streamlit structural borders that read as white section dividers */
  hr {{
    display: none !important;
  }}
  h1, h2, h3,
  [data-testid="stHeadingWithActionElements"],
  [data-testid="stHeadingWithActionElements"] h1,
  [data-testid="stHeadingWithActionElements"] h2,
  [data-testid="stHeadingWithActionElements"] h3 {{
    border-bottom: none !important;
    box-shadow: none !important;
  }}
  [data-testid="stVerticalBlockBorderWrapper"] {{
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
  }}
  [data-testid="stPlotlyChart"],
  [data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"]),
  [data-testid="stElementContainer"]:has(.panel-title) {{
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
  }}
  [data-testid="stHeadingWithActionElements"] {{
    border-bottom: none !important;
  }}
</style>
"""
