"""Tests for Training Plotly charts."""

import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from dashboard.charts import (
    ELEVATION_BAR,
    ELEVATION_COLORSCALE,
    FATIGUE_ATL_COLOR,
    FITNESS_CTL_COLOR,
    FITNESS_FRESHNESS_MARGIN,
    FORM_TSB_COLOR,
    FORM_TSB_FILL_OPACITY,
    HR_ZONE_COLORS,
    HR_ZONE_STACKGROUP,
    IN_PROGRESS_HATCH_COLOR,
    IN_PROGRESS_HATCH_SHAPE,
    MILEAGE_BAR,
    MILEAGE_COLORSCALE,
    PACE_HR_COLORSCALE,
    PACE_HR_MARGIN,
    PACE_HR_MARGIN_T,
    HR_ZONES_MARGIN,
    AEROBIC_EFFICIENCY_MARGIN,
    AEROBIC_EFFICIENCY_Y_TITLE_STANDOFF,
    FITNESS_MARGIN_L,
    FITNESS_MARGIN_R,
    FITNESS_MARGIN_T,
    FITNESS_XAXIS_DOMAIN,
    RACE_CHART_DIAMOND_SIZE,
    RACE_CHART_DIAMOND_Y_PAD_FRAC,
    RACE_LINE_CHART_DIAMOND_Y_PAD_FRAC,
    RACE_STRIP_DIAMOND_COLOR,
    RACE_STRIP_DIAMOND_SIZE,
    RACE_STRIP_HEIGHT,
    RACE_STRIP_MARGIN_B,
    RACE_STRIP_MARGIN_T,
    RACE_STRIP_PAPER_BG,
    RACE_STRIP_SQUARE_COLOR,
    RACE_STRIP_SQUARE_SIZE,
    RACE_DIM_OPACITY,
    RACE_HIGHLIGHT_PR_SIZE,
    RACE_HIGHLIGHT_RING_WIDTH,
    RACE_HIGHLIGHT_SIZE,
    RACE_TYPE_COLORS,
    race_results_scatter,
    TRAINING_BARGAP,
    TRAINING_EASY,
    TRAINING_GOAL_LINE,
    TRAINING_HARD,
    TRAINING_MARGIN_L,
    TRAINING_MARGIN_R,
    TRAINING_MARGIN_T,
    TRAINING_OFFSETGROUP,
    TRAINING_XAXIS_DOMAIN,
    COMPLIANCE_MARGIN_T,
    FITNESS_Y_TITLE_STANDOFF,
    LEGEND_FITNESS_GUTTER,
    LEGEND_UNDER_TITLE,
    aerobic_efficiency_line_chart,
    aerobic_efficiency_title,
    compliance_chart,
    elevation_chart,
    fitness_form_fatigue_line_chart,
    fitness_freshness_title,
    hr_zones_stacked_area_chart,
    hr_zones_title,
    mileage_chart,
    mileage_heatmap_chart,
    pace_hr_line_chart,
    pace_hr_bin_color_map,
    pace_hr_series_colors,
    pace_hr_title,
    pace_hr_trend_subtitle,
    pace_hr_trend_window,
    race_weeks_chart,
)
from dashboard.theme import (
    RACE_TABLE_FILL,
    CARD,
    CHART_AEROBIC_EFFICIENCY_MARGIN_TOP,
    CHART_COMPLIANCE_MARGIN_TOP,
    CHART_ELEVATION_MARGIN_TOP,
    CHART_FITNESS_FRESHNESS_MARGIN_TOP,
    CHART_HR_ZONES_MARGIN_TOP,
    CHART_MILEAGE_MARGIN_TOP,
    CHART_PACE_HR_MARGIN_TOP,
    CHART_RACE_WEEKS_MARGIN_TOP,
    EASY,
    ELEVATION_PURPLE,
    FITNESS_LEGEND_GUTTER_X_FRAC,
    FITNESS_SECTION_GAP,
    GLOBAL_CSS,
    HARD,
    INK,
    MILES,
    MUTED,
    RACE_STRIP_BG,
    RACE_STRIP_END_PAD_PX,
    RACE_STRIP_SCROLL_MARGIN_TOP,
    SURFACE,
)
from dashboard.ui import (
    RACE_WEEK_STRIP_KEYS,
    aerobic_efficiency_info_html,
    compliance_info_html,
    fitness_freshness_info_html,
    hr_zones_last_week_pie_html,
    pace_hr_title_html,
    race_weeks_legend_html,
)
from race_data import RACE_TYPE_ORDER


def _training_period_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "period_key": ["2026-10", "2026-11"],
            "period_label": ["Mar 2, 26", "Mar 9, 26"],
            "period_tooltip": ["March 2, 2026", "March 9, 2026"],
            "total_miles": [10.0, 20.0],
            "easy_frac": [0.8, 0.7],
            "hard_frac": [0.2, 0.3],
            "total_elevation_ft": [200.0, 350.0],
            "in_progress": [False, True],
            "is_race_period": [False, True],
            "race_names": ["", "Spring 5k"],
            "race_type": ["", "5k"],
            "race_hover": ["", "Spring 5k<br>5k"],
        }
    )


def _race_diamond_traces(fig) -> list:
    """Gold diamond scatter markers overlaid on Training bar charts."""
    diamonds = []
    for trace in fig.data:
        if getattr(trace, "type", None) != "scatter":
            continue
        marker = getattr(trace, "marker", None)
        if marker is None:
            continue
        symbol = getattr(marker, "symbol", None)
        if symbol != "diamond":
            continue
        diamonds.append(trace)
    return diamonds


def _has_dashed_race_vline(fig) -> bool:
    """True when a dashed vertical race-week guide line is present."""
    for shape in fig.layout.shapes or ():
        if getattr(shape, "type", None) != "line":
            continue
        yref = getattr(shape, "yref", None) or ""
        xref = getattr(shape, "xref", None) or "x"
        if yref not in {"paper", "y domain"}:
            continue
        if xref in {"paper", "x domain"}:
            continue
        line = getattr(shape, "line", None)
        dash = getattr(line, "dash", None) if line is not None else None
        if dash == "dash":
            return True
    return False


def _has_filled_race_vrect(fig) -> bool:
    """True when a non-transparent vertical band covers race periods."""
    for shape in fig.layout.shapes or ():
        if getattr(shape, "type", None) != "rect":
            continue
        yref = getattr(shape, "yref", None) or ""
        xref = getattr(shape, "xref", None) or "x"
        if yref not in {"paper", "y domain"}:
            continue
        if xref in {"paper", "x domain"}:
            continue
        fill = str(getattr(shape, "fillcolor", "") or "").replace(" ", "").lower()
        if fill and fill not in {"rgba(0,0,0,0)", "transparent", "none"}:
            return True
    return False


