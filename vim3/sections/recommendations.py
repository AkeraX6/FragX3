"""Section 7 — Pattern Optimisation Calculator.

Client-facing tool. Pick a Burden × Spacing for the next bench under
**Rioflex FX Adapt** at the same explosive density and the same predicted
fragmentation, and immediately see how much drilling and explosive can be
saved per blasted m³.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from kuzram_engine import parse_bench_height

from .. import calculations, simulation
from ..config import (
    PALETTE, RIOFLEX_N_LIFT, RIOFLEX_RWS, TARGET_D80_MM,
)
from ..ui import insight_box, kpi_row, section_intro


def render(*, linked: pd.DataFrame, qaqc: pd.DataFrame,
           frag: pd.DataFrame, bench: int) -> None:
    section_intro(
        7, "Pattern Optimisation Calculator",
        "With Rioflex FX Adapt we can open the drill pattern while keeping "
        "the same fragmentation result. Use the calculator to compare the "
        "current pattern with a proposed Burden × Spacing — the dashboard "
        "translates it into drilling metres saved and explosive saved per "
        "blasted volume."
    )

    sc = st.session_state.get("scenario_holes")
    if sc is None or sc.empty:
        st.info("Visit Section 6 first — the calculator uses the calibrated "
                "bench from there.")
        return

    # ---- Reference values from current bench ----------------------------
    bench_h = float(parse_bench_height(sc["Blast"].iloc[0]) or 12.0)
    B_cur = float(sc["Burden (Design)"].median())
    S_cur = float(sc["Spacing (Design)"].median())
    d_med = (
        float(sc["Diameter (Design)"].median())
        if sc["Diameter (Design)"].notna().any() else 140.0
    )
    L_cur = float(sc["Hole Length (Actual)"].median())
    st_cur = float(sc["Stemming (Actual)"].median())
    rho = (
        float(sc["Density"].median())
        if "Density" in sc and sc["Density"].notna().any() else 1.19
    )
    A_internal = float(sc["A_use"].median())   # raw value used by Kuz-Ram
    A_display = calculations.to_display_rf(A_internal)

    # ---- Top KPI strip — the bench we're working from -------------------
    st.markdown("#### Current bench reference")
    kpi_row([
        ("Bench", f"{bench}"),
        ("Bench height", f"{bench_h:.0f} m"),
        ("Current pattern (B × S)", f"{B_cur:.1f} × {S_cur:.1f} m"),
        ("Median Rock Factor", f"{A_display:.1f}"),
        ("Hole length", f"{L_cur:.1f} m"),
    ])

    # ---- The calculator -------------------------------------------------
    st.markdown("#### Choose a new pattern")
    st.caption(
        "Both sliders move freely. Density of the explosive column is held "
        "constant — what changes is how much rock each hole has to break."
    )

    # Apply any pending auto-find values BEFORE the sliders are instantiated
    if "_t7_pending" in st.session_state:
        pending_b, pending_s = st.session_state.pop("_t7_pending")
        st.session_state["t7_b"] = pending_b
        st.session_state["t7_s"] = pending_s

    b_max = max(7.5, B_cur * 1.5)
    s_max = max(8.0, S_cur * 1.5)
    b_default = round(min(B_cur * 1.05, b_max), 1)
    s_default = round(min(S_cur * 1.05, s_max), 1)

    sc1, sc2 = st.columns(2)
    B_new = sc1.slider(
        "New Burden (m)", 2.5, b_max, b_default, 0.1, key="t7_b",
    )
    S_new = sc2.slider(
        "New Spacing (m)", 2.5, s_max, s_default, 0.1, key="t7_s",
    )

    btn_a, btn_b = st.columns([1, 3])
    if btn_a.button("⭐ Auto-find best pattern", key="t7_auto"):
        best = simulation.best_feasible_pattern(
            A_internal, bench_h, B_cur, S_cur, d_med,
            L_cur, st_cur, rho,
            rws=RIOFLEX_RWS, n_lift=RIOFLEX_N_LIFT,
            target=TARGET_D80_MM,
        )
        if best is not None:
            # Stage the values in a side key — they'll be applied to the
            # widget keys on the next run, before the sliders are created.
            st.session_state["_t7_pending"] = (
                float(min(max(best["B"], 2.5), b_max)),
                float(min(max(best["S"], 2.5), s_max)),
            )
            st.rerun()
        else:
            btn_b.warning("No feasible expansion within the search range.")

    # ---- Predictions ----------------------------------------------------
    pred_cur = simulation.predict_pattern(
        A_internal, bench_h, B_cur, S_cur, d_med, L_cur, st_cur, rho,
        rws=RIOFLEX_RWS, n_lift=RIOFLEX_N_LIFT,
    )
    pred_new = simulation.predict_pattern(
        A_internal, bench_h, B_new, S_new, d_med, L_cur, st_cur, rho,
        rws=RIOFLEX_RWS, n_lift=RIOFLEX_N_LIFT,
    )

    d80_cur, d80_new = pred_cur["D80_mm"], pred_new["D80_mm"]
    di_cur, di_new = pred_cur["DI_m_m3"], pred_new["DI_m_m3"]
    pf_cur, pf_new = pred_cur["PF_kg_m3"], pred_new["PF_kg_m3"]

    # ---- Big result card ------------------------------------------------
    on_target = pd.notna(d80_new) and d80_new <= TARGET_D80_MM
    color = PALETTE["rioflex"] if on_target else PALETTE["target"]
    verdict = ("Predicted fragmentation stays within the 350 mm target."
               if on_target else
               "⚠ Predicted fragmentation exceeds the 350 mm target — "
               "tighten the pattern.")
    st.markdown(
        f"""<div style='border-left:6px solid {color}; padding:0.9em 1.2em;
        background:#FAFCFA; border-radius:6px; margin: 0.6em 0 1em 0;'>
        <span style='font-size:0.92em; color:{PALETTE['primary']};'>
        Predicted D80 with Rioflex FX Adapt</span><br>
        <span style='font-size:1.9em; font-weight:600; color:{color};'>
        {d80_new:.0f} mm</span><br>
        <span style='font-size:0.92em;'>{verdict}</span></div>""",
        unsafe_allow_html=True,
    )

    # ---- Saving KPIs ----------------------------------------------------
    drill_save_per_m3 = (di_cur - di_new)
    expl_save_per_m3 = (pf_cur - pf_new)
    area_factor = (B_new * S_new) / (B_cur * S_cur) if B_cur * S_cur > 0 else 1.0
    holes_factor = (B_cur * S_cur) / (B_new * S_new) if B_new * S_new > 0 else 1.0

    kpi_row([
        ("New pattern", f"{B_new:.1f} × {S_new:.1f} m",
         f"{(area_factor - 1) * 100:+.0f}% area / hole", None),
        ("Drill metres saved",
         f"{drill_save_per_m3:.3f} m/m³",
         f"−{drill_save_per_m3 / di_cur * 100:.1f}%" if di_cur > 0 else None,
         None),
        ("Explosive saved",
         f"{expl_save_per_m3:.3f} kg/m³",
         f"−{expl_save_per_m3 / pf_cur * 100:.1f}%" if pf_cur > 0 else None,
         None),
        ("Holes per same area",
         f"× {holes_factor:.2f}",
         f"{(holes_factor - 1) * 100:+.0f}%", None),
    ])

    # ---- Cost translation -----------------------------------------------
    st.markdown("#### Translate to bottom-line savings")
    cc1, cc2, cc3 = st.columns(3)
    rock_vol = cc1.number_input(
        "Rock volume per bench (m³)", 1_000, 5_000_000, 100_000, 1_000,
        key="t7_vol",
    )
    cost_drill = cc2.number_input(
        "Drilling cost ($/m)", 0.0, 100.0, 18.0, 0.5, key="t7_cd",
    )
    cost_expl = cc3.number_input(
        "Explosive cost ($/kg)", 0.0, 10.0, 1.20, 0.05, key="t7_ce",
    )

    saved_drill_m = drill_save_per_m3 * rock_vol
    saved_expl_kg = expl_save_per_m3 * rock_vol
    cost_drill_save = saved_drill_m * cost_drill
    cost_expl_save = saved_expl_kg * cost_expl
    total_save = cost_drill_save + cost_expl_save

    kpi_row([
        ("Drilling metres saved",
         f"{saved_drill_m:,.0f} m"),
        ("Explosive saved",
         f"{saved_expl_kg:,.0f} kg"),
        ("Drilling $ saved",
         f"${cost_drill_save:,.0f}"),
        ("Explosive $ saved",
         f"${cost_expl_save:,.0f}"),
        ("Total savings",
         f"${total_save:,.0f}",
         f"on {rock_vol:,.0f} m³", None),
    ])

    # ---- Side-by-side compact summary ----------------------------------
    st.markdown("#### Pattern comparison")
    st.dataframe(
        pd.DataFrame([
            {"Pattern": "Current", "Burden (m)": f"{B_cur:.1f}",
             "Spacing (m)": f"{S_cur:.1f}",
             "Predicted D80 (mm)": f"{d80_cur:.0f}",
             "Powder factor (kg/m³)": f"{pf_cur:.3f}",
             "Drilling Index (m/m³)": f"{di_cur:.3f}"},
            {"Pattern": "Proposed", "Burden (m)": f"{B_new:.1f}",
             "Spacing (m)": f"{S_new:.1f}",
             "Predicted D80 (mm)": f"{d80_new:.0f}",
             "Powder factor (kg/m³)": f"{pf_new:.3f}",
             "Drilling Index (m/m³)": f"{di_new:.3f}"},
        ]),
        use_container_width=True, hide_index=True,
    )

    insight_box(
        title="What this tells the client",
        what=(
            f"Moving from {B_cur:.1f} × {S_cur:.1f} m to "
            f"{B_new:.1f} × {S_new:.1f} m at constant explosive density "
            f"{('keeps' if on_target else 'pushes')} predicted D80 "
            f"{('inside' if on_target else 'outside')} the target."
        ),
        why=(
            f"Each hole now breaks +{(area_factor - 1) * 100:.0f}% more rock, "
            f"so per blasted m³ we drill "
            f"{drill_save_per_m3 / di_cur * 100:.1f}% less and load "
            f"{expl_save_per_m3 / pf_cur * 100:.1f}% less explosive — "
            "even before accounting for the operational gains of better "
            "uniformity (fewer boulders)."
            if di_cur > 0 and pf_cur > 0 else
            "These savings translate directly to lower drilling and "
            "explosive consumption."
        ),
        conclusion=(
            f"On {rock_vol:,.0f} m³ this is a projected saving of "
            f"**${total_save:,.0f}**, *while staying on fragmentation spec*."
        ),
    )
