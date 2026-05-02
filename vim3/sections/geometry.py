"""Section 2 — Input data and bench geometry."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import insights, plots
from ..data import bench_subset
from ..ui import insight_box, kpi_row, section_intro


def render(*, linked: pd.DataFrame, qaqc: pd.DataFrame,
           frag: pd.DataFrame, bench: int) -> None:
    section_intro(
        2, "Input Data & Bench Geometry",
        "Two independent records feed the analysis — drilling/loading "
        "(QA/QC) and image-analysis fragmentation (Data_Frag). They are "
        "linked by blast name. This section shows what we're working with "
        "and the layout of the chosen bench.",
    )

    bench_holes = bench_subset(linked, bench)
    n_holes = len(bench_holes)
    n_patterns = bench_holes["Pattern"].nunique() if "Pattern" in bench_holes else 0
    n_blasts = bench_holes["Blast"].nunique()
    n_blasts_frag = (
        bench_holes[bench_holes["D80_measured_mm"].notna()]["Blast"].nunique()
        if "D80_measured_mm" in bench_holes else 0
    )

    kpi_row([
        ("Bench", f"{bench}"),
        ("Holes drilled", f"{n_holes:,}"),
        ("Drill patterns", f"{n_patterns}"),
        ("Blasts on bench", f"{n_blasts}"),
    ])

    # ---- Variables actually used ----------------------------------------
    with st.expander("Variables used in the analysis"):
        st.markdown(
            "**From QA/QC** — `Local X (Design)`, `Local Y (Design)`, "
            "`Diameter (Design)`, `Density`, `Hole Length (Actual)`, "
            "`Explosive (kg) (Actual)`, `Stemming (Actual)`, "
            "`Burden (Design)`, `Spacing (Design)`.\n\n"
            "**From Data_Frag** — `D20`, `D50`, `D80`, `Uniformity index`, "
            "`Actual powder factor`, plus the *Old* counterparts "
            "(`Burden Old`, `Spacing Old`, `Stemming Old`, `Weight Old`, "
            "`Total of Holes Old`) used for the historical product scenario."
        )

    # ---- Bench geometry plot --------------------------------------------
    st.markdown("#### Drill-hole layout — plan view")
    if bench_holes["Local X (Design)"].notna().any():
        st.plotly_chart(plots.fig_bench_geometry(bench_holes, bench),
                        use_container_width=True)
        insight_box(**insights.geometry(bench, n_holes, n_patterns))
    else:
        st.warning("No design coordinates available for this bench.")

    # ---- Sample table ----------------------------------------------------
    with st.expander("Linked hole sample (first 25 rows)"):
        cols = [c for c in [
            "Blast", "Bench", "Pattern", "Borehole",
            "Local X (Design)", "Local Y (Design)",
            "Hole Length (Actual)", "Explosive (kg) (Actual)",
            "Stemming (Actual)", "Burden (Design)", "Spacing (Design)",
            "D50_measured_mm", "D80_measured_mm",
        ] if c in bench_holes.columns]
        st.dataframe(bench_holes[cols].head(25),
                     use_container_width=True, hide_index=True)