class TrainingChartTests(unittest.TestCase):
    """Elevation bars, race-week strip, and shared Training axes."""

    def test_elevation_chart_uses_feet(self):
        fig = elevation_chart(_training_period_df(), "Week")
        self.assertEqual(list(fig.data[0].y), [200.0, 350.0])
        self.assertIn("ft", fig.data[0].hovertemplate)
        self.assertIn("Elevation (ft)", fig.layout.yaxis.title.text)
        self.assertIn("Weekly Elevation", fig.layout.title.text)

    def test_main_charts_have_race_diamonds_at_bar_tops(self):
        period_df = _training_period_df()
        # Bar tops (race week) and chart-wide max used for the above-bar pad.
        bar_tops = {
            "compliance_chart": 1.0,  # easy_frac + hard_frac for race week
            "mileage_chart": 20.0,
            "elevation_chart": 350.0,
        }
        chart_max = {
            "compliance_chart": 1.0,  # both weeks sum to 1.0
            "mileage_chart": 20.0,
            "elevation_chart": 350.0,
        }
        for builder in (compliance_chart, mileage_chart, elevation_chart):
            fig = builder(period_df, "Week")
            diamonds = _race_diamond_traces(fig)
            self.assertEqual(
                len(diamonds),
                1,
                msg=f"{builder.__name__} should draw one race diamond scatter",
            )
            scatter = diamonds[0]
            pad = chart_max[builder.__name__] * RACE_CHART_DIAMOND_Y_PAD_FRAC
            expected_y = bar_tops[builder.__name__] + pad
            self.assertEqual(list(scatter.x), ["Mar 9, 26"])
            self.assertEqual(list(scatter.y), [expected_y])
            self.assertGreater(scatter.y[0], bar_tops[builder.__name__])
            self.assertEqual(scatter.marker.symbol, "diamond")
            self.assertEqual(scatter.marker.color, RACE_STRIP_DIAMOND_COLOR)
            self.assertEqual(scatter.marker.size, RACE_CHART_DIAMOND_SIZE)
            self.assertEqual(RACE_CHART_DIAMOND_SIZE, 10)
            self.assertGreater(RACE_CHART_DIAMOND_SIZE, RACE_STRIP_DIAMOND_SIZE)
            self.assertFalse(scatter.showlegend)
            self.assertEqual(scatter.customdata[0], "Spring 5k<br>5k")
            self.assertFalse(
                _has_dashed_race_vline(fig),
                msg=f"{builder.__name__} must not draw dashed race vlines",
            )
            self.assertFalse(
                _has_filled_race_vrect(fig),
                msg=f"{builder.__name__} must not draw filled race bands",
            )
            for trace in fig.data:
                name = (getattr(trace, "name", None) or "").lower()
                self.assertNotIn("race", name)
        self.assertEqual(RACE_STRIP_DIAMOND_COLOR, "#E3C677")

    def test_main_charts_skip_diamonds_without_race_column(self):
        period_df = _training_period_df().drop(columns=["is_race_period"])
        for builder in (compliance_chart, mileage_chart, elevation_chart):
            fig = builder(period_df, "Week")
            self.assertEqual(_race_diamond_traces(fig), [])
            self.assertFalse(_has_dashed_race_vline(fig))
            self.assertFalse(_has_filled_race_vrect(fig))

    def test_race_weeks_strip_marks_race_periods(self):
        fig = race_weeks_chart(_training_period_df(), "Week")
        scatter = next(trace for trace in fig.data if trace.type == "scatter")
        self.assertEqual(list(scatter.x), ["Mar 2, 26", "Mar 9, 26"])
        self.assertEqual(list(scatter.y), [0.5, 0.5])
        self.assertEqual(list(scatter.marker.symbol), ["square", "diamond"])
        colors = list(scatter.marker.color)
        self.assertEqual(RACE_STRIP_SQUARE_COLOR, "#9AA5AD")
        self.assertEqual(RACE_STRIP_DIAMOND_COLOR, "#E3C677")
        self.assertEqual(colors[0], RACE_STRIP_SQUARE_COLOR)
        self.assertEqual(colors[1], RACE_STRIP_DIAMOND_COLOR)
        hover = [tuple(row) for row in scatter.customdata]
        self.assertEqual(hover[1][1], "Spring 5k<br>5k")
        self.assertEqual(hover[0][1], "No race")
        self.assertFalse(fig.layout.title.text)
        sizes = list(scatter.marker.size)
        self.assertEqual(sizes[0], RACE_STRIP_SQUARE_SIZE)
        self.assertEqual(sizes[1], RACE_STRIP_DIAMOND_SIZE)
        self.assertLess(RACE_STRIP_SQUARE_SIZE, RACE_STRIP_DIAMOND_SIZE)
        self.assertLessEqual(RACE_STRIP_SQUARE_SIZE, 5)
        self.assertEqual(fig.layout.height, RACE_STRIP_HEIGHT)
        self.assertEqual(fig.layout.margin.t, RACE_STRIP_MARGIN_T)
        self.assertEqual(fig.layout.margin.b, RACE_STRIP_MARGIN_B)
        self.assertLessEqual(RACE_STRIP_HEIGHT, 40)
        self.assertEqual(fig.layout.plot_bgcolor, RACE_STRIP_PAPER_BG)
        self.assertEqual(fig.layout.paper_bgcolor, RACE_STRIP_PAPER_BG)
        self.assertEqual(RACE_STRIP_PAPER_BG, "rgba(0,0,0,0)")
        self.assertEqual(RACE_STRIP_BG, "rgba(0,0,0,0)")
        self.assertEqual(RACE_STRIP_BG, RACE_STRIP_PAPER_BG)
        self.assertNotEqual(RACE_STRIP_BG, CARD)
        self.assertNotEqual(RACE_STRIP_BG, "#FFFFFF")

    def test_race_weeks_strip_uses_alignment_bars(self):
        fig = race_weeks_chart(_training_period_df(), "Week")
        bar = next(trace for trace in fig.data if trace.type == "bar")
        self.assertEqual(list(bar.x), ["Mar 2, 26", "Mar 9, 26"])
        self.assertEqual(bar.offsetgroup, TRAINING_OFFSETGROUP)
        self.assertEqual(fig.layout.bargap, TRAINING_BARGAP)

    def test_race_weeks_strip_uses_single_race_color(self):
        self.assertEqual(RACE_STRIP_DIAMOND_COLOR, "#E3C677")
        self.assertEqual(RACE_TYPE_COLORS["Half"], "#E3C677")
        self.assertEqual(
            RACE_TYPE_COLORS,
            {
                "5k": "#3A9D8F",
                "5M": "#4C78A8",
                "10k": "#7A6FA8",
                "Half": "#E3C677",
                "Marathon": "#C85C5C",
                "Other": "#9AA5AD",
            },
        )
        period_df = _training_period_df()
        period_df.loc[1, "race_type"] = "Marathon"
        fig = race_weeks_chart(period_df, "Week")
        scatter = next(trace for trace in fig.data if trace.type == "scatter")
        self.assertEqual(scatter.marker.color[1], RACE_STRIP_DIAMOND_COLOR)
        self.assertNotEqual(scatter.marker.color[1], RACE_TYPE_COLORS["Marathon"])

    def test_race_marker_hover_shows_type_or_miles(self):
        typed = _training_period_df()
        strip = race_weeks_chart(typed, "Week")
        strip_hover = [tuple(row) for row in next(
            t for t in strip.data if t.type == "scatter"
        ).customdata]
        self.assertEqual(strip_hover[1][1], "Spring 5k<br>5k")
        diamonds = _race_diamond_traces(mileage_chart(typed, "Week"))
        self.assertEqual(diamonds[0].customdata[0], "Spring 5k<br>5k")

        other = _training_period_df()
        other.loc[1, "race_names"] = "Trail Classic"
        other.loc[1, "race_type"] = "Other"
        other.loc[1, "race_hover"] = ""
        other["race_distance_miles"] = [None, 12.4]
        strip_other = race_weeks_chart(other, "Week")
        other_hover = [tuple(row) for row in next(
            t for t in strip_other.data if t.type == "scatter"
        ).customdata]
        self.assertEqual(other_hover[1][1], "Trail Classic<br>12.4 mi")
        self.assertNotIn("Other", other_hover[1][1])
        other_diamonds = _race_diamond_traces(mileage_chart(other, "Week"))
        self.assertEqual(other_diamonds[0].customdata[0], "Trail Classic<br>12.4 mi")

        multi = _training_period_df()
        multi.loc[1, "race_hover"] = "Town 5k<br>5k<br>Odd Race<br>12.4 mi"
        multi_hover = [tuple(row) for row in next(
            t for t in race_weeks_chart(multi, "Week").data if t.type == "scatter"
        ).customdata]
        self.assertEqual(multi_hover[1][1], "Town 5k<br>5k<br>Odd Race<br>12.4 mi")

    def test_mileage_bars_use_solid_fill_by_default(self):
        fig = mileage_chart(_training_period_df(), "Week")
        marker = fig.data[0].marker
        self.assertEqual(marker.color, MILEAGE_BAR)
        self.assertFalse(marker.colorscale)
        self.assertEqual(MILEAGE_BAR, "#509B8F")
        self.assertEqual(MILES, "#3A4A55")
        self.assertNotEqual(MILEAGE_BAR, MILES)
        goal_lines = [
            shape
            for shape in fig.layout.shapes or ()
            if getattr(shape, "type", None) == "line"
            and getattr(shape, "y0", None) == getattr(shape, "y1", None)
        ]
        self.assertTrue(goal_lines)
        self.assertEqual(goal_lines[0].line.color, TRAINING_GOAL_LINE)
        self.assertEqual(TRAINING_GOAL_LINE, "#2E4552")

    def test_mileage_heatmap_uses_mileage_bar_palette(self):
        """Training calendar heatmap shares MILEAGE_COLORSCALE."""
        matrix = np.array([[5.0, 10.0], [15.0, 20.0]])
        fig = mileage_heatmap_chart(
            matrix,
            ["Week 1", "Week 2"],
            ["Jan", "Feb"],
            title="Weekly Mileage by Month",
            grain="Week",
        )
        heat = fig.data[0]
        self.assertEqual(heat.type, "heatmap")
        scale = [(float(stop), color.lower()) for stop, color in heat.colorscale]
        expected = [(float(stop), color.lower()) for stop, color in MILEAGE_COLORSCALE]
        self.assertEqual(scale, expected)
        self.assertEqual(MILEAGE_COLORSCALE[0][1], "#E8F2F0")
        self.assertEqual(MILEAGE_COLORSCALE[-1][1], MILEAGE_BAR)
        self.assertEqual(MILEAGE_BAR, "#509B8F")
        self.assertNotEqual(MILEAGE_COLORSCALE[-1][1], MILES)
        self.assertNotEqual(MILEAGE_COLORSCALE[-1][1], ELEVATION_PURPLE)
        self.assertNotEqual(MILEAGE_COLORSCALE, ELEVATION_COLORSCALE)
        self.assertTrue(heat.showscale)

    def test_mileage_heatmap_empty_cells_have_no_grid_lines(self):
        """NaN cells stay transparent; no grid avoids black strokes on page wash."""
        from dashboard.theme import BG

        matrix = np.array([[5.0, np.nan], [np.nan, 12.0]])
        fig = mileage_heatmap_chart(
            matrix,
            ["Week 1", "Week 2"],
            ["Jan", "Feb"],
            title="Weekly Mileage by Month",
            grain="Week",
        )
        heat = fig.data[0]
        z = np.asarray(heat.z, dtype=float)
        self.assertTrue(np.isnan(z[0, 1]))
        self.assertTrue(np.isnan(z[1, 0]))
        self.assertFalse(heat.hoverongaps)
        self.assertFalse(heat.connectgaps)
        self.assertEqual(heat.xgap, 1)
        self.assertEqual(heat.ygap, 1)
        # Transparent so .stApp (base BG) shows through — not solid BG/SURFACE card.
        self.assertEqual(fig.layout.plot_bgcolor, "rgba(0,0,0,0)")
        self.assertEqual(fig.layout.paper_bgcolor, "rgba(0,0,0,0)")
        self.assertEqual(BG, "#E8EEF2")
        self.assertNotEqual(fig.layout.plot_bgcolor, BG)
        self.assertNotEqual(fig.layout.plot_bgcolor, SURFACE)
        self.assertFalse(fig.layout.xaxis.showgrid)
        self.assertFalse(fig.layout.yaxis.showgrid)
        self.assertFalse(fig.layout.xaxis.zeroline)
        self.assertFalse(fig.layout.yaxis.zeroline)
        self.assertFalse(fig.layout.xaxis.showline)
        self.assertFalse(fig.layout.yaxis.showline)

    def test_mileage_heatmap_zero_miles_paints_not_gap(self):
        """z=0 stays 0 (pale colorscale); NaN stays a no-hover gap."""
        from dashboard.theme import BG

        matrix = np.array([[0.0, np.nan], [8.0, 0.0]])
        fig = mileage_heatmap_chart(
            matrix,
            ["Week 1", "Week 2"],
            ["Jan", "Feb"],
            title="Weekly Mileage by Month",
            grain="Week",
        )
        heat = fig.data[0]
        z = np.asarray(heat.z, dtype=float)
        self.assertEqual(float(z[0, 0]), 0.0)
        self.assertTrue(np.isnan(z[0, 1]))
        self.assertEqual(float(z[1, 1]), 0.0)
        self.assertEqual(heat.zmin, 0.0)
        self.assertFalse(heat.hoverongaps)
        # Pale teal at 0 must differ from page BG so zero cells read as painted.
        self.assertNotEqual(MILEAGE_COLORSCALE[0][1].lower(), BG.lower())

    def test_compliance_chart_is_not_a_heatmap(self):
        fig = compliance_chart(_training_period_df(), "Week")
        easy, hard = fig.data[0], fig.data[1]
        self.assertEqual(easy.marker.color, TRAINING_EASY)
        self.assertEqual(hard.marker.color, TRAINING_HARD)
        self.assertEqual(TRAINING_EASY, "#E8A66C")
        self.assertEqual(TRAINING_HARD, "#D87659")
        # Theme EASY/HARD still color Achievements; Training uses its own constants.
        self.assertEqual(EASY, "#5B9BD5")
        self.assertEqual(HARD, "#E67E22")
        self.assertFalse(easy.marker.colorscale)
        self.assertFalse(hard.marker.colorscale)
        goal_lines = [
            shape
            for shape in fig.layout.shapes or ()
            if getattr(shape, "type", None) == "line"
            and getattr(shape, "y0", None) == getattr(shape, "y1", None)
        ]
        self.assertTrue(goal_lines)
        self.assertEqual(goal_lines[0].line.color, TRAINING_GOAL_LINE)

    def test_compliance_legend_is_horizontal_under_title(self):
        """80:20 Easy / Moderate/Hard key sits under the HTML title, not a side legend."""
        fig = compliance_chart(_training_period_df(), "Week")
        self.assertEqual(fig.layout.title.text, "")
        self.assertTrue(fig.layout.showlegend)
        legend = fig.layout.legend
        self.assertEqual(legend.orientation, "h")
        self.assertEqual(legend.yanchor, "bottom")
        self.assertEqual(legend.y, LEGEND_UNDER_TITLE["y"])
        self.assertGreaterEqual(legend.y, 1.0)
        self.assertEqual(legend.xanchor, "left")
        self.assertEqual(legend.x, 0)
        self.assertEqual(legend.traceorder, "normal")
        self.assertEqual(legend.orientation, LEGEND_UNDER_TITLE["orientation"])
        self.assertEqual(fig.layout.margin.t, COMPLIANCE_MARGIN_T)
        # Room for HTML title+ⓘ above the horizontal key (was 72 when Plotly owned the title).
        self.assertGreaterEqual(COMPLIANCE_MARGIN_T, 96)
        self.assertGreater(COMPLIANCE_MARGIN_T, TRAINING_MARGIN_T)
        # Legend order Easy → Moderate/Hard; stack still has Easy as the base bar.
        bars = [t for t in fig.data if t.type == "bar"]
        self.assertEqual([t.name for t in bars], ["Easy", "Moderate/Hard"])
        self.assertEqual([t.legendrank for t in bars], [1, 2])

    def test_compliance_info_html_explains_8020(self):
        """ⓘ after the title covers polarized idea, zone split, and bar %."""
        html = compliance_info_html("Weekly 80:20 Compliance")
        self.assertIn("compliance-info", html)
        self.assertIn("compliance-chart-title", html)
        self.assertIn("kpi-info", html)
        self.assertIn("kpi-tooltip", html)
        self.assertIn("ⓘ", html)
        self.assertIn("Weekly 80:20 Compliance", html)
        self.assertLess(
            html.index("Weekly 80:20 Compliance"),
            html.index("kpi-info"),
        )
        self.assertIn("80%", html)
        self.assertIn("easy", html.lower())
        self.assertIn("Zones 1", html)
        self.assertIn("Moderate/Hard", html)
        self.assertIn("%_easy", html)
        self.assertIn("Show By", html)
        self.assertIn("HR zones", html)

    def test_elevation_bars_use_purple_heatmap_without_colorbar(self):
        fig = elevation_chart(_training_period_df(), "Week")
        marker = fig.data[0].marker
        self.assertEqual(list(marker.color), [200.0, 350.0])
        self.assertNotEqual(list(marker.color), [ELEVATION_BAR, ELEVATION_BAR])
        scale = [(float(stop), color.lower()) for stop, color in marker.colorscale]
        expected = [(float(stop), color.lower()) for stop, color in ELEVATION_COLORSCALE]
        self.assertEqual(scale, expected)
        self.assertEqual(ELEVATION_COLORSCALE[0][1], "#EBE7F2")
        self.assertEqual(ELEVATION_COLORSCALE[-1][1], ELEVATION_BAR)
        self.assertEqual(ELEVATION_BAR, "#8575A8")
        self.assertEqual(ELEVATION_PURPLE, "#6F5F8D")
        self.assertNotEqual(ELEVATION_COLORSCALE[-1][1], ELEVATION_PURPLE)
        self.assertFalse(marker.showscale)
        coloraxis = fig.layout.coloraxis
        self.assertTrue(coloraxis is None or coloraxis.showscale in (None, False))

    def test_in_progress_period_uses_hatch_not_fade(self):
        """Current (unfinished) period: full fill opacity + gray hatch overlay."""
        period_df = _training_period_df()
        expected_shapes = ["", IN_PROGRESS_HATCH_SHAPE]

        def _pattern_shapes(marker) -> list[str]:
            pattern = marker.pattern
            self.assertIsNotNone(pattern)
            shape = pattern.shape
            if isinstance(shape, (list, tuple)):
                return ["" if s is None else str(s) for s in shape]
            return ["" if shape is None else str(shape)] * len(period_df)

        def _opacity_values(marker, n: int) -> list[float]:
            opacity = marker.opacity
            if opacity is None:
                return [1.0] * n
            if isinstance(opacity, (list, tuple)):
                return [float(v) for v in opacity]
            return [float(opacity)] * n

        def _assert_no_outline(marker) -> None:
            line = marker.line
            if line is None:
                return
            width = line.width
            if width is None:
                return
            if isinstance(width, (list, tuple)):
                self.assertTrue(all(float(w) == 0.0 for w in width))
            else:
                self.assertEqual(float(width), 0.0)

        compliance = compliance_chart(period_df, "Week")
        for bar in (compliance.data[0], compliance.data[1]):
            self.assertEqual(_pattern_shapes(bar.marker), expected_shapes)
            self.assertEqual(bar.marker.pattern.fgcolor, IN_PROGRESS_HATCH_COLOR)
            self.assertEqual(bar.marker.pattern.fillmode, "overlay")
            _assert_no_outline(bar.marker)
            opacities = _opacity_values(bar.marker, len(period_df))
            self.assertEqual(len(set(opacities)), 1, msg="no per-bar opacity fade")
            self.assertAlmostEqual(opacities[0], 1.0)

        for builder, uniform_opacity in (
            (mileage_chart, 0.92),
            (elevation_chart, 0.92),
        ):
            fig = builder(period_df, "Week")
            bar = fig.data[0]
            self.assertEqual(_pattern_shapes(bar.marker), expected_shapes)
            self.assertEqual(bar.marker.pattern.fgcolor, IN_PROGRESS_HATCH_COLOR)
            self.assertEqual(bar.marker.pattern.fillmode, "overlay")
            _assert_no_outline(bar.marker)
            opacities = _opacity_values(bar.marker, len(period_df))
            self.assertEqual(len(set(opacities)), 1, msg="no per-bar opacity fade")
            self.assertAlmostEqual(opacities[0], uniform_opacity)
        self.assertEqual(IN_PROGRESS_HATCH_SHAPE, "/")
        self.assertEqual(IN_PROGRESS_HATCH_COLOR, "#9AA5AD")
        self.assertEqual(RACE_STRIP_SQUARE_COLOR, "#9AA5AD")
        # Hatch must stay cool gray hex (not ink / near-black).
        self.assertNotEqual(IN_PROGRESS_HATCH_COLOR.lower(), "#000")
        self.assertNotEqual(IN_PROGRESS_HATCH_COLOR.lower(), "#000000")
        self.assertNotEqual(IN_PROGRESS_HATCH_COLOR, INK)

    def test_in_progress_bar_hover_includes_grain_note(self):
        """Unfinished period hover appends ``{Grain} in progress``; completed do not."""
        period_df = _training_period_df()
        for grain, note in (("Week", "Week in progress"), ("Month", "Month in progress")):
            note_html = f"<br>{note}"
            for builder in (compliance_chart, mileage_chart, elevation_chart):
                fig = builder(period_df, grain)
                bars = [t for t in fig.data if getattr(t, "type", None) == "bar"]
                self.assertGreaterEqual(len(bars), 1, msg=builder.__name__)
                for bar in bars:
                    custom = list(bar.customdata)
                    self.assertEqual(custom[0][0], "March 2, 2026")
                    self.assertEqual(custom[0][1], "")
                    self.assertEqual(custom[1][0], "March 9, 2026")
                    self.assertEqual(custom[1][1], note_html)
                    self.assertIn("%{customdata[0]}", bar.hovertemplate)
                    self.assertIn("%{customdata[1]}", bar.hovertemplate)
                    self.assertIn(note, note_html)

    def test_training_charts_share_xaxis_and_side_margins(self):
        period_df = _training_period_df()
        figs = [
            race_weeks_chart(period_df, "Week"),
            compliance_chart(period_df, "Week"),
            mileage_chart(period_df, "Week"),
            elevation_chart(period_df, "Week"),
        ]
        margins = {(fig.layout.margin.l, fig.layout.margin.r) for fig in figs}
        self.assertEqual(margins, {(TRAINING_MARGIN_L, TRAINING_MARGIN_R)})
        # Slim right pad (no side legend); Fitness/HR Zones keep the 168px gutter.
        self.assertEqual(TRAINING_MARGIN_R, 32)
        self.assertLess(TRAINING_MARGIN_R, FITNESS_MARGIN_R)
        self.assertEqual(FITNESS_MARGIN_R, 168)
        tickvals = {tuple(fig.layout.xaxis.tickvals) for fig in figs}
        self.assertEqual(tickvals, {("Mar 2, 26", "Mar 9, 26")})
        ranges = {tuple(fig.layout.xaxis.range) for fig in figs}
        self.assertEqual(ranges, {(-0.5, 1.5)})
        domains = {tuple(fig.layout.xaxis.domain) for fig in figs}
        self.assertEqual(domains, {tuple(TRAINING_XAXIS_DOMAIN)})
        bargaps = {fig.layout.bargap for fig in figs}
        self.assertEqual(bargaps, {TRAINING_BARGAP})
        for fig in figs:
            self.assertFalse(fig.layout.xaxis.automargin)
            self.assertFalse(fig.layout.yaxis.automargin)
            self.assertFalse(fig.layout.margin.autoexpand)
        mileage_bars = [
            trace for trace in figs[2].data if trace.type == "bar" and trace.x[0] is not None
        ]
        self.assertEqual(len(mileage_bars), 1)
        self.assertEqual(mileage_bars[0].offsetgroup, TRAINING_OFFSETGROUP)

    def test_race_weeks_strip_backgrounds_are_transparent(self):
        fig = race_weeks_chart(_training_period_df(), "Week")
        self.assertEqual(fig.layout.paper_bgcolor, "rgba(0,0,0,0)")
        self.assertEqual(fig.layout.plot_bgcolor, "rgba(0,0,0,0)")
        shapes = list(fig.layout.shapes or ())
        self.assertGreaterEqual(len(shapes), 2)
        gutter = next(shape for shape in shapes if shape.xref == "paper")
        self.assertEqual(gutter.xsizemode, "pixel")
        self.assertEqual(gutter.xanchor, 0)
        self.assertEqual(gutter.x0, 0)
        self.assertEqual(gutter.x1, TRAINING_MARGIN_L)
        self.assertEqual(gutter.fillcolor, RACE_STRIP_BG)
        self.assertEqual(gutter.fillcolor, "rgba(0,0,0,0)")
        timeline = next(shape for shape in shapes if shape.xref == "x")
        self.assertEqual(timeline.x0, -0.5)
        self.assertEqual(timeline.x1, 1.5)
        self.assertEqual(timeline.fillcolor, RACE_STRIP_BG)
        self.assertEqual(timeline.fillcolor, "rgba(0,0,0,0)")
        self.assertEqual(tuple(fig.layout.xaxis.range), (-0.5, 1.5))
        self.assertEqual(fig.layout.margin.l, TRAINING_MARGIN_L)
        self.assertEqual(fig.layout.margin.r, TRAINING_MARGIN_R)
        self.assertFalse(
            any(
                shape.xref == "paper" and shape.x0 == 0 and shape.x1 == 1
                for shape in shapes
            )
        )
        self.assertFalse(
            any(
                str(shape.fillcolor).lower() in {"#ffffff", "#fff", "white"}
                for shape in shapes
            )
        )


