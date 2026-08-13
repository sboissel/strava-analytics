"""Shared KPI and sidebar UI helpers for the Runner's Dashboard."""

from __future__ import annotations

import html
import math

from charts import compliance_title, heatmap_title, mileage_title, pace_hr_title
from data import format_full_date
from theme import (
    TRAFFIC_GREEN,
    TRAFFIC_LIME,
    TRAFFIC_ORANGE,
    TRAFFIC_RED,
    TRAFFIC_YELLOW,
    EASY_TARGET_FRAC,
    GAUGE_TARGET_PROGRESS,
    LONGEST_RUN_GAUGE_MAX,
    LONGEST_RUN_GOAL,
    MILES_GAUGE_MAX,
    SHOE_MILEAGE_GOAL,
    WEEKLY_MILES_GOAL,
    eh_color,
    longest_run_color,
    miles_color,
    miles_legend_labels,
    shoe_wear_color,
)


def band_dot(color_hex: str) -> str:
    """Return HTML for a small colored circle in KPI tooltips.

    Parameters
    ----------
    color_hex : str
        CSS hex color for the dot.

    Returns
    -------
    str
        HTML ``span`` element markup for the colored dot.
    """
    return f'<span class="band-dot" style="background:{color_hex}"></span>'


def eh_kpi_tooltip(period: str) -> str:
    """Return tooltip HTML for easy:hard KPI cards.

    Parameters
    ----------
    period : str
        Window identifier, either ``"week"`` or ``"month"``.

    Returns
    -------
    str
        HTML tooltip body describing the ratio definition and target bands.

    Raises
    ------
    KeyError
        If ``period`` is not ``"week"`` or ``"month"``.
    """
    period_desc = {
        "week": "the last full Mon–Sun week",
        "month": "the last 30 days",
    }[period]
    return (
        "<strong>Definition</strong>"
        f"Easy:hard time ratio from heart-rate zones for {period_desc}."
        "<br><br>"
        "<strong>Target</strong>"
        "~80% easy (80:20)"
        "<br><br>"
        "<strong>Target Bands</strong>"
        f"{band_dot(TRAFFIC_GREEN)}≥85% easy"
        f"<br>{band_dot(TRAFFIC_LIME)}≥75%"
        f"<br>{band_dot(TRAFFIC_YELLOW)}≥65%"
        f"<br>{band_dot(TRAFFIC_ORANGE)}≥55%"
        f"<br>{band_dot(TRAFFIC_RED)}below 55%"
    )


def miles_kpi_tooltip() -> str:
    """Return tooltip HTML for the weekly mileage KPI card.

    Returns
    -------
    str
        HTML tooltip body describing mileage definition and target bands.
    """
    band_lines = "<br>".join(
        f"{band_dot(color)}{html.escape(label)}"
        for color, label in reversed(miles_legend_labels("Week"))
    )
    return (
        "<strong>Definition</strong>"
        "Total run mileage for the last full Mon–Sun week."
        "<br><br>"
        "<strong>Target</strong>"
        f"~{WEEKLY_MILES_GOAL:.0f} mi/week."
        "<br><br>"
        "<strong>Target Bands</strong>"
        f"{band_lines}"
    )


def longest_run_kpi_tooltip(goal: float = LONGEST_RUN_GOAL) -> str:
    """Return tooltip HTML for the longest-run KPI card."""
    return (
        "<strong>Definition</strong>"
        "Longest single run distance in the last 30 days."
        "<br><br>"
        "<strong>Target</strong>"
        f"At least {goal:.0f} mi."
        "<br><br>"
        "<strong>Target Bands</strong>"
        f"{band_dot(TRAFFIC_GREEN)}≥{goal:.0f} mi"
        f"<br>{band_dot(TRAFFIC_LIME)}≥{goal * 0.8:.0f} mi"
        f"<br>{band_dot(TRAFFIC_YELLOW)}≥{goal * 0.6:.0f} mi"
        f"<br>{band_dot(TRAFFIC_ORANGE)}≥{goal * 0.4:.0f} mi"
        f"<br>{band_dot(TRAFFIC_RED)}below {goal * 0.4:.0f} mi"
    )


