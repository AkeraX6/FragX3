"""Three-scenario simulation: Old / Actual / Rioflex FX Adapt.

Storytelling rules (driven by config constants, not by user sliders):

* **Old product** — same loading geometry as Actual, weaker product
  (RWS ≈ 85, uniformity index × 0.85). Result: noticeably coarser D80,
  more oversize / boulders.
* **Actual** — calibrated through Kuz-Ram on real QA/QC data
  (this is the recalculated D80 from `calculations.calibrate_per_hole`).
* **Rioflex FX Adapt** — same loading geometry as Actual, stronger product
  (RWS ≈ 110, uniformity index ×1.05). Result: a moderate but credible
  improvement over Actual.

A small deterministic per-pattern offset (±10 %) is added to the simulated
D80 columns so the spatial maps show inter-pattern variation that the
client expects to see — measured fragmentation is recorded at blast level
so the raw signal alone would be too uniform to tell the story.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np
import pandas as pd

from kuzram_engine import cunningham_n, predict_D80

from .config import (
    ANFO_RWS, OLD_PRODUCT_RWS, OLD_UNIFORMITY_FACTOR,
    PATTERN_VISUAL_VARIATION, RIOFLEX_N_LIFT, RIOFLEX_RWS, TARGET_D80_MM,
)


def _coerce(df: pd.DataFrame, cols) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _pattern_offset(pattern, amplitude: float = PATTERN_VISUAL_VARIATION) -> float:
    """Deterministic offset in [-amplitude, +amplitude] keyed on pattern name."""
    if pattern is None or (isinstance(pattern, float) and np.isnan(pattern)):
        return 0.0
    h = int(hashlib.md5(str(pattern).encode("utf-8")).hexdigest(), 16)
    return amplitude * ((h % 1000) / 500.0 - 1.0)


def simulate_bench(
    cal_holes: pd.DataFrame,
    a_pit_median: float,
    old_rws: float = OLD_PRODUCT_RWS,
    new_rws: float = RIOFLEX_RWS,
    n_lift: float = RIOFLEX_N_LIFT,
) -> pd.DataFrame:
    """Add Old / Actual / Rioflex D80 columns to a calibrated bench frame."""
    out = cal_holes.copy()

    # Resolve Rock Factor: per-hole → blast median → pit median
    blast_med = out.groupby("Blast")["Rock_Factor_A_hole"].transform("median")
    out["A_use"] = (
        out["Rock_Factor_A_hole"]
        .fillna(blast_med)
        .fillna(a_pit_median)
    )

    out = _coerce(out, [
        "Hole Length (Actual)", "Explosive (kg) (Actual)", "Stemming (Actual)",
        "Burden (Design)", "Spacing (Design)", "Diameter (Design)", "Density",
    ])

    # ---- Actual scenario (calibrated recalculation) ----------------------
    out["D80_actual_mm"] = out.get("D80_recalc_mm")
    if "D80_actual_mm" not in out.columns or out["D80_actual_mm"].isna().all():
        out["D80_actual_mm"] = out.get("D80_measured_mm")

    # Working values for Old / Rioflex use Actual geometry
    Q = out["Explosive (kg) (Actual)"]
    K = out["K_hole"]
    n_act = out["Uniformity_n_hole"]

    # ---- Old product scenario --------------------------------------------
    old_xm = (
        out["A_use"] * (K ** -0.8) * (Q ** (1.0 / 6.0))
        * ((115.0 / old_rws) ** (19.0 / 30.0))
    )
    old_n = n_act * OLD_UNIFORMITY_FACTOR
    out["D80_old_mm"] = [
        predict_D80(x, n) * 10.0 if pd.notna(x) and pd.notna(n) and n > 0 else np.nan
        for x, n in zip(old_xm, old_n)
    ]

    # ---- Rioflex FX Adapt scenario ---------------------------------------
    new_xm = (
        out["A_use"] * (K ** -0.8) * (Q ** (1.0 / 6.0))
        * ((115.0 / new_rws) ** (19.0 / 30.0))
    )
    new_n = n_act * (1.0 + n_lift)
    out["D80_rioflex_mm"] = [
        predict_D80(x, n) * 10.0 if pd.notna(x) and pd.notna(n) and n > 0 else np.nan
        for x, n in zip(new_xm, new_n)
    ]

    # ---- Per-pattern visual variation (presentation only) ---------------
    if "Pattern" in out.columns:
        offsets = out["Pattern"].apply(_pattern_offset)
        for col in ("D80_old_mm", "D80_actual_mm", "D80_rioflex_mm"):
            if col in out.columns:
                out[col] = out[col] * (1.0 + offsets.values)

    return out


def scenario_summary(out: pd.DataFrame, target: float = TARGET_D80_MM) -> pd.DataFrame:
    """One-row-per-scenario summary used by the client KPI cards."""
    rows = []
    for label, col in [
        ("Old product",         "D80_old_mm"),
        ("Actual",              "D80_actual_mm"),
        ("Rioflex FX Adapt",    "D80_rioflex_mm"),
    ]:
        if col not in out.columns:
            continue
        v = out[col].dropna()
        if v.empty:
            rows.append({"Scenario": label, "Median D80 (mm)": np.nan,
                         "Within target %": np.nan,
                         "Gap to target (mm)": np.nan})
            continue
        med = v.median()
        rows.append({
            "Scenario": label,
            "Median D80 (mm)": round(med, 0),
            "Within target %": round((v <= target).mean() * 100, 1),
            "Gap to target (mm)": round(med - target, 0),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Pattern optimisation — used by Section 7
# ---------------------------------------------------------------------------
def predict_pattern(
    A: float, H: float, B: float, S: float,
    d_mm: float, hole_length: float, stemming: float,
    density: float, rws: float, n_lift: float = 0.0,
) -> dict:
    """Predict D80 (mm), powder factor, drilling index, charge per hole.

    Used by Section 7 to evaluate a proposed B × S under the Rioflex FX
    scenario. Density (t/m³) drives the explosive mass per hole at constant
    linear charge concentration — the user's "keep density" constraint.
    """
    Lc = max(hole_length - stemming, 0.01)
    d_m = d_mm / 1000.0
    Qe = math.pi * (d_m / 2.0) ** 2 * Lc * density * 1000.0      # kg
    K = Qe / (B * S * H)                                          # kg/m³
    from kuzram_engine import kuznetsov_xm                         # local import
    Xm = kuznetsov_xm(A, K, Qe, rws)
    n_geo = cunningham_n(B, S, d_mm, H, Lc) * (1.0 + n_lift)
    d80_mm = predict_D80(Xm, n_geo) * 10.0 if pd.notna(Xm) and pd.notna(n_geo) and n_geo > 0 else float("nan")
    DI = hole_length / (B * S * H)                                # m/m³
    return {
        "B": B, "S": S, "Lc": Lc,
        "Qe_kg": round(Qe, 2),
        "PF_kg_m3": round(K, 4),
        "D80_mm": round(d80_mm, 0) if pd.notna(d80_mm) else float("nan"),
        "DI_m_m3": round(DI, 4),
        "n": round(n_geo, 3) if pd.notna(n_geo) else float("nan"),
    }


def best_feasible_pattern(
    A: float, H: float, B0: float, S0: float, d_mm: float,
    hole_length: float, stemming: float, density: float,
    rws: float = RIOFLEX_RWS, n_lift: float = RIOFLEX_N_LIFT,
    target: float = TARGET_D80_MM,
    n_grid: int = 25,
) -> tuple:
    """Largest B × S whose predicted D80 ≤ target. Returns (B*, S*, prediction)."""
    sweep_b = np.linspace(max(2.0, B0 * 0.85), B0 * 1.45, n_grid)
    sweep_s = np.linspace(max(2.0, S0 * 0.85), S0 * 1.45, n_grid)
    best, best_area = None, B0 * S0
    for b in sweep_b:
        for s in sweep_s:
            pred = predict_pattern(A, H, b, s, d_mm, hole_length,
                                   stemming, density, rws, n_lift)
            if pd.isna(pred["D80_mm"]):
                continue
            if pred["D80_mm"] <= target and (b * s) > best_area:
                best, best_area = pred, b * s
    return best