class TrainingChartThemeTests(unittest.TestCase):
    """Training page spacing, legend, and single top race-week strip."""

    def test_chart_stack_has_modest_extra_gap(self):
        self.assertEqual(CHART_RACE_WEEKS_MARGIN_TOP, "3rem")
        self.assertEqual(CHART_COMPLIANCE_MARGIN_TOP, "1.4rem")
        self.assertEqual(CHART_MILEAGE_MARGIN_TOP, "1.85rem")
        self.assertEqual(CHART_ELEVATION_MARGIN_TOP, "1.85rem")
        self.assertNotEqual(CHART_COMPLIANCE_MARGIN_TOP, "0.1rem")

    def test_race_week_strip_is_single_in_flow_copy(self):
        self.assertEqual(RACE_STRIP_SCROLL_MARGIN_TOP, "3.75rem")
        self.assertEqual(RACE_STRIP_END_PAD_PX, 12)
        self.assertEqual(RACE_STRIP_BG, "rgba(0,0,0,0)")
        self.assertNotEqual(RACE_STRIP_BG, CARD)
        self.assertNotEqual(RACE_STRIP_BG, "#FFFFFF")
        self.assertEqual(RACE_WEEK_STRIP_KEYS, ("race_week_strip",))
        self.assertIn(".st-key-race_week_strip", GLOBAL_CSS)
        self.assertNotIn("race_week_strip_mileage", GLOBAL_CSS)
        self.assertNotIn("race_week_strip_elevation", GLOBAL_CSS)
        self.assertNotIn("position: fixed", GLOBAL_CSS)
        self.assertNotIn("race-week-strip-fixed", GLOBAL_CSS)
        self.assertNotIn("race-week-strip-spacer", GLOBAL_CSS)
        self.assertNotIn("--race-strip-pin-gap:", GLOBAL_CSS)
        self.assertNotIn("--race-strip-snap-scan:", GLOBAL_CSS)
        self.assertNotIn("race-week-strip-snap", GLOBAL_CSS)
        self.assertNotIn("race-week-strip-inactive", GLOBAL_CSS)
        self.assertNotIn("race-week-strip-active", GLOBAL_CSS)
        self.assertIn("stLayoutWrapper", GLOBAL_CSS)
        self.assertIn("--race-strip-scroll-margin-top:", GLOBAL_CSS)
        self.assertIn(RACE_STRIP_SCROLL_MARGIN_TOP, GLOBAL_CSS)
        self.assertIn(RACE_STRIP_BG, GLOBAL_CSS)
        self.assertIn("overflow: visible !important", GLOBAL_CSS)
        self.assertIn("[data-testid=\"stMain\"]:has(.st-key-race_week_strip)", GLOBAL_CSS)
        self.assertIn("#chart-race-weeks", GLOBAL_CSS)
        self.assertNotIn("position: sticky !important", GLOBAL_CSS)
        self.assertNotIn("RACE_STRIP_SNAP_SCAN_PX", GLOBAL_CSS)
        import dashboard.theme as theme_mod
        import dashboard.ui as ui_mod

        self.assertFalse(hasattr(theme_mod, "RACE_STRIP_SNAP_SCAN_PX"))
        self.assertFalse(hasattr(theme_mod, "RACE_STRIP_SNAP_HYST_PX"))
        self.assertFalse(hasattr(ui_mod, "pick_race_week_strip_index"))
        self.assertFalse(hasattr(ui_mod, "race_weeks_snap_html"))

    def test_training_page_renders_one_top_strip(self):
        """One strip under Controls above 80:20; diamonds on charts."""
        page = (
            Path(__file__).resolve().parents[2]
            / "dashboard"
            / "pages"
            / "training.py"
        ).read_text()
        self.assertIn('key="race_week_strip"', page)
        self.assertEqual(page.count('key="race_week_strip"'), 1)
        self.assertNotIn("race_week_strip_mileage", page)
        self.assertNotIn("race_week_strip_elevation", page)
        self.assertIn('key="training_race_weeks"', page)
        self.assertIn('key="training_compliance"', page)
        self.assertIn("compliance_info_html", page)
        self.assertIn(
            "compliance_info_html(compliance_title(grain))",
            page,
        )
        self.assertIn('key="training_mileage"', page)
        self.assertIn('key="training_mileage_heatmap"', page)
        self.assertIn('key="training_mileage_heatmap_chart"', page)
        self.assertIn('"Mileage heatmap"', page)
        self.assertIn("expanded=False", page)
        self.assertIn("mileage_heatmap_matrix", page)
        self.assertIn("mileage_heatmap_chart", page)
        self.assertNotIn("color_by_magnitude", page)
        self.assertIn('key="training_elevation"', page)
        self.assertIn('id="chart-compliance"', page)
        self.assertIn('id="chart-hr-zones"', page)
        self.assertIn('id="chart-mileage"', page)
        self.assertIn('id="chart-elevation"', page)
        self.assertNotIn("race_weeks_snap_html", page)
        self.assertNotIn("unsafe_allow_javascript", page)
        self.assertLess(page.find("race_week_strip"), page.find("chart-compliance"))
        self.assertLess(page.find("chart-compliance"), page.find("chart-mileage"))
        self.assertLess(page.find("chart-mileage"), page.find("chart-elevation"))
        self.assertLess(page.find("chart-elevation"), page.find("chart-hr-zones"))
        self.assertLess(page.find("training_compliance"), page.find("training_mileage"))
        self.assertLess(page.find("training_mileage"), page.find("training_mileage_heatmap"))
        self.assertLess(page.find("training_mileage_heatmap"), page.find("training_elevation"))
        self.assertLess(page.find("training_elevation"), page.find("training_hr_zones"))
        self.assertLess(
            page.find("mileage_heatmap_chart"),
            page.find("training_elevation"),
        )
        self.assertIn("hr_zones_stacked_area_chart", page)
        self.assertIn("hr_zones_last_week_pie_html", page)
        self.assertIn("aggregate_hr_zones_by_period", page)
        self.assertIn("last_full_week_hr_zone_shares", page)
        metrics = (
            Path(__file__).resolve().parents[2]
            / "dashboard"
            / "pages"
            / "metrics.py"
        ).read_text()
        self.assertNotIn("race_weeks_snap_html", metrics)
        self.assertNotIn("race_week_strip", metrics)

    def test_fitness_page_has_no_mileage_heatmap(self):
        """Mileage heatmap lives on Training, not Fitness."""
        fitness = (
            Path(__file__).resolve().parents[2]
            / "dashboard"
            / "pages"
            / "fitness.py"
        ).read_text()
        self.assertIn("pace_hr_line_chart", fitness)
        self.assertNotIn("hr_zones_stacked_area_chart", fitness)
        self.assertNotIn("mileage_heatmap_chart", fitness)
        self.assertNotIn("mileage_heatmap_matrix", fitness)
        self.assertNotIn("chart-mileage-heatmap", fitness)
        self.assertNotIn("heatmap_showing_label", fitness)
        self.assertNotIn("Heatmap", fitness)
        ui = (
            Path(__file__).resolve().parents[2] / "dashboard" / "ui.py"
        ).read_text()
        insights_nav = ui[
            ui.index("def render_insights_section_nav") : ui.index(
                "def render_metrics_section_nav"
            )
        ]
        self.assertIn("chart-pace-hr", insights_nav)
        self.assertIn("chart-race-weeks", insights_nav)
        self.assertNotIn("chart-hr-zones", insights_nav)
        self.assertIn("chart-fitness-freshness", insights_nav)
        self.assertNotIn("chart-mileage-heatmap", insights_nav)
        self.assertNotIn("heatmap_title", insights_nav)
        training_nav = ui[
            ui.index("def render_sidebar_section_nav") : ui.index(
                "def render_race_section_nav"
            )
        ]
        self.assertIn("chart-hr-zones", training_nav)
        self.assertIn("hr_zones_title", training_nav)
        self.assertLess(
            training_nav.find("chart-compliance"),
            training_nav.find("chart-mileage"),
        )
        self.assertLess(
            training_nav.find("chart-mileage"),
            training_nav.find("chart-elevation"),
        )
        self.assertLess(
            training_nav.find("chart-elevation"),
            training_nav.find("chart-hr-zones"),
        )

    def test_race_week_strip_compact_box_css(self):
        self.assertIn(".st-key-race_week_strip::before", GLOBAL_CSS)
        self.assertIn(
            "calc(100% - var(--training-plot-margin-r) + var(--race-strip-end-pad))",
            GLOBAL_CSS,
        )
        self.assertIn("--training-plot-margin-r:", GLOBAL_CSS)
        self.assertIn("--race-strip-end-pad:", GLOBAL_CSS)
        self.assertIn("var(--race-strip-bg)", GLOBAL_CSS)
        self.assertIn("--race-strip-bg: rgba(0,0,0,0)", GLOBAL_CSS)
        self.assertIn("text-shadow: 0 0 8px", GLOBAL_CSS)
        self.assertNotIn("0 8px 16px rgba(21, 32, 40, 0.08)", GLOBAL_CSS)
        self.assertIn(CHART_RACE_WEEKS_MARGIN_TOP, GLOBAL_CSS)
        self.assertNotIn(".st-key-race_week_strip_mileage", GLOBAL_CSS)
        self.assertNotIn(".st-key-race_week_strip_elevation", GLOBAL_CSS)
        self.assertIn(".st-key-training_compliance", GLOBAL_CSS)
        self.assertIn(".compliance-info", GLOBAL_CSS)
        self.assertIn(".compliance-chart-title", GLOBAL_CSS)
        self.assertIn(".compliance-info .kpi-info", GLOBAL_CSS)
        self.assertIn("--chart-compliance-margin-top:", GLOBAL_CSS)
        info_block = GLOBAL_CSS.split(".compliance-info {", 1)[1].split("}", 1)[0]
        self.assertIn("display: inline-flex;", info_block)
        self.assertIn("align-items: center;", info_block)
        self.assertIn("gap: 0.28rem;", info_block)
        tip_block = GLOBAL_CSS.split(".compliance-info .kpi-tooltip {", 1)[1].split(
            "}", 1
        )[0]
        self.assertIn("left: calc(100% + 0.35rem);", tip_block)
        self.assertIn(".st-key-training_mileage", GLOBAL_CSS)
        self.assertIn(".st-key-training_mileage_heatmap", GLOBAL_CSS)
        self.assertIn(".st-key-training_elevation", GLOBAL_CSS)
        self.assertIn("height: 40px !important", GLOBAL_CSS)
        self.assertIn("max-height: 40px !important", GLOBAL_CSS)

    def test_race_events_title_is_constant(self):
        from charts import RACE_EVENTS_TITLE

        self.assertEqual(RACE_EVENTS_TITLE, "Races")

    def test_race_weeks_legend_explains_markers(self):
        html = race_weeks_legend_html()
        self.assertIn("race-week-legend", html)
        self.assertIn("Races", html)
        self.assertNotIn("Race events", html)
        self.assertNotIn("Race weeks", html)
        self.assertIn('aria-label="About races"', html)
        self.assertIn("<strong>Races</strong>", html)
        self.assertIn("kpi-info", html)
        self.assertIn("kpi-tooltip", html)
        # Tooltip is nested under .kpi-info (info-button-only), not the label.
        info_idx = html.index("kpi-info")
        tooltip_idx = html.index("kpi-tooltip")
        self.assertLess(info_idx, tooltip_idx)
        self.assertIn("Training period (no race)", html)
        self.assertIn("Race in this period", html)
        self.assertEqual(html.count("race-legend-row"), 2)
        self.assertIn("race-legend-marker", html)
        self.assertIn(RACE_STRIP_SQUARE_COLOR, html)
        self.assertIn(RACE_STRIP_DIAMOND_COLOR, html)
        self.assertNotIn("Race types", html)
        self.assertNotIn(RACE_TYPE_COLORS["5k"], html)
        self.assertNotIn(RACE_TYPE_COLORS["Marathon"], html)
        self.assertNotIn("Race Days", html)
        self.assertNotIn("Race Weeks", html)
        self.assertNotIn("Race Months", html)
        self.assertNotIn("Race Years", html)
        # Legend popup opens on ⓘ only (global .kpi-info rules), not label hover.
        self.assertNotIn(".race-week-legend:hover .kpi-tooltip", GLOBAL_CSS)
        self.assertNotIn(".race-week-legend:focus-within .kpi-tooltip", GLOBAL_CSS)
        self.assertIn(".kpi-info:hover .kpi-tooltip", GLOBAL_CSS)
        # Label + ⓘ sit on one horizontal line in the left margin.
        self.assertIn("flex-direction: row", GLOBAL_CSS)
        legend_css_idx = GLOBAL_CSS.index(".race-week-legend {")
        row_idx = GLOBAL_CSS.index("flex-direction: row", legend_css_idx)
        self.assertLess(row_idx - legend_css_idx, 200)
        # Tooltip legend rows: marker column + label, center-aligned.
        self.assertIn(".kpi-tooltip .race-legend-row {", GLOBAL_CSS)
        self.assertIn("align-items: center", GLOBAL_CSS)
        # Body text ink (not muted); headers may stay muted uppercase.
        self.assertIn(
            f".kpi-tooltip {{\n    visibility: hidden;\n    opacity: 0;",
            GLOBAL_CSS,
        )
        tip_idx = GLOBAL_CSS.index(".kpi-tooltip {\n    visibility: hidden;")
        tip_block = GLOBAL_CSS[tip_idx : tip_idx + 500]
        self.assertIn(f"color: {INK} !important", tip_block)
        self.assertNotIn(f"color: {MUTED}", tip_block.split("}", 1)[0])
        strong_block = GLOBAL_CSS.split(".kpi-tooltip strong {", 1)[1].split("}", 1)[0]
        self.assertIn(f"color: {MUTED} !important", strong_block)
        self.assertIn(".kpi-tooltip .race-legend-marker {", GLOBAL_CSS)


