"""Shared KPI and sidebar UI helpers for the Runner's Dashboard."""

from __future__ import annotations

import html
import math
from collections.abc import Mapping, Sequence

from charts import (
    RACE_EVENTS_TITLE,
    RACE_STRIP_DIAMOND_COLOR,
    RACE_STRIP_SQUARE_COLOR,
    RACE_TYPE_COLORS,
    HR_ZONE_COLORS,
    aerobic_efficiency_title,
    compliance_title,
    elevation_title,
    fitness_freshness_title,
    hr_zones_title,
    mileage_title,
    pace_hr_title,
)
from data import format_full_date
from race_data import (
    easy_hard_ratio_from_pct,
    fastest_races_by_type,
    format_pace_min_per_mile,
    race_buildup_comparison_title,
    race_compare_short_name,
)
from strava_analytics.activities import format_time
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
    MUTED,
    SHOE_MILEAGE_GOAL,
    WEEKLY_MILES_GOAL,
    eh_color,
    EH_BAND_THRESHOLDS,
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


def band_diamond(color_hex: str) -> str:
    """Return HTML for a small diamond swatch in race-strip tooltips."""
    return f'<span class="band-diamond" style="background:{color_hex}"></span>'


def band_square(color_hex: str) -> str:
    """Return HTML for a small square swatch in race-strip tooltips."""
    return f'<span class="band-square" style="background:{color_hex}"></span>'


def race_weeks_legend_html() -> str:
    """Return the Training race-strip label and hover legend.

    The left panel label is **Races** (CSS ``text-transform: uppercase``
    renders it as **RACES**). Hovering the ⓘ control (not the label or
    strip) shows marker shapes: cool-gray squares for training periods and
    muted-gold diamonds for race periods — same pattern as Shoes/KPI info icons.

    Returns
    -------
    str
        HTML markup for the frozen strip label and ``.kpi-tooltip`` legend.
    """
    title = RACE_EVENTS_TITLE
    tooltip = (
        f"<strong>{html.escape(title)}</strong>"
        '<span class="race-legend-row">'
        f'<span class="race-legend-marker">{band_square(RACE_STRIP_SQUARE_COLOR)}</span>'
        "<span>Training period (no race)</span>"
        "</span>"
        '<span class="race-legend-row">'
        f'<span class="race-legend-marker">{band_diamond(RACE_STRIP_DIAMOND_COLOR)}</span>'
        "<span>Race in this period</span>"
        "</span>"
    )
    return (
        '<div class="race-week-legend">'
        f'<span class="panel-label race-week-strip-label">{html.escape(title)}</span>'
        '<span class="kpi-info" tabindex="0" role="button" '
        f'aria-label="About {html.escape(title.lower())}">'
        '<span aria-hidden="true">ⓘ</span>'
        f'<span class="kpi-tooltip" role="tooltip">{tooltip}</span>'
        "</span></div>"
    )



def pace_hr_title_html(title: str, subtitle: str) -> str:
    """Return the Average HR by Pace HTML title row (heading + ⓘ + subtitle).

    Renders outside Plotly (blank Plotly title) so multi-line copy is not
    clipped by the SVG viewport. Subtitle is the grain rolling window
    (e.g. ``4-week rolling average``). The ``.kpi-tooltip`` opens to the
    right of the ⓘ on hover/focus.

    Parameters
    ----------
    title : str
        Chart heading from ``pace_hr_title``.
    subtitle : str
        Rolling-window line from ``pace_hr_trend_subtitle``.

    Returns
    -------
    str
        HTML markup for the title + info + subtitle stack above the chart.
    """
    tooltip = (
        "<strong>Why pace bands</strong>"
        "Same clock pace with a lower average HR over weeks is a classic "
        "fitness signal — you are doing comparable work with less cardiac "
        "cost. Tracking one familiar band strips out &ldquo;I just ran harder&rdquo; noise."
        "<br><br>"
        "<strong>Hills</strong>"
        "Within each pace band we residualize time-weighted HR against activity "
        "climb density (ft/mi), same idea as aerobic efficiency — not true GAP "
        "or altitude streams. Bands with fewer than five samples fall back to a "
        "global HR~ft/mi slope, then raw HR."
        "<br><br>"
        "<strong>Comparing bands</strong>"
        "Pick one or more Pace Range chips in Controls. Each selected band "
        "gets its own trend line (rolling average for the Show By grain). "
        "Use a single easy or tempo band to watch fitness over time, or "
        "several at once to see whether HR improves across intensities together."
    )
    return (
        '<div class="pace-hr-info" role="group" '
        'aria-label="Average heart rate by pace chart">'
        '<div class="pace-hr-chart-heading">'
        '<div class="pace-hr-chart-title-row">'
        f'<span class="pace-hr-chart-title">{html.escape(title)}</span>'
        '<span class="kpi-info" tabindex="0" role="button" '
        'aria-label="About average heart rate by pace">'
        '<span aria-hidden="true">ⓘ</span>'
        f'<span class="kpi-tooltip" role="tooltip">{tooltip}</span>'
        "</span></div>"
        f'<span class="pace-hr-chart-subtitle">{html.escape(subtitle)}</span>'
        "</div></div>"
    )


