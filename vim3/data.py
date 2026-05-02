"""Data loading, VIM3 filtering, type coercion and QA/QC ↔ Frag linkage."""
from __future__ import annotations

import re
from typing import Tuple

import numpy as np
import pandas as pd
import streamlit as st

from .config import (
    PIT_CODE, PIT_KEYS, QAQC_PATH, FRAG_CSV_PATH, FRAG_XLSX_PATH,
)

# Columns that should always be numeric ----------------------------------
QAQC_NUMERIC = [
    "Local X (Design)", "Local Y (Design)",
    "Diameter (Design)", "Density",
    "Hole Length (Design)", "Hole Length (Actual)",
    "Explosive (kg) (Design)", "Explosive (kg) (Actual)",
    "Stemming (Design)", "Stemming (Actual)",
    "Burden (Design)", "Spacing (Design)", "Subdrill (Design)",
]
FRAG_NUMERIC = [
    "Diameter", "Lenght", "Length Total", "Subdrill", "Burden", "Spacing",
    "Stemming", "Total of Holes", "Weight (kg)", "BCM", "PF (kg/m3)",
    "Meters Drilled (m)", "Burden Old", "Spacing Old", "Stemming Old",
    "Total of Holes Old", "Weight Old", "PF (kg/m3) Old",
    "Meters Drilled Old", "D20", "D50", "D80", "Xmas (mm)",
    "Uniformity index", "Number of Photos Analysed",
    "Actual powder factor", "Planned powder factor",
    "Passing on 600 mm pourcentage",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def parse_blast_key(name) -> str:
    """Normalise a blast name to a join key."""
    s = str(name).strip().lstrip("_").lower()
    s = re.sub(r"[_\-]+$", "", s)
    s = re.sub(r"\s+", "_", s)
    return s


def _norm_pit(v):
    if pd.isna(v):
        return np.nan
    txt = str(v).strip().upper().replace(" ", "")
    if txt in PIT_KEYS:
        return PIT_CODE
    try:
        return int(float(v))
    except Exception:
        return np.nan


def _coerce_numeric(df: pd.DataFrame, cols) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_qaqc() -> pd.DataFrame:
    """Load Blast_QAQC.csv, filtered to VIM3."""
    df = pd.read_csv(QAQC_PATH, sep=";", encoding="utf-8")
    df = _coerce_numeric(df, QAQC_NUMERIC)
    df["Bench_num"] = pd.to_numeric(df["Bench"], errors="coerce")
    df["_pit"] = df["Pit"].apply(_norm_pit)
    df = df[df["_pit"] == PIT_CODE].drop(columns=["_pit"]).reset_index(drop=True)
    return df


@st.cache_data(show_spinner=False)
def load_frag() -> pd.DataFrame:
    """Load Data_Frag.csv (or the xlsx fallback), filtered to VIM3."""
    if FRAG_CSV_PATH.exists():
        df = pd.read_csv(FRAG_CSV_PATH)
    else:
        df = pd.read_excel(FRAG_XLSX_PATH)

    df["BLAST"] = df["BLAST"].astype(str).str.strip()
    df["_key"] = df["BLAST"].apply(parse_blast_key)
    df["_pit"] = df["Pit"].apply(_norm_pit)
    df = _coerce_numeric(df, FRAG_NUMERIC)

    # Convert mm → cm for Kuz-Ram math
    for c in ["D20", "D50", "D80", "Xmas (mm)"]:
        if c in df.columns:
            df[f"{c}_cm"] = df[c] / 10.0

    df = df[df["_pit"] == PIT_CODE].drop(columns=["_pit"])
    df = (df.sort_values("BLAST")
            .drop_duplicates("_key", keep="first")
            .reset_index(drop=True))
    return df


def link_qaqc_to_frag(qaqc: pd.DataFrame, frag: pd.DataFrame) -> pd.DataFrame:
    """Outer-join hole-level QA/QC with blast-level fragmentation by blast key."""
    out = qaqc.copy()
    out["_key"] = out["Blast"].apply(parse_blast_key)

    keep = [c for c in [
        "_key", "BLAST",
        "D20", "D50", "D80", "D20_cm", "D50_cm", "D80_cm",
        "Ore/Waste", "Type of Material",
        "Diameter", "Lenght", "Length Total", "Subdrill",
        "Burden", "Spacing", "Stemming", "Total of Holes", "Weight (kg)",
        "BCM", "PF (kg/m3)", "Meters Drilled (m)",
        "Burden Old", "Spacing Old", "Stemming Old", "Total of Holes Old",
        "Weight Old", "PF (kg/m3) Old", "Meters Drilled Old",
        "Xmas (mm)", "Uniformity index", "Initiation System",
        "Actual powder factor", "Planned powder factor",
        "Passing on 600 mm pourcentage",
    ] if c in frag.columns]

    linked = out.merge(frag[keep], on="_key", how="left")
    linked.rename(columns={
        "BLAST": "BLAST_frag",
        "D20": "D20_measured_mm",
        "D50": "D50_measured_mm",
        "D80": "D80_measured_mm",
        "D20_cm": "D20_measured_cm",
        "D50_cm": "D50_measured_cm",
        "D80_cm": "D80_measured_cm",
    }, inplace=True)
    linked.drop(columns=["_key"], inplace=True)
    return linked


@st.cache_data(show_spinner=False)
def load_all() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Single entry point used by the app — returns (qaqc, frag, linked)."""
    qaqc = load_qaqc()
    frag = load_frag()
    linked = link_qaqc_to_frag(qaqc, frag)
    return qaqc, frag, linked


# ---------------------------------------------------------------------------
# Bench-level helpers used by sections
# ---------------------------------------------------------------------------
def available_benches(linked: pd.DataFrame) -> list:
    """Sorted list of valid bench numbers in the linked table."""
    return sorted(
        pd.to_numeric(linked["Bench"], errors="coerce")
        .dropna().astype(int).unique().tolist()
    )


def bench_subset(linked: pd.DataFrame, bench: int) -> pd.DataFrame:
    """Filter linked holes to a single bench."""
    return linked[
        pd.to_numeric(linked["Bench"], errors="coerce") == bench
    ].copy()


def quality_summary(linked: pd.DataFrame) -> pd.DataFrame:
    """Bench-level data quality scoring used to recommend a demo bench."""
    rows = []
    qaqc_cols = [c for c in [
        "Hole Length (Actual)", "Explosive (kg) (Actual)", "Stemming (Actual)",
        "Burden (Design)", "Spacing (Design)",
        "Local X (Design)", "Local Y (Design)",
    ] if c in linked.columns]

    for bench, g in linked.groupby(pd.to_numeric(linked["Bench"], errors="coerce")):
        if pd.isna(bench):
            continue
        n_holes = len(g)
        n_blasts_frag = (
            g[g["D80_measured_mm"].notna()]["Blast"].nunique()
            if "D80_measured_mm" in g else 0
        )
        n_pat = g["Pattern"].nunique() if "Pattern" in g else 0
        qaqc_pct = (
            g[qaqc_cols].notna().all(axis=1).mean() * 100 if qaqc_cols else 0
        )
        old_cols = ["Burden Old", "Spacing Old", "Weight Old",
                    "Total of Holes Old"]
        old_pct = (
            g[[c for c in old_cols if c in g.columns]].notna().all(axis=1).mean() * 100
            if all(c in g.columns for c in old_cols) else 0
        )
        rows.append({
            "Bench": int(bench),
            "Holes": n_holes,
            "Patterns": n_pat,
            "Blasts with frag": n_blasts_frag,
            "QAQC complete %": round(qaqc_pct, 1),
            "Old-product data %": round(old_pct, 1),
        })

    if not rows:
        return pd.DataFrame()

    rep = pd.DataFrame(rows)
    rep["Quality score"] = (
        np.minimum(rep["Holes"] / 200, 1.0) * 20
        + np.minimum(rep["Blasts with frag"] * 5, 25)
        + np.minimum(rep["Patterns"] * 5, 15)
        + rep["QAQC complete %"] * 0.2
        + rep["Old-product data %"] * 0.15
    ).round(1)
    return rep.sort_values("Quality score", ascending=False).reset_index(drop=True)