class FitnessHrZoneChartTests(unittest.TestCase):
    """100% stacked HR-zone area chart on Training."""

    def _period_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "period_key": ["2026-10", "2026-11"],
                "period_label": ["Mar 2, 26", "Mar 9, 26"],
                "period_tooltip": [
                    "Mar 2, 2026 - Mar 8, 2026",
                    "Mar 9, 2026 - Mar 15, 2026",
                ],
                "zone_1_pct": [20.0, np.nan],
                "zone_2_pct": [50.0, np.nan],
                "zone_3_pct": [20.0, np.nan],
                "zone_4_pct": [10.0, np.nan],
                "zone_5_pct": [0.0, np.nan],
                "in_progress": [False, True],
            }
        )

    def test_five_area_traces_y_in_0_100(self):
        fig = hr_zones_stacked_area_chart(self._period_df(), "Week")
        area = [t for t in fig.data if getattr(t, "type", None) == "scatter"]
        self.assertEqual(len(area), 5)
        self.assertEqual(
            [trace.name for trace in area],
            ["Zone 1", "Zone 2", "Zone 3", "Zone 4", "Zone 5"],
        )
        expected_first = [20.0, 50.0, 20.0, 10.0, 0.0]
        for trace, color, first_y in zip(
            area, HR_ZONE_COLORS, expected_first, strict=True
        ):
            self.assertEqual(trace.type, "scatter")
            self.assertEqual(trace.stackgroup, HR_ZONE_STACKGROUP)
            self.assertFalse(trace.connectgaps)
            self.assertEqual(trace.line.color, color)
            self.assertEqual(trace.fillcolor, color)
            y_vals = list(trace.y)
            self.assertEqual(len(y_vals), 2)
            self.assertAlmostEqual(float(y_vals[0]), first_y)
            self.assertTrue(y_vals[1] is None or (isinstance(y_vals[1], float) and np.isnan(y_vals[1])))
            self.assertGreaterEqual(float(y_vals[0]), 0.0)
            self.assertLessEqual(float(y_vals[0]), 100.0)
        self.assertEqual(tuple(fig.layout.yaxis.range), (0, 100))
        self.assertEqual(fig.layout.yaxis.ticksuffix, "%")
        self.assertEqual(fig.layout.title.text, "Weekly Heart Rate Zones")
        self.assertEqual(hr_zones_title("Week"), "Weekly Heart Rate Zones")
        self.assertEqual(
            HR_ZONE_COLORS,
            ("#6B9B96", "#509B8F", "#E3C677", "#D87659", "#A33B3B"),
        )
        self.assertEqual(HR_ZONE_COLORS[1], MILEAGE_BAR)
        self.assertEqual(HR_ZONE_COLORS[2], RACE_STRIP_DIAMOND_COLOR)
        self.assertEqual(HR_ZONE_COLORS[3], TRAINING_HARD)

    def test_last_week_pie_under_legend(self):
        """Donut HTML sits in the right gutter; Plotly figure has no pie trace."""
        last_week = {
            "week_key": "2026-10",
            "week_label": "Mar 2, 2026 - Mar 8, 2026",
            "zone_1_pct": 40.0,
            "zone_2_pct": 30.0,
            "zone_3_pct": 20.0,
            "zone_4_pct": 10.0,
            "zone_5_pct": 0.0,
            "zone_1_sec": 240.0,
            "zone_2_sec": 180.0,
            "zone_3_sec": 120.0,
            "zone_4_sec": 60.0,
            "zone_5_sec": 0.0,
        }
        fig = hr_zones_stacked_area_chart(self._period_df(), "Week")
        pies = [t for t in fig.data if getattr(t, "type", None) == "pie"]
        self.assertEqual(len(pies), 0)
        self.assertEqual(fig.layout.margin.r, FITNESS_MARGIN_R)

        html = hr_zones_last_week_pie_html(last_week)
        self.assertIn("hr-zones-pie-gutter", html)
        self.assertIn("hr-zones-pie-panel", html)
        self.assertIn("hr-zones-pie-donut", html)
        self.assertIn("hr-zones-pie-slice", html)
        self.assertIn("hr-zones-pie-tip", html)
        self.assertIn("Last week", html)
        self.assertIn("Mar 2, 2026 - Mar 8, 2026", html)
        self.assertIn("<svg", html)
        self.assertNotIn("conic-gradient", html)
        # Zero-share zones omit a path (no hover target); colors for used wedges only.
        for color in HR_ZONE_COLORS[:4]:
            self.assertIn(color, html)
        self.assertNotIn(HR_ZONE_COLORS[4], html)
        self.assertIn("Zone 1: 40% · 04:00", html)
        self.assertIn("<strong>Zone 1</strong>", html)
        self.assertIn("40% of HR time", html)
        self.assertIn("04:00", html)
        self.assertIn("Zone 2: 30% · 03:00", html)
        self.assertIn("01:00", html)  # zone 4 duration

        empty = hr_zones_last_week_pie_html({"week_label": "Mar 2, 2026 - Mar 8, 2026"})
        self.assertIn("hr-zones-pie-empty", empty)
        self.assertIn("No HR data", empty)

    def test_week_hover_uses_iso_week_range(self):
        """Unified hover header (x) and customdata are abbreviated Mon–Sun ranges."""
        fig = hr_zones_stacked_area_chart(self._period_df(), "Week")
        expected = ["Mar 2, 2026 - Mar 8, 2026", "Mar 9, 2026 - Mar 15, 2026"]
        area = [t for t in fig.data if getattr(t, "type", None) == "scatter"]
        for trace in area:
            self.assertEqual(list(trace.x), expected)
            self.assertEqual(list(trace.customdata), expected)
            self.assertIn("Zone", trace.hovertemplate)
            self.assertNotIn("%{x}", trace.hovertemplate)
        self.assertEqual(list(fig.layout.xaxis.ticktext), ["Mar 2, 26", "Mar 9, 26"])
        self.assertEqual(list(fig.layout.xaxis.tickvals), expected)

    def test_empty_chart_keeps_percent_axis(self):
        fig = hr_zones_stacked_area_chart(pd.DataFrame(), "Month")
        area = [t for t in fig.data if getattr(t, "type", None) == "scatter"]
        self.assertEqual(len(area), 0)
        self.assertEqual(tuple(fig.layout.yaxis.range), (0, 100))
        self.assertEqual(fig.layout.title.text, "Monthly Heart Rate Zones")

    def test_training_page_wires_hr_zones_chart(self):
        training = (
            Path(__file__).resolve().parents[2]
            / "dashboard"
            / "pages"
            / "training.py"
        ).read_text()
        fitness = (
            Path(__file__).resolve().parents[2]
            / "dashboard"
            / "pages"
            / "fitness.py"
        ).read_text()
        self.assertIn("hr_zones_stacked_area_chart", training)
        self.assertIn("aggregate_hr_zones_by_period", training)
        self.assertIn("last_full_week_hr_zone_shares", training)
        self.assertIn("hr_zones_last_week_pie_html", training)
        self.assertIn("hr_zones_last_week_pie_html(last_week_zones)", training)
        self.assertIn("hr_zones_stacked_area_chart(zone_periods, grain)", training)
        self.assertNotIn("last_week_zones=", training)
        self.assertIn('id="chart-hr-zones"', training)
        self.assertNotIn("hr_zones_stacked_area_chart", fitness)
        self.assertNotIn('id="chart-hr-zones"', fitness)
        self.assertLess(training.find("chart-compliance"), training.find("chart-mileage"))
        self.assertLess(training.find("chart-mileage"), training.find("chart-elevation"))
        self.assertLess(training.find("chart-elevation"), training.find("chart-hr-zones"))
        self.assertIn("#chart-hr-zones", GLOBAL_CSS)
        self.assertIn("--chart-hr-zones-margin-top:", GLOBAL_CSS)
        self.assertIn(".hr-zones-pie-gutter", GLOBAL_CSS)
        self.assertIn(".hr-zones-pie-panel", GLOBAL_CSS)
        self.assertIn(".hr-zones-pie-donut", GLOBAL_CSS)
        self.assertIn(".hr-zones-pie-slice", GLOBAL_CSS)
        self.assertIn(".hr-zones-pie-tip", GLOBAL_CSS)
        tip_block = GLOBAL_CSS.split(
            ".hr-zones-pie-donut .hr-zones-pie-tip {", 1
        )[1].split("}", 1)[0]
        self.assertIn("width: min(12rem, 72vw);", tip_block)
        self.assertIn("width: var(--fitness-plot-margin-r)", GLOBAL_CSS)
        self.assertEqual(CHART_HR_ZONES_MARGIN_TOP, "1.85rem")
        self.assertEqual(CHART_PACE_HR_MARGIN_TOP, "2.75rem")
        # Avg HR title is HTML (outside Plotly); hover swatch still scoped to this chart.
        self.assertIn(".pace-hr-info", GLOBAL_CSS)
        self.assertIn(".pace-hr-chart-title", GLOBAL_CSS)
        self.assertIn(".pace-hr-chart-subtitle", GLOBAL_CSS)
        pace_hr_title_css = GLOBAL_CSS.split(
            '[data-testid="stElementContainer"]:has(.pace-hr-info)',
            1,
        )[1]
        self.assertIn("overflow: visible !important;", pace_hr_title_css[:800])
        self.assertIn("margin-bottom: -2.85rem !important", pace_hr_title_css[:800])
        # Unified hover color swatch (legend line/marker) hidden for this chart only.
        hover_swatch_css = GLOBAL_CSS.split(
            "Avg HR by Pace: unified hover has no Plotly API to drop the trace color",
            1,
        )[1].split("/* Training: HR zone", 1)[0]
        self.assertIn(".hoverlayer", hover_swatch_css)
        self.assertIn(".legendlines", hover_swatch_css)
        self.assertIn(".legendsymbols", hover_swatch_css)
        self.assertIn(".legendfill", hover_swatch_css)
        self.assertIn("display: none !important;", hover_swatch_css)
        ui = (
            Path(__file__).resolve().parents[2] / "dashboard" / "ui.py"
        ).read_text()
        training_nav = ui[
            ui.index("def render_sidebar_section_nav") : ui.index(
                "def render_race_section_nav"
            )
        ]
        self.assertIn("chart-hr-zones", training_nav)
        self.assertIn("hr_zones_title", training_nav)
        insights_nav = ui[
            ui.index("def render_insights_section_nav") : ui.index(
                "def render_metrics_section_nav"
            )
        ]
        self.assertIn("chart-pace-hr", insights_nav)
        self.assertIn("chart-race-weeks", insights_nav)
        self.assertNotIn("chart-hr-zones", insights_nav)