def fitness_freshness_info_html(title: str) -> str:
    """Return the Fitness & Freshness title with an inline ⓘ definition.

    Title and info icon sit together in the Plotly title band (blank Plotly
    title). The ``.kpi-tooltip`` opens to the right of the icon on hover/focus.

    Parameters
    ----------
    title : str
        Chart heading (e.g. ``Weekly Fitness & Freshness``).

    Returns
    -------
    str
        HTML markup for the inline title + ``.kpi-info`` tooltip row.
    """
    tooltip = (
        "<strong>Definition</strong>"
        "Fitness (chronic load), Fatigue (acute load), and Form (Fitness − Fatigue), "
        "in the spirit of Strava Fitness &amp; Freshness / TrainingPeaks CTL·ATL·TSB."
        "<br><br>"
        "<strong>Daily load</strong>"
        "Edwards TRIMP from run HR zones: minutes in zone × zone number (1–5), "
        "summed per day. Not official Strava Relative Effort / Suffer Score."
        "<br><br>"
        "<strong>Curves</strong>"
        "Fitness = 42-day Banister EMA of daily load; Fatigue = 7-day EMA; "
        "Form = Fitness − Fatigue. Each point is the value on the last day of "
        "the Show By period."
    )
    return (
        '<div class="fitness-freshness-info" role="group" '
        'aria-label="Fitness and freshness chart info">'
        f'<span class="fitness-freshness-chart-title">{title}</span>'
        '<span class="kpi-info" tabindex="0" role="button" '
        'aria-label="About fitness and freshness">'
        '<span aria-hidden="true">ⓘ</span>'
        f'<span class="kpi-tooltip" role="tooltip">{tooltip}</span>'
        "</span></div>"
    )


def aerobic_efficiency_info_html(title: str) -> str:
    """Return the chart title with an inline ⓘ hover definition.

    Title and info icon sit together in the Plotly title band (blank Plotly
    title). The ``.kpi-tooltip`` opens to the right of the icon on hover/focus.

    Parameters
    ----------
    title : str
        Chart heading (e.g. ``Weekly Aerobic Efficiency``).

    Returns
    -------
    str
        HTML markup for the inline title + ``.kpi-info`` tooltip row.
    """
    tooltip = (
        "<strong>Definition</strong>"
        "How much speed you get per heartbeat, after accounting for hills."
        "<br><br>"
        "<strong>Calculation</strong>"
        "Per non-race run, raw efficiency = (3600 ÷ avg pace sec/mi) ÷ avg HR "
        "(mph per bpm). We fit that against climb density (ft/mi) and take the "
        "residual (observed − predicted). Each point is the median residual for "
        "the Show By period."
        "<br><br>"
        "Higher means more efficient than expected for that elevation."
    )
    return (
        '<div class="aerobic-efficiency-info" role="group" '
        'aria-label="Aerobic efficiency chart info">'
        f'<span class="aerobic-efficiency-chart-title">{title}</span>'
        '<span class="kpi-info" tabindex="0" role="button" '
        'aria-label="About aerobic efficiency">'
        '<span aria-hidden="true">ⓘ</span>'
        f'<span class="kpi-tooltip" role="tooltip">{tooltip}</span>'
        "</span></div>"
    )


def compliance_info_html(title: str) -> str:
    """Return the 80:20 compliance title with an inline ⓘ definition.

    Title and info icon sit together in the Plotly title band (blank Plotly
    title). The ``.kpi-tooltip`` opens to the right of the icon on hover/focus.

    Parameters
    ----------
    title : str
        Chart heading (e.g. ``Weekly 80:20 Compliance``).

    Returns
    -------
    str
        HTML markup for the inline title + ``.kpi-info`` tooltip row.
    """
    tooltip = (
        "<strong>What is 80:20</strong>"
        "Polarized training aims for roughly 80% of mileage easy and 20% "
        "moderate/hard (the goal line on the chart)."
        "<br><br>"
        "<strong>Easy vs Moderate/Hard</strong>"
        "From Strava heartrate zones: Zones 1–2 count as easy; the remaining "
        "buckets (typically Zones 3–5) are Moderate/Hard. Per run, "
        "<code>%_easy</code> is easy zone time ÷ all zone time."
        "<br><br>"
        "<strong>Bar percentages</strong>"
        "For each run with HR-zone data, easy miles = distance × "
        "(<code>%_easy</code> ÷ 100); the rest of that distance is hard miles. "
        "Each bar is the share of those summed miles in the Show By period "
        "(runs without HR zones are omitted from the %)."
    )
    return (
        '<div class="compliance-info" role="group" '
        'aria-label="80:20 compliance chart info">'
        f'<span class="compliance-chart-title">{html.escape(title)}</span>'
        '<span class="kpi-info" tabindex="0" role="button" '
        'aria-label="About 80:20 compliance">'
        '<span aria-hidden="true">ⓘ</span>'
        f'<span class="kpi-tooltip" role="tooltip">{tooltip}</span>'
        "</span></div>"
    )


