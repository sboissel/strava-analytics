"""Runner's Dashboard — Streamlit entrypoint."""

from __future__ import annotations

import streamlit as st

import _bootstrap  # noqa: F401

from theme import GLOBAL_CSS

st.set_page_config(
    page_title="Runner's Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

overview = st.Page("pages/training_overview.py", title="Training Overview", default=True)
insights = st.Page("pages/training_insights.py", title="Training Insights")
races = st.Page("pages/race_results.py", title="Race Results")

st.markdown(
    """
    <div class="hero">
      <div class="hero-kicker">Strava analytics</div>
      <h1 class="hero-title">Runner’s Dashboard</h1>
    </div>
    """,
    unsafe_allow_html=True,
)

pg = st.navigation(
    [overview, insights, races],
    position="sidebar",
    expanded=True,
)
pg.run()
