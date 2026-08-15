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

training = st.Page("pages/training.py", title="Training")
fitness = st.Page("pages/fitness.py", title="Fitness")
races = st.Page("pages/race_results.py", title="Race Results")
metrics = st.Page("pages/metrics.py", title="Metrics", default=True)

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
    [metrics, training, fitness, races],
    position="hidden",
)
pg.run()
