"""Runner's Dashboard — Streamlit entrypoint."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import streamlit as st

# Load by absolute path so a stale/wrong ``_bootstrap`` in ``sys.modules``
# (Streamlit Cloud mixed deploys) cannot win over ``dashboard/_bootstrap.py``.
_DASHBOARD_ROOT = Path(__file__).resolve().parent
_bs_spec = importlib.util.spec_from_file_location(
    "_sa_dashboard_bootstrap",
    _DASHBOARD_ROOT / "_bootstrap.py",
)
assert _bs_spec is not None and _bs_spec.loader is not None
_bootstrap = importlib.util.module_from_spec(_bs_spec)
sys.modules["_sa_dashboard_bootstrap"] = _bootstrap
sys.modules["_bootstrap"] = _bootstrap
_bs_spec.loader.exec_module(_bootstrap)
_bootstrap.bootstrap()

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
