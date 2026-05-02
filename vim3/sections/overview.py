"""Section 1 — Overview / Executive summary."""
from __future__ import annotations

import pandas as pd

from .. import insights
from ..config import TARGET_D80_MM
from ..ui import insight_box, kpi_row, section_intro


def render(*, linked: pd.DataFrame, qaqc: pd.DataFrame,
           frag: pd.DataFrame, bench: int) -> None:
    section_intro(
        1, "Overview & Executive Summary",
        "VIM3 is the focus pit. We use the QA/QC drilling record and "
        "image-analysis fragmentation results to calibrate the rock "
        "response, characterise the bench spatially, and project the "
        f"benefit of moving to **Rioflex FX Adapt** against a "
        f"**{TARGET_D80_MM:.0f} mm** D80 target.",
    )

    n_blasts = linked["Blast"].nunique()
    n_holes = len(linked)
    n_frag = len(frag)
    median_d80 = (
        frag["D80"].median()
        if "D80" in frag.columns and frag["D80"].notna().any()
        else float("nan")
    )
    avg_n = (
        frag["Uniformity index"].mean()
        if "Uniformity index" in frag.columns
        and frag["Uniformity index"].notna().any()
        else float("nan")
    )
    avg_pf = (
        frag["Actual powder factor"].mean()
        if "Actual powder factor" in frag.columns
        and frag["Actual powder factor"].notna().any()
        else float("nan")
    )

    kpi_row([
        ("Blasts analysed", f"{n_blasts:,}"),
        ("Average measured D80",
         f"{median_d80:.0f} mm" if pd.notna(median_d80) else "—"),
        ("Target D80", f"≤ {TARGET_D80_MM:.0f} mm"),
        ("Avg actual PF",
         f"{avg_pf:.3f} kg/m³" if pd.notna(avg_pf) else "—"),
        ("Avg uniformity n",
         f"{avg_n:.2f}" if pd.notna(avg_n) else "—"),
    ])

    insight_box(**insights.overview({
        "n_blasts": n_blasts, "n_frag": n_frag, "n_holes": n_holes,
    }))