class FitnessPaceHrChartTests(unittest.TestCase):
    """Average HR line chart on Fitness."""

    def _period_df(self, avg_hr: list[float] | None = None) -> pd.DataFrame:
        values = [148.0, 152.0] if avg_hr is None else avg_hr
        return pd.DataFrame(
            {
                "period_key": ["2026-10", "2026-11"],
                "period_label": ["Mar 2, 26", "Mar 9, 26"],
                "period_tooltip": [
                    "Mar 2, 2026 - Mar 8, 2026",
                    "Mar 9, 2026 - Mar 15, 2026",
                ],
                "avg_hr": values,
                "in_progress": [False, True],
            }
        )

    def _brightness(self, color: str) -> float:
        hex_color = color.lstrip("#")
        r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
        return 0.299 * r + 0.587 * g + 0.114 * b

    def test_week_hover_uses_iso_week_range(self):
        """Hover body uses the abbreviated ISO week Mon–Sun range on period labels."""
        fig = pace_hr_line_chart(
            [("8:00-8:30", self._period_df())],
            "Week",
        )
        self.assertEqual(len(fig.data), 1)
        scatter = fig.data[0]
        expected_x = ["Mar 2, 26", "Mar 9, 26"]
        expected_tooltips = [
            "Mar 2, 2026 - Mar 8, 2026",
            "Mar 9, 2026 - Mar 15, 2026",
        ]
        self.assertEqual(list(scatter.x), expected_x)
        self.assertEqual(list(fig.layout.xaxis.ticktext), expected_x)
        self.assertEqual(tuple(fig.layout.xaxis.range), (-0.5, 1.5))
        self.assertEqual(fig.layout.hovermode, "x unified")
        self.assertIn("Avg HR:", scatter.hovertemplate)
        self.assertIn("4-week avg:", scatter.hovertemplate)
        self.assertIn("%{customdata[0]}", scatter.hovertemplate)
        self.assertIn("%{customdata[1]", scatter.hovertemplate)
        self.assertNotIn("Trend", scatter.hovertemplate)
        self.assertNotIn("%{fullData.name}", scatter.hovertemplate)
        self.assertNotIn("8:00-8:30", scatter.hovertemplate)
        self.assertEqual(scatter.hoverlabel.namelength, 0)
        self.assertEqual(fig.layout.hoverlabel.namelength, 0)
        self.assertEqual(
            [list(row) for row in scatter.customdata],
            [[tip, hr] for tip, hr in zip(expected_tooltips, [148.0, 152.0])],
        )
        self.assertEqual(scatter.name, "8:00-8:30")
        self.assertEqual(scatter.mode, "lines")

    def test_multiple_traces_use_fixed_bin_colors_darker_equals_faster(self):
        """Selected bins keep full-list colors; fastest is darkest teal."""
        from dashboard.pace_bins import PACE_BIN_OPTIONS

        series = [
            ("7:30-8:00", self._period_df([150.0, 151.0])),
            ("8:00-8:30", self._period_df([148.0, 152.0])),
            ("8:30-9:00", self._period_df([146.0, 149.0])),
        ]
        fig = pace_hr_line_chart(series, "Week")
        self.assertEqual(len(fig.data), 3)
        color_map = pace_hr_bin_color_map()
        colors = pace_hr_series_colors([label for label, _ in series])
        self.assertEqual(colors, [color_map[label] for label, _ in series])
        # Full list has more than 3 bins, so these mid bins are not scale endpoints.
        all_labels = [label for label, _ in PACE_BIN_OPTIONS]
        self.assertGreater(len(all_labels), 3)
        self.assertNotEqual(colors[0], PACE_HR_COLORSCALE[-1][1])
        self.assertNotEqual(colors[-1], PACE_HR_COLORSCALE[0][1])
        for scatter, expected_name, expected_color in zip(
            fig.data,
            ["7:30-8:00", "8:00-8:30", "8:30-9:00"],
            colors,
        ):
            self.assertEqual(scatter.name, expected_name)
            self.assertEqual(scatter.mode, "lines")
            self.assertEqual(scatter.line.color, expected_color)
            self.assertNotIn("Trend", scatter.name)
        self.assertLess(self._brightness(colors[0]), self._brightness(colors[1]))
        self.assertLess(self._brightness(colors[1]), self._brightness(colors[2]))
        self.assertTrue(fig.layout.showlegend)

    def test_rolling_trend_only_per_bin(self):
        """Each pace bin draws only the trailing rolling-mean trend (no raw series)."""
        hr = [140.0, 150.0, 160.0, 170.0]
        period_df = pd.DataFrame(
            {
                "period_key": [f"2026-{i}" for i in range(10, 14)],
                "period_label": [f"W{i}" for i in range(1, 5)],
                "period_tooltip": [f"week {i}" for i in range(1, 5)],
                "avg_hr": hr,
                "in_progress": [False, False, False, True],
            }
        )
        self.assertEqual(pace_hr_trend_window("Week"), 4)
        self.assertEqual(pace_hr_trend_window("Day"), 5)
        self.assertEqual(pace_hr_trend_window("Month"), 3)
        self.assertEqual(pace_hr_trend_subtitle("Week"), "4-week rolling average")
        self.assertEqual(pace_hr_trend_subtitle("Day"), "5-day rolling average")
        self.assertEqual(pace_hr_trend_subtitle("Month"), "3-month rolling average")
        self.assertEqual(pace_hr_trend_subtitle("Year"), "3-year rolling average")

        fig = pace_hr_line_chart([("8:00-8:30", period_df)], "Week")
        self.assertEqual(len(fig.data), 1)
        trend = fig.data[0]
        self.assertEqual(trend.name, "8:00-8:30")
        self.assertEqual(trend.mode, "lines")
        self.assertNotEqual(getattr(trend.line, "dash", None), "dash")
        self.assertIn("Avg HR:", trend.hovertemplate)
        self.assertIn("4-week avg:", trend.hovertemplate)
        self.assertNotIn("Trend", trend.hovertemplate)
        self.assertEqual(fig.layout.title.text, "")
        self.assertEqual(
            [list(row) for row in trend.customdata],
            [[f"week {i}", hr] for i, hr in zip(range(1, 5), hr, strict=True)],
        )
        # Trailing mean with min_periods=1: first = 140, second = 145, …
        expected = [140.0, 145.0, 150.0, 155.0]
        self.assertEqual([float(y) for y in trend.y], expected)

        multi = pace_hr_line_chart(
            [
                ("7:30-8:00", period_df),
                ("8:00-8:30", period_df),
            ],
            "Week",
        )
        self.assertEqual(len(multi.data), 2)
        self.assertEqual(multi.data[0].name, "7:30-8:00")
        self.assertEqual(multi.data[1].name, "8:00-8:30")
        self.assertEqual(multi.data[0].legendgroup, "7:30-8:00")
        self.assertEqual(multi.data[1].legendgroup, "8:00-8:30")
        # Multi-bin hover keeps pace as body text (not Plotly series-name header).
        self.assertIn("7:30-8:00", multi.data[0].hovertemplate)
        self.assertIn("8:00-8:30", multi.data[1].hovertemplate)
        self.assertIn("Avg HR:", multi.data[0].hovertemplate)
        self.assertNotIn("%{fullData.name}", multi.data[0].hovertemplate)

    def test_pace_colors_are_static_not_selection_relative(self):
        """A lone slow bin stays light; Under 7:00 stays darkest alone or with peers."""
        color_map = pace_hr_bin_color_map()
        under = "Under 7:00"
        slow = "9:30-10:00"
        self.assertIn(under, color_map)
        self.assertIn(slow, color_map)
        self.assertEqual(color_map[under], PACE_HR_COLORSCALE[-1][1])
        self.assertEqual(color_map[slow], pace_hr_series_colors([slow])[0])
        self.assertEqual(
            pace_hr_series_colors([under]),
            [color_map[under]],
        )
        self.assertEqual(
            pace_hr_series_colors([under, slow]),
            [color_map[under], color_map[slow]],
        )
        # Slow alone must not jump to the dark end (old selection-relative behavior).
        self.assertNotEqual(pace_hr_series_colors([slow])[0], PACE_HR_COLORSCALE[-1][1])
        self.assertGreater(
            self._brightness(color_map[slow]),
            self._brightness(color_map[under]),
        )
        fig = pace_hr_line_chart([(slow, self._period_df())], "Week")
        self.assertEqual(fig.data[0].line.color, color_map[slow])

    def test_single_default_bin_uses_fixed_mid_scale_color(self):
        colors = pace_hr_series_colors(["8:00-8:30"])
        self.assertEqual(len(colors), 1)
        self.assertEqual(colors[0], pace_hr_bin_color_map()["8:00-8:30"])
        self.assertNotEqual(colors[0], PACE_HR_COLORSCALE[-1][1])
        fig = pace_hr_line_chart([("8:00-8:30", self._period_df())], "Week")
        self.assertEqual(fig.data[0].line.color, colors[0])
        self.assertEqual(fig.layout.title.text, "")
        # Heading + rolling subtitle are HTML (``pace_hr_title_html``); Plotly
        # top margin matches other Fitness charts.
        self.assertEqual(fig.layout.margin.t, PACE_HR_MARGIN_T)
        self.assertEqual(PACE_HR_MARGIN["t"], PACE_HR_MARGIN_T)
        self.assertEqual(PACE_HR_MARGIN_T, FITNESS_MARGIN_T)
        self.assertEqual(
            pace_hr_title("Week", ["8:00-8:30"]),
            "Average HR for 8:00-8:30 min/mile pace",
        )
        html = pace_hr_title_html(
            pace_hr_title("Week", ["8:00-8:30"]),
            pace_hr_trend_subtitle("Week"),
        )
        self.assertIn("Average HR for 8:00-8:30 min/mile pace", html)
        self.assertIn("4-week rolling average", html)
        self.assertIn('class="pace-hr-chart-title"', html)
        self.assertIn('class="pace-hr-chart-title-row"', html)
        self.assertIn('class="pace-hr-chart-subtitle"', html)
        self.assertIn("kpi-info", html)
        self.assertIn("kpi-tooltip", html)
        self.assertIn("ⓘ", html)
        self.assertLess(
            html.index("pace-hr-chart-title"),
            html.index("kpi-info"),
        )
        self.assertLess(
            html.index("kpi-info"),
            html.index("pace-hr-chart-subtitle"),
        )
        self.assertIn("Why pace bands", html)
        self.assertIn("Hills", html)
        self.assertIn("ft/mi", html)
        self.assertIn("GAP", html)
        self.assertIn("Comparing bands", html)
        self.assertIn("Pace Range", html)
        self.assertIn("fitness signal", html.lower())
        self.assertIn(".pace-hr-info .kpi-info", GLOBAL_CSS)
        tip_block = GLOBAL_CSS.split(".pace-hr-info .kpi-tooltip {", 1)[1].split(
            "}", 1
        )[0]
        self.assertIn("left: calc(100% + 0.35rem);", tip_block)

    def test_multi_bin_title_is_generic(self):
        self.assertEqual(
            pace_hr_title("Week", ["7:30-8:00", "8:00-8:30"]),
            "Average HR by Pace Range",
        )
        fig = pace_hr_line_chart(
            [
                ("7:30-8:00", self._period_df()),
                ("8:00-8:30", self._period_df()),
            ],
            "Week",
        )
        self.assertEqual(fig.layout.title.text, "")
        html = pace_hr_title_html(
            pace_hr_title("Week", ["7:30-8:00", "8:00-8:30"]),
            pace_hr_trend_subtitle("Week"),
        )
        self.assertIn("Average HR by Pace Range", html)
        self.assertIn("4-week rolling average", html)
        self.assertIn("kpi-info", html)

    def test_fitness_page_uses_pace_multiselect(self):
        fitness = (
            Path(__file__).resolve().parents[2]
            / "dashboard"
            / "pages"
            / "fitness.py"
        ).read_text()
        self.assertIn("st.multiselect", fitness)
        self.assertIn('key="insights_pace_bins"', fitness)
        self.assertIn("default=[default_label]", fitness)
        self.assertIn("DEFAULT_PACE_BIN_KEY", fitness)
        self.assertIn("pace_hr_line_chart(hr_series, grain, period_df=period_metrics)", fitness)
        self.assertIn("race_weeks_chart(period_metrics, grain, plot=\"fitness\")", fitness)
        self.assertIn("_race_week_strip(period_metrics, grain)", fitness)
        self.assertIn("annotate_race_periods", fitness)
        self.assertIn("merge_race_period_annotations", fitness)
        self.assertIn("pace_hr_title_html", fitness)
        self.assertIn("pace_hr_trend_subtitle(grain)", fitness)
        self.assertNotIn('key="insights_pace_bin"', fitness)

    def test_pace_hr_chart_has_no_efficiency_dual_axis(self):
        """Average HR by Pace is HR-only; efficiency lives on its own chart."""
        series = [
            ("7:30-8:00", self._period_df([150.0, 151.0])),
            ("8:00-8:30", self._period_df([148.0, 152.0])),
        ]
        fig = pace_hr_line_chart(series, "Week")
        self.assertEqual(len(fig.data), 2)
        self.assertEqual(fig.data[0].name, "7:30-8:00")
        self.assertEqual(fig.data[1].name, "8:00-8:30")
        for scatter in fig.data:
            self.assertNotEqual(getattr(scatter, "yaxis", "y"), "y2")
            self.assertNotEqual(scatter.name, "Aerobic Efficiency")
            self.assertEqual(scatter.mode, "lines")
        self.assertFalse(hasattr(fig.layout, "yaxis2") and fig.layout.yaxis2)
        self.assertEqual(fig.layout.yaxis.title.text, "Average HR (bpm)")

    def test_fitness_page_keeps_standalone_efficiency_chart(self):
        fitness = (
            Path(__file__).resolve().parents[2]
            / "dashboard"
            / "pages"
            / "fitness.py"
        ).read_text()
        self.assertIn("pace_hr_line_chart(hr_series, grain, period_df=period_metrics)", fitness)
        self.assertIn("race_weeks_chart(period_metrics, grain, plot=\"fitness\")", fitness)
        self.assertIn("_race_week_strip(period_metrics, grain)", fitness)
        self.assertIn("annotate_race_periods", fitness)
        self.assertIn("merge_race_period_annotations", fitness)
        self.assertNotIn(
            "pace_hr_line_chart(hr_series, grain, efficiency_periods)",
            fitness,
        )
        self.assertIn("aerobic_efficiency_line_chart(efficiency_periods, grain)", fitness)

    def test_fitness_pace_multiselect_css_uses_teal_chips_and_readable_width(self):
        """Pace chips teal; Pace Range ~90% (Show By 75%); wrap, hug single chip."""
        from dashboard.theme import INK, PACE_MULTISELECT_CHIP

        self.assertIn(".st-key-insights_pace_bins", GLOBAL_CSS)
        self.assertIn("[data-tag]", GLOBAL_CSS)
        self.assertIn(f"background: {PACE_MULTISELECT_CHIP} !important", GLOBAL_CSS)
        self.assertIn(f"background-color: {PACE_MULTISELECT_CHIP} !important", GLOBAL_CSS)
        self.assertEqual(PACE_MULTISELECT_CHIP.lower(), "#b7ddd8")
        chip_block = GLOBAL_CSS.split(".st-key-insights_pace_bins [data-tag]")[1][:800]
        self.assertIn(f"color: {INK} !important", chip_block)
        self.assertIn("text-overflow: clip !important", chip_block)
        self.assertIn("min-width: 0 !important", chip_block)
        # Show By stays compact 75%; Pace Range slightly wider for “Choose options”.
        self.assertIn(
            '[data-testid="stColumn"]:has(.controls-panel--compact) [data-testid="stMultiSelect"]',
            GLOBAL_CSS,
        )
        self.assertIn("max-width: 75% !important", GLOBAL_CSS)
        self.assertIn("width: 75% !important", GLOBAL_CSS)
        self.assertIn(
            ".st-key-insights_pace_bins [data-testid=\"stMultiSelect\"]",
            GLOBAL_CSS,
        )
        self.assertIn("max-width: 90% !important", GLOBAL_CSS)
        self.assertIn("width: 90% !important", GLOBAL_CSS)
        self.assertIn(".fitness-pace-bins-anchor", GLOBAL_CSS)
        self.assertNotIn("min-width: 11.5rem !important", GLOBAL_CSS)
        self.assertNotIn("max-width: 14.5rem", GLOBAL_CSS)
        self.assertIn("box-sizing: border-box !important", GLOBAL_CSS)
        self.assertIn("max-height: none !important", GLOBAL_CSS)
        self.assertIn("flex-wrap: wrap !important", GLOBAL_CSS)
        self.assertIn("overflow-x: hidden", GLOBAL_CSS)
        # Single chip: collapse filter input so it does not leave a blank second row.
        self.assertIn(
            '[data-testid="stMultiSelectTagsContainer"]:has([data-tag]) input',
            GLOBAL_CSS,
        )
        self.assertIn("align-content: flex-start !important", GLOBAL_CSS)
        # SHOWING must not be vertically clipped by the Avg HR column.
        avg_hr_overflow = GLOBAL_CSS.split(
            "[data-testid=\"stColumn\"]:has(.insights-controls-panel)"
        )
        self.assertTrue(
            any(
                "nth-child(2)" in block
                and "overflow-x: clip" in block
                and "overflow-y: visible" in block
                for block in avg_hr_overflow
            ),
            "Avg HR column should use overflow-x:clip / overflow-y:visible",
        )

    def test_fitness_controls_card_uses_teal_accent_and_breathing_room(self):
        """Controls reads as chrome beside the charts, not as a fourth chart."""
        card_block = GLOBAL_CSS.split(
            '[data-testid="column"]:has(.insights-controls-panel) {', 1
        )[1].split("}", 1)[0]
        self.assertIn("border-color: rgba(80, 155, 143, 0.20) !important;", card_block)
        self.assertIn("inset 0 1px 0 rgba(255, 255, 255, 0.75)", card_block)
        self.assertIn("padding: 1.2rem 1.35rem 1.3rem !important;", card_block)
        # No teal keyline before the Controls label (removed; border tint is enough).
        self.assertNotIn(".controls-title::before", GLOBAL_CSS)
        # Border teal matches mileage / Form series (`MILEAGE_BAR` = #509B8F).
        self.assertEqual(MILEAGE_BAR, "#509B8F")