def _parse_zone_float(raw: object) -> float:
    """Coerce a zone share/seconds value to a finite float (else ``0.0``)."""
    try:
        val = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(val):
        return 0.0
    return val


def _hr_zone_pie_slice_path(
    start_frac: float,
    end_frac: float,
    *,
    cx: float = 50.0,
    cy: float = 50.0,
    r: float = 50.0,
) -> str:
    """Return an SVG pie-slice path from ``start_frac`` to ``end_frac`` (0–1).

    Angles start at 12 o'clock and sweep clockwise, matching the previous
    ``conic-gradient(from -90deg, …)`` donut.
    """
    span = end_frac - start_frac
    if span <= 1e-9:
        return ""
    if span >= 1.0 - 1e-9:
        return (
            f"M {cx},{cy - r} "
            f"A {r},{r} 0 1 1 {cx},{cy + r} "
            f"A {r},{r} 0 1 1 {cx},{cy - r} Z"
        )

    def _point(frac: float) -> tuple[float, float]:
        angle = math.radians(-90.0 + frac * 360.0)
        return cx + r * math.cos(angle), cy + r * math.sin(angle)

    x1, y1 = _point(start_frac)
    x2, y2 = _point(end_frac)
    large_arc = 1 if span > 0.5 else 0
    return (
        f"M {cx},{cy} L {x1:.4f},{y1:.4f} "
        f"A {r},{r} 0 {large_arc} 1 {x2:.4f},{y2:.4f} Z"
    )


def _hr_zone_duration_label(seconds: float | None) -> str:
    """Format zone seconds with the dashboard ``HH:MM:SS`` / ``MM:SS`` helper."""
    if seconds is None or seconds < 0:
        return "—"
    # Under one hour, prefer MM:SS (pace-style); otherwise HH:MM:SS like moving time.
    include_hours = seconds >= 3600
    formatted = format_time(seconds, include_hours=include_hours)
    return formatted if formatted else "—"


def hr_zones_last_week_pie_html(
    last_week_zones: Mapping[str, object] | None,
) -> str:
    """Return a last-full-week HR-zone donut for the Training right gutter.

    Positioned under the Plotly Zone legend in the shared ``FITNESS_MARGIN_R``
    deadspan (same 168px legend column as other charts) so it sits beside the
    stacked area chart, not below it. Each zone wedge is an SVG path with a
    ``.kpi-tooltip`` on hover/focus showing zone name, percent of HR time, and
    total duration in that zone.

    Parameters
    ----------
    last_week_zones : mapping or None
        Shares from ``last_full_week_hr_zone_shares`` (``week_label`` plus
        ``zone_1_pct`` … ``zone_5_pct``, optionally ``zone_1_sec`` …).

    Returns
    -------
    str
        HTML for ``.hr-zones-pie-gutter`` (caption + SVG donut or empty state).
    """
    label = ""
    values: list[float] = []
    seconds: list[float | None] = []
    if last_week_zones is not None:
        label = str(last_week_zones.get("week_label") or "")
        for idx in range(1, len(HR_ZONE_COLORS) + 1):
            if f"zone_{idx}_pct" not in last_week_zones:
                values = []
                seconds = []
                break
            values.append(_parse_zone_float(last_week_zones.get(f"zone_{idx}_pct")))
            sec_key = f"zone_{idx}_sec"
            if sec_key in last_week_zones:
                seconds.append(_parse_zone_float(last_week_zones.get(sec_key)))
            else:
                seconds.append(None)

    caption = "Last week"
    if label:
        caption = f"Last week<br>{html.escape(label)}"

    total = sum(values)
    if not values or total <= 0:
        body = (
            '<div class="hr-zones-pie-empty" role="img" '
            'aria-label="No HR zone data for last week">No HR data</div>'
        )
    else:
        paths: list[str] = []
        tips: list[str] = []
        aria_parts: list[str] = []
        cursor = 0.0
        for idx, (color, pct, sec) in enumerate(
            zip(HR_ZONE_COLORS, values, seconds, strict=True), start=1
        ):
            start_frac = cursor / total
            cursor += pct
            end_frac = cursor / total
            duration = _hr_zone_duration_label(sec)
            pct_label = f"{pct:.0f}%"
            tip_plain = f"Zone {idx}: {pct_label} · {duration}"
            aria_parts.append(tip_plain)
            tip_html = (
                f"<strong>Zone {idx}</strong>"
                f"{html.escape(pct_label)} of HR time"
                f"<br>{html.escape(duration)}"
            )
            tips.append(
                f'<span class="kpi-tooltip hr-zones-pie-tip" data-zone="{idx}" '
                f'role="tooltip">{tip_html}</span>'
            )
            path_d = _hr_zone_pie_slice_path(start_frac, end_frac)
            if not path_d:
                continue
            paths.append(
                f'<path class="hr-zones-pie-slice" data-zone="{idx}" '
                f'tabindex="0" role="listitem" '
                f'aria-label="{html.escape(tip_plain)}" '
                f'fill="{color}" d="{path_d}" />'
            )
        aria = html.escape(", ".join(aria_parts))
        body = (
            f'<div class="hr-zones-pie-donut" role="list" aria-label="{aria}">'
            '<svg viewBox="0 0 100 100" aria-hidden="true" focusable="false">'
            f'{"".join(paths)}'
            "</svg>"
            f'{"".join(tips)}'
            "</div>"
        )

    return (
        '<div class="hr-zones-pie-gutter" role="group" '
        'aria-label="Last week heart rate zone share">'
        '<aside class="hr-zones-pie-panel">'
        f'<div class="hr-zones-pie-caption">{caption}</div>'
        f"{body}"
        "</aside></div>"
    )