def kpi_label_html(label: str, tooltip: str) -> str:
    """Render a KPI label with a muted info icon and hover tooltip.

    Parameters
    ----------
    label : str
        Visible KPI label text.
    tooltip : str
        HTML tooltip body shown on hover.

    Returns
    -------
    str
        HTML markup for the KPI label row.
    """
    safe_label = html.escape(label)
    return (
        f'<div class="kpi-label">'
        f"<span>{safe_label}</span>"
        f'<span class="kpi-info" tabindex="0" role="button" '
        f'aria-label="About {safe_label}">'
        f'<span aria-hidden="true">ⓘ</span>'
        f'<span class="kpi-tooltip" role="tooltip">{tooltip}</span>'
        f"</span></div>"
    )


def _gauge_svg(
    progress: float, color: str, *, target_progress: float | None = None
) -> str:
    """Semicircle gauge filled to ``progress`` (0–1) using ``color``.

    When ``target_progress`` is set (0–1), a short radial tick marks that
    position on the arc (distinct from the progress fill).
    """
    capped = max(0.0, min(float(progress), 1.0))
    filled = round(capped * 100, 1)
    cx, cy, r = 60.0, 60.0, 48.0
    tick = ""
    if target_progress is not None:
        t = max(0.0, min(float(target_progress), 1.0))
        # Arc runs left→right (π→0) as progress goes 0→1.
        theta = math.pi * (1.0 - t)
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        # Radial tick across the 10px track (~20% past track edges); color/weight via CSS.
        inner, outer = r - 6.0, r + 6.0
        x1, y1 = cx + inner * cos_t, cy - inner * sin_t
        x2, y2 = cx + outer * cos_t, cy - outer * sin_t
        tick = (
            f'<line class="gauge-target-tick" '
            f'x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}"/>'
        )
    return (
        '<svg viewBox="0 0 120 70" aria-hidden="true">'
        '<path d="M 12 60 A 48 48 0 0 1 108 60" fill="none" '
        'stroke="rgba(21, 32, 40, 0.10)" stroke-width="10" stroke-linecap="round"/>'
        '<path d="M 12 60 A 48 48 0 0 1 108 60" fill="none" '
        f'stroke="{html.escape(color)}" stroke-width="10" stroke-linecap="round" '
        f'pathLength="100" stroke-dasharray="{filled} 100"/>'
        f"{tick}"
        "</svg>"
    )


def _kpi_delta_html(delta: str | None) -> str:
    if not delta:
        return ""
    kind = "flat"
    if delta.startswith("↑"):
        kind = "up"
    elif delta.startswith("↓"):
        kind = "down"
    vs_idx = delta.find(" vs ")
    if vs_idx != -1:
        change = html.escape(delta[:vs_idx])
        period = html.escape(delta[vs_idx + 1 :].lstrip())
        inner = f'{change} <span class="kpi-delta-period">{period}</span>'
    else:
        inner = html.escape(delta)
    return f'<div class="kpi-delta kpi-delta--{kind}">{inner}</div>'


def _kpi_gauge_card(
    *,
    label: str,
    tooltip: str,
    value: str,
    sub: str,
    progress: float,
    accent: str,
    delta: str | None = None,
    target_progress: float | None = None,
) -> str:
    """One Key Indicators gauge card."""
    return (
        f'<div class="kpi-card" style="--accent:{accent}">'
        f"{kpi_label_html(label, tooltip)}"
        f'<div class="kpi-gauge">'
        f"{_gauge_svg(progress, accent, target_progress=target_progress)}"
        f"</div>"
        f'<div class="kpi-value">{html.escape(value)}</div>'
        f'<div class="kpi-sub">{html.escape(sub)}</div>'
        f"{_kpi_delta_html(delta)}"
        "</div>"
    )


