"""Section 3 — Fragmentation Performance."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import insights, plots
from ..config import TARGET_D80_MM
from ..data import parse_blast_key
from ..ui import insight_box, kpi_row, section_intro


def render(*, linked: pd.DataFrame, qaqc: pd.DataFrame,
           frag: pd.DataFrame, bench: int) -> None:
    section_intro(
        3, "Fragmentation Performance",
        "What did the bench actually deliver? Image-analysis results are "
        f"compared against the **{TARGET_D80_MM:.0f} mm** D80 target.",
    )

    # Filter Data_Frag to blasts present on this bench
    bench_blasts = (
        linked[
            pd.to_numeric(linked["Bench"], errors="coerce") == bench
        ]["Blast"].dropna().apply(parse_blast_key).unique()
    )
    frag_bench = frag[frag["_key"].isin(bench_blasts)].copy()

    if frag_bench.empty or frag_bench["D80"].isna().all():
        st.warning(f"No measured fragmentation linked to bench {bench}. "
                   "Try a different bench.")
        return

    median_d80 = frag_bench["D80"].median()
    median_d50 = frag_bench["D50"].median() if "D50" in frag_bench else float("nan")
    pct_within = (frag_bench["D80"] <= TARGET_D80_MM).mean() * 100
    gap = median_d80 - TARGET_D80_MM
    n_idx = (
        frag_bench["Uniformity index"].mean()
        if "Uniformity index" in frag_bench
        and frag_bench["Uniformity index"].notna().any() else float("nan")
    )
    p600 = (
        frag_bench["Passing on 600 mm pourcentage"].mean()
        if "Passing on 600 mm pourcentage" in frag_bench
        and frag_bench["Passing on 600 mm pourcentage"].notna().any()
        else float("nan")
    )

    kpi_row([
        ("Median D50",
         f"{median_d50:.0f} mm" if pd.notna(median_d50) else "—"),
        ("Median D80",
         f"{median_d80:.0f} mm",
         f"{gap:+.0f} mm vs target",
         "Negative = below target (good)."),
        ("% blasts ≤ target", f"{pct_within:.0f}%"),
        ("Mean uniformity n",
         f"{n_idx:.2f}" if pd.notna(n_idx) else "—"),
        ("Avg % passing 600 mm",
         f"{p600:.1f}%" if pd.notna(p600) else "—"),
    ])

    st.markdown("#### Measured D50 / D80 per blast")
    st.plotly_chart(plots.fig_d80_per_blast(frag_bench, TARGET_D80_MM),
                    use_container_width=True)
    insight_box(**insights.fragmentation_per_blast(median_d80, gap, pct_within))

    st.markdown("#### Fragmentation distribution across the whole pit")
    std_d80 = frag["D80"].std() if "D80" in frag else float("nan")
    st.plotly_chart(plots.fig_d80_distribution(frag, TARGET_D80_MM),
                    use_container_width=True)
    insight_box(**insights.fragmentation_distribution(
        frag["D80"].median() if "D80" in frag else float("nan"),
        std_d80,
    ))

    with st.expander("Per-blast fragmentation indicators (this bench)"):
        cols = [c for c in [
            "DATE", "BLAST", "Type of Material",
            "D20", "D50", "D80", "Xmas (mm)",
            "Uniformity index", "Actual powder factor",
            "Passing on 600 mm pourcentage",
        ] if c in frag_bench.columns]
        st.dataframe(frag_bench[cols].sort_values("D80"),
                     use_container_width=True, hide_index=True)
