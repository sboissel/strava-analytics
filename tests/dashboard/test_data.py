"""Tests for dashboard.data."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from dashboard.data import key_indicators


class KeyIndicatorsTests(unittest.TestCase):
    """Test key indicator week/month windows."""

    def _runs(self, dates: list[str], distances: list[float] | None = None) -> pd.DataFrame:
        n = len(dates)
        return pd.DataFrame(
            {
                "date": pd.to_datetime(dates, utc=True),
                "distance_miles": distances or [5.0] * n,
                "mt_min_easy": [30.0] * n,
                "mt_min_hard": [10.0] * n,
                "%_easy": [75.0] * n,
            }
        )

    def test_current_period_key_week(self):
        """ISO week key should match the Monday of the containing week."""
        sunday = pd.Timestamp("2026-03-15T12:00:00Z")
        from dashboard.data import current_period_key

        self.assertEqual(current_period_key("Week", sunday), "2026-11")

    def test_key_indicators_uses_last_full_week_on_monday(self):
        """Monday should use the last full Mon–Sun week for last-week KPIs."""
        monday = pd.Timestamp("2026-03-16T12:00:00Z")
        runs = self._runs(
            [
                "2026-03-09T08:00:00Z",
                "2026-03-15T08:00:00Z",
                "2026-03-16T08:00:00Z",
            ]
        )
        indicators = key_indicators(runs, as_of=monday)
        self.assertEqual(indicators["miles_last_week"], 10.0)

    def test_key_indicators_uses_last_full_week_on_sunday(self):
        """Sunday should use the previous completed Mon–Sun week, not the current one."""
        sunday = pd.Timestamp("2026-03-15T12:00:00Z")
        runs = self._runs(
            [
                "2026-03-02T08:00:00Z",
                "2026-03-08T08:00:00Z",
                "2026-03-09T08:00:00Z",
                "2026-03-15T08:00:00Z",
            ]
        )
        indicators = key_indicators(runs, as_of=sunday)
        self.assertEqual(indicators["miles_last_week"], 10.0)

    def test_key_indicators_uses_last_30_days_for_month(self):
        """E:H last month should aggregate the rolling 30-day window."""
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        runs = self._runs(
            [
                "2026-02-13T08:00:00Z",
                "2026-02-14T08:00:00Z",
                "2026-03-16T08:00:00Z",
            ],
            distances=[1.0, 5.0, 9.0],
        )
        indicators = key_indicators(runs, as_of=as_of)
        eh_label, _ = indicators["eh_last_month"]
        self.assertNotEqual(eh_label, "—")
        # Feb 13 is exactly 31 days before Mar 16 and should be excluded.
        # Feb 14 through Mar 16 should contribute easy/hard minutes.
        runs_in_window = runs.loc[
            (runs["date"] >= as_of.normalize() - pd.Timedelta(days=30))
            & (runs["date"] < as_of.normalize() + pd.Timedelta(days=1))
        ]
        self.assertEqual(len(runs_in_window), 2)

    def test_key_indicators_longest_run_last_30_days(self):
        """Longest run should be the max distance in the rolling 30-day window."""
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        runs = self._runs(
            [
                "2026-02-13T08:00:00Z",
                "2026-02-14T08:00:00Z",
                "2026-03-01T08:00:00Z",
                "2026-03-16T08:00:00Z",
            ],
            distances=[12.0, 8.0, 11.0, 6.0],
        )
        indicators = key_indicators(runs, as_of=as_of)
        # Feb 13 is outside the 30-day window; max in-window is 11.0.
        self.assertEqual(indicators["longest_run_30d"], 11.0)


class KeyIndicatorsHtmlTests(unittest.TestCase):
    """Overview KPI gauge markup."""

    def test_renders_gauge_cards_with_targets(self):
        from dashboard.ui import key_indicators_html

        html = key_indicators_html(
            {
                "eh_last_week": ("75:25", 75.0),
                "eh_last_month": ("80:20", 80.0),
                "miles_last_week": 18.5,
                "longest_run_30d": 9.0,
            },
            comparisons={
                "eh_week": "↑ 12% vs previous week",
                "eh_month": None,
                "miles_week": "↓ 5% vs previous week",
                "longest_run": "→ 0% vs previous 30 days",
            },
        )
        self.assertIn('id="key-indicators"', html)
        self.assertEqual(html.count("kpi-gauge"), 4)
        self.assertEqual(html.count("gauge-target-tick"), 4)
        self.assertIn("target 80:20", html)
        self.assertIn("of 20 mi", html)
        self.assertIn("of 10 mi", html)
        self.assertIn("18.50", html)
        # Fill = value / gauge_max (targets at 80% of arc: 100 / 25 / 12.5).
        self.assertIn('stroke-dasharray="75.0 100"', html)  # 75% / 100
        self.assertIn('stroke-dasharray="80.0 100"', html)  # 80% / 100
        self.assertIn('stroke-dasharray="74.0 100"', html)  # 18.5 / 25
        self.assertIn('stroke-dasharray="72.0 100"', html)  # 9 / 12.5
        self.assertIn("kpi-delta--up", html)
        self.assertIn("kpi-delta--down", html)
        self.assertIn("↑ 12%", html)
        self.assertIn("↓ 5%", html)
        self.assertIn('class="kpi-delta-period"', html)
        self.assertIn("vs previous week", html)
        self.assertNotIn("Below target", html)
        self.assertNotIn("Above target", html)
        self.assertNotIn("kpi-chip", html)
        self.assertNotIn("kpi-insight", html)
        self.assertIn('class="panel"', html)

    def test_wrap_panel_false_omits_panel_chrome(self):
        from dashboard.ui import key_indicators_html

        html = key_indicators_html(
            {
                "eh_last_week": ("75:25", 75.0),
                "eh_last_month": ("80:20", 80.0),
                "miles_last_week": 18.5,
                "longest_run_30d": 9.0,
            },
            wrap_panel=False,
        )
        self.assertIn('id="key-indicators"', html)
        self.assertIn('class="panel-label"', html)
        self.assertNotIn('class="panel"', html)


class MetricsInspectAnchorHtmlTests(unittest.TestCase):
    """Inspect scroll anchor (label lives on expander; not a left-nav jump)."""

    def test_anchor_only(self):
        from dashboard.ui import metrics_inspect_anchor_html

        html = metrics_inspect_anchor_html()
        self.assertIn('id="kpi-detail"', html)
        self.assertIn("metrics-inspect-anchor", html)
        self.assertNotIn("panel-label", html)
        self.assertNotIn("Inspect a KI further", html)

    def test_theme_styles_expander_summary_like_panel_label(self):
        from dashboard.theme import FONT_BODY, GLOBAL_CSS, MUTED

        self.assertNotIn("metrics-inspect-label", GLOBAL_CSS)
        self.assertNotIn("clip: rect(0, 0, 0, 0)", GLOBAL_CSS)
        self.assertNotIn("span:not(:has(svg))", GLOBAL_CSS)
        self.assertIn('[data-testid="stExpander"] summary', GLOBAL_CSS)
        self.assertIn(
            '[data-testid="stExpander"] summary [data-testid="stIconMaterial"]',
            GLOBAL_CSS,
        )
        self.assertIn(
            '[data-testid="stExpander"] summary::before',
            GLOBAL_CSS,
        )
        self.assertIn("content: '+'", GLOBAL_CSS)
        self.assertIn("content: '−'", GLOBAL_CSS)
        self.assertIn("font-size: 0.72rem !important", GLOBAL_CSS)
        self.assertIn("font-weight: 600 !important", GLOBAL_CSS)
        self.assertIn("letter-spacing: 0.08em !important", GLOBAL_CSS)
        self.assertIn("text-transform: uppercase !important", GLOBAL_CSS)
        self.assertIn(MUTED, GLOBAL_CSS)
        self.assertIn(FONT_BODY, GLOBAL_CSS)
        # Training mileage heatmap reuses the same expander chrome as Inspect.
        self.assertIn(".st-key-training_mileage_heatmap", GLOBAL_CSS)
        self.assertIn(
            ".st-key-training_mileage_heatmap [data-testid=\"stExpander\"] summary::before",
            GLOBAL_CSS,
        )
        # Heatmap expander chrome is transparent so .stApp shows through (base BG);
        # not white secondaryBg / SURFACE; Metrics Inspect untouched.
        from dashboard.theme import BG, SURFACE

        self.assertEqual(BG, "#E8EEF2")
        self.assertIn(
            ".st-key-training_mileage_heatmap [data-testid=\"stExpander\"] details",
            GLOBAL_CSS,
        )
        heatmap_css_idx = GLOBAL_CSS.index(
            "Every visible layer of the mileage heatmap expander"
        )
        heatmap_block = GLOBAL_CSS[heatmap_css_idx : heatmap_css_idx + 2200]
        self.assertIn("background: transparent !important", heatmap_block)
        self.assertIn("background-color: transparent !important", heatmap_block)
        self.assertIn("--secondary-background-color:", GLOBAL_CSS)
        self.assertIn(f"--secondary-background-color: {BG}", GLOBAL_CSS)
        self.assertIn('[data-testid="stExpander"] summary', heatmap_block)
        self.assertIn('[data-testid="stExpanderDetails"]', heatmap_block)
        self.assertIn('[data-testid="stVerticalBlock"]', heatmap_block)
        self.assertIn('[data-testid="stPlotlyChart"]', heatmap_block)
        self.assertIn(".js-plotly-plot", heatmap_block)
        self.assertIn("iframe", heatmap_block)
        self.assertNotIn(f"background: {SURFACE}", heatmap_block)
        # Scoped rule must not share a selector list with Metrics Inspect.
        rule_body_start = heatmap_block.index("{")
        self.assertNotIn("metrics_inspect_ki", heatmap_block[:rule_body_start])
        self.assertIn("metrics_inspect_ki", GLOBAL_CSS)

    def test_theme_keeps_kpi_detail_above_dataframe(self):
        """Inspect detail must reserve space so the table cannot cover copy."""
        from dashboard.theme import GLOBAL_CSS

        self.assertIn(".kpi-detail-panel", GLOBAL_CSS)
        self.assertIn(".kpi-detail-after", GLOBAL_CSS)
        self.assertIn("height: 1.25rem", GLOBAL_CSS)
        self.assertIn(
            '[data-testid="stExpanderDetails"] [data-testid="stVerticalBlock"]',
            GLOBAL_CSS,
        )
        self.assertIn("gap: 0.35rem !important", GLOBAL_CSS)
        self.assertIn(
            '[data-testid="stElementContainer"]:has(.kpi-detail-panel)',
            GLOBAL_CSS,
        )
        self.assertIn(
            '+ [data-testid="stElementContainer"]:has([data-testid="stDataFrame"])',
            GLOBAL_CSS,
        )
        # CHEVRON_RIGHT fix must remain (icon hidden, not restyled as text).
        self.assertIn(
            '[data-testid="stExpander"] summary [data-testid="stIconMaterial"]',
            GLOBAL_CSS,
        )
        self.assertIn("display: none !important", GLOBAL_CSS)

    def test_theme_ki_shoes_gap_matches_achievements(self):
        """KI → Shoes must use the same section spacing as Achievements → KI."""
        from dashboard.theme import GLOBAL_CSS, LAYOUT_GAP

        self.assertEqual(LAYOUT_GAP, "1.8rem")
        self.assertIn("margin-top: var(--layout-gap) !important", GLOBAL_CSS)
        # st.columns KI row: match Streamlit markdown's -1rem pull-up after Achievements.
        self.assertIn(
            '[data-testid="stHorizontalBlock"]:has(.ki-panel)',
            GLOBAL_CSS,
        )
        self.assertIn("margin-bottom: -1rem !important", GLOBAL_CSS)
        self.assertIn(
            '[data-testid="stElementContainer"]:has(#shoe-mileage)',
            GLOBAL_CSS,
        )
        # Collapsed Inspect details must not add padding below the KI card.
        self.assertIn("details:not([open]) [data-testid=\"stExpanderDetails\"]", GLOBAL_CSS)
        self.assertIn("details[open] [data-testid=\"stExpanderDetails\"]", GLOBAL_CSS)


class MetricsSectionNavTests(unittest.TestCase):
    """Metrics left-nav jumps omit Inspect and sit below the page list."""

    def test_metrics_sections_omit_inspect(self):
        from dashboard.ui import METRICS_SECTIONS, section_nav_html

        labels = [label for _, label in METRICS_SECTIONS]
        self.assertEqual(labels, ["Achievements", "Key Indicators", "Shoes"])
        self.assertNotIn("Inspect", labels)
        html = section_nav_html(METRICS_SECTIONS, aria_label="Metrics sections")
        self.assertIn("Achievements", html)
        self.assertIn("Key Indicators", html)
        self.assertIn("#shoe-mileage", html)
        self.assertNotIn("Inspect", html)
        self.assertNotIn("kpi-detail", html)
        self.assertIn("On this page", html)

    def test_on_this_page_follows_page_links(self):
        from dashboard.ui import METRICS_SECTIONS, NAV_PAGES, sidebar_nav_entries

        page_titles = [title for _, title, _ in NAV_PAGES]
        entries = sidebar_nav_entries("metrics", METRICS_SECTIONS)
        labels = [label for _, _, label in entries]
        self.assertEqual(
            labels,
            [*page_titles, "Achievements", "Key Indicators", "Shoes"],
        )
        self.assertEqual(page_titles, [
            "Metrics",
            "Training",
            "Fitness",
            "Performance",
        ])
        self.assertNotIn("Inspect", labels)

    def test_training_sections_follow_page_links(self):
        from dashboard.ui import NAV_PAGES, sidebar_nav_entries

        sections = [
            ("chart-race-weeks", "Races"),
            ("chart-compliance", "Compliance"),
            ("chart-mileage", "Mileage"),
            ("chart-elevation", "Elevation"),
            ("chart-hr-zones", "Heart Rate Zones"),
        ]
        entries = sidebar_nav_entries("training", sections)
        kinds = [(kind, label) for kind, _, label in entries]
        page_count = len(NAV_PAGES)
        self.assertEqual(kinds[:page_count], [
            ("page", "Metrics"),
            ("page", "Training"),
            ("page", "Fitness"),
            ("page", "Performance"),
        ])
        self.assertEqual(
            kinds[page_count:],
            [
                ("section", "Races"),
                ("section", "Compliance"),
                ("section", "Mileage"),
                ("section", "Elevation"),
                ("section", "Heart Rate Zones"),
            ],
        )

    def test_on_this_page_has_hairline_divider(self):
        from dashboard.theme import GLOBAL_CSS, LINE
        from dashboard.ui import METRICS_SECTIONS, section_nav_html

        html = section_nav_html(METRICS_SECTIONS, aria_label="Metrics sections")
        self.assertIn('class="sidebar-section-nav"', html)
        self.assertNotIn("<hr", html)
        self.assertIn(".sidebar-section-nav {", GLOBAL_CSS)
        self.assertIn("margin: 0.85rem 0 0.75rem", GLOBAL_CSS)
        self.assertIn("padding: 0.5rem 0 0.35rem", GLOBAL_CSS)
        self.assertIn(f"border-top: 1px solid {LINE}", GLOBAL_CSS)

    def test_page_link_labels_force_readable_colors(self):
        """Inactive st.page_link labels must get muted color on nested text nodes."""
        from dashboard.theme import GLOBAL_CSS, INK, MUTED

        self.assertIn("stPageLink-NavLink", GLOBAL_CSS)
        # Inactive labels: force MUTED on NavLink + nested span (not only <a>).
        self.assertIn('[data-testid="stPageLink-NavLink"] span', GLOBAL_CSS)
        inactive_span = GLOBAL_CSS.split('[data-testid="stPageLink-NavLink"] span')[1][
            :400
        ]
        self.assertIn(f"color: {MUTED} !important", inactive_span)
        self.assertIn("opacity: 1 !important", inactive_span)
        # Current page still highlighted in ink via the marker selectors.
        self.assertIn("sidebar-nav-current-marker", GLOBAL_CSS)
        self.assertIn(
            f":has(.sidebar-nav-current-marker) [data-testid=\"stPageLink-NavLink\"]",
            GLOBAL_CSS,
        )
        self.assertIn(f"color: {INK} !important", GLOBAL_CSS)

    def test_selectbox_styles_force_light_readable_chrome(self):
        """Streamlit 1.61 selects use theme.secondaryBg — keep light on our page."""
        from dashboard.theme import CARD, GLOBAL_CSS, INK, SURFACE

        # New React Aria select (not BaseWeb-only polish).
        self.assertIn('[data-testid="stSelectbox"]', GLOBAL_CSS)
        self.assertIn('[data-testid="stSelectboxVirtualDropdown"]', GLOBAL_CSS)
        self.assertIn('[data-testid="stMultiSelect"]', GLOBAL_CSS)
        self.assertIn('[data-testid="stMultiSelectVirtualDropdown"]', GLOBAL_CSS)
        self.assertIn("div:has(> input)", GLOBAL_CSS)
        polish = GLOBAL_CSS.split("Selectbox polish")[1][:1200]
        self.assertIn(f"background: {CARD} !important", polish)
        self.assertIn(f"background-color: {CARD} !important", polish)
        self.assertIn(f"color: {INK} !important", polish)
        # Controls panel still uses a light surface fill.
        self.assertIn(f"background: {SURFACE} !important", GLOBAL_CSS)
        # Expander panel-label CSS must stay scoped to summary — not all selects.
        self.assertNotIn("span:not(:has(svg))", GLOBAL_CSS)
        summary_block = GLOBAL_CSS.split(
            "Match .panel-label on expander summary label only"
        )[1][:900]
        self.assertIn('[data-testid="stExpander"] summary', summary_block)
        self.assertNotIn("stSelectbox", summary_block)


class KpiComparisonBadgeTests(unittest.TestCase):
    """Prior-period compact delta badges."""

    def _runs(self, rows: list[tuple[str, float, float, float]]) -> pd.DataFrame:
        dates, distances, easy, hard = zip(*rows)
        return pd.DataFrame(
            {
                "date": pd.to_datetime(list(dates), utc=True),
                "name": [f"Run {i}" for i in range(len(dates))],
                "distance_miles": list(distances),
                "mt_min_easy": list(easy),
                "mt_min_hard": list(hard),
                "%_easy": [
                    100.0 * e / (e + h) if (e + h) > 0 else None
                    for e, h in zip(easy, hard)
                ],
            }
        )

    def test_percent_change_vs_previous_week(self):
        from dashboard.data import kpi_comparison_badges

        # as_of Monday 2026-03-16 → last full week is Mon 3/9–Sun 3/15
        # prior week Mon 3/2–Sun 3/8
        runs = self._runs(
            [
                ("2026-03-03T08:00:00Z", 10.0, 80.0, 20.0),  # prior: 80% easy, 10 mi
                ("2026-03-10T08:00:00Z", 12.0, 56.0, 44.0),  # current: 56% easy, 12 mi
            ]
        )
        badges = kpi_comparison_badges(runs, as_of=pd.Timestamp("2026-03-16T12:00:00Z"))
        # easy 56 vs 80 → −30%
        self.assertEqual(badges["eh_week"], "↓ 30% vs previous week")
        # miles 12 vs 10 → +20%
        self.assertEqual(badges["miles_week"], "↑ 20% vs previous week")

    def test_missing_prior_omits_badge(self):
        from dashboard.data import kpi_comparison_badges

        runs = self._runs(
            [
                ("2026-03-10T08:00:00Z", 12.0, 56.0, 44.0),
            ]
        )
        badges = kpi_comparison_badges(runs, as_of=pd.Timestamp("2026-03-16T12:00:00Z"))
        self.assertIsNone(badges["eh_week"])
        self.assertIsNone(badges["miles_week"])


class KpiDetailTests(unittest.TestCase):
    """Drill-down payloads for Metrics inspect panel."""

    def test_build_kpi_detail_eh_week_table(self):
        from dashboard.data import build_kpi_detail

        runs = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    ["2026-03-10T08:00:00Z", "2026-03-12T08:00:00Z"], utc=True
                ),
                "name": ["A", "B"],
                "distance_miles": [5.0, 6.0],
                "mt_min_easy": [40.0, 20.0],
                "mt_min_hard": [10.0, 30.0],
                "%_easy": [80.0, 40.0],
            }
        )
        detail = build_kpi_detail(
            runs, "eh_week", as_of=pd.Timestamp("2026-03-16T12:00:00Z")
        )
        self.assertEqual(detail["title"], "Easy:Hard Last Week")
        self.assertEqual(len(detail["table"]), 2)
        self.assertIn("Easy min", detail["table"].columns)


class LifetimeAchievementsTests(unittest.TestCase):
    """All-time achievement aggregates for the Metrics page."""

    def _runs(
        self,
        rows: list[tuple],
    ) -> pd.DataFrame:
        # rows: (date, miles, elev) or (date, miles, elev, name)
        dates = [r[0] for r in rows]
        distances = [r[1] for r in rows]
        elev = [r[2] for r in rows]
        data = {
            "date": pd.to_datetime(list(dates), utc=True),
            "distance_miles": list(distances),
            "elevation_gain_ft": list(elev),
        }
        if rows and len(rows[0]) >= 4:
            data["name"] = [r[3] for r in rows]
        return pd.DataFrame(data)

    def test_empty_dataframe(self):
        from dashboard.data import lifetime_achievements

        result = lifetime_achievements(pd.DataFrame())
        self.assertEqual(result["total_miles"], 0.0)
        self.assertEqual(result["total_elevation_miles"], 0.0)
        self.assertEqual(result["this_year_miles"], 0.0)
        self.assertEqual(result["this_year_elevation_miles"], 0.0)
        self.assertIsInstance(result["this_year"], int)
        self.assertIsNone(result["best_week_miles"])
        self.assertIsNone(result["best_week_date"])
        self.assertIsNone(result["best_week_end"])
        self.assertEqual(result["best_week_runs"], [])
        self.assertIsNone(result["longest_run_miles"])
        self.assertIsNone(result["longest_run_date"])
        self.assertIsNone(result["longest_run_name"])
        self.assertIsNone(result["most_elevation_ft"])
        self.assertIsNone(result["most_elevation_date"])
        self.assertIsNone(result["most_elevation_name"])

    def test_totals_and_longest_run(self):
        from dashboard.data import lifetime_achievements

        runs = self._runs(
            [
                ("2026-01-05T08:00:00Z", 5.0, 100.0, "Easy Five"),
                ("2026-01-12T08:00:00Z", 12.5, 250.5, "Long Sunday"),
                ("2026-02-01T08:00:00Z", 8.0, 50.0, "Tempo"),
            ]
        )
        result = lifetime_achievements(runs)
        self.assertEqual(result["total_miles"], 25.5)
        # elevation_gain_ft is feet; convert ft → miles (÷ 5280)
        self.assertAlmostEqual(result["total_elevation_miles"], 400.5 / 5280.0)
        self.assertEqual(result["this_year"], 2026)
        self.assertEqual(result["this_year_miles"], 25.5)
        self.assertAlmostEqual(result["this_year_elevation_miles"], 400.5 / 5280.0)
        self.assertEqual(result["longest_run_miles"], 12.5)
        self.assertEqual(
            result["longest_run_date"],
            pd.Timestamp("2026-01-12T08:00:00Z"),
        )
        self.assertEqual(result["longest_run_name"], "Long Sunday")
        self.assertAlmostEqual(result["most_elevation_ft"], 250.5)
        self.assertEqual(
            result["most_elevation_date"],
            pd.Timestamp("2026-01-12T08:00:00Z"),
        )
        self.assertEqual(result["most_elevation_name"], "Long Sunday")

    def test_most_elevation_in_a_run(self):
        """Peak elevation is the max single-run gain, not the longest run."""
        from dashboard.data import lifetime_achievements

        runs = self._runs(
            [
                ("2026-03-01T08:00:00Z", 4.0, 1200.0, "Hill Repeats"),
                ("2026-04-10T08:00:00Z", 18.0, 200.0, "Flat Twenty"),
                ("2026-05-20T08:00:00Z", 6.0, 800.0, "Trail Six"),
            ]
        )
        result = lifetime_achievements(runs)
        self.assertEqual(result["longest_run_miles"], 18.0)
        self.assertEqual(result["longest_run_name"], "Flat Twenty")
        self.assertAlmostEqual(result["most_elevation_ft"], 1200.0)
        self.assertEqual(
            result["most_elevation_date"],
            pd.Timestamp("2026-03-01T08:00:00Z"),
        )
        self.assertEqual(result["most_elevation_name"], "Hill Repeats")

    def test_most_miles_in_iso_week(self):
        """Best week should sum by ISO week, not a rolling 7-day window."""
        from dashboard.data import lifetime_achievements

        # ISO week 2026-02: Mon 2026-01-05 … Sun 2026-01-11
        # ISO week 2026-03: Mon 2026-01-12 … Sun 2026-01-18
        runs = self._runs(
            [
                ("2026-01-05T08:00:00Z", 10.0, 0.0, "Mon Ten"),
                ("2026-01-07T08:00:00Z", 6.0, 0.0, "Wed Six"),  # week 02 → 16 mi
                ("2026-01-12T08:00:00Z", 12.0, 0.0, "Next Week"),  # week 03 → 12 mi
            ]
        )
        result = lifetime_achievements(runs)
        self.assertEqual(result["best_week_miles"], 16.0)
        self.assertEqual(
            result["best_week_date"],
            pd.Timestamp("2026-01-05", tz="UTC"),
        )
        self.assertEqual(
            result["best_week_end"],
            pd.Timestamp("2026-01-11", tz="UTC"),
        )
        self.assertEqual(len(result["best_week_runs"]), 2)
        self.assertEqual(result["best_week_runs"][0]["name"], "Mon Ten")
        self.assertEqual(result["best_week_runs"][0]["miles"], 10.0)
        self.assertEqual(
            result["best_week_runs"][0]["date"],
            pd.Timestamp("2026-01-05T08:00:00Z"),
        )
        self.assertEqual(result["best_week_runs"][1]["name"], "Wed Six")
        self.assertEqual(result["best_week_runs"][1]["miles"], 6.0)

    def test_best_week_date_is_iso_monday(self):
        """Badge date is the ISO-week Monday, not the first activity timestamp."""
        from dashboard.data import lifetime_achievements

        # Peak week 2026-14: Mon 2026-03-30 … Sun 2026-04-05 (spans Mar/Apr)
        # Only April activities, reverse chronological — Monday is still Mar 30.
        runs = self._runs(
            [
                ("2026-04-05T18:00:00Z", 8.0, 0.0),
                ("2026-04-03T12:00:00Z", 7.0, 0.0),
                ("2026-04-01T09:00:00Z", 6.0, 0.0),  # week 14 → 21 mi
                ("2026-04-08T09:00:00Z", 10.0, 0.0),  # week 15 → 10 mi
            ]
        )
        result = lifetime_achievements(runs)
        self.assertEqual(result["best_week_miles"], 21.0)
        self.assertEqual(
            result["best_week_date"],
            pd.Timestamp("2026-03-30", tz="UTC"),
        )
        self.assertEqual(
            result["best_week_end"],
            pd.Timestamp("2026-04-05", tz="UTC"),
        )
        self.assertEqual(result["best_week_date"].strftime("%b %Y").upper(), "MAR 2026")
        self.assertEqual(len(result["best_week_runs"]), 3)
        # Sorted by date ascending within the week
        self.assertEqual(
            [r["miles"] for r in result["best_week_runs"]],
            [6.0, 7.0, 8.0],
        )

    def test_best_week_ignores_rolling_window_trap(self):
        """Seven consecutive days that cross an ISO boundary stay split by week."""
        from dashboard.data import lifetime_achievements

        # Sun 2026-01-11 (week 02) + Mon–Sat week 03: rolling 7d = 28 mi,
        # but calendar weeks are 10 + 18.
        runs = self._runs(
            [
                ("2026-01-11T08:00:00Z", 10.0, 0.0),  # week 02
                ("2026-01-12T08:00:00Z", 3.0, 0.0),  # week 03
                ("2026-01-13T08:00:00Z", 3.0, 0.0),
                ("2026-01-14T08:00:00Z", 3.0, 0.0),
                ("2026-01-15T08:00:00Z", 3.0, 0.0),
                ("2026-01-16T08:00:00Z", 3.0, 0.0),
                ("2026-01-17T08:00:00Z", 3.0, 0.0),  # week 03 → 18 mi
            ]
        )
        result = lifetime_achievements(runs)
        self.assertEqual(result["best_week_miles"], 18.0)
        self.assertEqual(
            result["best_week_date"],
            pd.Timestamp("2026-01-12", tz="UTC"),
        )
        self.assertEqual(len(result["best_week_runs"]), 6)

    def test_best_week_iso_year_boundary(self):
        """Early-January days can belong to the previous ISO year."""
        from dashboard.data import lifetime_achievements

        # 2021-01-01 was Friday of ISO week 2020-53 (Mon 2020-12-28 … Sun 2021-01-03)
        runs = self._runs(
            [
                ("2021-01-01T10:00:00Z", 20.0, 0.0),  # 2020-53
                ("2021-01-02T10:00:00Z", 15.0, 0.0),  # 2020-53 → 35 mi
                ("2021-01-04T10:00:00Z", 12.0, 0.0),  # 2021-01 → 12 mi
            ]
        )
        result = lifetime_achievements(runs)
        self.assertEqual(result["best_week_miles"], 35.0)
        self.assertEqual(
            result["best_week_date"],
            pd.Timestamp("2020-12-28", tz="UTC"),
        )
        self.assertEqual(
            result["best_week_end"],
            pd.Timestamp("2021-01-03", tz="UTC"),
        )
        self.assertEqual(result["best_week_date"].strftime("%b %Y").upper(), "DEC 2020")

    def test_this_year_totals_filter_by_latest_activity_year(self):
        """This-year miles/elevation use the UTC calendar year of the latest run."""
        from dashboard.data import lifetime_achievements

        runs = self._runs(
            [
                ("2025-12-31T08:00:00Z", 10.0, 1000.0),
                ("2026-01-01T08:00:00Z", 5.0, 200.0),
                ("2026-06-01T08:00:00Z", 7.0, 300.0),
            ]
        )
        result = lifetime_achievements(runs)
        self.assertEqual(result["this_year"], 2026)
        self.assertEqual(result["this_year_miles"], 12.0)
        self.assertAlmostEqual(result["this_year_elevation_miles"], 500.0 / 5280.0)
        self.assertEqual(result["total_miles"], 22.0)
        self.assertAlmostEqual(result["total_elevation_miles"], 1500.0 / 5280.0)

    def test_this_year_follows_latest_activity_not_clock(self):
        """Stale data still uses the dataset max date, not datetime.now()."""
        from dashboard.data import lifetime_achievements

        runs = self._runs(
            [
                ("2024-06-01T08:00:00Z", 8.0, 100.0),
                ("2025-03-01T08:00:00Z", 4.0, 50.0),
            ]
        )
        result = lifetime_achievements(runs)
        self.assertEqual(result["this_year"], 2025)
        self.assertEqual(result["this_year_miles"], 4.0)
        self.assertAlmostEqual(result["this_year_elevation_miles"], 50.0 / 5280.0)
        self.assertEqual(result["total_miles"], 12.0)


class AchievementsHtmlTests(unittest.TestCase):
    """Achievements panel markup."""

    def test_renders_five_stat_cards(self):
        from dashboard.ui import achievements_html

        html = achievements_html(
            {
                "total_miles": 6091.0,
                "total_elevation_miles": 41.75,
                "this_year": 2026,
                "this_year_miles": 412.4,
                "this_year_elevation_miles": 8.25,
                "best_week_miles": 52.67,
                "best_week_date": pd.Timestamp("2017-04-24", tz="UTC"),
                "best_week_end": pd.Timestamp("2017-04-30", tz="UTC"),
                "best_week_runs": [
                    {
                        "name": "Afternoon Run",
                        "date": pd.Timestamp("2017-04-24T23:49:23Z"),
                        "miles": 8.59,
                    },
                    {
                        "name": "Running on fumes... but it's TAPER TIME!!",
                        "date": pd.Timestamp("2017-04-30T20:27:35Z"),
                        "miles": 18.03,
                    },
                ],
                "longest_run_miles": 26.5,
                "longest_run_date": pd.Timestamp("2017-05-21T11:00:28Z"),
                "longest_run_name": "Sugarloaf Marathon",
                "most_elevation_ft": 2305.77,
                "most_elevation_date": pd.Timestamp("2018-10-04T14:17:36Z"),
                "most_elevation_name": (
                    "Bryce Canyon Half - when your lungs barely work at sea level"
                ),
            }
        )
        self.assertIn('id="achievements"', html)
        self.assertIn("Total Miles", html)
        self.assertIn("Total Elevation", html)
        self.assertIn("Most Miles in a Week", html)
        self.assertIn("Longest Run", html)
        self.assertIn("Most Elevation in a Run", html)
        self.assertIn("6,091 mi", html)
        self.assertIn("41.8 mi", html)  # large-format 1 decimal for 10–99
        self.assertIn("52.67 mi", html)
        self.assertIn("26.50 mi", html)
        self.assertIn("2,306 ft", html)
        self.assertIn("ALL-TIME", html)
        self.assertIn("APR 2017", html)
        self.assertIn("MAY 2017", html)
        self.assertIn("OCT 2018", html)
        self.assertIn("🏃", html)
        self.assertIn("⛰", html)
        self.assertIn("↗", html)
        self.assertIn("🏅", html)
        self.assertIn("🔺", html)
        self.assertEqual(html.count('class="achievement-badge '), 5)
        self.assertEqual(html.count("achievement-medal"), 5)
        self.assertEqual(html.count("achievement-icon"), 5)
        self.assertIn("achievement-badge--miles", html)
        self.assertIn("achievement-badge--elevation", html)
        self.assertIn("achievement-badge--week", html)
        self.assertIn("achievement-badge--longest", html)
        self.assertIn("achievement-badge--peak", html)
        self.assertNotIn("ft gained", html)
        self.assertNotIn("achievement-mark", html)
        self.assertNotIn("ISO week", html)
        self.assertNotIn("single run", html)
        self.assertNotIn(" title=", html)
        self.assertNotIn("ⓘ", html)
        self.assertEqual(html.count("kpi-tooltip"), 5)
        self.assertEqual(html.count("achievement-badge--tip"), 5)
        self.assertIn("<strong>All-time</strong>", html)
        self.assertIn("<strong>This year (2026)</strong>", html)
        self.assertEqual(html.count("<strong>All-time</strong>"), 2)
        self.assertEqual(html.count("<strong>This year (2026)</strong>"), 2)
        self.assertIn("412 mi", html)
        self.assertIn("8.25 mi", html)
        self.assertIn("<strong>Sugarloaf Marathon</strong>", html)
        self.assertIn("May 21, 2017", html)
        self.assertIn(
            "<strong>Bryce Canyon Half - when your lungs barely work at sea level</strong>",
            html,
        )
        self.assertIn("October 4, 2018", html)
        self.assertIn("<strong>Week of Apr 24–30, 2017</strong>", html)
        self.assertIn("Afternoon Run (Apr 24): 8.59 mi", html)
        self.assertIn(
            "Running on fumes... but it&#x27;s TAPER TIME!! (Apr 30): 18.03 mi",
            html,
        )
        self.assertIn("<br>", html)

    def test_empty_values_show_em_dash(self):
        from dashboard.ui import achievements_html

        html = achievements_html(
            {
                "total_miles": 0.0,
                "total_elevation_miles": 0.0,
                "this_year": None,
                "this_year_miles": 0.0,
                "this_year_elevation_miles": 0.0,
                "best_week_miles": None,
                "best_week_date": None,
                "best_week_end": None,
                "best_week_runs": [],
                "longest_run_miles": None,
                "longest_run_date": None,
                "longest_run_name": None,
                "most_elevation_ft": None,
                "most_elevation_date": None,
                "most_elevation_name": None,
            }
        )
        self.assertIn('id="achievements"', html)
        self.assertIn("Most Elevation in a Run", html)
        self.assertEqual(html.count('class="achievement-badge '), 5)
        self.assertIn("0.00 mi", html)
        self.assertIn("—", html)
        self.assertIn("ALL-TIME", html)
        self.assertNotIn(" title=", html)
        self.assertNotIn("ⓘ", html)
        self.assertEqual(html.count("kpi-tooltip"), 2)
        self.assertEqual(html.count("achievement-badge--tip"), 2)
        self.assertIn("<strong>All-time</strong>", html)
        self.assertNotIn("This year", html)


class PeriodMetricsTests(unittest.TestCase):
    """Period aggregation for Training charts."""

    def _runs(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "date": pd.to_datetime(
                    [
                        "2026-03-03T08:00:00Z",
                        "2026-03-10T08:00:00Z",
                        "2026-03-12T08:00:00Z",
                    ],
                    utc=True,
                ),
                "distance_miles": [4.0, 5.0, 3.0],
                "%_easy": [80.0, 80.0, 80.0],
                "elevation_gain_ft": [200.0, 100.0, 50.0],
            }
        )

    def test_sums_elevation_feet_by_week(self):
        from dashboard.data import aggregate_period_metrics

        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        result = aggregate_period_metrics(self._runs(), "Week", as_of=as_of)
        week_11 = result.loc[result["period_key"] == "2026-11"]
        week_10 = result.loc[result["period_key"] == "2026-10"]
        self.assertEqual(len(week_11), 1)
        self.assertAlmostEqual(float(week_11["total_elevation_ft"].iloc[0]), 150.0)
        self.assertAlmostEqual(float(week_10["total_elevation_ft"].iloc[0]), 200.0)

    def test_missing_elevation_column_is_zero(self):
        from dashboard.data import aggregate_period_metrics

        runs = self._runs().drop(columns=["elevation_gain_ft"])
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        result = aggregate_period_metrics(runs, "Week", as_of=as_of)
        self.assertTrue((result["total_elevation_ft"] == 0.0).all())

    def test_empty_runs_include_elevation_column(self):
        from dashboard.data import aggregate_period_metrics

        result = aggregate_period_metrics(
            pd.DataFrame(), "Week", as_of=pd.Timestamp("2026-03-16T12:00:00Z")
        )
        self.assertIn("total_elevation_ft", result.columns)
        self.assertTrue((result["total_elevation_ft"] == 0.0).all())
        self.assertTrue(result["easy_frac"].isna().all())
        self.assertTrue(result["hard_frac"].isna().all())

    def test_hr_mile_breakdown_and_nan_without_hr(self):
        """HR miles drive fractions; no HR coverage → NaN fracs and full unaccounted."""
        from dashboard.data import aggregate_period_metrics

        runs = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    [
                        "2026-03-03T08:00:00Z",  # week 10: 10 mi, tiny HR easy
                        "2026-03-04T08:00:00Z",  # week 10: 90 mi, no HR
                        "2026-03-10T08:00:00Z",  # week 11: 8 mi, no HR at all
                    ],
                    utc=True,
                ),
                "distance_miles": [10.0, 90.0, 8.0],
                "%_easy": [100.0, None, None],
                "elevation_gain_ft": [0.0, 0.0, 0.0],
            }
        )
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        result = aggregate_period_metrics(runs, "Week", as_of=as_of, count=3)
        week_10 = result.loc[result["period_key"] == "2026-10"].iloc[0]
        week_11 = result.loc[result["period_key"] == "2026-11"].iloc[0]

        self.assertAlmostEqual(float(week_10["total_miles"]), 100.0)
        self.assertAlmostEqual(float(week_10["easy_miles"]), 10.0)
        self.assertAlmostEqual(float(week_10["hard_miles"]), 0.0)
        self.assertAlmostEqual(float(week_10["unaccounted_miles"]), 90.0)
        self.assertAlmostEqual(float(week_10["easy_frac"]), 1.0)
        self.assertAlmostEqual(float(week_10["hard_frac"]), 0.0)

        self.assertAlmostEqual(float(week_11["total_miles"]), 8.0)
        self.assertAlmostEqual(float(week_11["easy_miles"]), 0.0)
        self.assertAlmostEqual(float(week_11["hard_miles"]), 0.0)
        self.assertAlmostEqual(float(week_11["unaccounted_miles"]), 8.0)
        self.assertTrue(pd.isna(week_11["easy_frac"]))
        self.assertTrue(pd.isna(week_11["hard_frac"]))

    def test_custom_count_shortens_window(self):
        from dashboard.data import aggregate_period_metrics

        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        result = aggregate_period_metrics(
            self._runs(), "Week", as_of=as_of, count=12
        )
        self.assertEqual(len(result), 12)


class YearlyWindowTests(unittest.TestCase):
    """Year grain defaults to a rolling last-10-years lookback."""

    def test_period_count_defaults_to_ten_years(self):
        from dashboard.data import PERIOD_CONFIG, period_count, period_showing_label

        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        self.assertEqual(int(PERIOD_CONFIG["Year"]["count"]), 10)
        self.assertEqual(period_count("Year", as_of), 10)
        later = pd.Timestamp("2027-08-01T12:00:00Z")
        self.assertEqual(period_count("Year", later), 10)
        self.assertEqual(period_showing_label("Year"), "Last 10 years")
        self.assertEqual(period_showing_label("Year", 15), "Last 15 years")

    def test_year_index_is_rolling_ten(self):
        from dashboard.data import generate_period_index, period_count

        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        index = generate_period_index("Year", as_of, period_count("Year", as_of))
        keys = list(index["period_key"])
        self.assertEqual(keys[0], "2017")
        self.assertEqual(keys[-1], "2026")
        self.assertEqual(len(keys), 10)

    def test_year_metrics_use_rolling_window(self):
        from dashboard.data import aggregate_period_metrics, filter_to_recent_periods

        runs = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    ["2016-02-01T08:00:00Z", "2017-06-01T08:00:00Z", "2026-03-10T08:00:00Z"],
                    utc=True,
                ),
                "distance_miles": [5.0, 9.0, 3.0],
                "%_easy": [80.0, 80.0, 80.0],
                "elevation_gain_ft": [10.0, 20.0, 30.0],
            }
        )
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        kept = filter_to_recent_periods(runs, "Year")
        years = set(kept["date"].dt.year)
        self.assertNotIn(2016, years)
        self.assertIn(2017, years)
        self.assertIn(2026, years)

        result = aggregate_period_metrics(runs, "Year", as_of=as_of)
        self.assertEqual(result["period_key"].iloc[0], "2017")
        self.assertEqual(len(result), 10)
        self.assertAlmostEqual(
            float(result.loc[result["period_key"] == "2017", "total_miles"].iloc[0]),
            9.0,
        )
        self.assertAlmostEqual(
            float(result.loc[result["period_key"] == "2026", "total_miles"].iloc[0]),
            3.0,
        )

    def test_year_override_can_reach_2016(self):
        from dashboard.data import aggregate_period_metrics

        runs = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    ["2016-02-01T08:00:00Z", "2026-03-10T08:00:00Z"],
                    utc=True,
                ),
                "distance_miles": [5.0, 3.0],
                "%_easy": [80.0, 80.0],
                "elevation_gain_ft": [10.0, 30.0],
            }
        )
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        result = aggregate_period_metrics(runs, "Year", as_of=as_of, count=11)
        self.assertEqual(len(result), 11)
        self.assertEqual(result["period_key"].iloc[0], "2016")
        self.assertAlmostEqual(
            float(result.loc[result["period_key"] == "2016", "total_miles"].iloc[0]),
            5.0,
        )

    def test_showing_label_is_last_ten_years(self):
        from dashboard.data import PERIOD_CONFIG

        self.assertEqual(PERIOD_CONFIG["Year"]["showing"], "Last 10 years")
        self.assertEqual(int(PERIOD_CONFIG["Year"]["count"]), 10)

    def test_period_count_rejects_non_positive_override(self):
        from dashboard.data import period_count

        with self.assertRaises(ValueError):
            period_count("Week", count=0)


class PeriodWindowControlsTests(unittest.TestCase):
    """Training and Fitness expose start/end period range controls."""

    def test_pages_wire_period_range_override(self):
        root = Path(__file__).resolve().parents[2] / "dashboard" / "pages"
        training = (root / "training.py").read_text()
        fitness = (root / "fitness.py").read_text()
        for page in (training, fitness):
            self.assertIn("render_period_range_inputs", page)
            self.assertIn("period_showing_label", page)
            self.assertIn("start=window.start", page)
            self.assertIn("end=window.end", page)
            self.assertNotIn("render_period_count_input", page)
            self.assertNotIn("count=window", page)
        self.assertIn('page_key="training"', training)
        self.assertIn('page_key="fitness"', fitness)
        ui = (
            Path(__file__).resolve().parents[2] / "dashboard" / "ui.py"
        ).read_text()
        self.assertIn("def render_period_range_inputs", ui)
        self.assertIn("Start / End", ui)
        self.assertNotIn("Periods to show", ui)

    def test_default_bounds_match_period_config(self):
        from dashboard.data import PERIOD_CONFIG, default_period_bounds, generate_period_index_range

        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        for grain, cfg in PERIOD_CONFIG.items():
            window = default_period_bounds(grain, as_of)
            index = generate_period_index_range(grain, window.start, window.end)
            self.assertEqual(len(index), int(cfg["count"]), grain)

    def test_start_end_shortens_metrics_window(self):
        from dashboard.data import aggregate_period_metrics, align_to_period_start

        runs = pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-03-10T08:00:00Z"], utc=True),
                "distance_miles": [5.0],
                "%_easy": [80.0],
                "elevation_gain_ft": [40.0],
            }
        )
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        start = align_to_period_start("Week", pd.Timestamp("2026-01-05T12:00:00Z"))
        end = align_to_period_start("Week", as_of)
        result = aggregate_period_metrics(
            runs, "Week", as_of=as_of, start=start, end=end
        )
        self.assertGreaterEqual(len(result), 1)
        self.assertLess(len(result), 20)

    def test_clamp_swaps_reversed_bounds(self):
        from dashboard.data import clamp_period_window

        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        window = clamp_period_window(
            "Month",
            pd.Timestamp("2026-03-01T00:00:00Z"),
            pd.Timestamp("2025-01-01T00:00:00Z"),
            as_of=as_of,
        )
        self.assertLessEqual(window.start, window.end)

    def test_showing_label_uses_range(self):
        from dashboard.data import period_showing_label

        label = period_showing_label(
            "Year",
            start=pd.Timestamp("2017-01-01T00:00:00Z"),
            end=pd.Timestamp("2026-01-01T00:00:00Z"),
        )
        self.assertEqual(label, "2017 – 2026")


class AnnotateRacePeriodsTests(unittest.TestCase):
    """Race periods match Performance race rows (race=true) on the period axis."""

    def _periods(self) -> pd.DataFrame:
        from dashboard.data import aggregate_period_metrics

        runs = pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-03-10T08:00:00Z"], utc=True),
                "distance_miles": [5.0],
                "%_easy": [80.0],
                "elevation_gain_ft": [40.0],
            }
        )
        return aggregate_period_metrics(
            runs, "Week", as_of=pd.Timestamp("2026-03-16T12:00:00Z")
        )

    def test_marks_iso_week_containing_race(self):
        from dashboard.data import annotate_race_periods

        races = pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-03-11T09:00:00Z"], utc=True),
                "name": ["Spring 5k"],
            }
        )
        result = annotate_race_periods(self._periods(), races, "Week")
        week_11 = result.loc[result["period_key"] == "2026-11"].iloc[0]
        week_10 = result.loc[result["period_key"] == "2026-10"].iloc[0]
        self.assertTrue(bool(week_11["is_race_period"]))
        self.assertEqual(week_11["race_names"], "Spring 5k")
        self.assertEqual(week_11["race_type"], "Other")
        self.assertEqual(week_11["race_hover"], "Spring 5k")
        self.assertFalse(bool(week_10["is_race_period"]))
        self.assertEqual(week_10["race_names"], "")
        self.assertEqual(week_10["race_type"], "")
        self.assertEqual(week_10["race_hover"], "")

    def test_day_grain_marks_only_race_day(self):
        from dashboard.data import aggregate_period_metrics, annotate_race_periods

        runs = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    ["2026-03-10T08:00:00Z", "2026-03-11T08:00:00Z"], utc=True
                ),
                "distance_miles": [5.0, 3.0],
                "%_easy": [80.0, 80.0],
                "elevation_gain_ft": [10.0, 20.0],
            }
        )
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        periods = aggregate_period_metrics(runs, "Day", as_of=as_of)
        races = pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-03-11T09:00:00Z"], utc=True),
                "name": ["Town 5k"],
            }
        )
        result = annotate_race_periods(periods, races, "Day")
        race_day = result.loc[result["period_key"] == "2026-03-11"].iloc[0]
        other_day = result.loc[result["period_key"] == "2026-03-10"].iloc[0]
        self.assertTrue(bool(race_day["is_race_period"]))
        self.assertFalse(bool(other_day["is_race_period"]))

    def test_empty_races_marks_none(self):
        from dashboard.data import annotate_race_periods

        result = annotate_race_periods(self._periods(), pd.DataFrame(), "Week")
        self.assertFalse(result["is_race_period"].any())
        self.assertTrue((result["race_names"] == "").all())
        self.assertTrue((result["race_type"] == "").all())
        self.assertTrue((result["race_hover"] == "").all())

    def test_object_dtype_dates_are_coerced(self):
        """Single-row race frames (e.g. Series→DataFrame) can lose datetime dtype."""
        from dashboard.data import annotate_race_periods

        race_row = pd.Series(
            {
                "date": pd.Timestamp("2026-03-11T09:00:00Z"),
                "name": "Spring 5k",
                "race_type": "5k",
            }
        )
        races = race_row.to_frame().T.reset_index(drop=True)
        self.assertFalse(pd.api.types.is_datetime64_any_dtype(races["date"]))
        result = annotate_race_periods(self._periods(), races, "Week")
        week_11 = result.loc[result["period_key"] == "2026-11"].iloc[0]
        self.assertTrue(bool(week_11["is_race_period"]))
        self.assertEqual(week_11["race_names"], "Spring 5k")

    def test_primary_type_is_longest_distance(self):
        from dashboard.data import annotate_race_periods

        races = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    ["2026-03-11T09:00:00Z", "2026-03-12T09:00:00Z"], utc=True
                ),
                "name": ["Town 5k", "City Half"],
                "race_type": ["5k", "Half"],
                "distance_miles": [3.1, 13.1],
            }
        )
        result = annotate_race_periods(self._periods(), races, "Week")
        week_11 = result.loc[result["period_key"] == "2026-11"].iloc[0]
        self.assertTrue(bool(week_11["is_race_period"]))
        self.assertEqual(week_11["race_names"], "Town 5k · City Half")
        self.assertEqual(week_11["race_type"], "Half")
        self.assertEqual(week_11["race_hover"], "Town 5k<br>5k<br>City Half<br>Half")

    def test_other_race_hover_uses_miles(self):
        from dashboard.data import annotate_race_periods

        races = pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-03-11T09:00:00Z"], utc=True),
                "name": ["Trail Classic"],
                "race_type": ["Other"],
                "distance_miles": [12.4],
            }
        )
        result = annotate_race_periods(self._periods(), races, "Week")
        week_11 = result.loc[result["period_key"] == "2026-11"].iloc[0]
        self.assertEqual(week_11["race_type"], "Other")
        self.assertEqual(week_11["race_hover"], "Trail Classic<br>12.4 mi")


class PeriodTooltipLabelTests(unittest.TestCase):
    """Hover date strings for Day / Week / Month / Year period keys."""

    def test_format_week_range_short_abbreviated_mon_sun(self):
        from dashboard.data import format_week_range_short

        monday = pd.Timestamp("2026-01-05", tz="UTC")
        self.assertEqual(
            format_week_range_short(monday),
            "Jan 5, 2026 - Jan 11, 2026",
        )

    def test_format_week_range_short_spans_year(self):
        from dashboard.data import format_week_range_short

        monday = pd.Timestamp("2025-12-29", tz="UTC")
        self.assertEqual(
            format_week_range_short(monday),
            "Dec 29, 2025 - Jan 4, 2026",
        )

    def test_week_tooltip_is_iso_week_range(self):
        from dashboard.data import period_tooltip_label

        self.assertEqual(
            period_tooltip_label("2026-02", "Week"),
            "Jan 5, 2026 - Jan 11, 2026",
        )
        self.assertEqual(
            period_tooltip_label("2026-01", "Week"),
            "Dec 29, 2025 - Jan 4, 2026",
        )

    def test_day_month_year_tooltips_keep_existing_formats(self):
        from dashboard.data import period_tooltip_label

        self.assertEqual(
            period_tooltip_label("2026-01-05", "Day"),
            "January 5, 2026",
        )
        self.assertEqual(period_tooltip_label("2026-01", "Month"), "January 2026")
        self.assertEqual(period_tooltip_label("2026", "Year"), "2026")


class LoadRunsParsingTests(unittest.TestCase):
    """Fitness fields parsed from the run analysis CSV."""

    def test_parses_efficiency_fields_and_race_flag(self):
        from dashboard.data import load_runs

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            pd.DataFrame(
                [
                    {
                        "activity_id": "1",
                        "name": "Easy run",
                        "type": "Run",
                        "date": "2026-03-10T08:00:00Z",
                        "distance_miles": "6.2",
                        "elevation_gain_ft": "210.5",
                        "avg_pace_sec": "480",
                        "avg_hr": "148.2",
                        "race": "False",
                    },
                    {
                        "activity_id": "2",
                        "name": "5k",
                        "type": "Run",
                        "date": "2026-03-12T08:00:00Z",
                        "distance_miles": "3.1",
                        "elevation_gain_ft": "40",
                        "avg_pace_sec": "360",
                        "avg_hr": "172",
                        "race": "True",
                    },
                ]
            ).to_csv(data_dir / "strava_run_analysis.csv", index=False)
            runs = load_runs(data_dir)

        self.assertEqual(len(runs), 2)
        self.assertAlmostEqual(float(runs.iloc[0]["avg_hr"]), 148.2)
        self.assertAlmostEqual(float(runs.iloc[0]["avg_pace_sec"]), 480.0)
        self.assertAlmostEqual(float(runs.iloc[0]["elevation_gain_ft"]), 210.5)
        self.assertAlmostEqual(float(runs.iloc[0]["distance_miles"]), 6.2)
        self.assertFalse(bool(runs.iloc[0]["race"]))
        self.assertTrue(bool(runs.iloc[1]["race"]))
        self.assertEqual(str(runs["race"].dtype), "bool")


if __name__ == "__main__":
    unittest.main()