def key_indicators_html(
    indicators: dict[str, object],
    *,
    comparisons: dict[str, str | None] | None = None,
    wrap_panel: bool = True,
) -> str:
    """Render Key Indicators as semicircle gauge cards.

    Parameters
    ----------
    wrap_panel :
        When False, omit the outer ``.panel`` chrome so the Metrics page can
        nest gauges + Inspect inside a Streamlit column painted as one panel.
    """
    comparisons = comparisons or {}
    eh_week, eh_week_pct = indicators["eh_last_week"]  # type: ignore[misc]
    eh_month, eh_month_pct = indicators["eh_last_month"]  # type: ignore[misc]
    miles_week = float(indicators["miles_last_week"] or 0.0)  # type: ignore[arg-type]
    longest_run = indicators["longest_run_30d"]

    easy_target_pct = EASY_TARGET_FRAC * 100.0
    week_pct = None if eh_week_pct is None else float(eh_week_pct)
    month_pct = None if eh_month_pct is None else float(eh_month_pct)
    longest = None if longest_run is None else float(longest_run)  # type: ignore[arg-type]

    week_accent = eh_color(week_pct)
    month_accent = eh_color(month_pct)
    miles_accent = miles_color(miles_week, grain="Week")
    longest_accent = longest_run_color(longest)

    # Scale maxima so real targets land at GAUGE_TARGET_PROGRESS (80% of arc).
    eh_gauge_max = 100.0

    cards = [
        _kpi_gauge_card(
            label="Easy:Hard Last Week",
            tooltip=eh_kpi_tooltip("week"),
            value=str(eh_week),
            sub=f"target {round(easy_target_pct)}:{round(100 - easy_target_pct)}",
            progress=0.0 if week_pct is None else week_pct / eh_gauge_max,
            target_progress=GAUGE_TARGET_PROGRESS,
            accent=week_accent,
            delta=comparisons.get("eh_week"),
        ),
        _kpi_gauge_card(
            label="Easy:Hard 30 Days",
            tooltip=eh_kpi_tooltip("month"),
            value=str(eh_month),
            sub=f"target {round(easy_target_pct)}:{round(100 - easy_target_pct)}",
            progress=0.0 if month_pct is None else month_pct / eh_gauge_max,
            target_progress=GAUGE_TARGET_PROGRESS,
            accent=month_accent,
            delta=comparisons.get("eh_month"),
        ),
        _kpi_gauge_card(
            label="Miles Last Week",
            tooltip=miles_kpi_tooltip(),
            value=f"{miles_week:.2f}",
            sub=f"of {WEEKLY_MILES_GOAL:.0f} mi",
            progress=miles_week / MILES_GAUGE_MAX,
            target_progress=GAUGE_TARGET_PROGRESS,
            accent=miles_accent,
            delta=comparisons.get("miles_week"),
        ),
        _kpi_gauge_card(
            label="Longest Run 30 Days",
            tooltip=longest_run_kpi_tooltip(),
            value="—" if longest is None else f"{longest:.2f}",
            sub=f"of {LONGEST_RUN_GOAL:.0f} mi",
            progress=(
                0.0 if longest is None else longest / LONGEST_RUN_GAUGE_MAX
            ),
            target_progress=GAUGE_TARGET_PROGRESS,
            accent=longest_accent,
            delta=comparisons.get("longest_run"),
        ),
    ]

    body = (
        '<div class="panel-label">Key Indicators</div>'
        f'<div class="kpi-grid">{"".join(cards)}</div>'
    )
    if wrap_panel:
        return f'<div class="panel" id="key-indicators">{body}</div>'
    return f'<div id="key-indicators">{body}</div>'


def metrics_inspect_anchor_html() -> str:
    """Scroll target for the Metrics section nav ``Inspect`` link.

    The visible Inspect title lives on the expander summary, styled as
    ``.panel-label`` in CSS — this helper is an invisible anchor only.
    """
    return (
        '<div id="kpi-detail" class="metrics-inspect-anchor" aria-hidden="true"></div>'
    )