class FitnessAerobicEfficiencyChartTests(unittest.TestCase):
    """Elevation-adjusted aerobic-efficiency line chart on Fitness."""

    def _period_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "period_key": ["2026-10", "2026-11", "2026-12"],
                "period_label": ["Mar 2, 26", "Mar 9, 26", "Mar 16, 26"],
                "period_tooltip": [
                    "Mar 2, 2026 - Mar 8, 2026",
                    "Mar 9, 2026 - Mar 15, 2026",
                    "Mar 16, 2026 - Mar 22, 2026",
                ],
                "residual": [0.002, np.nan, -0.001],
                "efficiency": [0.050, np.nan, 0.048],
                "elev_ft_per_mile": [40.0, np.nan, 80.0],
                "in_progress": [False, False, True],
            }
        )

    def test_line_trace_gaps_missing_periods(self):
        fig = aerobic_efficiency_line_chart(self._period_df(), "Week")
        self.assertEqual(len(fig.data), 3)
        scatter, legend_proxy, trend = fig.data
        self.assertEqual(scatter.type, "scatter")
        self.assertEqual(scatter.mode, "lines+markers")
        self.assertEqual(scatter.name, "Aerobic Efficiency")
        self.assertFalse(scatter.showlegend)
        self.assertEqual(scatter.legendgroup, "Aerobic Efficiency")
        self.assertEqual(scatter.line.color, ELEVATION_BAR)
        self.assertEqual(scatter.marker.color, ELEVATION_BAR)
        self.assertFalse(scatter.connectgaps)
        y_vals = list(scatter.y)
        self.assertEqual(len(y_vals), 3)
        self.assertAlmostEqual(float(y_vals[0]), 0.002)
        self.assertTrue(y_vals[1] is None or (isinstance(y_vals[1], float) and np.isnan(y_vals[1])))
        self.assertAlmostEqual(float(y_vals[2]), -0.001)
        # Legend shows a plain line (no marker symbol) for Aerobic Efficiency.
        self.assertEqual(legend_proxy.mode, "lines")
        self.assertEqual(legend_proxy.name, "Aerobic Efficiency")
        self.assertTrue(legend_proxy.showlegend)
        self.assertEqual(legend_proxy.legendgroup, "Aerobic Efficiency")
        self.assertEqual(legend_proxy.line.color, ELEVATION_BAR)
        self.assertEqual(legend_proxy.hoverinfo, "skip")
        self.assertEqual(trend.name, "Trend")
        self.assertEqual(trend.mode, "lines")
        self.assertEqual(trend.line.dash, "dash")
        self.assertTrue(trend.showlegend)
        self.assertEqual(trend.legendgroup, "Trend")
        self.assertFalse(trend.connectgaps)
        self.assertIn("4-week avg", trend.hovertemplate)
        # Plotly title is blank; HTML title row supplies the heading + ⓘ.
        self.assertEqual(fig.layout.title.text, "")
        self.assertEqual(
            aerobic_efficiency_title("Week"),
            "Weekly Aerobic Efficiency",
        )
        self.assertNotIn("elevation-adjusted", aerobic_efficiency_title("Week"))
        self.assertEqual(
            fig.layout.yaxis.title.text,
            "Aerobic Efficiency",
        )
        self.assertNotIn("elevation", (fig.layout.yaxis.title.text or "").lower())
        self.assertEqual(
            fig.layout.yaxis.title.standoff,
            AEROBIC_EFFICIENCY_Y_TITLE_STANDOFF,
        )
        self.assertEqual(AEROBIC_EFFICIENCY_Y_TITLE_STANDOFF, 32)
        self.assertEqual(FITNESS_MARGIN_L, 80)
        self.assertEqual(FITNESS_MARGIN_R, 168)
        self.assertEqual(fig.layout.margin.l, PACE_HR_MARGIN["l"])
        self.assertEqual(fig.layout.margin.r, PACE_HR_MARGIN["r"])
        self.assertEqual(fig.layout.margin.l, HR_ZONES_MARGIN["l"])
        self.assertEqual(fig.layout.margin.r, HR_ZONES_MARGIN["r"])
        self.assertEqual(fig.layout.margin.l, AEROBIC_EFFICIENCY_MARGIN["l"])
        self.assertEqual(fig.layout.margin.r, AEROBIC_EFFICIENCY_MARGIN["r"])
        self.assertEqual(fig.layout.margin.l, FITNESS_MARGIN_L)
        self.assertEqual(fig.layout.margin.r, FITNESS_MARGIN_R)
        self.assertEqual(tuple(fig.layout.xaxis.domain), tuple(FITNESS_XAXIS_DOMAIN))
        self.assertFalse(fig.layout.xaxis.automargin)
        self.assertFalse(fig.layout.yaxis.automargin)
        self.assertFalse(fig.layout.margin.autoexpand)
        self.assertTrue(fig.layout.showlegend)

    def test_fitness_charts_share_shortest_plot_margins(self):
        """Avg HR legend column sets the shortest plot; Efficiency + F&F match.

        HR Zones (Training) keeps the same L/R gutter constants for legend + pie.
        """
        pace_series = [
            (
                "7:30-8:00",
                pd.DataFrame(
                    {
                        "period_key": ["2026-10", "2026-11", "2026-12"],
                        "period_label": ["Mar 2, 26", "Mar 9, 26", "Mar 16, 26"],
                        "period_tooltip": [
                            "Mar 2, 2026 - Mar 8, 2026",
                            "Mar 9, 2026 - Mar 15, 2026",
                            "Mar 16, 2026 - Mar 22, 2026",
                        ],
                        "avg_hr": [150.0, 151.0, 152.0],
                        "in_progress": [False, False, True],
                    }
                ),
            )
        ]
        zone_df = pd.DataFrame(
            {
                "period_key": ["2026-10", "2026-11"],
                "period_label": ["Mar 2, 26", "Mar 9, 26"],
                "period_tooltip": [
                    "Mar 2, 2026 - Mar 8, 2026",
                    "Mar 9, 2026 - Mar 15, 2026",
                ],
                "zone_1_pct": [20.0, 25.0],
                "zone_2_pct": [50.0, 45.0],
                "zone_3_pct": [20.0, 20.0],
                "zone_4_pct": [10.0, 10.0],
                "zone_5_pct": [0.0, 0.0],
                "in_progress": [False, True],
            }
        )
        fitness_figs = [
            fitness_form_fatigue_line_chart(
                pd.DataFrame(
                    {
                        "period_key": ["2026-10", "2026-11", "2026-12"],
                        "period_label": ["Mar 2, 26", "Mar 9, 26", "Mar 16, 26"],
                        "period_tooltip": [
                            "Mar 2, 2026 - Mar 8, 2026",
                            "Mar 9, 2026 - Mar 15, 2026",
                            "Mar 16, 2026 - Mar 22, 2026",
                        ],
                        "fitness": [40.0, 42.0, 43.0],
                        "fatigue": [35.0, 38.0, 39.0],
                        "form": [5.0, 4.0, 4.0],
                        "load": [100.0, 110.0, 105.0],
                        "in_progress": [False, False, True],
                    }
                ),
                "Week",
            ),
            pace_hr_line_chart(pace_series, "Week"),
            aerobic_efficiency_line_chart(self._period_df(), "Week"),
        ]
        margins = {(fig.layout.margin.l, fig.layout.margin.r) for fig in fitness_figs}
        self.assertEqual(margins, {(FITNESS_MARGIN_L, FITNESS_MARGIN_R)})
        domains = {tuple(fig.layout.xaxis.domain) for fig in fitness_figs}
        self.assertEqual(domains, {tuple(FITNESS_XAXIS_DOMAIN)})
        ranges = {tuple(fig.layout.xaxis.range) for fig in fitness_figs}
        self.assertEqual(ranges, {(-0.5, 2.5)})
        # Rotated Y titles share one standoff so the three left edges line up.
        standoffs = {fig.layout.yaxis.title.standoff for fig in fitness_figs}
        self.assertEqual(standoffs, {FITNESS_Y_TITLE_STANDOFF})
        for fig in fitness_figs:
            self.assertFalse(fig.layout.xaxis.automargin)
            self.assertFalse(fig.layout.yaxis.automargin)
            self.assertFalse(fig.layout.margin.autoexpand)
        zones = hr_zones_stacked_area_chart(zone_df, "Week")
        self.assertEqual(zones.layout.margin.l, FITNESS_MARGIN_L)
        self.assertEqual(zones.layout.margin.r, FITNESS_MARGIN_R)

    def test_week_hover_uses_iso_week_range(self):
        fig = aerobic_efficiency_line_chart(self._period_df(), "Week")
        scatter = next(t for t in fig.data if t.mode == "lines+markers")
        custom = [list(row) for row in scatter.customdata]
        self.assertEqual(custom[0][0], "Mar 2, 2026 - Mar 8, 2026")
        self.assertEqual(custom[1][0], "Mar 9, 2026 - Mar 15, 2026")
        self.assertIn("<b>%{customdata[0]}</b>", scatter.hovertemplate)
        self.assertIn("Adj. efficiency", scatter.hovertemplate)
        self.assertIn("mph/bpm", scatter.hovertemplate)
        self.assertIn("ft/mi", scatter.hovertemplate)
        self.assertEqual(list(scatter.x), ["Mar 2, 26", "Mar 9, 26", "Mar 16, 26"])

    def test_fitness_line_charts_lift_race_diamonds_by_axis_span(self):
        """AE + F&F diamonds sit above markers using the visible y-axis span."""
        race_period = pd.DataFrame(
            {
                "period_key": ["2026-10", "2026-11"],
                "period_label": ["Mar 2, 26", "Mar 9, 26"],
                "period_tooltip": [
                    "Mar 2, 2026 - Mar 8, 2026",
                    "Mar 9, 2026 - Mar 15, 2026",
                ],
                "residual": [0.010, 0.020],
                "efficiency": [0.050, 0.052],
                "elev_ft_per_mile": [40.0, 42.0],
                "fitness": [40.0, 42.0],
                "fatigue": [35.0, 38.0],
                "form": [5.0, 4.0],
                "load": [100.0, 110.0],
                "in_progress": [False, True],
                "is_race_period": [False, True],
                "race_names": ["", "Spring 5k"],
                "race_type": ["", "5k"],
                "race_hover": ["", "Spring 5k<br>5k"],
            }
        )
        ae = aerobic_efficiency_line_chart(race_period, "Week")
        ae_diamond = _race_diamond_traces(ae)[0]
        self.assertGreater(ae_diamond.y[0], 0.020)
        self.assertLessEqual(ae_diamond.y[0], ae.layout.yaxis.range[1])
        self.assertGreater(
            ae_diamond.y[0] - 0.020,
            0.020 * RACE_CHART_DIAMOND_Y_PAD_FRAC,
        )

        ff = fitness_form_fatigue_line_chart(race_period, "Week")
        ff_diamond = _race_diamond_traces(ff)[0]
        ff_top = max(race_period[["fitness", "fatigue", "form"]].iloc[1].astype(float))
        self.assertGreater(ff_diamond.y[0], ff_top)
        self.assertLessEqual(ff_diamond.y[0], ff.layout.yaxis.range[1])

    def test_fitness_freshness_keeps_peak_race_diamond_in_view(self):
        """Race at the chart peak stays inside the y-axis after diamond lift."""
        period_df = pd.DataFrame(
            {
                "period_key": ["2026-10", "2026-11", "2026-12"],
                "period_label": ["Mar 2, 26", "Mar 9, 26", "Mar 16, 26"],
                "period_tooltip": ["w1", "w2", "w3"],
                "fitness": [95.0, 80.0, 70.0],
                "fatigue": [90.0, 75.0, 65.0],
                "form": [5.0, 5.0, 5.0],
                "load": [100.0, 90.0, 80.0],
                "in_progress": [False, False, True],
                "is_race_period": [True, False, False],
                "race_names": ["Peak 5k", "", ""],
                "race_type": ["5k", "", ""],
                "race_hover": ["Peak 5k<br>5k", "", ""],
            }
        )
        fig = fitness_form_fatigue_line_chart(period_df, "Week")
        diamond = _race_diamond_traces(fig)[0]
        y_lo, y_hi = fig.layout.yaxis.range
        self.assertEqual(list(diamond.x), ["Mar 2, 26"])
        self.assertGreaterEqual(diamond.y[0], y_lo)
        self.assertLessEqual(diamond.y[0], y_hi)

    def test_rolling_trend_companion_matches_pace_hr_window(self):
        """Dashed Trend uses the same Show By rolling window as Avg HR by Pace."""
        residuals = [0.010, 0.020, 0.030, 0.040]
        period_df = pd.DataFrame(
            {
                "period_key": [f"2026-{i}" for i in range(10, 14)],
                "period_label": [f"W{i}" for i in range(1, 5)],
                "period_tooltip": [f"week {i}" for i in range(1, 5)],
                "residual": residuals,
                "efficiency": [0.05] * 4,
                "elev_ft_per_mile": [40.0] * 4,
                "in_progress": [False, False, False, True],
            }
        )
        self.assertEqual(pace_hr_trend_window("Week"), 4)
        fig = aerobic_efficiency_line_chart(period_df, "Week")
        self.assertEqual(len(fig.data), 3)
        points, legend_proxy, trend = fig.data
        self.assertEqual(points.mode, "lines+markers")
        self.assertFalse(points.showlegend)
        self.assertEqual(legend_proxy.mode, "lines")
        self.assertTrue(legend_proxy.showlegend)
        self.assertEqual(trend.name, "Trend")
        self.assertEqual(trend.mode, "lines")
        self.assertEqual(trend.line.dash, "dash")
        self.assertIn("4-week avg", trend.hovertemplate)
        expected = [0.010, 0.015, 0.020, 0.025]
        self.assertEqual([float(y) for y in trend.y], expected)

    def test_fitness_page_wires_aerobic_efficiency_chart(self):
        fitness = (
            Path(__file__).resolve().parents[2]
            / "dashboard"
            / "pages"
            / "fitness.py"
        ).read_text()
        self.assertIn("aerobic_efficiency_line_chart", fitness)
        self.assertIn("aggregate_aerobic_efficiency_by_period", fitness)
        self.assertIn('id="chart-aerobic-efficiency"', fitness)
        self.assertIn("aerobic_efficiency_info_html", fitness)
        # Panel must be its own markdown block — not inside the zero-height page-anchor.
        self.assertNotIn(
            'id="chart-aerobic-efficiency" class="page-anchor insights-chart"></div>"\n'
            "    + aerobic_efficiency_info_html()",
            fitness,
        )
        self.assertIn("aerobic_efficiency_info_html(aerobic_efficiency_title(grain))", fitness)
        self.assertIn(".aerobic-efficiency-chart-title", GLOBAL_CSS)
        self.assertIn(".aerobic-efficiency-info .kpi-info", GLOBAL_CSS)
        # ⓘ inline after the chart title (not in the right legend gutter).
        info_block = GLOBAL_CSS.split(".aerobic-efficiency-info {", 1)[1].split(
            "}", 1
        )[0]
        self.assertIn("display: inline-flex;", info_block)
        self.assertIn("align-items: center;", info_block)
        self.assertIn("gap: 0.28rem;", info_block)
        self.assertNotIn(
            "left: calc(100% - var(--fitness-plot-margin-r)",
            GLOBAL_CSS,
        )
        self.assertNotIn("--fitness-gutter-x:", GLOBAL_CSS)
        self.assertEqual(LEGEND_FITNESS_GUTTER["x"], 1 + FITNESS_LEGEND_GUTTER_X_FRAC)
        # Tooltip opens to the right of ⓘ (readable width).
        tip_block = GLOBAL_CSS.split(
            ".aerobic-efficiency-info .kpi-tooltip {", 1
        )[1].split("}", 1)[0]
        self.assertIn("left: calc(100% + 0.35rem);", tip_block)
        self.assertIn("transform: none;", tip_block)
        self.assertIn("width: min(20rem, 72vw);", tip_block)
        self.assertNotIn("fitness-plot-margin-r) - 1.25rem", tip_block)
        self.assertNotIn("translateX(50%)", tip_block)
        self.assertNotIn(".aerobic-efficiency-side-panel", GLOBAL_CSS)
        self.assertIn("--fitness-plot-margin-r:", GLOBAL_CSS)
        self.assertLess(fitness.find("chart-pace-hr"), fitness.find("chart-aerobic-efficiency"))
        self.assertLess(
            fitness.find("chart-aerobic-efficiency"),
            fitness.find("chart-fitness-freshness"),
        )
        self.assertNotIn("chart-hr-zones", fitness)
        self.assertIn("#chart-aerobic-efficiency", GLOBAL_CSS)
        self.assertIn("--chart-aerobic-efficiency-margin-top:", GLOBAL_CSS)
        # Fitness sections share one gap so the three charts read as one rhythm.
        self.assertEqual(CHART_AEROBIC_EFFICIENCY_MARGIN_TOP, FITNESS_SECTION_GAP)
        self.assertEqual(CHART_PACE_HR_MARGIN_TOP, FITNESS_SECTION_GAP)
        self.assertEqual(CHART_FITNESS_FRESHNESS_MARGIN_TOP, FITNESS_SECTION_GAP)
        self.assertIn(
            "[data-testid=\"stElementContainer\"]:has(.aerobic-efficiency-info)",
            GLOBAL_CSS,
        )
        self.assertIn("margin-bottom: -2.15rem !important", GLOBAL_CSS)
        ui = (
            Path(__file__).resolve().parents[2] / "dashboard" / "ui.py"
        ).read_text()
        insights_nav = ui[
            ui.index("def render_insights_section_nav") : ui.index(
                "def render_metrics_section_nav"
            )
        ]
        self.assertIn("chart-aerobic-efficiency", insights_nav)
        self.assertIn("aerobic_efficiency_title", insights_nav)
        self.assertLess(
            insights_nav.find("chart-pace-hr"),
            insights_nav.find("chart-aerobic-efficiency"),
        )
        self.assertLess(
            insights_nav.find("chart-aerobic-efficiency"),
            insights_nav.find("chart-fitness-freshness"),
        )
        self.assertNotIn("chart-hr-zones", insights_nav)
        html = aerobic_efficiency_info_html("Weekly Aerobic Efficiency")
        self.assertIn("kpi-info", html)
        self.assertIn("kpi-tooltip", html)
        self.assertIn("aerobic-efficiency-info", html)
        self.assertIn("aerobic-efficiency-chart-title", html)
        self.assertNotIn("aerobic-efficiency-side-panel", html)
        self.assertIn("Weekly Aerobic Efficiency", html)
        self.assertLess(
            html.index("Weekly Aerobic Efficiency"),
            html.index("kpi-info"),
        )
        self.assertIn("ⓘ", html)
        self.assertIn("3600", html)
        self.assertIn("mph per bpm", html)
        self.assertIn("ft/mi", html)
        self.assertIn("residual", html.lower())
        self.assertIn("non-race", html.lower())
        self.assertIn("Show By", html)
        self.assertIn("more efficient than expected", html)


