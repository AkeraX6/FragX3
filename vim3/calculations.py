"""VIM3 engineering calculations.

All math delegates to ``kuzram_engine`` (Cunningham 1983, 1987 — modified
Kuz-Ram, Faramarzi et al. 2009). This module orchestrates the pieces and
exposes per-blast and per-hole calibration in a way the sections consume.

Convention used in column names:
    *_measured  →  raw value from Data_Frag (image analysis)
    *_recalc    →  back-calculated through Kuz-Ram on real loading
    *_old       →  predicted under old product / old pattern
    *_rioflex   →  predicted under Rioflex FX Adapt
"""
from __future__ import annotations

import pandas as pd

import pandas as pd

from kuzram_engine import (
    ANFO_RWS,
    calibrate_rock_factor,
    compute_hole_calibration_from_measured_d50,
    rollup_blast_data,
)

from .config import ROCK_FACTOR_DISPLAY_MULTIPLIER


# ---------------------------------------------------------------------------
# Display helpers — keep internal math untouched, only scale client KPIs
# ---------------------------------------------------------------------------
def to_display_rf(value):
    """Scale a calibrated Rock Factor for client display (× 2.2)."""
    if value is None:
        return value
    return value * ROCK_FACTOR_DISPLAY_MULTIPLIER


def add_display_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Append client-facing display columns to a calibration table."""
    out = df.copy()
    if "Rock_Factor_A" in out.columns:
        out["Rock_Factor_A_display"] = (
            out["Rock_Factor_A"] * ROCK_FACTOR_DISPLAY_MULTIPLIER
        )
    if "Rock_Factor_A_hole" in out.columns:
        out["Rock_Factor_A_hole_display"] = (
            out["Rock_Factor_A_hole"] * ROCK_FACTOR_DISPLAY_MULTIPLIER
        )
    return out


# ---------------------------------------------------------------------------
# Drilling Index (Drill Factor) — m of drilling per m³ of rock blasted
# ---------------------------------------------------------------------------
def drilling_index(L: float, B: float, S: float, H: float) -> float:
    """Drilling Index = L / (B · S · H)  [m / m³].

    L is total hole depth including sub-drill (m); B, S, H in metres.
    """
    if B is None or S is None or H is None or B <= 0 or S <= 0 or H <= 0:
        return float("nan")
    return L / (B * S * H)


def blast_summary(qaqc: pd.DataFrame) -> pd.DataFrame:
    """One row per blast — averages of design + actual loading geometry."""
    return rollup_blast_data(qaqc.copy())


def calibrate_per_blast(
    qaqc: pd.DataFrame,
    frag: pd.DataFrame,
    rws: float = ANFO_RWS,
) -> pd.DataFrame:
    """Back-calculate Rock Factor A and uniformity index n per blast.

    Uses Cunningham (1983) Kuz-Ram inversion:
        A = D50 · K^0.8 · Q^(-1/6) · (RWS / 115)^(19/30)
    and Rosin-Rammler relation:
        n = ln(ln5 / ln2) / ln(D80 / D50)
    """
    summary = blast_summary(qaqc)
    return calibrate_rock_factor(
        summary, frag, RWS=rws,
        blast_col_frag="BLAST",
        d50_col="D50_cm", d80_col="D80_cm",
    )


def calibrate_per_hole(
    bench_linked: pd.DataFrame,
    rws: float = ANFO_RWS,
) -> pd.DataFrame:
    """Back-calculate per-hole Rock Factor and recalculated D80 (mm)."""
    return compute_hole_calibration_from_measured_d50(
        bench_linked, RWS=rws, mode="actual",
        d50_col="D50_measured_cm", d80_col="D80_measured_cm",
    )
