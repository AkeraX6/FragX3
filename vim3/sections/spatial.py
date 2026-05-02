"""Section 5 — Spatial analysis of the bench."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from kuzram_engine import parse_bench_height

from .. import calculations, insights, plots
from ..config import TARGET_D80_MM
from ..data import bench_subset
from ..ui import insight_box, kpi_row, section_intro


def render(*, linked: pd.DataFrame, qaqc: pd.DataFrame,
           frag: pd.DataFrame, bench: int) -> None:
    section_intro(
        5, "Spatial Analysis",
        "Where on the bench the rock is harder, where the fragmentation "
        "drifts away from target, and where the calibrated zones lie. "
        "Grey holes are the rest of the bench — they share the same "
        "geological context but were not sampled by image analysis."
    )

    rws = float(st.session_state.get("RWS", 100.0))
    bench_holes = bench_subset(linked, bench)
    if bench_holes.empty:
        st.warning("No holes on this bench.")
        return

    cal_holes = calculations.calibrate_per_hole(bench_holes, rws=rws)
    cal_holes = cal_holes.dropna(
        subset=["Local X (Design)", "Local Y (Design)"]
    )
    cal_holes = calculations.add_display_columns(cal_holes)
    st.session_state["cal_holes"] = cal_holes
    st.session_state["bench_holes_all"] = bench_holes

    if cal_holes.empty:
        st.warning("No hole-level calibration available for this bench.")
        return

    median_a_disp = (
        cal_holes["Rock_Factor_A_hole_display"].median()
        if cal_holes["Rock_Factor_A_hole_display"].notna().any()
        else float("nan")
    )
    median_d80_recalc = (
        cal_holes["D80_recalc_mm"].median()
        if "D80_recalc_mm" in cal_holes
        and cal_holes["D80_recalc_mm"].notna().any() else float("nan")
    )

    # Drilling Index = L / (B · S · H) — m of drill per m³ of rock
    bench_h = float(parse_bench_height(bench_holes["Blast"].iloc[0]) or 12.0)
    B_med = float(bench_holes["Burden (Design)"].median())
    S_med = float(bench_holes["Spacing (Design)"].median())
    L_med = float(bench_holes["Hole Length (Actual)"].median())
    di = calculations.drilling_index(L_med, B_med, S_med, bench_h)

    cal_count = cal_holes["D80_recalc_mm"].notna().sum() \
        if "D80_recalc_mm" in cal_holes else 0
    pct_calibrated = cal_count / len(bench_holes) * 100 \
        if len(bench_holes) > 0 else 0.0

    kpi_row([
        ("Bench", f"{bench}"),
        ("Holes mapped", f"{len(bench_holes):,}"),
        ("Calibrated zone", f"{pct_calibrated:.0f}%"),
        ("Median Rock Factor",
         f"{median_a_disp:.1f}" if pd.notna(median_a_disp) else "—"),
        ("Drilling Index",
         f"{di:.3f} m/m³" if pd.notna(di) else "—"),
    ])

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("#### Where the rock is harder / softer")
        st.plotly_chart(
            plots.fig_spatial_rf_grey_base(
                bench_holes, cal_holes, bench,
                col="Rock_Factor_A_hole_display",
            ),
            use_container_width=True,
        )
        insight_box(**insights.spatial_rf(bench, median_a_disp))

    with col_r:
        st.markdown("#### Where fragmentation is coarser / finer")
        st.plotly_chart(
            plots.fig_spatial_d80_grey_base(
                bench_holes, cal_holes, bench,
                col="D80_recalc_mm", target=TARGET_D80_MM,
            ),
            use_container_width=True,
        )
        insight_box(**insights.spatial_d80(bench, median_d80_recalc))