RACE_WEEK_STRIP_KEYS = ("race_week_strip",)


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
    return _eh_kpi_tooltip_body(
        f"Easy:hard time ratio from heart-rate zones for {period_desc}."
    )


def race_buildup_eh_kpi_tooltip(weeks: int) -> str:
    """Return tooltip HTML for race build-up easy:hard values.

    Definition only — no target / target-band guidance (unlike Metrics KPIs).
    """
    n = max(0, int(weeks))
    week_word = "week" if n == 1 else "weeks"
    return (
        "<strong>Definition</strong>"
        "Easy:hard share from heart-rate zones over the "
        f"{n} pre-race {week_word} (race week excluded)."
    )


def _eh_kpi_tooltip_body(definition: str) -> str:
    green, lime, yellow, orange = EH_BAND_THRESHOLDS
    return (
        "<strong>Definition</strong>"
        f"{definition}"
        "<br><br>"
        "<strong>Target</strong>"
        "~80% easy (80:20)"
        "<br><br>"
        "<strong>Target Bands</strong>"
        f"{band_dot(TRAFFIC_GREEN)}≥{green}% easy"
        f"<br>{band_dot(TRAFFIC_LIME)}≥{lime}%"
        f"<br>{band_dot(TRAFFIC_YELLOW)}≥{yellow}%"
        f"<br>{band_dot(TRAFFIC_ORANGE)}≥{orange}%"
        f"<br>{band_dot(TRAFFIC_RED)}below {orange}%"
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
    """Invisible scroll target for the Metrics Inspect expander.

    The visible Inspect title lives on the expander summary, styled as
    ``.panel-label`` in CSS. Inspect is not a left-nav jump link.
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


# Page key, sidebar label, path relative to ``dashboard/streamlit_app.py``.
# Labels follow ``st.Page`` titles in the entrypoint.
NAV_PAGES: tuple[tuple[str, str, str], ...] = (
    ("metrics", "Metrics", "pages/metrics.py"),
    ("training", "Training", "pages/training.py"),
    ("fitness", "Fitness", "pages/fitness.py"),
    ("performance", "Performance", "pages/performance.py"),
)

METRICS_SECTIONS: list[tuple[str, str]] = [
    ("achievements", "Achievements"),
    ("key-indicators", "Key Indicators"),
    ("shoe-mileage", "Shoes"),
]


def sidebar_nav_entries(
    current_page: str,
    sections: list[tuple[str, str]],
) -> list[tuple[str, str, str]]:
    """Return left-nav entries: page links first, then On this page jumps.

    Parameters
    ----------
    current_page : str
        ``NAV_PAGES`` key for the page being viewed. ``sections`` are the
        in-page jumps for that page; they are appended after every page link.
    sections : list[tuple[str, str]]
        In-page jump pairs of anchor id and link label.

    Returns
    -------
    list[tuple[str, str, str]]
        ``(kind, key, label)`` rows. ``kind`` is ``"page"`` or ``"section"``.
    """
    entries: list[tuple[str, str, str]] = [
        ("page", key, title) for key, title, _path in NAV_PAGES
    ]
    if any(key == current_page for key, _title, _path in NAV_PAGES):
        entries.extend(("section", anchor, label) for anchor, label in sections)
    return entries


def section_nav_html(sections: list[tuple[str, str]], *, aria_label: str) -> str:
    """Return HTML for the ``On this page`` jump-link block.

    Parameters
    ----------
    sections : list[tuple[str, str]]
        Pairs of anchor id and link label.
    aria_label : str
        Accessible name for the navigation landmark.

    Returns
    -------
    str
        Sidebar markup for in-page section links.
    """
    links = "".join(
        f'<a href="#{anchor}">{html.escape(label)}</a>'
        for anchor, label in sections
    )
    return f"""
<div class="sidebar-section-nav">
  <div class="sidebar-section-nav-label">On this page</div>
  <nav class="sidebar-section-nav-links" aria-label="{html.escape(aria_label)}">
    {links}
  </nav>
</div>
"""


def render_section_nav(
    sections: list[tuple[str, str]],
    *,
    aria_label: str,
    current_page: str,
) -> None:
    """Render page links, then ``On this page`` jumps as a separate block.

    Native ``st.navigation`` is hidden; this helper draws the full left nav
    so page links come first and ``On this page`` sits at the bottom.

    Parameters
    ----------
    sections : list[tuple[str, str]]
        Pairs of anchor id and link label.
    aria_label : str
        Accessible name for the in-page navigation landmark.
    current_page : str
        ``NAV_PAGES`` key for the page being viewed.

    Returns
    -------
    None
        Renders sidebar HTML via Streamlit.
    """
    import streamlit as st

    jumps = section_nav_html(sections, aria_label=aria_label)
    with st.sidebar:
        st.markdown(
            '<div class="sidebar-nav-heading">Navigation</div>',
            unsafe_allow_html=True,
        )
        for key, title, path in NAV_PAGES:
            with st.container():
                if key == current_page:
                    st.markdown(
                        '<div class="sidebar-nav-current-marker" aria-hidden="true"></div>',
                        unsafe_allow_html=True,
                    )
                st.page_link(path, label=title, use_container_width=True)
        st.markdown(jumps, unsafe_allow_html=True)


def render_insights_section_nav(
    hr_grain: str, pace_labels: str | Sequence[str]
) -> None:
    """Render in-page section links for Fitness.

    Parameters
    ----------
    hr_grain : str
        Period grain label for the pace-vs-HR chart title.
    pace_labels : str or sequence of str
        Selected pace-bin display label(s).

    Returns
    -------
    None
        Renders sidebar navigation links via Streamlit.
    """
    render_section_nav(
        [
            ("chart-race-weeks", RACE_EVENTS_TITLE),
            ("chart-pace-hr", pace_hr_title(hr_grain, pace_labels)),
            ("chart-aerobic-efficiency", aerobic_efficiency_title(hr_grain)),
            ("chart-fitness-freshness", fitness_freshness_title(hr_grain)),
        ],
        aria_label="Fitness sections",
        current_page="fitness",
    )


def render_metrics_section_nav() -> None:
    """Render in-page section links for Metrics (no Inspect jump)."""
    render_section_nav(
        METRICS_SECTIONS,
        aria_label="Metrics sections",
        current_page="metrics",
    )


def render_sidebar_section_nav(grain: str) -> None:
    """Render in-page section links for Training.

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
            ("chart-race-weeks", RACE_EVENTS_TITLE),
            ("chart-compliance", compliance_title(grain)),
            ("chart-mileage", mileage_title(grain)),
            ("chart-elevation", elevation_title(grain)),
            ("chart-hr-zones", hr_zones_title(grain)),
        ],
        aria_label="Training sections",
        current_page="training",
    )