def render_kpi_detail_panel(detail: dict[str, object]) -> None:
    """Render the selected KPI drill-down inside the Metrics inspect expander."""
    import streamlit as st

    title = str(detail.get("title") or "Detail")
    window_label = str(detail.get("window_label") or "")
    comparison = str(detail.get("comparison") or "")
    insight = str(detail.get("insight") or "")
    table = detail.get("table")
    empty_message = str(detail.get("empty_message") or "No data.")

    # No nested .panel — Inspect lives inside the painted KI column already.
    # Compact HTML (no indented markdown block) so Streamlit doesn't mangle
    # height; spacer reserves space before the dataframe under ki-panel zeros.
    st.markdown(
        (
            '<div class="kpi-detail-panel">'
            f'<div class="panel-label">Inspect · {html.escape(title)}</div>'
            f'<div class="kpi-detail-meta">{html.escape(window_label)}</div>'
            f'<div class="kpi-detail-insight">{html.escape(insight)}</div>'
            f'<div class="kpi-detail-comparison">{html.escape(comparison)}</div>'
            '<div class="kpi-detail-after" aria-hidden="true"></div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    if table is None or getattr(table, "empty", True):
        st.markdown(
            f'<div class="race-results-empty">{html.escape(empty_message)}</div>',
            unsafe_allow_html=True,
        )
        return

    column_config = {}
    if "Date" in table.columns:
        column_config["Date"] = st.column_config.DateColumn("Date", format="MMM D, YYYY")
    if "Miles" in table.columns:
        column_config["Miles"] = st.column_config.NumberColumn("Miles", format="%.2f")
    if "Easy min" in table.columns:
        column_config["Easy min"] = st.column_config.NumberColumn("Easy min", format="%.1f")
    if "Hard min" in table.columns:
        column_config["Hard min"] = st.column_config.NumberColumn("Hard min", format="%.1f")
    if "% Easy" in table.columns:
        column_config["% Easy"] = st.column_config.NumberColumn("% Easy", format="%.1f")

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config=column_config or None,
    )


def _format_achievement_miles(value: float | None, *, large: bool = False) -> str:
    """Format a mileage value with unit, or an em dash when missing."""
    if value is None:
        return "—"
    if large:
        if abs(value) >= 100:
            return f"{value:,.0f} mi"
        if abs(value) >= 10:
            return f"{value:,.1f} mi"
        return f"{value:,.2f} mi"
    return f"{value:,.2f} mi"


def _format_achievement_feet(value: float | None) -> str:
    """Format an elevation value in feet, or an em dash when missing."""
    if value is None:
        return "—"
    if abs(value) >= 100:
        return f"{value:,.0f} ft"
    if abs(value) >= 10:
        return f"{value:,.1f} ft"
    return f"{value:,.2f} ft"


def _format_achievement_month(value: object | None) -> str:
    """Format a timestamp as ``MON YYYY``, or an em dash when missing."""
    if value is None:
        return "—"
    strftime = getattr(value, "strftime", None)
    if strftime is None:
        return "—"
    try:
        # pandas.NaT raises ValueError on strftime
        return strftime("%b %Y").upper()
    except (TypeError, ValueError):
        return "—"


def _format_short_month_day(value: object) -> str:
    """Format a timestamp as ``Apr 24``."""
    strftime = getattr(value, "strftime", None)
    if strftime is None:
        return ""
    try:
        return f"{strftime('%b')} {value.day}"
    except (TypeError, ValueError, AttributeError):
        return ""


def _format_week_span(start: object, end: object) -> str:
    """Format an ISO week Mon–Sun span such as ``Apr 24–30, 2017``."""
    start_md = _format_short_month_day(start)
    end_md = _format_short_month_day(end)
    if not start_md or not end_md:
        return ""
    start_year = getattr(start, "year", None)
    end_year = getattr(end, "year", None)
    start_month = getattr(start, "month", None)
    end_month = getattr(end, "month", None)
    if start_year is None or end_year is None:
        return f"{start_md}–{end_md}"
    if start_year != end_year:
        return f"{start_md}, {start_year}–{end_md}, {end_year}"
    if start_month != end_month:
        return f"{start_md}–{end_md}, {start_year}"
    end_day = getattr(end, "day", None)
    start_strftime = getattr(start, "strftime", None)
    if end_day is None or start_strftime is None:
        return f"{start_md}–{end_md}, {start_year}"
    return f"{start_strftime('%b')} {start.day}–{end_day}, {start_year}"


def _totals_achievement_tooltip(
    all_time: object | None,
    this_year_value: object | None,
    year: object | None,
) -> str | None:
    """Build KPI-style hover tooltip HTML for all-time + this-year totals."""
    if all_time is None:
        return None
    body = (
        "<strong>All-time</strong>"
        f"{html.escape(_format_achievement_miles(float(all_time), large=True))}"
    )
    if year is not None and this_year_value is not None:
        body += (
            f"<br><strong>This year ({html.escape(str(int(year)))})</strong>"
            f"{html.escape(_format_achievement_miles(float(this_year_value), large=True))}"
        )
    return body


def _run_achievement_tooltip(
    name: object | None,
    date: object | None,
) -> str | None:
    """Build KPI-style hover tooltip HTML for a single-run achievement badge."""
    name_text = ""
    if name is not None:
        name_text = str(name).strip()
    date_text = ""
    if date is not None:
        try:
            date_text = format_full_date(date)
        except (TypeError, ValueError):
            date_text = ""
    if not name_text and not date_text:
        return None
    if name_text and date_text:
        return (
            f"<strong>{html.escape(name_text)}</strong>"
            f"{html.escape(date_text)}"
        )
    return html.escape(name_text or date_text)


def _best_week_tooltip(achievements: dict) -> str | None:
    """Build KPI-style hover tooltip HTML for the best-week badge."""
    miles = achievements.get("best_week_miles")
    start = achievements.get("best_week_date")
    end = achievements.get("best_week_end")
    runs = achievements.get("best_week_runs") or []
    if miles is None or start is None or end is None:
        return None
    span = _format_week_span(start, end)
    if not span:
        return None
    body = (
        f"<strong>Week of {html.escape(span)}</strong>"
        f"{html.escape(f'{float(miles):,.2f} mi')}"
    )
    for run in runs:
        run_name = (run.get("name") or "Untitled").strip() or "Untitled"
        run_date = run.get("date")
        run_miles = run.get("miles")
        date_part = ""
        if run_date is not None:
            short = _format_short_month_day(run_date)
            if short:
                date_part = f" ({short})"
        miles_part = (
            f"{float(run_miles):,.2f} mi" if run_miles is not None else "—"
        )
        body += f"<br>{html.escape(f'{run_name}{date_part}: {miles_part}')}"
    return body


def _achievement_badge(
    icon: str,
    label: str,
    value: str,
    sub: str,
    accent: str,
    tooltip: str | None = None,
) -> str:
    """Return HTML for one circular achievement badge."""
    safe_label = html.escape(label)
    safe_value = html.escape(value)
    safe_sub = html.escape(sub)
    safe_accent = html.escape(accent)
    tip_class = " achievement-badge--tip" if tooltip else ""
    focus_attr = ' tabindex="0"' if tooltip else ""
    tooltip_html = (
        f'<span class="kpi-tooltip" role="tooltip">{tooltip}</span>'
        if tooltip
        else ""
    )
    return (
        f'<div class="achievement-badge achievement-badge--{safe_accent}'
        f'{tip_class}"{focus_attr}>'
        f'<div class="achievement-medal" aria-hidden="true">'
        f'<span class="achievement-icon">{icon}</span>'
        f'<span class="achievement-value">{safe_value}</span>'
        f"</div>"
        f"{tooltip_html}"
        f'<div class="achievement-caption">'
        f'<div class="achievement-label">{safe_label}</div>'
        f'<div class="achievement-sub">{safe_sub}</div>'
        f"</div>"
        "</div>"
    )


def achievements_html(achievements: dict) -> str:
    """Render all-time Achievements as a five-badge panel.

    Parameters
    ----------
    achievements : dict
        Output of ``lifetime_achievements`` with total miles, elevation miles,
        this-year miles / elevation (UTC calendar year of the latest activity),
        best week (miles + dates + runs), longest run (miles + date + name),
        and most elevation in a run (feet + date + name).

    Returns
    -------
    str
        HTML markup for the Achievements panel.
    """
    total_miles = achievements.get("total_miles")
    elevation = achievements.get("total_elevation_miles")
    best_week = achievements.get("best_week_miles")
    best_week_date = achievements.get("best_week_date")
    longest = achievements.get("longest_run_miles")
    longest_date = achievements.get("longest_run_date")
    most_elev = achievements.get("most_elevation_ft")
    most_elev_date = achievements.get("most_elevation_date")

    badges = [
        _achievement_badge(
            "🏃",
            "Total Miles",
            _format_achievement_miles(
                None if total_miles is None else float(total_miles), large=True
            ),
            "ALL-TIME",
            "miles",
            tooltip=_totals_achievement_tooltip(
                total_miles,
                achievements.get("this_year_miles"),
                achievements.get("this_year"),
            ),
        ),
        _achievement_badge(
            "⛰",
            "Total Elevation",
            _format_achievement_miles(
                None if elevation is None else float(elevation), large=True
            ),
            "ALL-TIME",
            "elevation",
            tooltip=_totals_achievement_tooltip(
                elevation,
                achievements.get("this_year_elevation_miles"),
                achievements.get("this_year"),
            ),
        ),
        _achievement_badge(
            "↗",
            "Most Miles in a Week",
            _format_achievement_miles(
                None if best_week is None else float(best_week)
            ),
            _format_achievement_month(best_week_date),
            "week",
            tooltip=_best_week_tooltip(achievements),
        ),
        _achievement_badge(
            "🏅",
            "Longest Run",
            _format_achievement_miles(
                None if longest is None else float(longest)
            ),
            _format_achievement_month(longest_date),
            "longest",
            tooltip=_run_achievement_tooltip(
                achievements.get("longest_run_name"),
                longest_date,
            ),
        ),
        _achievement_badge(
            "🔺",
            "Most Elevation in a Run",
            _format_achievement_feet(
                None if most_elev is None else float(most_elev)
            ),
            _format_achievement_month(most_elev_date),
            "peak",
            tooltip=_run_achievement_tooltip(
                achievements.get("most_elevation_name"),
                most_elev_date,
            ),
        ),
    ]

    return (
        '<div class="panel" id="achievements">'
        '<div class="panel-label">Achievements</div>'
        f'<div class="achievement-grid">{"".join(badges)}</div>'
        "</div>"
    )


def shoe_kpi_tooltip(goal: float = SHOE_MILEAGE_GOAL) -> str:
    """Return tooltip HTML for shoe mileage gauge cards."""
    return (
        "<strong>Definition</strong>"
        "Total miles on this shoe."
        "<br><br>"
        "<strong>Target</strong>"
        f"Retire around {goal:.0f} mi."
        "<br><br>"
        "<strong>Wear Bands</strong>"
        f"{band_dot(TRAFFIC_GREEN)}&lt;50% of goal"
        f"<br>{band_dot(TRAFFIC_LIME)}50–70%"
        f"<br>{band_dot(TRAFFIC_YELLOW)}70–85%"
        f"<br>{band_dot(TRAFFIC_ORANGE)}85–100%"
        f"<br>{band_dot(TRAFFIC_RED)}at or above goal"
    )


def shoe_kpi_cards_html(gear, goal: float = SHOE_MILEAGE_GOAL) -> str:
    """Render shoe mileage gauge cards for the Metrics page.

    Parameters
    ----------
    gear :
        DataFrame with ``name``, ``type``, ``mileage``, and ``status`` columns.
    goal : float, optional
        Retirement mileage target. Defaults to ``SHOE_MILEAGE_GOAL``.

    Returns
    -------
    str
        HTML markup for the Shoes panel, or an empty-state panel.
    """
    section_label = (
        '<div class="panel-label shoe-panel-label">'
        "<span>Shoes</span>"
        '<span class="kpi-info" tabindex="0" role="button" '
        'aria-label="About Shoes">'
        '<span aria-hidden="true">ⓘ</span>'
        f'<span class="kpi-tooltip" role="tooltip">{shoe_kpi_tooltip(goal)}</span>'
        "</span></div>"
    )
    if gear is None or getattr(gear, "empty", True):
        return (
            f'<div class="panel" id="shoe-mileage">'
            f"{section_label}"
            '<div class="race-results-empty">No shoe mileage data yet.</div>'
            "</div>"
        )

    ordered = gear.sort_values("mileage", ascending=False, kind="mergesort")
    cards = []
    for _, row in ordered.iterrows():
        name = html.escape(str(row.get("name") or "Shoe"))
        shoe_type = html.escape(str(row.get("type") or "—").strip() or "—")
        mileage = float(row.get("mileage") or 0.0)
        status = str(row.get("status") or "active").strip().lower()
        accent = shoe_wear_color(mileage, goal)
        progress = mileage / goal if goal > 0 else 0.0
        retired_class = " is-retired" if status == "retired" else ""
        cards.append(
            f'<div class="shoe-kpi-card{retired_class}" style="--accent:{accent}">'
            f'<div class="shoe-kpi-name">{name}</div>'
            f'<div class="shoe-gauge">'
            f"{_gauge_svg(progress, accent, target_progress=1.0)}"
            f"</div>"
            f'<div class="shoe-kpi-value">{mileage:.0f}</div>'
            f'<div class="shoe-kpi-sub">of {goal:.0f} mi</div>'
            f'<div class="shoe-kpi-type">{shoe_type}</div>'
            "</div>"
        )

    return (
        f'<div class="panel" id="shoe-mileage">'
        f"{section_label}"
        f'<div class="shoe-kpi-grid">{"".join(cards)}</div>'
        "</div>"
    )


def render_section_nav(sections: list[tuple[str, str]], *, aria_label: str) -> None:
    """Render in-page section links in the Streamlit sidebar.

    Parameters
    ----------
    sections : list[tuple[str, str]]
        Pairs of anchor id and link label.
    aria_label : str
        Accessible name for the navigation landmark.

    Returns
    -------
    None
        Renders sidebar HTML via Streamlit.
    """
    import streamlit as st

    links = "".join(
        f'<a href="#{anchor}">{html.escape(label)}</a>'
        for anchor, label in sections
    )
    nav_html = f"""
<div class="sidebar-section-nav">
  <div class="sidebar-section-nav-label">On this page</div>
  <nav class="sidebar-section-nav-links" aria-label="{html.escape(aria_label)}">
    {links}
  </nav>
</div>
"""
    with st.sidebar:
        st.markdown(nav_html, unsafe_allow_html=True)


def render_insights_section_nav(
    hr_grain: str, heatmap_grain: str, pace_label: str
) -> None:
    """Render in-page section links for Training Insights.

    Parameters
    ----------
    hr_grain : str
        Period grain label for the pace-vs-HR chart title.
    heatmap_grain : str
        Period grain label for the mileage heatmap title.
    pace_label : str
        Selected pace-bin display label.

    Returns
    -------
    None
        Renders sidebar navigation links via Streamlit.
    """
    render_section_nav(
        [
            ("chart-pace-hr", pace_hr_title(hr_grain, pace_label)),
            ("chart-mileage-heatmap", heatmap_title(heatmap_grain)),
        ],
        aria_label="Training Insights sections",
    )


def render_metrics_section_nav() -> None:
    """Render in-page section links for Metrics."""
    render_section_nav(
        [
            ("achievements", "Achievements"),
            ("key-indicators", "Key Indicators"),
            ("kpi-detail", "Inspect"),
            ("shoe-mileage", "Shoes"),
        ],
        aria_label="Metrics sections",
    )


def render_sidebar_section_nav(grain: str) -> None:
    """Render in-page section links for Training Overview.

    Parameters
    ----------
    grain : str
        Period grain used for chart section titles.

    Returns
    -------
    None
        Renders sidebar navigation links via Streamlit.
    """
    render_section_nav(
        [
            ("chart-compliance", compliance_title(grain)),
            ("chart-mileage", mileage_title(grain)),
        ],
        aria_label="Training Overview sections",
    )


def render_race_section_nav(*, chart_label: str = "Finish Times") -> None:
    """Render in-page section links for Race Results.

    Parameters
    ----------
    chart_label : str, optional
        Label for the scatter chart link. Defaults to ``"Finish Times"``.

    Returns
    -------
    None
        Renders sidebar navigation links via Streamlit.
    """
    render_section_nav(
        [
            ("chart-race-results", chart_label),
            ("race-results-table", "Race History"),
        ],
        aria_label="Race Results sections",
    )