class FitnessFreshnessChartTests(unittest.TestCase):
    """Fitness / Fatigue lines and Form area on Fitness."""

    def _period_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "period_key": ["2026-10", "2026-11", "2026-12"],
                "period_label": ["Mar 2, 26", "Mar 9, 26", "Mar 16, 26"],
                "period_tooltip": [
                    "Mar 2, 2026 - Mar 8, 2026",
                    "Mar 9, 2026 - Mar 15, 2026",
                    "Mar 16, 2026 - Mar 22, 2026",
                ],
                "fitness": [40.0, 42.0, 41.0],
                "fatigue": [35.0, 38.0, 30.0],
                "form": [5.0, 4.0, 11.0],
                "load": [100.0, 110.0, 80.0],
                "in_progress": [False, False, True],
            }
        )

    def test_three_series_colors_and_shared_margins(self):
        fig = fitness_form_fatigue_line_chart(self._period_df(), "Week")
        plot_traces = [t for t in fig.data if t.mode == "lines+markers"]
        legend_traces = [
            t for t in fig.data if t.mode == "lines" and t.showlegend and t.hoverinfo == "skip"
        ]
        self.assertEqual(len(plot_traces), 3)
        self.assertEqual(len(legend_traces), 3)
        # Draw order: Form shade behind, then Fitness / Fatigue lines on top.
        self.assertEqual([t.name for t in plot_traces], ["Form", "Fitness", "Fatigue"])
        form_trace = plot_traces[0]
        self.assertEqual(form_trace.line.color, FORM_TSB_COLOR)
        self.assertEqual(form_trace.fill, "tozeroy")
        self.assertEqual(
            form_trace.fillcolor,
            f"rgba(80, 155, 143, {FORM_TSB_FILL_OPACITY})",
        )
        self.assertFalse(form_trace.showlegend)
        self.assertEqual(plot_traces[1].line.color, FITNESS_CTL_COLOR)
        self.assertFalse(plot_traces[1].showlegend)
        self.assertEqual(plot_traces[2].line.color, FATIGUE_ATL_COLOR)
        self.assertFalse(plot_traces[2].showlegend)
        self.assertEqual([t.name for t in legend_traces], ["Fitness", "Fatigue", "Form"])
        self.assertEqual([t.legendrank for t in legend_traces], [1, 2, 3])
        for proxy in legend_traces:
            self.assertEqual(proxy.mode, "lines")
            self.assertTrue(proxy.showlegend)
            self.assertEqual(proxy.hoverinfo, "skip")
        self.assertEqual(fig.layout.margin.l, FITNESS_FRESHNESS_MARGIN["l"])
        self.assertEqual(fig.layout.margin.r, FITNESS_FRESHNESS_MARGIN["r"])
        self.assertEqual(fig.layout.margin.l, FITNESS_MARGIN_L)
        self.assertEqual(fig.layout.margin.r, FITNESS_MARGIN_R)
        self.assertEqual(tuple(fig.layout.xaxis.domain), tuple(FITNESS_XAXIS_DOMAIN))
        self.assertTrue(fig.layout.showlegend)
        self.assertEqual(fitness_freshness_title("Week"), "Weekly Fitness & Freshness")

    def test_fitness_page_wires_freshness_chart(self):
        fitness = (
            Path(__file__).resolve().parents[2]
            / "dashboard"
            / "pages"
            / "fitness.py"
        ).read_text()
        self.assertIn("fitness_form_fatigue_line_chart", fitness)
        self.assertIn("aggregate_fitness_form_fatigue_by_period", fitness)
        self.assertIn('id="chart-fitness-freshness"', fitness)
        self.assertIn("fitness_freshness_info_html", fitness)
        self.assertIn(
            "fitness_freshness_info_html(fitness_freshness_title(grain))",
            fitness,
        )
        self.assertLess(
            fitness.find("chart-aerobic-efficiency"),
            fitness.find("chart-fitness-freshness"),
        )
        self.assertNotIn("chart-hr-zones", fitness)
        self.assertIn(".fitness-freshness-info", GLOBAL_CSS)
        self.assertNotIn(".fitness-freshness-info-gutter", GLOBAL_CSS)
        self.assertIn("#chart-fitness-freshness", GLOBAL_CSS)
        self.assertIn("--chart-fitness-freshness-margin-top:", GLOBAL_CSS)
        self.assertEqual(CHART_FITNESS_FRESHNESS_MARGIN_TOP, "2.75rem")
        # ⓘ inline after the chart title (not under the right-gutter legend).
        info_block = GLOBAL_CSS.split(".fitness-freshness-info {", 1)[1].split(
            "}", 1
        )[0]
        self.assertIn("display: inline-flex;", info_block)
        self.assertIn("align-items: center;", info_block)
        self.assertIn("gap: 0.28rem;", info_block)
        self.assertEqual(
            fitness_form_fatigue_line_chart(self._period_df(), "Week").layout.legend.x,
            LEGEND_FITNESS_GUTTER["x"],
        )
        tip_block = GLOBAL_CSS.split(
            ".fitness-freshness-info .kpi-tooltip {", 1
        )[1].split("}", 1)[0]
        self.assertIn("left: calc(100% + 0.35rem);", tip_block)
        html = fitness_freshness_info_html("Weekly Fitness & Freshness")
        self.assertIn("Edwards", html)
        self.assertIn("Relative Effort", html)
        self.assertIn("42-day", html)
        self.assertIn("7-day", html)
        self.assertIn("Fitness − Fatigue", html)
        self.assertNotIn("fitness-freshness-info-gutter", html)
        self.assertIn("kpi-info", html)
        self.assertLess(
            html.index("fitness-freshness-chart-title"),
            html.index("kpi-info"),
        )
        self.assertLess(
            html.index("Weekly Fitness & Freshness"),
            html.index("kpi-info"),
        )