def fastest_race_cards_html(races) -> str:
    """Render Personal Records cards for each non-``Other`` race type.

    Parameters
    ----------
    races :
        Race dataframe (typically the full loaded set). Cards use the fastest
        finish time per type via ``fastest_races_by_type``.

    Returns
    -------
    str
        HTML markup for the Personal Records strip, or ``""`` when there are no
        eligible races.
    """
    best = fastest_races_by_type(races)
    if best.empty:
        return ""

    cards: list[str] = []
    for _, row in best.iterrows():
        race_type = str(row.get("race_type") or "").strip() or "—"
        accent = RACE_TYPE_COLORS.get(race_type, MUTED)
        time_label = str(row.get("elapsed_time_min") or "—").strip() or "—"
        name = str(row.get("name") or "").strip() or "—"
        date_raw = row.get("date")
        try:
            date_label = format_full_date(date_raw) if date_raw is not None else "—"
        except (TypeError, ValueError):
            date_label = "—"
        pace = str(row.get("elapsed_pace") or "—").strip() or "—"
        cards.append(
            f'<div class="fastest-race-card" style="--accent:{accent}">'
            f'<div class="fastest-race-type">{html.escape(race_type)}</div>'
            f'<div class="fastest-race-time">{html.escape(time_label)}</div>'
            f'<div class="fastest-race-name" title="{html.escape(name)}">'
            f"{html.escape(name)}</div>"
            f'<div class="fastest-race-meta">'
            f"{html.escape(date_label)}"
            f'<span class="fastest-race-meta-sep" aria-hidden="true">·</span>'
            f"{html.escape(pace)} /mi"
            f"</div>"
            "</div>"
        )

    return (
        '<div class="panel" id="fastest-races">'
        '<div class="panel-label">Personal Records</div>'
        f'<div class="fastest-race-grid">{"".join(cards)}</div>'
        "</div>"
    )


