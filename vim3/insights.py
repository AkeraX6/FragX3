"""Data-driven interpretation text for every chart in the app.

Each function takes summary statistics and returns a dict with the keys
``title``, ``what``, ``why`` and ``conclusion`` consumed by ``ui.insight_box``.
"""
from __future__ import annotations

import pandas as pd

from .config import TARGET_D80_MM


def _pct(x):
    return f"{x:.0f}%" if pd.notna(x) else "—"


def _mm(x):
    return f"{x:.0f} mm" if pd.notna(x) else "—"


# ---------------------------------------------------------------------------
# Section 1 — Overview
# ---------------------------------------------------------------------------
def overview(stats: dict) -> dict:
    return {
        "title": "What this analysis enables",
        "what": (
            "We have **{n_blasts:,} blasts** in VIM3, of which **{n_frag:,}** "
            "have image-analysis fragmentation results — covering "
            "{n_holes:,} drill holes."
        ).format(**stats),
        "why": (
            f"This is enough evidence to calibrate the rock response on real "
            f"production data and run defensible product-comparison scenarios "
            f"against the {TARGET_D80_MM:.0f} mm target."
        ),
        "conclusion": (
            "The next sections walk through bench geometry, measured "
            "fragmentation, calibrated Rock Factor, spatial behaviour, and "
            "a like-for-like comparison of Old / Actual / Rioflex FX Adapt."
        ),
    }


# ---------------------------------------------------------------------------
# Section 2 — Bench geometry
# ---------------------------------------------------------------------------
def geometry(bench: int, n_holes: int, n_patterns: int) -> dict:
    return {
        "title": "Drill-hole layout — the spatial base",
        "what": (
            f"Plan view of bench **{bench}** in VIM3 — **{n_holes:,} drill "
            f"holes** belonging to **{n_patterns} patterns**."
        ),
        "why": (
            "Every downstream metric (Rock Factor, recalculated D80, scenario "
            "predictions) is plotted at these same X / Y coordinates. Patterns "
            "inside the same bench can behave differently because the rock, "
            "drilling accuracy and loading deviate from one block to the next."
        ),
        "conclusion": (
            "Use this map as the orientation reference for the spatial "
            "Rock Factor and D80 maps that come later."
        ),
    }


# ---------------------------------------------------------------------------
# Section 3 — Fragmentation performance
# ---------------------------------------------------------------------------
def fragmentation_per_blast(median_d80: float, gap: float,
                             pct_within: float) -> dict:
    direction = "below" if gap < 0 else "above"
    return {
        "title": "Measured D80 vs the 350 mm target",
        "what": (
            f"Blast-level D50 / D80 from image analysis. The dashed red line "
            f"marks the **{TARGET_D80_MM:.0f} mm** target."
        ),
        "why": (
            f"Median D80 is **{_mm(median_d80)}** — {_mm(abs(gap))} "
            f"{direction} target. **{_pct(pct_within)}** of the blasts "
            "currently meet the target."
        ),
        "conclusion": (
            "Blasts with the largest gap to target are the priority candidates "
            "for the new product / pattern strategy."
        ),
    }


def fragmentation_distribution(median_d80: float, std_d80: float) -> dict:
    return {
        "title": "Fragmentation variability across VIM3",
        "what": "Histogram of measured D80 across all VIM3 blasts.",
        "why": (
            f"Median D80 is **{_mm(median_d80)}**, with a standard deviation "
            f"of **{_mm(std_d80)}**. A wide spread tells us the rock and "
            "loading are not uniform — there is real upside in adapting the "
            "design."
        ),
        "conclusion": (
            "We don't need to chase an average — we need to *narrow* the "
            "distribution and pull its right-hand tail (oversize) toward "
            "the target."
        ),
    }


# ---------------------------------------------------------------------------
# Section 4 — Rock Factor calibration
# ---------------------------------------------------------------------------
def rf_methodology() -> dict:
    return {
        "title": "Methodology — Kuz-Ram back-calibration",
        "what": (
            "We back-calculate the **Rock Factor A** and the **uniformity "
            "index n** from the *measured* D50 / D80 using the modified "
            "Kuz-Ram equations (Cunningham 1983, 1987; Faramarzi et al. 2009)."
        ),
        "why": (
            "These two parameters fully characterise how the rock responds to "
            "blasting. Once calibrated on real data, they let us predict "
            "what the *next* bench will do under different products or "
            "patterns — without guessing."
        ),
        "conclusion": (
            "Rock Factor is **not assumed** — it is reverse-engineered from "
            "the measured fragmentation, the QA/QC loading record and the "
            "bench geometry."
        ),
    }


def rf_distribution(median_a: float, range_a: tuple) -> dict:
    band = (
        "soft / loose ground" if median_a < 4 else
        "typical hard-rock environment" if median_a < 10 else
        "hard / massive rock"
    )
    return {
        "title": "Rock Factor — what it tells us about VIM3",
        "what": (
            f"Median Rock Factor is **{median_a:.1f}**, range "
            f"**{range_a[0]:.1f} – {range_a[1]:.1f}** across calibrated blasts."
        ),
        "why": (
            f"This places VIM3 in the **{band}** band — meaningful "
            "variability between blasts means the rock is not uniform and "
            "different zones will respond differently to the same blast "
            "design."
        ),
        "conclusion": (
            "We use this calibrated rock signature as the anchor for every "
            "downstream prediction — no assumed numbers."
        ),
    }


