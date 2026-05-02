"""VIM3 Blast Performance & Fragmentation Analysis — entrypoint.

Run with::

    streamlit run app.py

The app is scoped to pit VIM3. Modules live in the ``vim3/`` package — see
``vim3/sections/`` for the seven client-presentation sections.
"""
from __future__ import annotations

import streamlit as st

from vim3 import sections
from vim3.data import available_benches, load_all
from vim3.ui import app_header, page_setup, sidebar_nav

# ---------------------------------------------------------------------------
# Page chrome
# ---------------------------------------------------------------------------
page_setup()

# ---------------------------------------------------------------------------
# Data load (cached)
# ---------------------------------------------------------------------------
qaqc, frag, linked = load_all()

if linked.empty:
    st.error(
        "No QA/QC data found for VIM3 in `Blast_QAQC.csv`. "
        "Verify the file is in the project folder."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar navigation + bench selector
# ---------------------------------------------------------------------------
benches = available_benches(linked)
section_key, bench = sidebar_nav(benches)

if bench is None:
    st.stop()

# ---------------------------------------------------------------------------
# Sticky header (KPI strip)
# ---------------------------------------------------------------------------
app_header(linked, frag)

# ---------------------------------------------------------------------------
# Section router
# ---------------------------------------------------------------------------
ROUTER = {
    "overview":        sections.overview.render,
    "geometry":        sections.geometry.render,
    "fragmentation":   sections.fragmentation.render,
    "calibration":     sections.calibration.render,
    "spatial":         sections.spatial.render,
    "comparison":      sections.comparison.render,
    "recommendations": sections.recommendations.render,
}
ROUTER[section_key](
    linked=linked, qaqc=qaqc, frag=frag, bench=bench,
)