def _race_buildup_side_html(
    row,
    *,
    avg_pace_min: float | None = None,
) -> str:
    """One race column for the build-up comparison summary.

    Finish time stays the race result; pace under it is training-period
    average pace (pre-race window, race week excluded).
    """
    name = race_compare_short_name(row)
    date_raw = row.get("date")
    try:
        date_label = format_full_date(date_raw) if date_raw is not None else "—"
    except (TypeError, ValueError):
        date_label = "—"
    time_label = str(row.get("elapsed_time_min") or "—").strip() or "—"
    pace_label = format_pace_min_per_mile(avg_pace_min)
    pr_badge = (
        '<span class="race-buildup-pr">PR</span>' if bool(row.get("is_pr")) else ""
    )
    return (
        '<div class="race-buildup-side">'
        f'<div class="race-buildup-name" title="{html.escape(str(row.get("name") or name))}">'
        f'<span class="race-buildup-name-text">{html.escape(name)}</span>'
        f"{pr_badge}</div>"
        f'<div class="race-buildup-date">{html.escape(date_label)}</div>'
        f'<div class="race-buildup-time">{html.escape(time_label)}</div>'
        f'<div class="race-buildup-pace">{html.escape(pace_label)}</div>'
        "</div>"
    )


def race_buildup_summary_html(
    race_type: str,
    race_a,
    race_b,
    *,
    avg_pace_min_a: float | None = None,
    avg_pace_min_b: float | None = None,
) -> str:
    """Render the two-race header above Performance build-up charts.

    Column labels (Race A | Race B) sit above the comparison title, aligned
    with the A/B data columns (not the row-title gutter). Pace under each
    finish time is training-period average pace (not race result pace).

    Parameters
    ----------
    race_type : str
        Selected race type (e.g. ``"Half"``).
    race_a, race_b :
        Race rows (Series-like) for the left and right charts.
    avg_pace_min_a, avg_pace_min_b :
        Distance-weighted average pace (min/mi) over each race's pre-race
        training window.

    Returns
    -------
    str
        HTML markup for column labels, comparison title, and race facts.
    """
    title = race_buildup_comparison_title(race_type)
    gutter = '<div class="race-buildup-label-gutter" aria-hidden="true"></div>'
    mid = '<div class="race-buildup-mid-gutter" aria-hidden="true"></div>'
    return (
        '<div class="race-buildup-summary">'
        '<div class="race-buildup-col-headers race-buildup-compare-row" '
        'role="row" aria-label="Column labels">'
        f"{gutter}"
        '<div class="race-buildup-col-header" role="columnheader">Race A</div>'
        f"{mid}"
        '<div class="race-buildup-col-header" role="columnheader">Race B</div>'
        "</div>"
        '<div class="race-buildup-compare-row">'
        f"{gutter}"
        f'<div class="race-buildup-summary-title">{html.escape(title)}</div>'
        "</div>"
        '<div class="race-buildup-summary-grid race-buildup-compare-row">'
        f"{gutter}"
        f"{_race_buildup_side_html(race_a, avg_pace_min=avg_pace_min_a)}"
        f"{mid}"
        f"{_race_buildup_side_html(race_b, avg_pace_min=avg_pace_min_b)}"
        "</div>"
        "</div>"
    )


def race_buildup_section_heading_html(
    title: str,
    *,
    subtitle: str | None = None,
) -> str:
    """Centered training-comparison heading (optional subtitle below title)."""
    sub = (
        f'<div class="race-buildup-section-sub">{html.escape(subtitle)}</div>'
        if subtitle
        else ""
    )
    return (
        '<div class="race-buildup-section-heading race-buildup-compare-row">'
        '<div class="race-buildup-label-gutter" aria-hidden="true"></div>'
        '<div class="race-buildup-section-heading-main">'
        f'<div class="race-buildup-section-title">{html.escape(title)}</div>'
        f"{sub}"
        "</div>"
        "</div>"
    )


