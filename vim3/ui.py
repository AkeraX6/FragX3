"""Reusable UI primitives — keeps section files declarative.

* ``page_setup``     — st.set_page_config + global CSS
* ``app_header``     — sticky title bar with KPI strip
* ``sidebar_nav``    — section radio + persistent bench selector
* ``section_intro``  — section number, title, lead paragraph
* ``insight_box``    — styled "what / why / take-away" card under each chart
* ``kpi_row``        — equal-width metric cards
* ``methodology_box``— expandable scientific reference box
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd
import streamlit as st

from .config import (
    PALETTE, PIT_LABEL, RECOMMENDED_BENCH, SECTIONS, TARGET_D80_MM,
)


# ---------------------------------------------------------------------------
# Page-level
# ---------------------------------------------------------------------------
def page_setup():
    st.set_page_config(
        page_title=f"{PIT_LABEL} Blast Performance & Fragmentation Analysis",
        page_icon="💥",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(f"""
        <style>
            .block-container {{ padding-top: 1.4rem; padding-bottom: 2rem; }}
            h1, h2, h3 {{ color: {PALETTE['primary']}; }}
            .vim3-insight {{
                background: #F4F6F7;
                border-left: 4px solid {PALETTE['accent']};
                padding: 0.85em 1.1em;
                margin: 0.4em 0 1.4em 0;
                border-radius: 4px;
                font-size: 0.94em;
                line-height: 1.55em;
            }}
            .vim3-insight .ttl {{
                color: {PALETTE['primary']};
                font-weight: 600;
                display: block;
                margin-bottom: 0.25em;
            }}
            .vim3-insight .lbl {{
                color: {PALETTE['primary']};
                font-weight: 600;
            }}
            .vim3-method {{
                background: #FFF8E1;
                border-left: 4px solid {PALETTE['warn']};
                padding: 0.85em 1.1em;
                margin: 0.4em 0 1.4em 0;
                border-radius: 4px;
                font-size: 0.92em;
            }}
            .vim3-tag {{
                display:inline-block; padding:2px 8px; border-radius: 10px;
                color: white; font-size: 0.78em; margin-right: 0.4em;
            }}
        </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
def app_header(linked: pd.DataFrame, frag: pd.DataFrame):
    st.title(f"{PIT_LABEL} · Blast Performance & Fragmentation Analysis")
    st.caption(
        f"Calibrating the rock response on real production data and "
        f"projecting the impact of **Rioflex FX Adapt** against the "
        f"**{TARGET_D80_MM:.0f} mm** D80 target. — A first step toward "
        f"X-Energy / Smart Rioflex workflows."
    )

    n_blasts = linked["Blast"].nunique()
    n_holes = len(linked)
    n_frag = len(frag)
    median_d80 = (
        frag["D80"].median()
        if "D80" in frag.columns and frag["D80"].notna().any() else float("nan")
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Pit", PIT_LABEL)
    c2.metric("Blasts (QA/QC)", f"{n_blasts:,}")
    c3.metric("Holes (QA/QC)", f"{n_holes:,}")
    c4.metric("Blasts with frag", f"{n_frag:,}")
    c5.metric("Target D80", f"≤ {TARGET_D80_MM:.0f} mm")
    st.divider()


# ---------------------------------------------------------------------------
# Sidebar nav
# ---------------------------------------------------------------------------
def sidebar_nav(bench_options: list) -> tuple:
    st.sidebar.header("📑 Sections")
    keys = [k for k, _ in SECTIONS]
    labels = [lbl for _, lbl in SECTIONS]
    chosen_label = st.sidebar.radio(
        "Step", labels, label_visibility="collapsed", key="nav_section",
    )
    section_key = keys[labels.index(chosen_label)]

    st.sidebar.divider()
    st.sidebar.subheader("Bench")
    if not bench_options:
        st.sidebar.error("No valid benches in VIM3.")
        return section_key, None

    default_idx = (
        bench_options.index(RECOMMENDED_BENCH)
        if RECOMMENDED_BENCH in bench_options
        else len(bench_options) - 1
    )
    bench = st.sidebar.selectbox(
        "Working bench", bench_options, index=default_idx,
        help=f"Bench {RECOMMENDED_BENCH} is the recommended demo bench "
             "(highest data quality).",
        key="nav_bench",
    )
    if bench == RECOMMENDED_BENCH:
        st.sidebar.success(f"⭐ Bench {bench} — recommended demo bench")
    else:
        st.sidebar.info(f"Demo recommendation: bench {RECOMMENDED_BENCH}")
    st.sidebar.divider()
    st.sidebar.markdown(
        f"**Client target**  \nD80 ≤ {TARGET_D80_MM:.0f} mm  \n"
        f"**"
    )
    return section_key, bench


# ---------------------------------------------------------------------------
# Section primitives
# ---------------------------------------------------------------------------
def section_intro(number: int, title: str, lead: str):
    st.subheader(f"Section {number} · {title}")
    st.markdown(lead)
    st.markdown("")


def kpi_row(items: Iterable[tuple]):
    """``items`` = iterable of (label, value, delta_or_None, help_or_None)."""
    items = list(items)
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        label, value, *rest = item
        delta = rest[0] if len(rest) > 0 else None
        help_t = rest[1] if len(rest) > 1 else None
        col.metric(label, value, delta=delta, help=help_t)


def insight_box(title: str, what: str, why: str, conclusion: str):
    st.markdown(f"""
        <div class="vim3-insight">
            <span class="ttl">📊 {title}</span>
            <span class="lbl">What:</span> {what}<br>
            <span class="lbl">Why it matters:</span> {why}<br>
            <span class="lbl">Take-away:</span> {conclusion}
        </div>
    """, unsafe_allow_html=True)


def methodology_box(text_md: str):
    st.markdown(f"""
        <div class="vim3-method">{text_md}</div>
    """, unsafe_allow_html=True)


def tag(text: str, color: str):
    return (
        f'<span class="vim3-tag" style="background:{color}">{text}</span>'
    )
