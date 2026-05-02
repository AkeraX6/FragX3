"""Section 6 — Old / Actual / Rioflex FX product comparison."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import calculations, insights, plots, simulation
from ..config import (
    OLD_PRODUCT_RWS, RIOFLEX_N_LIFT, RIOFLEX_RWS, TARGET_D80_MM,
)
from ..data import bench_subset
from ..plots import SCENARIO_SPECS
from ..ui import insight_box, kpi_row, section_intro


def render(*, linked: pd.DataFrame, qaqc: pd.DataFrame,
           frag: pd.DataFrame, bench: int) -> None:
    section_intro(
        6, "Product Comparison",
        "The same bench, the same rock — only the explosive product changes:\n\n"
        "* **Old product** — what the operation used before (weaker emulsion).\n"
        "* **Actual** — current emulsion, calibrated against measured fragmentation.\n"
        "* **Rioflex FX Adapt** — the proposed product, moderately stronger "
        "with better energy distribution.\n\n"
        f"Client target: **D80 ≤ {TARGET_D80_MM:.0f} mm**."
    )

    cal_holes = st.session_state.get("cal_holes")
    bench_holes_all = st.session_state.get("bench_holes_all")

    if cal_holes is None or cal_holes.empty:
        bench_holes_all = bench_subset(linked, bench)
        cal_holes = calculations.calibrate_per_hole(
            bench_holes_all, rws=float(st.session_state.get("RWS", 100.0)),
        ).dropna(subset=["Local X (Design)", "Local Y (Design)"])
        cal_holes = calculations.add_display_columns(cal_holes)
        st.session_state["cal_holes"] = cal_holes
        st.session_state["bench_holes_all"] = bench_holes_all

    if cal_holes is None or cal_holes.empty:
        st.warning("No bench-level calibration available — go back to "
                   "Section 4 / 5.")
        return

    A_pit = float(st.session_state.get("A_pit_median", 8.0))
    out = simulation.simulate_bench(
        cal_holes, a_pit_median=A_pit,
        old_rws=OLD_PRODUCT_RWS,
        new_rws=RIOFLEX_RWS,
        n_lift=RIOFLEX_N_LIFT,
    )
    summary = simulation.scenario_summary(out, target=TARGET_D80_MM)
    st.session_state["scenario_holes"] = out
    st.session_state["scenario_summary"] = summary

    # ---- KPI cards -------------------------------------------------------
    cols = st.columns(3)
    for col, (name, dcol, color) in zip(cols, SCENARIO_SPECS):
        v = out[dcol].dropna() if dcol in out else pd.Series(dtype=float)
        if v.empty:
            col.metric(name, "—")
            continue
        med = v.median()
        pct_ok = (v <= TARGET_D80_MM).mean() * 100
        col.metric(
            name, f"{med:.0f} mm",
            delta=f"{pct_ok:.0f}% ≤ target",
            delta_color="normal" if pct_ok >= 70 else "inverse",
        )

    insight_box(**insights.comparison_kpis(summary))

    # ---- Side-by-side spatial maps with grey base -----------------------
    st.markdown("#### Side-by-side bench maps — three scenarios")
    plot_cols = st.columns(3)
    for col, (name, dcol, _) in zip(plot_cols, SCENARIO_SPECS):
        if dcol not in out or out[dcol].dropna().empty:
            col.warning(f"No D80 for {name}.")
            continue
        fig = plots.fig_spatial_d80_grey_base(
            bench_holes_all, out, bench,
            col=dcol, target=TARGET_D80_MM,
            title_suffix=name,
        )
        fig.update_layout(height=470)
        col.plotly_chart(fig, use_container_width=True,
                         key=f"t6_map_{name}")
    st.caption(
        "Grey holes mark the rest of the bench (no measured fragmentation). "
        "Coloured holes are inside the calibrated zone — they show how the "
        "size distribution shifts when only the explosive product changes."
    )

    # ---- Distribution shift ---------------------------------------------
    st.markdown("#### Distribution shift across the bench")
    st.plotly_chart(plots.fig_scenario_box(out, TARGET_D80_MM),
                    use_container_width=True)
    insight_box(**insights.comparison_box())

    # ---- Summary table for the client -----------------------------------
    st.markdown("#### Three-scenario summary")
    st.dataframe(summary, use_container_width=True, hide_index=True)