class RaceResultsScatterTests(unittest.TestCase):
    """Performance finish-time / pace scatter."""

    def _races(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "activity_id": ["101", "202", "303"],
                "date": pd.to_datetime(
                    ["2024-01-01T12:00:00Z", "2024-06-01T12:00:00Z", "2025-01-01T12:00:00Z"],
                    utc=True,
                ),
                "name": ["Winter 5k", "Spring Half", "NYC Marathon"],
                "race_type": ["5k", "Half", "Marathon"],
                "distance_miles": [3.1, 13.1, 26.2],
                "elapsed_time_min": ["0:22:00", "1:45:00", "3:30:00"],
                "elapsed_min": [22.0, 105.0, 210.0],
                "elapsed_pace": ["7:06", "8:01", "8:01"],
                "pace_min": [7.1, 8.02, 8.02],
                "is_pr": [True, False, True],
            }
        )

    def test_margin_uses_tight_legend_gutter(self):
        from dashboard.charts import RACE_RESULTS_LEGEND_GUTTER_PX, RACE_RESULTS_MARGIN

        self.assertEqual(RACE_RESULTS_LEGEND_GUTTER_PX, 96)
        self.assertEqual(RACE_RESULTS_MARGIN["r"], 96)
        self.assertLess(RACE_RESULTS_MARGIN["r"], FITNESS_MARGIN_R)
        fig = race_results_scatter(self._races(), metric="time")
        self.assertEqual(fig.layout.margin.r, 96)

    def test_highlight_dims_others_and_adds_ring_marker(self):
        fig = race_results_scatter(
            self._races(), metric="time", highlight_activity_id="202"
        )
        selected = [t for t in fig.data if t.name == "Selected"]
        self.assertEqual(len(selected), 1)
        hit = selected[0]
        self.assertEqual(hit.marker.size, RACE_HIGHLIGHT_SIZE)
        self.assertEqual(hit.marker.line.width, RACE_HIGHLIGHT_RING_WIDTH)
        self.assertEqual(hit.marker.line.color, INK)
        self.assertEqual(hit.marker.symbol, "circle")
        for trace in fig.data:
            if trace.name in {"Selected", "PR"} and list(trace.x) == [None]:
                continue
            if trace.name == "Selected":
                continue
            opacity = trace.marker.opacity
            if opacity is not None:
                self.assertEqual(opacity, RACE_DIM_OPACITY)

    def test_highlight_pr_uses_star_size(self):
        fig = race_results_scatter(
            self._races(), metric="time", highlight_activity_id=101
        )
        hit = next(t for t in fig.data if t.name == "Selected")
        self.assertEqual(hit.marker.symbol, "star")
        self.assertEqual(hit.marker.size, RACE_HIGHLIGHT_PR_SIZE)

    def test_race_table_fill_matches_header_css(self):
        self.assertEqual(RACE_TABLE_FILL, "transparent")
        self.assertIn(f"--gdg-bg-cell: {RACE_TABLE_FILL}", GLOBAL_CSS)
        self.assertIn(f"--gdg-bg-cell-medium: {RACE_TABLE_FILL}", GLOBAL_CSS)
        self.assertIn(f"--gdg-bg-header: {RACE_TABLE_FILL}", GLOBAL_CSS)
        self.assertIn(f"--gdg-bg-header-has-focus: {RACE_TABLE_FILL}", GLOBAL_CSS)
        self.assertIn(f"--gdg-bg-header-hovered: {RACE_TABLE_FILL}", GLOBAL_CSS)
        self.assertIn(f"--gdg-bg-group-header: {RACE_TABLE_FILL}", GLOBAL_CSS)
        self.assertIn(f"--gdg-bg-group-header-hovered: {RACE_TABLE_FILL}", GLOBAL_CSS)
        self.assertIn("--chart-race-table-title-gap:", GLOBAL_CSS)
        self.assertIn("width: 100% !important;", GLOBAL_CSS)


if __name__ == "__main__":
    unittest.main()
