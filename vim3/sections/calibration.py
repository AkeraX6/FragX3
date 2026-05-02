"""Section 4 — Rock Factor calibration."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import calculations, insights, plots
from ..config import ANFO_RWS, ROCK_FACTOR_DISPLAY_MULTIPLIER
from ..ui import insight_box, kpi_row, methodology_box, section_intro


def render(*, linked: pd.DataFrame, qaqc: pd.DataFrame,
           frag: pd.DataFrame, bench: int) -> None:
    section_intro(
        4, "Rock Factor Calibration",
        "We back-calculate the **Rock Factor** of the rock mass from the "
        "real fragmentation results and the loading record. This number is "
        "what every prediction in the next sections is anchored on — "
        "we don't guess the rock, we measure it.",
    )

    cal = calculations.calibrate_per_blast(qaqc, frag, rws=ANFO_RWS)
    cal_view = cal.dropna(subset=["Rock_Factor_A"]).copy()

    if cal_view.empty:
        st.warning("No calibration could be computed for VIM3.")
        return

    # Apply display scaling for client KPIs
    cal_view = calculations.add_display_columns(cal_view)

    median_a_disp = cal_view["Rock_Factor_A_display"].median()
    a_min_disp = cal_view["Rock_Factor_A_display"].min()
    a_max_disp = cal_view["Rock_Factor_A_display"].max()
    n_med = (
        cal_view["n_backcalc"].median()
        if "n_backcalc" in cal_view else float("nan")
    )

    # Persist the *internal* (un-scaled) value for the engine
    st.session_state["A_pit_median"] = float(cal_view["Rock_Factor_A"].median())
    st.session_state["RWS"] = float(ANFO_RWS)

    # Classify the rock
    band = (
        "Soft / loose rock"
        if median_a_disp < 4 else
        "Typical hard-rock environment"
        if median_a_disp < 10 else
        "Hard / massive rock"
    )

    kpi_row([
        ("Calibrated blasts", f"{len(cal_view)}"),
        ("Median Rock Factor", f"{median_a_disp:.1f}",
         band, None),
        ("Range", f"{a_min_disp:.1f} – {a_max_disp:.1f}"),
        ("Median uniformity n",
         f"{n_med:.2f}" if pd.notna(n_med) else "—"),
    ])

    insight_box(**insights.rf_methodology())

    st.markdown("#### Rock Factor distribution")
    # Re-use existing histogram on the display column
    import plotly.express as px
    from ..config import PALETTE, PLOTLY_TEMPLATE, DEFAULT_HEIGHT
    fig_h = px.histogram(
        cal_view, x="Rock_Factor_A_display", nbins=15,
        title="Rock Factor across calibrated blasts",
        color_discrete_sequence=[PALETTE["primary"]],
    )
    fig_h.update_layout(
        template=PLOTLY_TEMPLATE, height=DEFAULT_HEIGHT,
        xaxis_title="Rock Factor", yaxis_title="Number of blasts",
    )
    st.plotly_chart(fig_h, use_container_width=True)
    insight_box(**insights.rf_distribution(median_a_disp,
                                            (a_min_disp, a_max_disp)))

    # Methodology kept available, but tucked behind an expander
    with st.expander("Methodology — how Rock Factor is computed"):
        methodology_box(
            "**Modified Kuz-Ram framework** (Cunningham 1983, 1987; "
            "Faramarzi et al. 2009).\n\n"
            "1. Powder factor `K = Q / (B · S · H)` &nbsp;[kg/m³]\n"
            "2. Kuznetsov mean size `X50 = A · K^(-0.8) · Q^(1/6) · "
            "(115/RWS)^(19/30)`\n"
            "3. Cunningham uniformity index from blast geometry.\n"
            "4. Rosin-Rammler distribution links D50 to D80.\n"
            "5. Rock Factor is solved by inversion from measured D50.\n\n"
            "Inputs taken directly from QA/QC and Data_Frag — Hole Length "
            "(Actual), Explosive (kg) (Actual), Stemming (Actual), Burden, "
            "Spacing, Diameter, Density, measured D50/D80."
        )
