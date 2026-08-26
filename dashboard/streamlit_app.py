"""Runner's Dashboard — Streamlit entrypoint."""

from __future__ import annotations

import streamlit as st

import _bootstrap  # noqa: F401

_bootstrap.ensure_sys_path()

from theme import GLOBAL_CSS


def _is_embed_mode() -> bool:
    """Return True when the app is loaded inside an iframe embed."""
    try:
        embed = st.query_params.get("embed", "")
        if isinstance(embed, list):
            embed = embed[0] if embed else ""
        return str(embed).lower() in ("true", "1", "yes")
    except Exception:
        return False


st.set_page_config(
    page_title="Runner's Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed" if _is_embed_mode() else "expanded",
)

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

training = st.Page("pages/training.py", title="Training")
fitness = st.Page("pages/fitness.py", title="Fitness")
performance = st.Page("pages/performance.py", title="Performance")
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
    [metrics, training, fitness, performance],
    position="hidden",
)
pg.run()