def race_buildup_row_heading_html(title: str) -> str:
    """Inline row title for the Weekly mileage chart gutter."""
    return (
        '<div class="race-buildup-mileage-label">'
        f'<div class="race-buildup-row-title">{html.escape(title)}</div>'
        "</div>"
    )


def race_buildup_eh_values_html(
    *,
    weeks: int,
    easy_pct_a: float | None = None,
    easy_pct_b: float | None = None,
    insufficient_a: bool = False,
    insufficient_b: bool = False,
    label_a: str = "Race A",
    label_b: str = "Race B",
) -> str:
    """Easy:hard ratios with the row title inline beside Race A | Race B.

    When ``insufficient_a`` / ``insufficient_b`` is True (HR coverage ≤ 10% of
    training miles), that column shows “Insufficient HR data” instead of a
    ratio. ``label_a`` / ``label_b`` are accepted for call-site compatibility
    but are not rendered — column identity comes from the Race A | Race B
    header row.
    """
    _ = (label_a, label_b)
    tooltip = race_buildup_eh_kpi_tooltip(weeks)
    mid = '<div class="race-buildup-mid-gutter" aria-hidden="true"></div>'
    return (
        '<div class="race-buildup-eh-values race-buildup-compare-row" '
        'aria-label="Easy to hard ratio">'
        '<div class="race-buildup-eh-title">'
        "<span>% easy : % hard</span>"
        '<span class="kpi-info" tabindex="0" role="button" '
        'aria-label="About easy to hard ratio">'
        '<span aria-hidden="true">ⓘ</span>'
        f'<span class="kpi-tooltip" role="tooltip">{tooltip}</span>'
        "</span>"
        "</div>"
        f"{_race_buildup_eh_value(easy_pct_a, insufficient=insufficient_a)}"
        f"{mid}"
        f"{_race_buildup_eh_value(easy_pct_b, insufficient=insufficient_b)}"
        "</div>"
    )


def _race_buildup_eh_value(
    easy_pct: float | None,
    *,
    insufficient: bool = False,
) -> str:
    """Plain easy:hard ratio value (no per-cell race name)."""
    if insufficient:
        return (
            '<div class="race-buildup-eh-item">'
            '<div class="race-buildup-eh-value race-buildup-eh-insufficient" '
            'role="status">Insufficient HR data</div>'
            "</div>"
        )
    value, _pct = easy_hard_ratio_from_pct(easy_pct)
    return (
        '<div class="race-buildup-eh-item">'
        f'<div class="race-buildup-eh-value">{html.escape(value)}</div>'
        "</div>"
    )


def race_buildup_delta_table_html(
    rows: Sequence[Mapping[str, str]],
    *,
    weeks: int | None = None,
) -> str:
    """Render training metrics as inline title | Race A | Δ | Race B rows.

    Shared compare-row grid keeps metric titles aligned with EH / HR / mileage
    labels. ``weeks`` is accepted for call-site compatibility; the
    ``Excludes race week`` note lives on the training-comparison heading.

    Parameters
    ----------
    rows :
        Rows from ``race_buildup_compare_rows`` with ``metric``, ``race_a``,
        ``race_b``, and ``delta`` keys.
    weeks :
        Unused; kept so older call sites that pass ``weeks=`` still work.

    Returns
    -------
    str
        HTML for stacked metric value rows.
    """
    _ = weeks
    blocks: list[str] = []
    for row in rows:
        blocks.append(
            '<div class="race-buildup-metric-block race-buildup-compare-row">'
            f'<div class="race-buildup-metric-title">'
            f'{html.escape(row["metric"])}</div>'
            f'<div class="race-buildup-metric-value">'
            f'{html.escape(row["race_a"])}</div>'
            '<div class="race-buildup-metric-mid" aria-label="Delta">'
            f'<span class="race-buildup-delta-delta">'
            f'{html.escape(row["delta"])}</span>'
            "</div>"
            f'<div class="race-buildup-metric-value">'
            f'{html.escape(row["race_b"])}</div>'
            "</div>"
        )
    return (
        '<div class="race-buildup-delta">'
        f'<div class="race-buildup-metric-list">{"".join(blocks)}</div>'
        "</div>"
    )


