"""Shared visual theme for the Runner's Dashboard."""

from __future__ import annotations

# Athletic palette: cool mist + pine/coral accents (not purple / cream / terracotta).
BG = "#E8EEF2"
SURFACE = "#F7FAFC"
CARD = "#FFFFFF"
INK = "#152028"
MUTED = "#5B6B75"
# Race History Glide cells inherit the page wash (no opaque fill).
RACE_TABLE_FILL = "transparent"
# Transparent so Training charts show through the race-week strip.
RACE_STRIP_BG = "rgba(0,0,0,0)"
LINE = "#D5DEE5"
NAV_ACTIVE = "#E8EAED"
EASY = "#5B9BD5"
HARD = "#E67E22"
MILES = "#3A4A55"
TARGET = "#152028"
# Fitness Pace Range multiselect chips — light teal (not Streamlit primary red).
PACE_MULTISELECT_CHIP = "#B7DDD8"

# Traffic-light KPI/chart bins (best → worst). Separate from EASY/HARD series colors.
TRAFFIC_GREEN = "#2dc937"  # bright green
TRAFFIC_LIME = "#99c140"  # yellow-green
TRAFFIC_YELLOW = "#e7b416"  # yellow/gold
TRAFFIC_ORANGE = "#db7b2b"  # orange
TRAFFIC_RED = "#cc3232"  # red

# Weekly on-target center (middle of the 18–22 green band).
WEEKLY_MILES_GOAL = 20.0
# Target tick sits at this fraction of every KPI gauge arc.
GAUGE_TARGET_PROGRESS = 0.8
# Gauge scale max so WEEKLY_MILES_GOAL lands at GAUGE_TARGET_PROGRESS (20 / 0.8).
MILES_GAUGE_MAX = WEEKLY_MILES_GOAL / GAUGE_TARGET_PROGRESS
SHOE_MILEAGE_GOAL = 400.0
LONGEST_RUN_GOAL = 10.0
# Gauge scale max so LONGEST_RUN_GOAL lands at GAUGE_TARGET_PROGRESS (10 / 0.8).
LONGEST_RUN_GAUGE_MAX = LONGEST_RUN_GOAL / GAUGE_TARGET_PROGRESS
EASY_TARGET_FRAC = 0.8
EH_BAND_THRESHOLDS = (80, 70, 60, 50)

# Weekly band edges relative to WEEKLY_MILES_GOAL (scaled per grain in miles_color).
_MILES_BAND_EDGES = (10.0, 14.0, 18.0, 22.0, 25.0, 28.0)


def eh_color(easy_pct: float | None) -> str:
    """Return a traffic-light color for easy-percentage KPIs.

    Parameters
    ----------
    easy_pct : float or None
        Percentage of time spent in the easy heart-rate zone.

    Returns
    -------
    str
        Hex color from the dashboard traffic-light palette, or ``INK`` when
        ``easy_pct`` is ``None``.
    """
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


def shoe_wear_color(mileage: float, goal: float = SHOE_MILEAGE_GOAL) -> str:
    """Return a traffic-light color for shoe wear toward the mileage goal.

    Low mileage stays green; color warms as the shoe approaches retirement.
    """
    if goal <= 0:
        return INK
    used = float(mileage) / float(goal)
    if used < 0.50:
        return TRAFFIC_GREEN
    if used < 0.70:
        return TRAFFIC_LIME
    if used < 0.85:
        return TRAFFIC_YELLOW
    if used < 1.0:
        return TRAFFIC_ORANGE
    return TRAFFIC_RED


def longest_run_color(miles: float | None, goal: float = LONGEST_RUN_GOAL) -> str:
    """Return a traffic-light color for longest-run progress toward the goal.

    Higher mileage is better; green once the goal is met or exceeded.
    """
    if miles is None:
        return INK
    if goal <= 0:
        return INK
    frac = float(miles) / float(goal)
    if frac >= 1.0:
        return TRAFFIC_GREEN
    if frac >= 0.8:
        return TRAFFIC_LIME
    if frac >= 0.6:
        return TRAFFIC_YELLOW
    if frac >= 0.4:
        return TRAFFIC_ORANGE
    return TRAFFIC_RED


def miles_goal(grain: str = "Week") -> float:
    """Extrapolate the weekly mileage goal to the selected period grain.

    Parameters
    ----------
    grain : str, optional
        Period grain (``Day``, ``Week``, ``Month``, or ``Year``). Defaults to
        ``"Week"``.

    Returns
    -------
    float
        Target mileage for the selected grain, scaled from the 20 mi/week center.
    """
    if grain == "Day":
        return WEEKLY_MILES_GOAL / 7.0
    if grain == "Month":
        return WEEKLY_MILES_GOAL * (52.0 / 12.0)
    if grain == "Year":
        return WEEKLY_MILES_GOAL * 52.0
    return WEEKLY_MILES_GOAL


def miles_color(miles: float | None, grain: str = "Week") -> str:
    """Return a traffic-light color for mileage against goal bands.

    Parameters
    ----------
    miles : float or None
        Total mileage for the period.
    grain : str, optional
        Period grain used to scale goal bands. Defaults to ``"Week"``.

    Returns
    -------
    str
        Hex color from the dashboard traffic-light palette, or ``INK`` when
        ``miles`` is ``None``.
    """
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
    """Return legend color and label pairs for mileage goal bands.

    Parameters
    ----------
    grain : str, optional
        Period grain used to scale band labels. Defaults to ``"Week"``.

    Returns
    -------
    list[tuple[str, str]]
        Pairs of hex color and mileage-band label strings.
    """
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
CHART_TITLE_SIZE_PX = 18
CHART_TITLE_FONT_WEIGHT = 600

# Vertical section whitespace — single source of truth for controls→chart and chart→chart gaps.
LAYOUT_GAP = "1.8rem"

# Per-chart top margin (space above each chart title). Edit individually.
CHART_RACE_WEEKS_MARGIN_TOP = "3rem"        # Training: gap above first race-week strip
CHART_COMPLIANCE_MARGIN_TOP = "1.4rem"      # Training: 80:20 compliance (races strip → chart)
CHART_MILEAGE_MARGIN_TOP = "1.85rem"        # Training: mileage
CHART_ELEVATION_MARGIN_TOP = "1.85rem"      # Training: elevation
# Header offset for Training section jumps.
RACE_STRIP_SCROLL_MARGIN_TOP = "3.75rem"
# Compact strip width: past the last marker; matches Training bar-chart right pad.
RACE_STRIP_END_PAD_PX = 12
# Training bar charts (race strip / 80:20 / mileage / elevation): slim right pad —
# 80:20 Easy/Hard key is horizontal under the title, not a side legend.
TRAINING_PLOT_MARGIN_R_PX = 32
# Fitness sections share one gap so Avg HR → Aerobic Efficiency → Fitness &
# Freshness read as one rhythm. Training keeps its own per-chart values.
FITNESS_SECTION_GAP = "2.75rem"
CHART_PACE_HR_MARGIN_TOP = FITNESS_SECTION_GAP          # Fitness: HR line
CHART_HR_ZONES_MARGIN_TOP = "1.85rem"                   # Training: HR zone stack
CHART_AEROBIC_EFFICIENCY_MARGIN_TOP = FITNESS_SECTION_GAP  # Fitness: efficiency
CHART_FITNESS_FRESHNESS_MARGIN_TOP = FITNESS_SECTION_GAP   # Fitness: Fitness & Freshness
# Fitness (+ Training HR Zones) right gutter: pace/zone legends + last-week pie.
FITNESS_PLOT_MARGIN_R_PX = 168
FITNESS_PLOT_MARGIN_L_PX = 80
# Plotly puts the Fitness legends at paper x = 1 + this fraction of plot width.
FITNESS_LEGEND_GUTTER_X_FRAC = 0.02
CHART_RACE_RESULTS_MARGIN_TOP = LAYOUT_GAP      # Performance: scatter
CHART_RACE_TABLE_MARGIN_TOP = "0.75rem"         # Performance: table section (above title)
CHART_RACE_TABLE_TITLE_GAP = "0.75rem"          # Performance: Race History title → table
# Subtle athletic purple for Total Elevation achievement badge.
ELEVATION_PURPLE = "#6F5F8D"