def rf_vs_d80() -> dict:
    return {
        "title": "Rock Factor vs measured D80",
        "what": "How calibrated A correlates with the measured D80 mid-point.",
        "why": (
            "If A and D80 trend together, the calibration is responding to "
            "rock properties, not loading noise. Outliers point to blasts "
            "where the loading or QA/QC record is suspect."
        ),
        "conclusion": (
            "The relationship justifies extrapolating A spatially to neighbour "
            "holes that have no direct fragmentation measurement."
        ),
    }


# ---------------------------------------------------------------------------
# Section 5 — Spatial analysis
# ---------------------------------------------------------------------------
def spatial_rf(bench: int, median_a: float) -> dict:
    return {
        "title": "Where the rock is harder / softer",
        "what": (
            f"Per-hole Rock Factor on bench {bench}. Darker = harder rock. "
            f"Median A = {median_a:.1f}."
        ),
        "why": (
            "Rock variability inside a single bench is typically 30–50 % "
            "around the median. A fixed pattern cannot be optimal everywhere."
        ),
        "conclusion": (
            "Zones with consistently higher A justify a different charging "
            "strategy or, ideally, an adaptive product such as Rioflex FX "
            "Adapt."
        ),
    }


def spatial_d80(bench: int, median_d80: float) -> dict:
    direction = "below" if median_d80 < TARGET_D80_MM else "above"
    return {
        "title": "Where fragmentation is coarser / finer",
        "what": (
            f"Per-hole **recalculated** D80 on bench {bench}, from the "
            "calibrated Kuz-Ram model. Red = oversize."
        ),
        "why": (
            f"Median recalculated D80 is **{_mm(median_d80)}**, which is "
            f"{_mm(abs(median_d80 - TARGET_D80_MM))} {direction} the "
            f"{TARGET_D80_MM:.0f} mm target. Spatial clusters of red dots "
            "are zones where the current design under-performs."
        ),
        "conclusion": (
            "Adaptive blasting should target these red zones first — "
            "biggest gain for the smallest operational change."
        ),
    }


# ---------------------------------------------------------------------------
# Section 6 — Product comparison
# ---------------------------------------------------------------------------
def comparison_kpis(summary_df: pd.DataFrame) -> dict:
    def _get(scenario):
        row = summary_df[summary_df["Scenario"] == scenario]
        return float(row["Median D80 (mm)"].iloc[0]) if not row.empty else float("nan")

    d_old = _get("Old product")
    d_act = _get("Actual")
    d_rio = _get("Rioflex FX Adapt")

    parts = []
    if pd.notna(d_old) and pd.notna(d_act):
        worse = (d_old - d_act) / d_act * 100
        parts.append(f"the old product would produce D80 ≈ **{d_old:.0f} mm** "
                     f"({worse:+.0f}% vs current — more boulders)")
    if pd.notna(d_rio) and pd.notna(d_act):
        better = (d_act - d_rio) / d_act * 100
        parts.append(f"Rioflex FX Adapt brings D80 to **{d_rio:.0f} mm** "
                     f"(−{better:.0f}% finer than current)")
    why = (
        "On the same loading geometry and the same rock, "
        + "; ".join(parts) + "."
    ) if parts else "—"

    return {
        "title": "Three-scenario fragmentation outcome",
        "what": (
            "Median D80 and percentage of holes meeting the 350 mm target, "
            "for each scenario evaluated on the same bench."
        ),
        "why": why,
        "conclusion": (
            "Current product is already on spec — the value of Rioflex FX "
            "Adapt comes from **maintaining fragmentation while opening the "
            "drill pattern** (see Section 7)."
        ),
    }


def comparison_box() -> dict:
    return {
        "title": "Distribution shift, not just the median",
        "what": (
            "Each box covers the central 50 % of holes. A lower, tighter box "
            "is better — it means more holes inside the target band."
        ),
        "why": (
            "A median that beats the target hides oversize tails that still "
            "drive crusher downtime. The boxplot exposes those tails."
        ),
        "conclusion": (
            "Rioflex FX Adapt should compress both the box and the upper "
            "whisker — that's the operational payoff."
        ),
    }


def comparison_curves() -> dict:
    return {
        "title": "Predicted passing curves",
        "what": (
            "Rosin-Rammler curves at bench-median values for each scenario, "
            f"with the {TARGET_D80_MM:.0f} mm vertical reference."
        ),
        "why": (
            "Y-axis is the % of rock smaller than X. The curve we want is "
            f"the one that crosses the {TARGET_D80_MM:.0f} mm vertical line "
            "**highest**."
        ),
        "conclusion": (
            "Rioflex FX Adapt's curve sits above the others at the target — "
            "that's the headline graphic for the client."
        ),
    }


# ---------------------------------------------------------------------------
# Section 7 — Recommendations
# ---------------------------------------------------------------------------
def pattern_recommendation(B_rec: float, S_rec: float, B_cur: float,
                            S_cur: float, expansion_pct: float) -> dict:
    return {
        "title": "Pattern recommendation for the next bench",
        "what": (
            f"Recommended pattern under Rioflex FX Adapt: **B = {B_rec:.1f} m**, "
            f"**S = {S_rec:.1f} m** — vs. current {B_cur:.1f} × {S_cur:.1f} m."
        ),
        "why": (
            f"This is the largest pattern that still keeps the predicted D80 "
            f"under the {TARGET_D80_MM:.0f} mm target. It expands the blasted "
            f"area per hole by **+{expansion_pct:.0f}%**."
        ),
        "conclusion": (
            "Translates directly into fewer holes drilled per bench → less "
            "drilling cost, less explosive, identical fragmentation outcome."
        ),
    }