def _race_buildup_hr_pie_donut(
    shares: Mapping[str, float] | None,
    *,
    insufficient: bool = False,
) -> str:
    """One mileage-weighted HR-zone donut for build-up compare."""
    if insufficient:
        # Single bold label inside the dashed circle (no caption below).
        body = (
            '<div class="race-buildup-hr-pie-empty race-buildup-hr-insufficient" '
            'role="status">Insufficient HR data</div>'
        )
        return (
            '<div class="race-buildup-hr-pie-side">'
            f"{body}"
            "</div>"
        )

    values: list[float] = []
    miles: list[float | None] = []
    if shares is not None:
        for idx in range(1, len(HR_ZONE_COLORS) + 1):
            if f"zone_{idx}_pct" not in shares:
                values = []
                miles = []
                break
            values.append(_parse_zone_float(shares.get(f"zone_{idx}_pct")))
            mile_key = f"zone_{idx}_miles"
            if mile_key in shares:
                miles.append(_parse_zone_float(shares.get(mile_key)))
            else:
                miles.append(None)

    total = sum(values)
    if not values or total <= 0:
        body = (
            '<div class="race-buildup-hr-pie-empty" role="img" '
            'aria-label="No HR zone data">No HR data</div>'
        )
    else:
        paths: list[str] = []
        tips: list[str] = []
        aria_parts: list[str] = []
        cursor = 0.0
        for idx, (color, pct, zone_miles) in enumerate(
            zip(HR_ZONE_COLORS, values, miles, strict=True), start=1
        ):
            start_frac = cursor / total
            cursor += pct
            end_frac = cursor / total
            pct_label = f"{pct:.0f}%"
            if zone_miles is None:
                miles_label = "—"
            else:
                miles_label = f"{zone_miles:.1f} mi"
            tip_plain = f"Zone {idx}: {pct_label} · {miles_label}"
            aria_parts.append(tip_plain)
            tip_html = (
                f"<strong>Zone {idx}</strong>"
                f"{html.escape(pct_label)} of mileage"
                f"<br>{html.escape(miles_label)}"
            )
            tips.append(
                f'<span class="kpi-tooltip race-buildup-hr-pie-tip" data-zone="{idx}" '
                f'role="tooltip">{tip_html}</span>'
            )
            path_d = _hr_zone_pie_slice_path(start_frac, end_frac)
            if not path_d:
                continue
            paths.append(
                f'<path class="hr-zones-pie-slice race-buildup-hr-pie-slice" '
                f'data-zone="{idx}" tabindex="0" role="listitem" '
                f'aria-label="{html.escape(tip_plain)}" '
                f'fill="{color}" d="{path_d}" />'
            )
        aria = html.escape(", ".join(aria_parts))
        body = (
            f'<div class="race-buildup-hr-pie-donut" role="list" aria-label="{aria}">'
            '<svg viewBox="0 0 100 100" aria-hidden="true" focusable="false">'
            f'{"".join(paths)}'
            "</svg>"
            f'{"".join(tips)}'
            "</div>"
        )

    return (
        '<div class="race-buildup-hr-pie-side">'
        f"{body}"
        "</div>"
    )


def race_buildup_hr_pies_html(
    shares_a: Mapping[str, float] | None,
    shares_b: Mapping[str, float] | None,
    *,
    insufficient_a: bool = False,
    insufficient_b: bool = False,
    label_a: str = "Race A",
    label_b: str = "Race B",
) -> str:
    """Side-by-side mileage-weighted HR-zone pies for Race A / Race B.

    When ``insufficient_a`` / ``insufficient_b`` is True (HR coverage ≤ 10% of
    training miles), that column shows “Insufficient HR data” instead of a pie.
    ``label_a`` / ``label_b`` are accepted for call-site compatibility but are
    not rendered — column identity comes from the Race A | Race B header row.
    Returns ``""`` when neither side has HR-zone data nor an insufficient label.
    """
    _ = (label_a, label_b)
    has_a = (not insufficient_a) and bool(shares_a) and any(
        f"zone_{i}_pct" in shares_a for i in range(1, len(HR_ZONE_COLORS) + 1)
    )
    has_b = (not insufficient_b) and bool(shares_b) and any(
        f"zone_{i}_pct" in shares_b for i in range(1, len(HR_ZONE_COLORS) + 1)
    )
    if not has_a and not has_b and not insufficient_a and not insufficient_b:
        return ""

    mid = '<div class="race-buildup-mid-gutter" aria-hidden="true"></div>'
    return (
        '<div class="race-buildup-hr-pies race-buildup-compare-row" '
        'role="group" aria-label="Heart rate zones">'
        '<div class="race-buildup-hr-pies-title">HR zones</div>'
        f"{_race_buildup_hr_pie_donut(shares_a if has_a else None, insufficient=insufficient_a)}"
        f"{mid}"
        f"{_race_buildup_hr_pie_donut(shares_b if has_b else None, insufficient=insufficient_b)}"
        "</div>"
    )


def render_race_section_nav(*, chart_label: str = "Finish Times") -> None:
    """Render in-page section links for Performance.

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
            ("fastest-races", "Personal Records"),
            ("chart-race-results", chart_label),
            ("race-results-table", "Race History"),
            ("chart-race-buildup", "Race Build-Up Comparison"),
        ],
        aria_label="Performance sections",
        current_page="performance",
    )