GLOBAL_CSS = f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  .stApp {{
    --layout-gap: {LAYOUT_GAP};
    --chart-race-weeks-margin-top: {CHART_RACE_WEEKS_MARGIN_TOP};
    --chart-compliance-margin-top: {CHART_COMPLIANCE_MARGIN_TOP};
    --chart-mileage-margin-top: {CHART_MILEAGE_MARGIN_TOP};
    --chart-elevation-margin-top: {CHART_ELEVATION_MARGIN_TOP};
    --race-strip-scroll-margin-top: {RACE_STRIP_SCROLL_MARGIN_TOP};
    --training-plot-margin-l: 78px;
    --training-plot-margin-r: {TRAINING_PLOT_MARGIN_R_PX}px;
    --fitness-plot-margin-l: {FITNESS_PLOT_MARGIN_L_PX}px;
    --fitness-plot-margin-r: {FITNESS_PLOT_MARGIN_R_PX}px;
    --race-strip-end-pad: {RACE_STRIP_END_PAD_PX}px;
    --race-strip-bg: {RACE_STRIP_BG};
    --chart-pace-hr-margin-top: {CHART_PACE_HR_MARGIN_TOP};
    --chart-hr-zones-margin-top: {CHART_HR_ZONES_MARGIN_TOP};
    --chart-aerobic-efficiency-margin-top: {CHART_AEROBIC_EFFICIENCY_MARGIN_TOP};
    --chart-fitness-freshness-margin-top: {CHART_FITNESS_FRESHNESS_MARGIN_TOP};
    --chart-race-results-margin-top: {CHART_RACE_RESULTS_MARGIN_TOP};
    --chart-race-table-margin-top: {CHART_RACE_TABLE_MARGIN_TOP};
    --chart-race-table-title-gap: {CHART_RACE_TABLE_TITLE_GAP};
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
    font-family: {FONT_BODY};
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
    display: none;
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
  section[data-testid="stSidebar"] .sidebar-nav-heading {{
    display: block;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {MUTED};
    padding: 0.35rem 0.85rem 0.55rem;
  }}
  section[data-testid="stSidebar"] [data-testid="stSidebarContent"] > div > [data-testid="stVerticalBlock"] {{
    gap: 0.2rem !important;
  }}
  section[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.sidebar-nav-current-marker) {{
    display: none !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
  }}
  div[kind="header"] {{ gap: 0.4rem !important; }}
  [data-testid="stHeadingWithActionElements"] h1,
  [data-testid="stHeadingWithActionElements"] h2,
  [data-testid="stHeadingWithActionElements"] h3 {{
    font-family: {FONT_BODY} !important;
    color: {INK} !important;
  }}

  /* Sidebar page links (st.page_link; native st.navigation is hidden).
     Streamlit 1.61 uses <a data-testid="stPageLink-NavLink"> with the label in a
     nested span/markdown/p. Color must be set on those descendants — styling only
     the <a> left inactive labels on Streamlit's default (often unreadable here),
     while the current-page span override made only the active title visible. */
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] a,
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLinkContainer"] a,
  section[data-testid="stSidebar"] div[data-testid="stPageLink-Nav"] a,
  section[data-testid="stSidebar"] [data-testid="stPageLink"] a,
  section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {{
    display: flex !important;
    align-items: center !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.92rem !important;
    color: {MUTED} !important;
    padding: 0.55rem 0.85rem !important;
    margin-bottom: 0.15rem;
    border: 1px solid transparent !important;
    background: transparent !important;
    text-decoration: none !important;
    opacity: 1 !important;
    visibility: visible !important;
    transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
  }}
  section[data-testid="stSidebar"] [data-testid="stPageLink"] a span,
  section[data-testid="stSidebar"] [data-testid="stPageLink"] a p,
  section[data-testid="stSidebar"] [data-testid="stPageLink"] a [data-testid="stMarkdownContainer"],
  section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] span,
  section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] p,
  section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] [data-testid="stMarkdownContainer"] {{
    color: {MUTED} !important;
    opacity: 1 !important;
    visibility: visible !important;
    overflow: visible !important;
  }}
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] a:hover,
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLinkContainer"] a:hover,
  section[data-testid="stSidebar"] div[data-testid="stPageLink-Nav"] a:hover,
  section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover,
  section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover {{
    background: rgba(21, 32, 40, 0.04) !important;
    color: {INK} !important;
  }}
  section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover span,
  section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover p,
  section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover [data-testid="stMarkdownContainer"],
  section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover span,
  section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover p,
  section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover [data-testid="stMarkdownContainer"] {{
    color: {INK} !important;
  }}
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] a[aria-current="page"],
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLinkContainer"] a[aria-current="page"],
  section[data-testid="stSidebar"] div[data-testid="stPageLink-Nav"] a[aria-current="page"],
  section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"]:has(.sidebar-nav-current-marker) [data-testid="stPageLink"] a,
  section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"]:has(.sidebar-nav-current-marker) [data-testid="stPageLink-NavLink"],
  section[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.sidebar-nav-current-marker) + [data-testid="stElementContainer"] [data-testid="stPageLink"] a,
  section[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.sidebar-nav-current-marker) + [data-testid="stElementContainer"] [data-testid="stPageLink-NavLink"] {{
    background: {NAV_ACTIVE} !important;
    color: {INK} !important;
    border-color: {LINE} !important;
  }}
  section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"]:has(.sidebar-nav-current-marker) [data-testid="stPageLink"] a span,
  section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"]:has(.sidebar-nav-current-marker) [data-testid="stPageLink"] a p,
  section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"]:has(.sidebar-nav-current-marker) [data-testid="stPageLink"] a [data-testid="stMarkdownContainer"],
  section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"]:has(.sidebar-nav-current-marker) [data-testid="stPageLink-NavLink"] span,
  section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"]:has(.sidebar-nav-current-marker) [data-testid="stPageLink-NavLink"] p,
  section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"]:has(.sidebar-nav-current-marker) [data-testid="stPageLink-NavLink"] [data-testid="stMarkdownContainer"],
  section[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.sidebar-nav-current-marker) + [data-testid="stElementContainer"] [data-testid="stPageLink"] a span,
  section[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.sidebar-nav-current-marker) + [data-testid="stElementContainer"] [data-testid="stPageLink"] a p,
  section[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.sidebar-nav-current-marker) + [data-testid="stElementContainer"] [data-testid="stPageLink"] a [data-testid="stMarkdownContainer"],
  section[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.sidebar-nav-current-marker) + [data-testid="stElementContainer"] [data-testid="stPageLink-NavLink"] span,
  section[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.sidebar-nav-current-marker) + [data-testid="stElementContainer"] [data-testid="stPageLink-NavLink"] p,
  section[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.sidebar-nav-current-marker) + [data-testid="stElementContainer"] [data-testid="stPageLink-NavLink"] [data-testid="stMarkdownContainer"] {{
    color: {INK} !important;
  }}

  /* In-page section navigation (On this page block below page links) */
  section[data-testid="stSidebar"] .sidebar-section-nav {{
    margin: 0.85rem 0 0.75rem;
    padding: 0.5rem 0 0.35rem;
    border-top: 1px solid {LINE};
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
  #chart-race-weeks,
  #chart-compliance,
  #chart-mileage,
  #chart-elevation,
  #chart-pace-hr,
  #chart-hr-zones,
  #chart-aerobic-efficiency,
  #chart-fitness-freshness,
  #chart-race-results,
  #race-results-table {{
    scroll-margin-top: 1.25rem;
    height: 0;
    margin: 0;
    padding: 0;
    overflow: hidden;
  }}
  /* 80:20 jump keeps the in-flow strip (above this anchor) in view. */
  #chart-compliance {{
    scroll-margin-top: calc(var(--race-strip-scroll-margin-top) + 4.5rem);
  }}
  /* Mileage / elevation / HR zones: keep race strip in view on section jump. */
  #chart-mileage,
  #chart-elevation,
  #chart-hr-zones {{
    scroll-margin-top: var(--race-strip-scroll-margin-top);
  }}
  /* Fitness: first chart after the shared race-week strip. */
  [data-testid="stMain"]:has(#chart-pace-hr) #chart-pace-hr {{
    scroll-margin-top: calc(var(--race-strip-scroll-margin-top) + 4.5rem);
  }}
  [data-testid="stMain"]:has(#chart-pace-hr) #chart-aerobic-efficiency,
  [data-testid="stMain"]:has(#chart-pace-hr) #chart-fitness-freshness {{
    scroll-margin-top: var(--race-strip-scroll-margin-top);
  }}
  #key-indicators {{
    scroll-margin-top: 1.25rem;
  }}
  /* Standalone KI panel (non-Metrics). Nested Metrics KI uses .ki-panel column. */
  [data-testid="stElementContainer"]:has(#key-indicators) {{
    margin-top: var(--layout-gap) !important;
    margin-bottom: 0 !important;
  }}
  [data-testid="stColumn"]:has(.ki-panel) [data-testid="stElementContainer"]:has(#key-indicators),
  [data-testid="column"]:has(.ki-panel) [data-testid="stElementContainer"]:has(#key-indicators) {{
    margin-top: 0 !important;
  }}
  /* Metrics: KI gauges + Inspect share one painted column (same idea as controls-panel).
     Achievements is HTML markdown: Streamlit's stMarkdownContainer uses
     margin-bottom: -1rem (spacing.lg) to cancel its default 1rem flex gap.
     Page gap is 0, so that pull-up still shrinks Achievements → KI. KI is
     st.columns + expander, which does not get that offset — without it,
     KI → Shoes is a full --layout-gap larger. Match the markdown pull-up. */
  [data-testid="stHorizontalBlock"]:has(.ki-panel) {{
    margin-top: var(--layout-gap) !important;
    margin-bottom: -1rem !important;
    width: 100% !important;
    gap: 0 !important;
    padding-bottom: 0 !important;
  }}
  [data-testid="stElementContainer"]:has(.ki-panel):has([data-testid="stHorizontalBlock"]) {{
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
  }}
  [data-testid="stColumn"]:has(.ki-panel),
  [data-testid="column"]:has(.ki-panel) {{
    background: rgba(255, 255, 255, 0.82) !important;
    border: 1px solid rgba(21, 32, 40, 0.06) !important;
    border-radius: 20px !important;
    padding: 1.25rem 1.2rem 0.85rem !important;
    box-shadow: 0 10px 30px rgba(21, 32, 40, 0.04) !important;
    backdrop-filter: blur(10px);
    overflow: visible !important;
    width: 100% !important;
    flex: 1 1 100% !important;
  }}
  .ki-panel {{
    display: none;
  }}
  [data-testid="stColumn"]:has(.ki-panel) [data-testid="stVerticalBlock"],
  [data-testid="column"]:has(.ki-panel) [data-testid="stVerticalBlock"] {{
    gap: 0 !important;
  }}
  /* Inspect expander body needs normal stacking: detail copy then table.
     The flush gap:0 above is for KI chrome; restore spacing inside details. */
  [data-testid="stColumn"]:has(.ki-panel) [data-testid="stExpanderDetails"] [data-testid="stVerticalBlock"],
  [data-testid="column"]:has(.ki-panel) [data-testid="stExpanderDetails"] [data-testid="stVerticalBlock"],
  .st-key-metrics_inspect_ki [data-testid="stExpanderDetails"] [data-testid="stVerticalBlock"] {{
    gap: 0.35rem !important;
  }}
  [data-testid="stColumn"]:has(.ki-panel) [data-testid="stElementContainer"],
  [data-testid="column"]:has(.ki-panel) [data-testid="stElementContainer"] {{
    margin-top: 0 !important;
    margin-bottom: 0 !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
  }}
  /* Nested columns inside KI (inspect select) stay flush — no nested cards. */
  [data-testid="stColumn"]:has(.ki-panel) [data-testid="stColumn"],
  [data-testid="stColumn"]:has(.ki-panel) [data-testid="column"],
  [data-testid="column"]:has(.ki-panel) [data-testid="stColumn"],
  [data-testid="column"]:has(.ki-panel) [data-testid="column"] {{
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    padding: 0 !important;
    backdrop-filter: none;
  }}
  #achievements {{
    scroll-margin-top: 1.25rem;
    overflow: visible;
  }}
  [data-testid="stElementContainer"]:has(#achievements) {{
    margin-top: var(--layout-gap) !important;
    margin-bottom: 0 !important;
    overflow: visible !important;
  }}
  [data-testid="stElementContainer"]:has(#achievements)
    [data-testid="stMarkdownContainer"],
  [data-testid="stElementContainer"]:has(#achievements)
    [data-testid="stMarkdown"] {{
    overflow: visible !important;
  }}
  /* Metrics: achievements sit under the page summary (no controls row). */
  [data-testid="stElementContainer"]:has(.panel-summary)
    + [data-testid="stElementContainer"]:has(#achievements) {{
    margin-top: 0 !important;
  }}
  /* Performance: Personal Records sit under the page summary, above Controls. */
  [data-testid="stElementContainer"]:has(.panel-summary)
    + [data-testid="stElementContainer"]:has(#fastest-races) {{
    margin-top: 0 !important;
  }}
  #shoe-mileage {{
    scroll-margin-top: 1.25rem;
  }}
  [data-testid="stElementContainer"]:has(#shoe-mileage) {{
    margin-top: var(--layout-gap) !important;
    margin-bottom: 0 !important;
  }}
  #fastest-races {{
    scroll-margin-top: 1.25rem;
    /* Override .panel height:100% — on Streamlit Cloud that can shrink the
       layout box below the card grid so Controls overlaps the strip. */
    height: auto;
  }}
  /* Main page stack: spacing is explicit via --layout-gap (not Streamlit gap). */
  .block-container > div[data-testid="stVerticalBlock"] {{
    gap: 0 !important;
  }}
  /* Scroll anchors: zero footprint; chart containers supply section gap above. */
  [data-testid="stElementContainer"]:has(.page-anchor) {{
    margin: 0 !important;
    padding: 0 !important;
  }}
  /* Plotly chart containers: zero bottom; gap comes from each chart's top margin. */
  [data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"]) {{
    margin-bottom: 0 !important;
  }}
  /* Training: one in-flow race-week strip under Controls (above 80:20).
     Charts use gold diamond markers (not dashed guides); no snap JS,
     hide/show CSS, sticky positioning, or duplicate strips above
     mileage/elevation. Metrics is unchanged. */
  [data-testid="stMain"]:has(.st-key-race_week_strip)
    [data-testid="stLayoutWrapper"]:has(.st-key-race_week_strip),
  .st-key-race_week_strip {{
    background: transparent !important;
    overflow: visible !important;
  }}
  /* Permanent Controls → race-week strip gap. */
  [data-testid="stElementContainer"]:has(#chart-race-weeks) {{
    margin-top: var(--chart-race-weeks-margin-top) !important;
  }}
  .st-key-race_week_strip {{
    align-self: flex-start;
    position: relative;
    width: 100%;
    margin-top: 0 !important;
    margin-bottom: 0 !important;
    background: transparent !important;
    overflow: visible !important;
  }}
  .st-key-race_week_strip::before {{
    content: "";
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: calc(100% - var(--training-plot-margin-r) + var(--race-strip-end-pad));
    max-width: 100%;
    background: var(--race-strip-bg);
    border: none;
    border-radius: 0;
    box-shadow: none;
    pointer-events: none;
    z-index: 0;
  }}
  [data-testid="stMain"]:has(#chart-pace-hr) .st-key-race_week_strip::before {{
    width: calc(100% - var(--fitness-plot-margin-r) + var(--race-strip-end-pad));
  }}
  .st-key-race_week_strip [data-testid="stVerticalBlockBorderWrapper"],
  .st-key-race_week_strip [data-testid="stVerticalBlock"],
  .st-key-race_week_strip [data-testid="stLayoutWrapper"] {{
    position: relative;
    background: transparent !important;
    overflow: visible !important;
  }}
  /* Label lives in the 78px plot left-margin so diamonds line up with bars. */
  .st-key-race_week_strip [data-testid="stElementContainer"]:has(.race-week-legend) {{
    position: absolute !important;
    left: 0;
    top: 0;
    bottom: 0;
    width: var(--training-plot-margin-l);
    margin: 0 !important;
    padding: 0 !important;
    /* Above compliance HTML title band (z-index 8) so the ⓘ tooltip is readable. */
    z-index: 12;
    pointer-events: none;
  }}
  [data-testid="stMain"]:has(#chart-pace-hr)
    .st-key-race_week_strip
    [data-testid="stElementContainer"]:has(.race-week-legend) {{
    width: var(--fitness-plot-margin-l);
  }}
  .race-week-legend {{
    pointer-events: auto;
    height: 100%;
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: flex-start;
    gap: 0.2rem;
    padding: 0 0.2rem 0 0.15rem;
    box-sizing: border-box;
  }}
  .race-week-strip-label {{
    margin: 0 !important;
    font-size: 0.62rem;
    letter-spacing: 0.07em;
    line-height: 1.2;
    max-width: none;
    flex-shrink: 0;
    text-shadow: 0 0 8px {BG}, 0 1px 2px {BG};
  }}
  .race-week-legend .kpi-info {{
    margin-top: 0;
    flex-shrink: 0;
  }}
  .race-week-legend .kpi-tooltip {{
    left: 0;
    right: auto;
    bottom: auto;
    top: calc(100% + 0.35rem);
    transform: none;
    width: min(16.5rem, 72vw);
    /* Solid white over the 80:20 title band; parent stack is z-index 12. */
    background: {CARD};
    background-color: {CARD};
    z-index: 70;
  }}
  .kpi-tooltip .race-legend-row {{
    display: flex;
    align-items: center;
    gap: 0.45rem;
    margin-top: 0.2rem;
    line-height: 1.35;
    color: {INK} !important;
  }}
  .kpi-tooltip .race-legend-marker {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 12px;
    height: 12px;
    flex-shrink: 0;
  }}
  .kpi-tooltip .race-legend-marker .band-square,
  .kpi-tooltip .race-legend-marker .band-diamond {{
    margin: 0;
  }}

  .band-square {{
    display: inline-block;
    width: 5px;
    height: 5px;
    margin-right: 0.35rem;
    vertical-align: middle;
    flex-shrink: 0;
  }}
  .band-diamond {{
    display: inline-block;
    width: 8px;
    height: 8px;
    transform: rotate(45deg);
    margin-right: 0.45rem;
    margin-left: 0.12rem;
    vertical-align: middle;
    flex-shrink: 0;
  }}
  .st-key-race_week_strip [data-testid="stPlotlyChart"],
  .st-key-race_week_strip .js-plotly-plot,
  .st-key-race_week_strip .plot-container,
  .st-key-race_week_strip .svg-container {{
    position: relative;
    z-index: 1;
    background: transparent !important;
    height: 40px !important;
    max-height: 40px !important;
    min-height: 0 !important;
  }}
  .st-key-race_week_strip [data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"]) {{
    min-height: 0 !important;
    height: 40px !important;
    margin: 0 !important;
    padding: 0 !important;
  }}
  /* Training charts: top gap on each chart container. */
  /* 80:20: HTML title + ⓘ sit in the Plotly title band (blank Plotly title);
     margin-top lives on the info container (Fitness pattern). */
  .st-key-training_compliance {{
    margin-top: 0 !important;
    margin-bottom: 0 !important;
  }}
  [data-testid="stElementContainer"]:has(.compliance-info) {{
    position: relative;
    z-index: 8;
    display: block;
    width: 100%;
    margin-top: var(--chart-compliance-margin-top) !important;
    margin-bottom: -2.15rem !important;
    padding: 0 !important;
    overflow: visible !important;
    pointer-events: none;
  }}
  [data-testid="stElementContainer"]:has(.compliance-info)
    [data-testid="stMarkdownContainer"],
  [data-testid="stElementContainer"]:has(.compliance-info)
    [data-testid="stMarkdown"] {{
    overflow: visible !important;
    width: 100% !important;
  }}
  [data-testid="stElementContainer"]:has(.compliance-info)
    + [data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"]) {{
    margin-top: 0 !important;
    margin-bottom: 0 !important;
  }}
  .compliance-info {{
    position: relative;
    top: 0.4rem;
    display: inline-flex;
    align-items: center;
    gap: 0.28rem;
    max-width: calc(100% - var(--training-plot-margin-r) - 0.75rem);
    min-height: 1.6rem;
    z-index: 8;
    pointer-events: none;
  }}
  .compliance-chart-title {{
    display: inline;
    font-family: {FONT_BODY};
    font-size: {CHART_TITLE_SIZE_PX}px;
    font-weight: {CHART_TITLE_FONT_WEIGHT};
    color: {INK};
    line-height: 1.2;
  }}
  .compliance-info .kpi-info {{
    position: relative;
    flex-shrink: 0;
    opacity: 0.85;
    pointer-events: auto;
    z-index: 9;
  }}
  .compliance-info .kpi-tooltip {{
    /* Open to the right of ⓘ on hover/focus. */
    left: calc(100% + 0.35rem);
    right: auto;
    bottom: auto;
    top: 0;
    transform: none;
    width: min(22rem, 72vw);
    z-index: 60;
  }}
  .st-key-training_mileage {{
    margin-top: var(--chart-mileage-margin-top) !important;
    margin-bottom: 0 !important;
  }}
  /* Mileage heatmap expander: sit under the solid bar chart like Metrics Inspect. */
  .st-key-training_mileage_heatmap {{
    margin-top: 0.55rem !important;
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
    /* Streamlit expander chrome reads theme.secondaryBg; pin to page BG hex and
       clear fills so the .stApp gradient (base {BG}) shows through — a solid
       {BG} card looked cooler/darker against the lighter mid-page wash. */
    --secondary-background-color: {BG};
  }}
  /* Every visible layer of the mileage heatmap expander = page surface.
     Transparent (not solid BG/SURFACE/CARD/secondaryBg) so .stApp shows through.
     Scoped to this key only — Metrics Inspect stays on the KI panel surface. */
  .st-key-training_mileage_heatmap,
  .st-key-training_mileage_heatmap [data-testid="stExpander"],
  .st-key-training_mileage_heatmap [data-testid="stExpander"] details,
  .st-key-training_mileage_heatmap [data-testid="stExpander"] summary,
  .st-key-training_mileage_heatmap [data-testid="stExpander"] details[open]
    [data-testid="stExpanderDetails"],
  .st-key-training_mileage_heatmap [data-testid="stExpanderDetails"],
  .st-key-training_mileage_heatmap [data-testid="stVerticalBlockBorderWrapper"],
  .st-key-training_mileage_heatmap [data-testid="stVerticalBlock"],
  .st-key-training_mileage_heatmap [data-testid="stLayoutWrapper"],
  .st-key-training_mileage_heatmap [data-testid="stElementContainer"],
  .st-key-training_mileage_heatmap [data-testid="stPlotlyChart"],
  .st-key-training_mileage_heatmap .stPlotlyChart,
  .st-key-training_mileage_heatmap .js-plotly-plot,
  .st-key-training_mileage_heatmap .plot-container,
  .st-key-training_mileage_heatmap .svg-container,
  .st-key-training_mileage_heatmap .main-svg,
  .st-key-training_mileage_heatmap iframe {{
    background: transparent !important;
    background-color: transparent !important;
    box-shadow: none !important;
  }}
  .st-key-training_elevation {{
    margin-top: var(--chart-elevation-margin-top) !important;
    margin-bottom: 0 !important;
  }}
  /* Fitness: Average HR by Pace — HTML title + rolling subtitle outside
     Plotly (blank Plotly title) so SVG margin clipping cannot cut caps.
     In-flow + negative margin mirrors AE / F&F title-band overlay. */
  [data-testid="stElementContainer"]:has(.pace-hr-info) {{
    position: relative;
    z-index: 8;
    display: block;
    width: 100%;
    margin-top: var(--chart-pace-hr-margin-top) !important;
    margin-bottom: -2.85rem !important;
    padding: 0 !important;
    overflow: visible !important;
    pointer-events: none;
  }}
  [data-testid="stMain"]:has(#chart-pace-hr)
    [data-testid="stElementContainer"]:has(.pace-hr-info) {{
    margin-top: var(--chart-compliance-margin-top) !important;
  }}
  [data-testid="stElementContainer"]:has(.pace-hr-info)
    [data-testid="stMarkdownContainer"],
  [data-testid="stElementContainer"]:has(.pace-hr-info)
    [data-testid="stMarkdown"] {{
    overflow: visible !important;
    width: 100% !important;
  }}
  [data-testid="stElementContainer"]:has(.pace-hr-info)
    + [data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"]) {{
    margin-top: 0 !important;
    margin-bottom: 0 !important;
  }}
  .pace-hr-info {{
    position: relative;
    top: 0.35rem;
    display: block;
    max-width: calc(100% - var(--fitness-plot-margin-r) - 0.75rem);
    min-height: 2.35rem;
    z-index: 8;
    pointer-events: none;
  }}
  .pace-hr-chart-heading {{
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.12rem;
  }}
  .pace-hr-chart-title-row {{
    display: inline-flex;
    align-items: center;
    gap: 0.28rem;
    max-width: 100%;
  }}
  .pace-hr-chart-title {{
    display: inline;
    font-family: {FONT_BODY};
    font-size: {CHART_TITLE_SIZE_PX}px;
    font-weight: {CHART_TITLE_FONT_WEIGHT};
    color: {INK};
    line-height: 1.2;
  }}
  .pace-hr-info .kpi-info {{
    position: relative;
    flex-shrink: 0;
    opacity: 0.85;
    pointer-events: auto;
    z-index: 9;
  }}
  .pace-hr-info .kpi-tooltip {{
    /* Open to the right of ⓘ on hover/focus. */
    left: calc(100% + 0.35rem);
    right: auto;
    bottom: auto;
    top: 0;
    transform: none;
    width: min(20rem, 72vw);
    z-index: 60;
  }}
  .pace-hr-chart-subtitle {{
    display: block;
    font-family: {FONT_BODY};
    font-size: 12px;
    font-weight: 400;
    color: {MUTED};
    line-height: 1.25;
  }}
  /* Avg HR by Pace: unified hover has no Plotly API to drop the trace color
     swatch (legend line/marker). Hide only in this chart's hoverlayer so other
     Fitness/Training charts keep theirs. Side legend is outside .hoverlayer. */
  [data-testid="stElementContainer"]:has(.pace-hr-info)
    + [data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"])
    .hoverlayer
    .legendlines,
  [data-testid="stElementContainer"]:has(.pace-hr-info)
    + [data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"])
    .hoverlayer
    .legendsymbols,
  [data-testid="stElementContainer"]:has(.pace-hr-info)
    + [data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"])
    .hoverlayer
    .legendfill {{
    display: none !important;
  }}
  /* Training: HR zone 100% stacked area — last-week donut overlays the shared
     right deadspan under the Zone legend (beside the stack, not below it). */
  [data-testid="stElementContainer"]:has(#chart-hr-zones)
    + [data-testid="stElementContainer"]:has(.hr-zones-pie-gutter) {{
    position: relative;
    z-index: 8;
    display: block;
    width: 100%;
    height: 0 !important;
    min-height: 0 !important;
    margin-top: var(--chart-hr-zones-margin-top) !important;
    margin-bottom: 0 !important;
    padding: 0 !important;
    overflow: visible !important;
    pointer-events: none;
  }}
  [data-testid="stElementContainer"]:has(.hr-zones-pie-gutter)
    [data-testid="stMarkdownContainer"],
  [data-testid="stElementContainer"]:has(.hr-zones-pie-gutter)
    [data-testid="stMarkdown"] {{
    overflow: visible !important;
    width: 100% !important;
  }}
  [data-testid="stElementContainer"]:has(.hr-zones-pie-gutter)
    + [data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"]) {{
    margin-top: 0 !important;
    margin-bottom: 0 !important;
  }}
  .hr-zones-pie-gutter {{
    position: relative;
    width: 100%;
    height: 0;
    z-index: 8;
    pointer-events: none;
  }}
  .hr-zones-pie-panel {{
    position: absolute;
    top: 10.75rem;
    right: 0;
    width: var(--fitness-plot-margin-r);
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.35rem;
    padding: 0 0.35rem 0.25rem;
    pointer-events: none;
    z-index: 9;
  }}
  .hr-zones-pie-caption {{
    font-family: {FONT_BODY};
    font-size: 0.68rem;
    line-height: 1.25;
    text-align: center;
    color: {MUTED};
  }}
  .hr-zones-pie-donut {{
    position: relative;
    width: 6.75rem;
    height: 6.75rem;
    flex-shrink: 0;
    pointer-events: auto;
  }}
  .hr-zones-pie-donut svg {{
    display: block;
    width: 100%;
    height: 100%;
    border-radius: 50%;
    overflow: visible;
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.55);
    -webkit-mask: radial-gradient(circle, transparent 28%, #000 29%);
    mask: radial-gradient(circle, transparent 28%, #000 29%);
  }}
  .hr-zones-pie-slice {{
    cursor: default;
    outline: none;
  }}
  .hr-zones-pie-slice:focus-visible {{
    filter: brightness(1.08);
  }}
  .hr-zones-pie-donut .hr-zones-pie-tip {{
    left: 50%;
    right: auto;
    bottom: calc(100% + 0.35rem);
    top: auto;
    transform: translateX(-50%);
    /* Wider than the ~168px gutter so zone / % / time lines read cleanly. */
    width: min(12rem, 72vw);
    z-index: 60;
  }}
  .hr-zones-pie-donut:has(.hr-zones-pie-slice[data-zone="1"]:hover) .hr-zones-pie-tip[data-zone="1"],
  .hr-zones-pie-donut:has(.hr-zones-pie-slice[data-zone="1"]:focus) .hr-zones-pie-tip[data-zone="1"],
  .hr-zones-pie-donut:has(.hr-zones-pie-slice[data-zone="1"]:focus-visible) .hr-zones-pie-tip[data-zone="1"],
  .hr-zones-pie-donut:has(.hr-zones-pie-slice[data-zone="2"]:hover) .hr-zones-pie-tip[data-zone="2"],
  .hr-zones-pie-donut:has(.hr-zones-pie-slice[data-zone="2"]:focus) .hr-zones-pie-tip[data-zone="2"],
  .hr-zones-pie-donut:has(.hr-zones-pie-slice[data-zone="2"]:focus-visible) .hr-zones-pie-tip[data-zone="2"],
  .hr-zones-pie-donut:has(.hr-zones-pie-slice[data-zone="3"]:hover) .hr-zones-pie-tip[data-zone="3"],
  .hr-zones-pie-donut:has(.hr-zones-pie-slice[data-zone="3"]:focus) .hr-zones-pie-tip[data-zone="3"],
  .hr-zones-pie-donut:has(.hr-zones-pie-slice[data-zone="3"]:focus-visible) .hr-zones-pie-tip[data-zone="3"],
  .hr-zones-pie-donut:has(.hr-zones-pie-slice[data-zone="4"]:hover) .hr-zones-pie-tip[data-zone="4"],
  .hr-zones-pie-donut:has(.hr-zones-pie-slice[data-zone="4"]:focus) .hr-zones-pie-tip[data-zone="4"],
  .hr-zones-pie-donut:has(.hr-zones-pie-slice[data-zone="4"]:focus-visible) .hr-zones-pie-tip[data-zone="4"],
  .hr-zones-pie-donut:has(.hr-zones-pie-slice[data-zone="5"]:hover) .hr-zones-pie-tip[data-zone="5"],
  .hr-zones-pie-donut:has(.hr-zones-pie-slice[data-zone="5"]:focus) .hr-zones-pie-tip[data-zone="5"],
  .hr-zones-pie-donut:has(.hr-zones-pie-slice[data-zone="5"]:focus-visible) .hr-zones-pie-tip[data-zone="5"] {{
    visibility: visible;
    opacity: 1;
  }}
  .hr-zones-pie-empty {{
    width: 6.75rem;
    height: 6.75rem;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    font-family: {FONT_BODY};
    font-size: 0.68rem;
    line-height: 1.25;
    color: {MUTED};
  }}
  /* Fitness: aerobic efficiency — HTML title + ⓘ inline in the empty Plotly
     title band. Hover/focus shows definition via .kpi-tooltip opening to the
     right of the icon. In-flow + negative margin so Streamlit does not clip
     the overlay (not inside the zero-height page-anchor). */
  [data-testid="stElementContainer"]:has(.aerobic-efficiency-info) {{
    position: relative;
    z-index: 8;
    display: block;
    width: 100%;
    margin-top: var(--chart-aerobic-efficiency-margin-top) !important;
    margin-bottom: -2.15rem !important;
    padding: 0 !important;
    overflow: visible !important;
    pointer-events: none;
  }}
  [data-testid="stElementContainer"]:has(.aerobic-efficiency-info)
    [data-testid="stMarkdownContainer"],
  [data-testid="stElementContainer"]:has(.aerobic-efficiency-info)
    [data-testid="stMarkdown"] {{
    overflow: visible !important;
    width: 100% !important;
  }}
  [data-testid="stElementContainer"]:has(.aerobic-efficiency-info)
    + [data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"]) {{
    margin-top: 0 !important;
    margin-bottom: 0 !important;
  }}
  .aerobic-efficiency-info {{
    position: relative;
    top: 0.4rem;
    display: inline-flex;
    align-items: center;
    gap: 0.28rem;
    max-width: calc(100% - var(--fitness-plot-margin-r) - 0.75rem);
    min-height: 1.6rem;
    z-index: 8;
    pointer-events: none;
  }}
  .aerobic-efficiency-chart-title {{
    display: inline;
    font-family: {FONT_BODY};
    font-size: {CHART_TITLE_SIZE_PX}px;
    font-weight: {CHART_TITLE_FONT_WEIGHT};
    color: {INK};
    line-height: 1.2;
  }}
  .aerobic-efficiency-info .kpi-info {{
    position: relative;
    flex-shrink: 0;
    opacity: 0.85;
    pointer-events: auto;
    z-index: 9;
  }}
  .aerobic-efficiency-info .kpi-tooltip {{
    /* Open to the right of ⓘ on hover/focus. */
    left: calc(100% + 0.35rem);
    right: auto;
    bottom: auto;
    top: 0;
    transform: none;
    width: min(20rem, 72vw);
    z-index: 60;
  }}
  /* Fitness: Fitness & Freshness — HTML title + ⓘ inline in the title band.
     Tooltip opens to the right of the icon. In-flow + negative margin so
     Streamlit does not clip the overlay. */
  [data-testid="stElementContainer"]:has(.fitness-freshness-info) {{
    position: relative;
    z-index: 8;
    display: block;
    width: 100%;
    margin-top: var(--chart-fitness-freshness-margin-top) !important;
    margin-bottom: -2.15rem !important;
    padding: 0 !important;
    overflow: visible !important;
    pointer-events: none;
  }}
  [data-testid="stElementContainer"]:has(.fitness-freshness-info)
    [data-testid="stMarkdownContainer"],
  [data-testid="stElementContainer"]:has(.fitness-freshness-info)
    [data-testid="stMarkdown"] {{
    overflow: visible !important;
    width: 100% !important;
  }}
  [data-testid="stElementContainer"]:has(.fitness-freshness-info)
    + [data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"]) {{
    margin-top: 0 !important;
    margin-bottom: 0 !important;
  }}
  .fitness-freshness-info {{
    position: relative;
    top: 0.4rem;
    display: inline-flex;
    align-items: center;
    gap: 0.28rem;
    max-width: calc(100% - var(--fitness-plot-margin-r) - 0.75rem);
    min-height: 1.6rem;
    z-index: 8;
    pointer-events: none;
  }}
  .fitness-freshness-chart-title {{
    display: inline;
    font-family: {FONT_BODY};
    font-size: {CHART_TITLE_SIZE_PX}px;
    font-weight: {CHART_TITLE_FONT_WEIGHT};
    color: {INK};
    line-height: 1.2;
  }}
  .fitness-freshness-info .kpi-info {{
    position: relative;
    flex-shrink: 0;
    opacity: 0.85;
    pointer-events: auto;
    z-index: 9;
  }}
  .fitness-freshness-info .kpi-tooltip {{
    /* Open to the right of ⓘ on hover/focus. */
    left: calc(100% + 0.35rem);
    right: auto;
    bottom: auto;
    top: 0;
    transform: none;
    width: min(20rem, 72vw);
    z-index: 60;
  }}
  /* Performance: Personal Records strip under page summary */
  [data-testid="stElementContainer"]:has(#fastest-races) {{
    margin-top: var(--layout-gap) !important;
    margin-bottom: 0 !important;
    /* Keep layout height tied to the PR panel (Cloud can clip otherwise). */
    overflow: visible !important;
  }}
  [data-testid="stElementContainer"]:has(#fastest-races)
    [data-testid="stMarkdownContainer"],
  [data-testid="stElementContainer"]:has(#fastest-races)
    [data-testid="stMarkdown"] {{
    overflow: visible !important;
  }}
  /* In-flow spacer between PR cards and Controls (Cloud-safe; avoids depending
     on margin-bottom collapsing against the columns row). */
  .performance-pr-gap {{
    height: calc(var(--layout-gap) * 1.5);
    margin: 0;
    padding: 0;
  }}
  [data-testid="stElementContainer"]:has(.performance-pr-gap) {{
    margin: 0 !important;
    padding: 0 !important;
    min-height: calc(var(--layout-gap) * 1.5);
  }}
  /* Performance: scatter chart — full-bleed like Race History table */
  [data-testid="stElementContainer"]:has(#chart-race-results)
    + [data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"]) {{
    margin-top: var(--chart-race-results-margin-top) !important;
    margin-bottom: 0 !important;
    width: 100% !important;
    max-width: 100% !important;
  }}
  [data-testid="stElementContainer"]:has(#chart-race-results)
    + [data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"])
    [data-testid="stPlotlyChart"],
  [data-testid="stElementContainer"]:has(#chart-race-results)
    + [data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"])
    .js-plotly-plot,
  [data-testid="stElementContainer"]:has(#chart-race-results)
    + [data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"])
    .plot-container {{
    width: 100% !important;
    max-width: 100% !important;
  }}
  /* Performance: table section */
  [data-testid="stElementContainer"]:has(#race-results-table)
    + [data-testid="stElementContainer"]:has(.chart-section-title) {{
    margin-top: var(--chart-race-table-margin-top) !important;
  }}
  [data-testid="stElementContainer"]:has(.chart-section-title)
    + [data-testid="stElementContainer"]:has([data-testid="stDataFrame"]) {{
    margin-top: var(--chart-race-table-title-gap) !important;
  }}
  [data-testid="stElementContainer"]:has(.chart-section-title)
    + [data-testid="stElementContainer"]:has([data-testid="stDataFrame"]) [data-testid="stDataFrame"] {{
    background: {RACE_TABLE_FILL};
    border: 1px solid rgba(21, 32, 40, 0.06);
    border-radius: 20px;
    box-shadow: 0 10px 30px rgba(21, 32, 40, 0.04);
    overflow: hidden;
    /* Transparent body, header, and row-marker chrome so the page wash shows
       through. Streamlit also maps header/checkbox fills from
       dataframeHeaderBackgroundColor (see .streamlit/config.toml). */
    --gdg-bg-cell: {RACE_TABLE_FILL};
    --gdg-bg-cell-medium: {RACE_TABLE_FILL};
    --gdg-bg-header: {RACE_TABLE_FILL};
    --gdg-bg-header-has-focus: {RACE_TABLE_FILL};
    --gdg-bg-header-hovered: {RACE_TABLE_FILL};
    --gdg-bg-group-header: {RACE_TABLE_FILL};
    --gdg-bg-group-header-hovered: {RACE_TABLE_FILL};
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
    padding: 1.2rem !important;
    box-shadow: 0 10px 30px rgba(21, 32, 40, 0.04) !important;
    backdrop-filter: blur(10px);
  }}
  /* Nested columns inside a unified controls panel stay flush (no nested cards). */
  [data-testid="stColumn"]:has(.controls-panel) [data-testid="stColumn"],
  [data-testid="stColumn"]:has(.controls-panel) [data-testid="column"],
  [data-testid="column"]:has(.controls-panel) [data-testid="stColumn"],
  [data-testid="column"]:has(.controls-panel) [data-testid="column"] {{
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    padding: 0 !important;
    backdrop-filter: none;
  }}
  .controls-panel:not(.controls-title) {{
    display: none;
  }}
  .controls-title {{
    font-family: {FONT_BODY};
    font-size: 0.95rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    text-transform: none;
    color: {INK};
    margin: 0 0 1.05rem 0;
    line-height: 1.2;
  }}
  .controls-section-label {{
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {MUTED};
    margin: 0 0 0.9rem 0;
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
  [data-testid="column"]:has(.controls-panel) [data-testid="stSelectbox"],
  [data-testid="stColumn"]:has(.controls-panel) [data-testid="stMultiSelect"],
  [data-testid="column"]:has(.controls-panel) [data-testid="stMultiSelect"] {{
    margin-bottom: 0 !important;
  }}
  /* Streamlit 1.61+ select control (React Aria) — not BaseWeb. */
  [data-testid="stColumn"]:has(.controls-panel) [data-testid="stSelectbox"] div:has(> input),
  [data-testid="column"]:has(.controls-panel) [data-testid="stSelectbox"] div:has(> input),
  [data-testid="stColumn"]:has(.controls-panel) [data-testid="stMultiSelect"] div:has(> input),
  [data-testid="column"]:has(.controls-panel) [data-testid="stMultiSelect"] div:has(> input),
  [data-testid="stColumn"]:has(.controls-panel) div[data-baseweb="select"] > div,
  [data-testid="column"]:has(.controls-panel) div[data-baseweb="select"] > div {{
    background: {SURFACE} !important;
    background-color: {SURFACE} !important;
    border: 1px solid {LINE} !important;
    border-radius: 10px !important;
    min-height: 38px !important;
    box-shadow: none !important;
    color: {INK} !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
  }}
  [data-testid="stColumn"]:has(.controls-panel) [data-testid="stSelectbox"] div:has(> input):focus-within,
  [data-testid="column"]:has(.controls-panel) [data-testid="stSelectbox"] div:has(> input):focus-within,
  [data-testid="stColumn"]:has(.controls-panel) [data-testid="stMultiSelect"] div:has(> input):focus-within,
  [data-testid="column"]:has(.controls-panel) [data-testid="stMultiSelect"] div:has(> input):focus-within,
  [data-testid="stColumn"]:has(.controls-panel) div[data-baseweb="select"] > div:focus-within,
  [data-testid="column"]:has(.controls-panel) div[data-baseweb="select"] > div:focus-within {{
    border-color: rgba(91, 155, 213, 0.45) !important;
    box-shadow: 0 0 0 3px rgba(91, 155, 213, 0.1) !important;
  }}
  [data-testid="stColumn"]:has(.controls-panel) [data-testid="stSelectbox"] input,
  [data-testid="column"]:has(.controls-panel) [data-testid="stSelectbox"] input,
  [data-testid="stColumn"]:has(.controls-panel) [data-testid="stMultiSelect"] input,
  [data-testid="column"]:has(.controls-panel) [data-testid="stMultiSelect"] input,
  [data-testid="stColumn"]:has(.controls-panel) div[data-baseweb="select"] span,
  [data-testid="column"]:has(.controls-panel) div[data-baseweb="select"] span {{
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    color: {INK} !important;
    -webkit-text-fill-color: {INK} !important;
  }}
  /* Compact controls panels (Fitness + Performance): narrow selectboxes /
     multiselects (same 75% width as Show By). */
  [data-testid="stColumn"]:has(.controls-panel--compact) [data-testid="stSelectbox"],
  [data-testid="column"]:has(.controls-panel--compact) [data-testid="stSelectbox"],
  [data-testid="stColumn"]:has(.controls-panel--compact) [data-testid="stSelectbox"] div:has(> input),
  [data-testid="column"]:has(.controls-panel--compact) [data-testid="stSelectbox"] div:has(> input),
  [data-testid="stColumn"]:has(.controls-panel--compact) [data-testid="stMultiSelect"],
  [data-testid="column"]:has(.controls-panel--compact) [data-testid="stMultiSelect"],
  [data-testid="stColumn"]:has(.controls-panel--compact) [data-testid="stMultiSelect"] div:has(> input),
  [data-testid="column"]:has(.controls-panel--compact) [data-testid="stMultiSelect"] div:has(> input),
  [data-testid="stColumn"]:has(.controls-panel--compact) div[data-baseweb="select"] > div,
  [data-testid="column"]:has(.controls-panel--compact) div[data-baseweb="select"] > div,
  [data-testid="stElementContainer"]:has(.controls-select-narrow)
    + [data-testid="stElementContainer"] [data-testid="stSelectbox"],
  [data-testid="stElementContainer"]:has(.controls-select-narrow)
    + [data-testid="stElementContainer"] [data-testid="stSelectbox"] div:has(> input),
  [data-testid="stElementContainer"]:has(.controls-select-narrow)
    + [data-testid="stElementContainer"] [data-testid="stMultiSelect"],
  [data-testid="stElementContainer"]:has(.controls-select-narrow)
    + [data-testid="stElementContainer"] [data-testid="stMultiSelect"] div:has(> input),
  [data-testid="stElementContainer"]:has(.controls-select-narrow)
    + [data-testid="stElementContainer"] div[data-baseweb="select"] > div {{
    max-width: 75% !important;
    width: 75% !important;
  }}
  /* Fitness Pace Range: wider than Show By’s 75% so “Choose options” + chips
     fit; ~90% stays inside the card (avoid 100% / min-width floors that spilled).
     Chips wrap and grow height. Streamlit tags use theme.primary (coral/red)
     — force soft teal + ink. */
  .st-key-insights_pace_bins {{
    max-width: 100% !important;
    min-width: 0 !important;
    box-sizing: border-box !important;
  }}
  /* Beat shared compact 75% (higher specificity). Keep min-width: 0. */
  [data-testid="stColumn"]:has(.controls-panel--compact) .st-key-insights_pace_bins [data-testid="stMultiSelect"],
  [data-testid="column"]:has(.controls-panel--compact) .st-key-insights_pace_bins [data-testid="stMultiSelect"],
  [data-testid="stColumn"]:has(.controls-panel--compact) .st-key-insights_pace_bins [data-testid="stMultiSelect"] div:has(> input),
  [data-testid="column"]:has(.controls-panel--compact) .st-key-insights_pace_bins [data-testid="stMultiSelect"] div:has(> input),
  [data-testid="stColumn"]:has(.controls-panel--compact) .st-key-insights_pace_bins div[data-baseweb="select"] > div,
  [data-testid="column"]:has(.controls-panel--compact) .st-key-insights_pace_bins div[data-baseweb="select"] > div,
  [data-testid="stElementContainer"]:has(.fitness-pace-bins-anchor)
    + [data-testid="stElementContainer"] [data-testid="stMultiSelect"],
  [data-testid="stElementContainer"]:has(.fitness-pace-bins-anchor)
    + [data-testid="stElementContainer"] [data-testid="stMultiSelect"] div:has(> input),
  [data-testid="stElementContainer"]:has(.fitness-pace-bins-anchor)
    + [data-testid="stElementContainer"] div[data-baseweb="select"] > div {{
    max-width: 90% !important;
    width: 90% !important;
    min-width: 0 !important;
    box-sizing: border-box !important;
  }}
  .st-key-insights_pace_bins [data-testid="stMultiSelect"] > div,
  .st-key-insights_pace_bins div[data-baseweb="select"],
  .st-key-insights_pace_bins [data-testid="stMultiSelectTagsContainer"] {{
    box-sizing: border-box !important;
    max-width: 100% !important;
    min-width: 0 !important;
    flex-shrink: 1 !important;
  }}
  .st-key-insights_pace_bins [data-testid="stMultiSelect"] div:has(> input),
  .st-key-insights_pace_bins div[data-baseweb="select"] > div {{
    height: auto !important;
    max-height: none !important;
    min-height: 38px !important;
    align-items: center !important;
    overflow: hidden !important;
  }}
  .st-key-insights_pace_bins [data-testid="stMultiSelectTagsContainer"] {{
    flex-wrap: wrap !important;
    flex-grow: 1 !important;
    flex-shrink: 1 !important;
    flex-basis: 0 !important;
    align-content: flex-start !important;
    min-width: 0 !important;
    min-height: 0 !important;
    overflow-x: hidden !important;
    overflow-y: visible !important;
    max-height: none !important;
    height: auto !important;
    padding-bottom: 0 !important;
  }}
  /* Streamlit’s filter input sits in the tags flex row; with one chip it often
     wraps to a blank second row (tall empty white box). Collapse it when any
     chip is present so single-selection height hugs the chip; multi still wraps. */
  .st-key-insights_pace_bins [data-testid="stMultiSelectTagsContainer"]:has([data-tag]) input {{
    flex: 0 0 0 !important;
    min-width: 0 !important;
    width: 0 !important;
    max-width: 0 !important;
    height: 0 !important;
    min-height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
    overflow: hidden !important;
  }}
  .st-key-insights_pace_bins [data-tag] {{
    background: {PACE_MULTISELECT_CHIP} !important;
    background-color: {PACE_MULTISELECT_CHIP} !important;
    color: {INK} !important;
    -webkit-text-fill-color: {INK} !important;
    min-width: 0 !important;
    flex-shrink: 1 !important;
    max-width: 100% !important;
    padding-top: 0.1rem !important;
    padding-bottom: 0.1rem !important;
    padding-left: 0.35rem !important;
    padding-right: 0.28rem !important;
    overflow: hidden !important;
    text-overflow: clip !important;
  }}
  .st-key-insights_pace_bins [data-tag] span {{
    /* No Streamlit ellipsis; keep full bin text when it fits the control. */
    max-width: none !important;
    overflow: visible !important;
    text-overflow: clip !important;
    white-space: nowrap !important;
    font-size: 0.82rem !important;
  }}
  .st-key-insights_pace_bins [data-tag] span,
  .st-key-insights_pace_bins [data-tag] button,
  .st-key-insights_pace_bins [data-tag] svg {{
    color: {INK} !important;
    -webkit-text-fill-color: {INK} !important;
    fill: {INK} !important;
  }}
  /* Avg HR column: allow shrink so max-content grid cannot inflate the card.
     Avoid overflow:hidden — it clipped SHOWING under Pace Range while LATEST
     ACTIVITY (left) stayed visible. Use clip/visible pairing so horizontal
     spill is cut without forcing a vertical scrollport. */
  [data-testid="stColumn"]:has(.insights-controls-panel)
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2),
  [data-testid="stColumn"]:has(.insights-controls-panel)
    [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2),
  [data-testid="column"]:has(.insights-controls-panel)
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2),
  [data-testid="column"]:has(.insights-controls-panel)
    [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2) {{
    min-width: 0 !important;
    max-width: 100%;
    overflow-x: clip;
    overflow-y: visible;
  }}
  .controls-select-narrow {{
    display: none;
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
  /* Compact controls: meta dividers and labels match narrow select width. */
  [data-testid="stColumn"]:has(.controls-panel--compact) .controls-meta-divider,
  [data-testid="column"]:has(.controls-panel--compact) .controls-meta-divider,
  [data-testid="stColumn"]:has(.controls-panel--compact) .controls-section-label,
  [data-testid="column"]:has(.controls-panel--compact) .controls-section-label,
  [data-testid="stColumn"]:has(.controls-panel--compact) .controls-filter-label,
  [data-testid="column"]:has(.controls-panel--compact) .controls-filter-label,
  [data-testid="stColumn"]:has(.controls-panel--compact) .controls-meta,
  [data-testid="column"]:has(.controls-panel--compact) .controls-meta,
  [data-testid="stColumn"]:has(.controls-panel--compact) .race-date-inputs,
  [data-testid="column"]:has(.controls-panel--compact) .race-date-inputs {{
    width: 75%;
    max-width: 75%;
  }}
  [data-testid="stColumn"]:has(.controls-panel--compact),
  [data-testid="column"]:has(.controls-panel--compact) {{
    width: fit-content !important;
    max-width: 28rem;
    flex: 0 0 auto !important;
    /* Prefer clip over hidden so overflow-y can stay visible (CSS overflow
       pairing); avoids clipping SHOWING / LATEST ACTIVITY at the card bottom. */
    overflow-x: clip;
    overflow-y: visible;
  }}
  [data-testid="stColumn"]:has(.race-controls-panel),
  [data-testid="column"]:has(.race-controls-panel) {{
    max-width: 24rem;
  }}
  /* Fitness Controls: same card language as the rest of the page, tuned so the
     filter card reads as chrome next to the charts — soft top-lit surface,
     teal-tinted hairline, and a little more room around the two filter columns. */
  [data-testid="stColumn"]:has(.insights-controls-panel),
  [data-testid="column"]:has(.insights-controls-panel) {{
    background:
      linear-gradient(
        180deg,
        rgba(255, 255, 255, 0.92) 0%,
        rgba(247, 250, 252, 0.80) 100%
      ) !important;
    border-color: rgba(80, 155, 143, 0.20) !important;
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.75),
      0 10px 30px rgba(21, 32, 40, 0.05) !important;
    padding: 1.2rem 1.35rem 1.3rem !important;
  }}
  /* Inner 2-col row: shrink-wrap columns; divider sits in visual whitespace. */
  [data-testid="stColumn"]:has(.insights-controls-panel) [data-testid="stHorizontalBlock"],
  [data-testid="column"]:has(.insights-controls-panel) [data-testid="stHorizontalBlock"] {{
    display: grid !important;
    grid-template-columns: minmax(0, max-content) minmax(0, max-content) !important;
    width: max-content !important;
    max-width: 100%;
    align-items: stretch !important;
    gap: var(--layout-gap) !important;
  }}
  [data-testid="stColumn"]:has(.insights-controls-panel) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
  [data-testid="stColumn"]:has(.insights-controls-panel) [data-testid="stHorizontalBlock"] > [data-testid="column"],
  [data-testid="column"]:has(.insights-controls-panel) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
  [data-testid="column"]:has(.insights-controls-panel) [data-testid="stHorizontalBlock"] > [data-testid="column"] {{
    width: auto !important;
    min-width: 10.5rem;
    max-width: 100%;
    flex: unset !important;
    align-self: stretch !important;
  }}
  /* Match left-column dead zone: labels/meta use same 75% width as selectboxes. */
  [data-testid="stColumn"]:has(.insights-controls-panel) .controls-section-label,
  [data-testid="column"]:has(.insights-controls-panel) .controls-section-label,
  [data-testid="stColumn"]:has(.insights-controls-panel) .controls-filter-label,
  [data-testid="column"]:has(.insights-controls-panel) .controls-filter-label,
  [data-testid="stColumn"]:has(.insights-controls-panel) .controls-meta,
  [data-testid="column"]:has(.insights-controls-panel) .controls-meta {{
    width: 75%;
    max-width: 75%;
  }}
  /* Performance: side-by-side date pickers */
  [data-testid="stElementContainer"]:has(.race-date-inputs)
    + [data-testid="stElementContainer"] [data-testid="stHorizontalBlock"] {{
    width: 75% !important;
    max-width: 75% !important;
    gap: 0.45rem !important;
  }}
  [data-testid="stElementContainer"]:has(.race-date-inputs)
    + [data-testid="stElementContainer"] [data-testid="stDateInput"] input,
  [data-testid="stElementContainer"]:has(.race-date-inputs)
    + [data-testid="stElementContainer"] [data-testid="stDateInput"] [data-baseweb="input"] {{
    background: {SURFACE} !important;
    border: 1px solid {LINE} !important;
    border-radius: 10px !important;
    min-height: 38px !important;
    box-shadow: none !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    color: {INK} !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
  }}
  [data-testid="stElementContainer"]:has(.race-date-inputs)
    + [data-testid="stElementContainer"] [data-testid="stDateInput"] input:focus-within,
  [data-testid="stElementContainer"]:has(.race-date-inputs)
    + [data-testid="stElementContainer"] [data-testid="stDateInput"] [data-baseweb="input"]:focus-within {{
    border-color: rgba(91, 155, 213, 0.45) !important;
    box-shadow: 0 0 0 3px rgba(91, 155, 213, 0.1) !important;
  }}
  [data-testid="stColumn"]:has(.insights-controls-panel) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1),
  [data-testid="stColumn"]:has(.insights-controls-panel) [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(1),
  [data-testid="column"]:has(.insights-controls-panel) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1),
  [data-testid="column"]:has(.insights-controls-panel) [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(1) {{
    position: relative !important;
  }}
  [data-testid="stColumn"]:has(.insights-controls-panel) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2),
  [data-testid="stColumn"]:has(.insights-controls-panel) [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2),
  [data-testid="column"]:has(.insights-controls-panel) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2),
  [data-testid="column"]:has(.insights-controls-panel) [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2) {{
    border-left: none !important;
    padding-left: 0 !important;
    margin-left: 0 !important;
  }}
  /* Center between 75%-width left content and right column; row height + 0.1rem. */
  [data-testid="stColumn"]:has(.insights-controls-panel) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1)::after,
  [data-testid="stColumn"]:has(.insights-controls-panel) [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(1)::after,
  [data-testid="column"]:has(.insights-controls-panel) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1)::after,
  [data-testid="column"]:has(.insights-controls-panel) [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(1)::after {{
    content: "";
    position: absolute;
    top: 0;
    left: calc(75% + (25% + var(--layout-gap)) / 2);
    width: 1px;
    height: calc(100% + 0.2rem);
    background: {LINE};
    pointer-events: none;
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
  .controls-date-filter {{
    margin-top: 0.15rem;
  }}
  .controls-date-filter .controls-filter-label {{
    margin-bottom: 0.42rem;
  }}
  .race-date-inputs {{
    display: none;
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
    font-family: {FONT_BODY};
    font-size: 1.25rem;
    font-weight: 700;
    color: {INK};
    margin: 0 0 0.25rem 0;
    border-bottom: none !important;
  }}
  .panel-summary {{
    font-size: 0.92rem;
    color: {MUTED};
    margin: 0;
  }}
  /* Page subtitle → controls/KPI row: reliable gap (Streamlit vertical block gap is 0). */
  [data-testid="stElementContainer"]:has(.panel-summary) {{
    margin-bottom: calc(var(--layout-gap) * 1.5) !important;
  }}
  .panel-label {{
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {MUTED};
    margin-bottom: 0.55rem;
  }}
  .shoe-panel-label {{
    display: inline-flex;
    align-items: center;
    gap: 0.28rem;
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
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.75rem;
  }}
  @media (max-width: 900px) {{
    .kpi-grid {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
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
    inset: 0 5% auto 5%;
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
  /* Body text must stay INK. Parent .kpi-label/.kpi-info (and any broad
     muted span rules) are MUTED — without !important, tooltip copy inherits
     that grey and becomes hard to read. Section headers stay muted uppercase. */
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
    color: {INK} !important;
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
  .kpi-info .kpi-tooltip,
  .achievement-badge .kpi-tooltip {{
    color: {INK} !important;
  }}
  .kpi-tooltip strong {{
    display: block;
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: {MUTED} !important;
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
    font-family: {FONT_BODY};
    font-size: 1.55rem;
    font-weight: 700;
    line-height: 1;
    color: var(--accent, {INK});
    margin-top: 0.15rem;
  }}
  .kpi-gauge {{
    width: 7.25rem;
    margin: 0 auto 0.15rem;
  }}
  .kpi-gauge svg {{
    width: 100%;
    height: auto;
    display: block;
  }}
  .gauge-target-tick {{
    stroke: rgba(21, 32, 40, 0.28);
    stroke-width: 5;
    stroke-linecap: round;
  }}
  .kpi-sub {{
    font-size: 0.72rem;
    color: {MUTED};
    margin-top: 0.28rem;
  }}
  .kpi-delta {{
    margin-top: 0.35rem;
    font-size: 0.72rem;
    font-weight: 600;
    color: {INK};
  }}
  .kpi-delta-period {{
    font-weight: 400;
  }}
  .kpi-delta--up,
  .kpi-delta--down,
  .kpi-delta--flat {{
    color: {INK};
  }}
  #kpi-detail,
  .metrics-inspect-anchor {{
    scroll-margin-top: 1.25rem;
    height: 0;
    margin: 0;
    padding: 0;
    overflow: hidden;
  }}
  /* Inspect expander: single label on the gray bar — summary matches .panel-label. */
  [data-testid="stColumn"]:has(.ki-panel)
    [data-testid="stElementContainer"]:has(.metrics-inspect-anchor)
    + [data-testid="stElementContainer"]:has([data-testid="stExpander"]),
  [data-testid="column"]:has(.ki-panel)
    [data-testid="stElementContainer"]:has(.metrics-inspect-anchor)
    + [data-testid="stElementContainer"]:has([data-testid="stExpander"]),
  .st-key-metrics_inspect_ki {{
    margin-top: 0.55rem !important;
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
  }}
  [data-testid="stColumn"]:has(.ki-panel) [data-testid="stExpander"],
  [data-testid="column"]:has(.ki-panel) [data-testid="stExpander"],
  .st-key-metrics_inspect_ki [data-testid="stExpander"],
  .st-key-training_mileage_heatmap [data-testid="stExpander"] {{
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
  }}
  /* Open Inspect / mileage heatmap: compact expander details default paddingTop is 0.5rem.
     Do not leave that (or 0.35rem) in layout when collapsed — it sat below
     the KI card and widened KI → Shoes vs Achievements → KI. */
  [data-testid="stColumn"]:has(.ki-panel) [data-testid="stExpander"] details[open] [data-testid="stExpanderDetails"],
  [data-testid="column"]:has(.ki-panel) [data-testid="stExpander"] details[open] [data-testid="stExpanderDetails"],
  .st-key-metrics_inspect_ki [data-testid="stExpander"] details[open] [data-testid="stExpanderDetails"],
  .st-key-training_mileage_heatmap [data-testid="stExpander"] details[open] [data-testid="stExpanderDetails"] {{
    padding: 0.35rem 0 0 !important;
    border-top: none !important;
  }}
  [data-testid="stColumn"]:has(.ki-panel) [data-testid="stExpander"] details:not([open]) [data-testid="stExpanderDetails"],
  [data-testid="column"]:has(.ki-panel) [data-testid="stExpander"] details:not([open]) [data-testid="stExpanderDetails"],
  .st-key-metrics_inspect_ki [data-testid="stExpander"] details:not([open]) [data-testid="stExpanderDetails"],
  .st-key-training_mileage_heatmap [data-testid="stExpander"] details:not([open]) [data-testid="stExpanderDetails"] {{
    display: none !important;
    padding: 0 !important;
    margin: 0 !important;
    height: 0 !important;
    overflow: hidden !important;
  }}
  /* Compact expander trailing icon is a Material ligature (chevron_right).
     Restyling all summary spans as .panel-label turned that into visible
     "CHEVRON_RIGHT" text overlapping Inspect a KI further — hide the icon instead.
     +/− via summary::before is the expand/collapse cue. */
  [data-testid="stColumn"]:has(.ki-panel) [data-testid="stExpander"] summary [data-testid="stIconMaterial"],
  [data-testid="column"]:has(.ki-panel) [data-testid="stExpander"] summary [data-testid="stIconMaterial"],
  .st-key-metrics_inspect_ki [data-testid="stExpander"] summary [data-testid="stIconMaterial"],
  .st-key-training_mileage_heatmap [data-testid="stExpander"] summary [data-testid="stIconMaterial"] {{
    display: none !important;
  }}
  /* + when collapsed / − when open — Metrics Inspect + Training mileage heatmap. */
  [data-testid="stColumn"]:has(.ki-panel) [data-testid="stExpander"] summary::before,
  [data-testid="column"]:has(.ki-panel) [data-testid="stExpander"] summary::before,
  .st-key-metrics_inspect_ki [data-testid="stExpander"] summary::before,
  .st-key-training_mileage_heatmap [data-testid="stExpander"] summary::before {{
    content: '+';
    display: inline-block;
    margin-right: 0.35em;
    font-family: {FONT_BODY};
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: none;
    color: {MUTED};
    line-height: 1.2;
  }}
  [data-testid="stColumn"]:has(.ki-panel) [data-testid="stExpander"][open] summary::before,
  [data-testid="stColumn"]:has(.ki-panel) [data-testid="stExpander"] details[open] summary::before,
  [data-testid="column"]:has(.ki-panel) [data-testid="stExpander"][open] summary::before,
  [data-testid="column"]:has(.ki-panel) [data-testid="stExpander"] details[open] summary::before,
  .st-key-metrics_inspect_ki [data-testid="stExpander"][open] summary::before,
  .st-key-metrics_inspect_ki [data-testid="stExpander"] details[open] summary::before,
  .st-key-training_mileage_heatmap [data-testid="stExpander"][open] summary::before,
  .st-key-training_mileage_heatmap [data-testid="stExpander"] details[open] summary::before {{
    content: '−';
  }}
  /* Match .panel-label on expander summary label only (not icon spans). */
  [data-testid="stColumn"]:has(.ki-panel) [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"],
  [data-testid="stColumn"]:has(.ki-panel) [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] p,
  [data-testid="stColumn"]:has(.ki-panel) [data-testid="stExpander"] summary p,
  [data-testid="column"]:has(.ki-panel) [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"],
  [data-testid="column"]:has(.ki-panel) [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] p,
  [data-testid="column"]:has(.ki-panel) [data-testid="stExpander"] summary p,
  .st-key-metrics_inspect_ki [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"],
  .st-key-metrics_inspect_ki [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] p,
  .st-key-metrics_inspect_ki [data-testid="stExpander"] summary p,
  .st-key-training_mileage_heatmap [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"],
  .st-key-training_mileage_heatmap [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] p,
  .st-key-training_mileage_heatmap [data-testid="stExpander"] summary p {{
    font-family: {FONT_BODY} !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    color: {MUTED} !important;
    line-height: 1.2 !important;
    margin: 0 !important;
  }}
  /* Compact inspect select: short width + smaller text/height.
     Scoped via .metrics-inspect-select marker — do not style global selects. */
  .metrics-inspect-select {{
    display: none;
  }}
  [data-testid="stElementContainer"]:has(.metrics-inspect-select)
    + [data-testid="stElementContainer"] [data-testid="stSelectbox"],
  [data-testid="stElementContainer"]:has(.metrics-inspect-select)
    + [data-testid="stElementContainer"] [data-testid="stSelectbox"] div:has(> input),
  [data-testid="stElementContainer"]:has(.metrics-inspect-select)
    + [data-testid="stElementContainer"] div[data-baseweb="select"] > div {{
    max-width: 16rem !important;
    width: 100% !important;
  }}
  [data-testid="stElementContainer"]:has(.metrics-inspect-select)
    + [data-testid="stElementContainer"] [data-testid="stSelectbox"] div:has(> input),
  [data-testid="stElementContainer"]:has(.metrics-inspect-select)
    + [data-testid="stElementContainer"] div[data-baseweb="select"] > div {{
    min-height: 2rem !important;
    border-radius: 10px !important;
  }}
  [data-testid="stElementContainer"]:has(.metrics-inspect-select)
    + [data-testid="stElementContainer"] [data-testid="stSelectbox"] input,
  [data-testid="stElementContainer"]:has(.metrics-inspect-select)
    + [data-testid="stElementContainer"] div[data-baseweb="select"] span {{
    font-size: 0.82rem !important;
    font-weight: 500 !important;
  }}
  /* Detail copy must keep document flow above the dataframe. KI-panel rules
     zero every stElementContainer margin/gap; without reserved space the
     white dataframe paints over the comparison line. */
  .kpi-detail-panel {{
    margin-top: 0.65rem;
    padding-bottom: 0.15rem;
    overflow: visible;
    position: relative;
    z-index: 1;
  }}
  .kpi-detail-after {{
    height: 1.25rem;
    line-height: 0;
    margin: 0;
    padding: 0;
  }}
  .kpi-detail-meta {{
    font-size: 0.78rem;
    color: {MUTED};
    margin: 0 0 0.35rem;
  }}
  .kpi-detail-insight {{
    font-size: 0.92rem;
    color: {INK};
    margin: 0 0 0.25rem;
  }}
  .kpi-detail-comparison {{
    font-size: 0.84rem;
    color: {MUTED};
    margin: 0;
    line-height: 1.35;
  }}
  /* Restore spacing after detail markdown → table (overrides ki-panel zeros). */
  [data-testid="stColumn"]:has(.ki-panel)
    [data-testid="stElementContainer"]:has(.kpi-detail-panel)
    + [data-testid="stElementContainer"]:has([data-testid="stDataFrame"]),
  [data-testid="column"]:has(.ki-panel)
    [data-testid="stElementContainer"]:has(.kpi-detail-panel)
    + [data-testid="stElementContainer"]:has([data-testid="stDataFrame"]),
  .st-key-metrics_inspect_ki
    [data-testid="stElementContainer"]:has(.kpi-detail-panel)
    + [data-testid="stElementContainer"]:has([data-testid="stDataFrame"]),
  [data-testid="stColumn"]:has(.ki-panel)
    [data-testid="stElementContainer"]:has(.kpi-detail-panel)
    + [data-testid="stElementContainer"]:has(.race-results-empty),
  [data-testid="column"]:has(.ki-panel)
    [data-testid="stElementContainer"]:has(.kpi-detail-panel)
    + [data-testid="stElementContainer"]:has(.race-results-empty),
  .st-key-metrics_inspect_ki
    [data-testid="stElementContainer"]:has(.kpi-detail-panel)
    + [data-testid="stElementContainer"]:has(.race-results-empty) {{
    margin-top: 0.25rem !important;
  }}

  .achievement-grid {{
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 0.55rem 0.4rem;
    justify-items: center;
    width: 100%;
    overflow: visible;
  }}
  @media (max-width: 900px) {{
    .achievement-grid {{
      grid-template-columns: repeat(auto-fit, minmax(9.5rem, 1fr));
    }}
  }}
  .achievement-badge {{
    --achievement-accent: {EASY};
    --achievement-ring: rgba(91, 155, 213, 0.22);
    --achievement-fill: rgba(91, 155, 213, 0.10);
    --achievement-border: rgba(91, 155, 213, 0.38);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.45rem;
    width: 100%;
    max-width: 9.5rem;
    text-align: center;
    position: relative;
    overflow: visible;
  }}
  .achievement-badge--tip {{
    cursor: help;
  }}
  .achievement-badge:hover,
  .achievement-badge:focus-within {{
    z-index: 40;
    outline: none;
  }}
  .achievement-badge .kpi-tooltip {{
    z-index: 50;
  }}
  .achievement-badge:hover .kpi-tooltip,
  .achievement-badge:focus-within .kpi-tooltip {{
    visibility: visible;
    opacity: 1;
  }}
  .achievement-badge--miles {{
    --achievement-accent: {EASY};
    --achievement-ring: rgba(91, 155, 213, 0.22);
    --achievement-fill: rgba(91, 155, 213, 0.10);
    --achievement-border: rgba(91, 155, 213, 0.38);
  }}
  .achievement-badge--elevation {{
    --achievement-accent: {ELEVATION_PURPLE};
    --achievement-ring: rgba(111, 95, 141, 0.22);
    --achievement-fill: rgba(111, 95, 141, 0.10);
    --achievement-border: rgba(111, 95, 141, 0.38);
  }}
  .achievement-badge--week {{
    --achievement-accent: {TRAFFIC_LIME};
    --achievement-ring: rgba(153, 193, 64, 0.26);
    --achievement-fill: rgba(153, 193, 64, 0.11);
    --achievement-border: rgba(153, 193, 64, 0.42);
  }}
  .achievement-badge--longest {{
    --achievement-accent: {HARD};
    --achievement-ring: rgba(230, 126, 34, 0.22);
    --achievement-fill: rgba(230, 126, 34, 0.10);
    --achievement-border: rgba(230, 126, 34, 0.40);
  }}
  .achievement-badge--peak {{
    --achievement-accent: {TRAFFIC_YELLOW};
    --achievement-ring: rgba(231, 180, 22, 0.24);
    --achievement-fill: rgba(231, 180, 22, 0.10);
    --achievement-border: rgba(231, 180, 22, 0.42);
  }}
  .achievement-medal {{
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.32rem;
    width: 9.25rem;
    height: 9.25rem;
    border-radius: 50%;
    background:
      radial-gradient(
        circle at 32% 28%,
        #ffffff 0%,
        {SURFACE} 40%,
        var(--achievement-fill) 100%
      );
    border: 2px solid var(--achievement-border);
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.85),
      inset 0 -1px 0 rgba(21, 32, 40, 0.05),
      0 0 0 4px var(--achievement-ring),
      0 8px 18px rgba(21, 32, 40, 0.06);
  }}
  .achievement-medal::before {{
    content: "";
    position: absolute;
    inset: 9px;
    border-radius: 50%;
    border: 1px solid var(--achievement-ring);
    pointer-events: none;
  }}
  .achievement-icon {{
    position: relative;
    z-index: 1;
    font-size: 1.5rem;
    line-height: 1;
    margin-top: -0.15rem;
  }}
  .achievement-value {{
    position: relative;
    z-index: 1;
    font-family: {FONT_BODY};
    font-size: clamp(1.05rem, 1.7vw, 1.32rem);
    font-weight: 700;
    line-height: 1.15;
    color: {INK};
    max-width: 7.5rem;
    word-break: break-word;
    text-align: center;
  }}
  .achievement-caption {{
    display: flex;
    flex-direction: column;
    gap: 0.18rem;
    min-height: 2.4rem;
  }}
  .achievement-label {{
    font-size: 0.8rem;
    font-weight: 600;
    color: {INK};
    letter-spacing: 0.01em;
    line-height: 1.25;
  }}
  .achievement-sub {{
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: {MUTED};
  }}

  .shoe-kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(9.5rem, 1fr));
    gap: 0.75rem;
  }}
  .shoe-kpi-card {{
    background: {CARD};
    border: 1px solid transparent;
    border-radius: 16px;
    padding: 1rem 0.75rem 0.85rem;
    text-align: center;
    position: relative;
    overflow: visible;
  }}
  .shoe-kpi-card::before {{
    content: "";
    position: absolute;
    inset: 0 5% auto 5%;
    height: 3px;
    background: var(--accent, {MILES});
  }}
  .shoe-kpi-card.is-retired {{
    opacity: 0.72;
  }}
  .shoe-kpi-name {{
    font-size: 0.78rem;
    font-weight: 500;
    color: {MUTED};
    margin-bottom: 0.35rem;
    min-height: 2.1em;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .shoe-gauge {{
    width: 7.25rem;
    margin: 0 auto 0.15rem;
  }}
  .shoe-gauge svg {{
    width: 100%;
    height: auto;
    display: block;
  }}
  .shoe-kpi-value {{
    font-family: {FONT_BODY};
    font-size: 1.55rem;
    font-weight: 700;
    line-height: 1;
    color: var(--accent, {INK});
    margin-top: 0.15rem;
  }}
  .shoe-kpi-sub {{
    font-size: 0.72rem;
    color: {MUTED};
    margin-top: 0.28rem;
  }}
  .shoe-kpi-type {{
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: {MUTED};
    margin-top: 0.35rem;
  }}

  .fastest-race-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(9.5rem, 1fr));
    gap: 0.75rem;
  }}
  .fastest-race-card {{
    background: {CARD};
    border: 1px solid transparent;
    border-radius: 16px;
    padding: 1rem 0.75rem 0.9rem;
    text-align: center;
    position: relative;
    overflow: hidden;
  }}
  .fastest-race-card::before {{
    content: "";
    position: absolute;
    inset: 0 5% auto 5%;
    height: 3px;
    background: var(--accent, {MILES});
  }}
  .fastest-race-type {{
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: {MUTED};
    margin-bottom: 0.4rem;
  }}
  .fastest-race-time {{
    font-family: {FONT_BODY};
    font-size: 1.45rem;
    font-weight: 700;
    line-height: 1.05;
    color: var(--accent, {INK});
  }}
  .fastest-race-name {{
    font-size: 0.78rem;
    font-weight: 500;
    color: {INK};
    margin-top: 0.45rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .fastest-race-meta {{
    font-size: 0.7rem;
    color: {MUTED};
    margin-top: 0.28rem;
    line-height: 1.35;
  }}
  .fastest-race-meta-sep {{
    margin: 0 0.28rem;
  }}

  /* Selectbox polish — Streamlit 1.61+ dropped BaseWeb select.
     Controls use theme.secondaryBg; under a dark OS/theme that reads as a
     black pill on our light page CSS. Force light chrome + readable ink on
     the control and the virtual dropdown popover. Keep BaseWeb fallback. */
  [data-testid="stSelectbox"] div:has(> input),
  [data-testid="stMultiSelect"] div:has(> input),
  div[data-baseweb="select"] > div {{
    background: {CARD} !important;
    background-color: {CARD} !important;
    border-color: {LINE} !important;
    border-radius: 12px !important;
    color: {INK} !important;
  }}
  [data-testid="stSelectbox"] input,
  [data-testid="stMultiSelect"] input {{
    color: {INK} !important;
    -webkit-text-fill-color: {INK} !important;
    background: transparent !important;
  }}
  [data-testid="stSelectboxVirtualDropdown"],
  [data-testid="stMultiSelectVirtualDropdown"] {{
    background: {CARD} !important;
    background-color: {CARD} !important;
    color: {INK} !important;
    border: 1px solid {LINE} !important;
    border-radius: 12px !important;
  }}
  /* Ink on options only — leave option background alone so hover/focus still tint. */
  [data-testid="stSelectboxVirtualDropdown"] [data-option-value],
  [data-testid="stSelectboxVirtualDropdown"] [role="option"],
  [data-testid="stSelectboxVirtualDropdown"] li,
  [data-testid="stMultiSelectVirtualDropdown"] [data-option-value],
  [data-testid="stMultiSelectVirtualDropdown"] [role="option"],
  [data-testid="stMultiSelectVirtualDropdown"] li {{
    color: {INK} !important;
  }}
  label[data-testid="stWidgetLabel"] p {{
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: {MUTED} !important;
  }}

  .chart-section-title {{
    font-family: {FONT_BODY};
    font-size: {CHART_TITLE_SIZE_PX}px;
    font-weight: {CHART_TITLE_FONT_WEIGHT};
    color: {INK};
    margin: 0 0 0.55rem 0;
  }}
  .race-results-empty {{
    background: rgba(255, 255, 255, 0.78);
    border: 1px dashed rgba(21, 32, 40, 0.08);
    border-radius: 20px;
    padding: 1.5rem 1.25rem;
    text-align: center;
    color: {MUTED};
    font-size: 0.92rem;
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
