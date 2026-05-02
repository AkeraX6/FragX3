"""
Kuz-Ram Fragmentation Model Engine
===================================
Implements:
  - Kuznetsov mean-size equation (Cunningham 1983/1987)
  - Cunningham uniformity index
  - Rosin-Rammler size distribution (D50, D80, full curve)
  - Back-calculation of Rock Factor (A) from measured fragmentation
  - Powder factor & bench-volume calculations
"""

import math
import numpy as np
import pandas as pd
import re
from typing import Optional, Tuple, Dict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
LN2 = math.log(2)        # 0.6931
LN5 = math.log(5)        # 1.6094
ANFO_RWS = 100.0          # Reference RWS for ANFO


# ---------------------------------------------------------------------------
# Blast-name parsing helpers
# ---------------------------------------------------------------------------
def parse_bench_height(blast_name: str) -> Optional[float]:
    """Extract bench height from blast name pattern 'prefix_UPPER-LOWER_pattern'.

    Examples
    --------
    >>> parse_bench_height('Hn2_165-159_106')
    6.0
    >>> parse_bench_height('_vin1_261-249_106')
    12.0
    >>> parse_bench_height('kp3_230-220_119')
    10.0
    """
    s = str(blast_name).strip().lstrip("_")
    m = re.search(r"(\d+)\s*-\s*(\d+)", s)
    if m:
        upper = float(m.group(1))
        lower = float(m.group(2))
        return abs(upper - lower)
    return None


def parse_blast_key(blast_name: str) -> str:
    """Normalise blast name to a lowercase key for matching."""
    s = str(blast_name).strip().lstrip("_").lower()
    s = re.sub(r"[_\-]+$", "", s)            # strip trailing separators
    s = re.sub(r"\s+", "_", s)               # whitespace → underscore
    return s


# ---------------------------------------------------------------------------
# Core Kuz-Ram equations
# ---------------------------------------------------------------------------
def powder_factor(Qe: float, B: float, S: float, H: float) -> float:
    """Specific charge  K = Qe / (B × S × H)  [kg/m³].

    Parameters
    ----------
    Qe : float  –  explosive mass per hole (kg)
    B  : float  –  burden (m)
    S  : float  –  spacing (m)
    H  : float  –  bench height (m)
    """
    vol = B * S * H
    if vol <= 0:
        return 0.0
    return Qe / vol


def kuznetsov_xm(A: float, K: float, Qe: float, RWS: float = ANFO_RWS) -> float:
    """Kuznetsov mean fragment size  Xm  (cm).

    Xm = A · K^(-0.8) · Qe^(1/6) · (115 / RWS)^(19/30)

    Parameters
    ----------
    A   : float  –  Rock Factor (dimensionless, typically 1–22)
    K   : float  –  Powder factor (kg/m³)
    Qe  : float  –  Explosive mass per hole (kg)
    RWS : float  –  Relative Weight Strength (ANFO = 100)
    """
    if K <= 0 or Qe <= 0:
        return float("nan")
    return A * (K ** -0.8) * (Qe ** (1.0 / 6.0)) * ((115.0 / RWS) ** (19.0 / 30.0))


def cunningham_n(B: float, S: float, d_mm: float, H: float,
                 Lc: float, W: float = 0.0) -> float:
    """Cunningham uniformity index  n  (dimensionless).

    n = (2.2 − 14·B/d) · √((1 + S/B)/2) · (1 − W/B) · (Lc/H)

    Parameters
    ----------
    B    : float  –  burden (m)
    S    : float  –  spacing (m)
    d_mm : float  –  hole diameter (mm)
    H    : float  –  bench height (m)
    Lc   : float  –  charge length (m) = hole_length − stemming
    W    : float  –  drilling accuracy std-dev (m), default 0
    """
    if B <= 0 or d_mm <= 0 or H <= 0 or Lc <= 0:
        return float("nan")
    d_m = d_mm / 1000.0                       # mm → m
    term1 = 2.2 - 14.0 * (B / d_mm)          # note: B in m, d in mm (Cunningham uses B/d in m/mm)
    # Cunningham original: B in metres, d in millimetres gives B/d ~0.02-0.04
    term2 = math.sqrt((1.0 + S / B) / 2.0)
    term3 = 1.0 - W / B if W < B else 0.01   # avoid negative
    term4 = Lc / H
    n = term1 * term2 * term3 * term4
    return max(n, 0.5)                        # floor to prevent non-physical values


# ---------------------------------------------------------------------------
# Rosin-Rammler distribution
# ---------------------------------------------------------------------------
def characteristic_size(Xm: float, n: float) -> float:
    """Characteristic size  Xc = Xm / (ln2)^(1/n)."""
    if n <= 0:
        return float("nan")
    return Xm / (LN2 ** (1.0 / n))


def rosin_rammler_passing(x: float, Xc: float, n: float) -> float:
    """Fraction passing  P(x) = 1 − exp(−(x/Xc)^n)."""
    if Xc <= 0 or n <= 0:
        return float("nan")
    return 1.0 - math.exp(-(x / Xc) ** n)


def rosin_rammler_size(P: float, Xc: float, n: float) -> float:
    """Fragment size at a given passing fraction P.

    x = Xc · (−ln(1−P))^(1/n)
    """
    if P <= 0 or P >= 1 or Xc <= 0 or n <= 0:
        return float("nan")
    return Xc * ((-math.log(1.0 - P)) ** (1.0 / n))


def predict_D50(Xm: float) -> float:
    """D50 equals the Kuznetsov mean size Xm (by definition)."""
    return Xm


def predict_D80(Xm: float, n: float) -> float:
    """D80 from Rosin-Rammler.

    D80 = Xm · (ln5 / ln2)^(1/n)
    """
    if n <= 0:
        return float("nan")
    return Xm * ((LN5 / LN2) ** (1.0 / n))


def full_curve(Xm: float, n: float, sizes_cm: Optional[np.ndarray] = None
               ) -> pd.DataFrame:
    """Return a Rosin-Rammler size-distribution curve.

    Parameters
    ----------
    Xm       : float  –  mean fragment size (cm)
    n        : float  –  uniformity index
    sizes_cm : array  –  screen sizes to evaluate (cm).
                         Default: logspace from 0.1 to 10×Xm.

    Returns
    -------
    DataFrame with columns  ['Size_cm', 'Passing']
    """
    Xc = characteristic_size(Xm, n)
    if sizes_cm is None:
        sizes_cm = np.geomspace(max(0.1, Xm * 0.01), Xm * 5, 100)
    passing = [rosin_rammler_passing(x, Xc, n) for x in sizes_cm]
    return pd.DataFrame({"Size_cm": sizes_cm, "Passing": passing})


# ---------------------------------------------------------------------------
# Back-calculation of Rock Factor from measured fragmentation
# ---------------------------------------------------------------------------
def back_calculate_A_from_D50(D50_cm: float, K: float, Qe: float,
                               RWS: float = ANFO_RWS) -> float:
    """Solve for Rock Factor A given measured D50.

    A = D50 · K^(0.8) · Qe^(−1/6) · (RWS/115)^(19/30)
    """
    if K <= 0 or Qe <= 0:
        return float("nan")
    return D50_cm * (K ** 0.8) * (Qe ** (-1.0 / 6.0)) * ((RWS / 115.0) ** (19.0 / 30.0))


def back_calculate_n_from_D50_D80(D50_cm: float, D80_cm: float) -> float:
    """Back-calculate uniformity index n from D50 and D80.

    From Rosin-Rammler:
        D80/D50 = (ln5/ln2)^(1/n)
     →  n = ln(ln5/ln2) / ln(D80/D50)
    """
    if D50_cm <= 0 or D80_cm <= D50_cm:
        return float("nan")
    ratio = D80_cm / D50_cm
    return math.log(LN5 / LN2) / math.log(ratio)


# ---------------------------------------------------------------------------
# Blast-level roll-up  (hole-by-hole → blast summary)
# ---------------------------------------------------------------------------
def rollup_blast_data(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate hole-by-hole QA/QC data to blast-level summaries.

    Expects columns matching the Blast_QAQC.csv schema.
    Returns one row per blast with computed metrics.
    """
    # Ensure numeric
    num_cols = [
        "Hole Length (Design)", "Hole Length (Actual)",
        "Explosive (kg) (Design)", "Explosive (kg) (Actual)",
        "Stemming (Design)", "Stemming (Actual)",
        "Burden (Design)", "Spacing (Design)",
        "Diameter (Design)", "Density", "Subdrill (Design)",
    ]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    agg = df.groupby("Blast").agg(
        Pit=("Pit", "first"),
        Bench=("Bench", "first"),
        Pattern=("Pattern", "first"),
        n_holes=("Borehole", "count"),
        Diameter_mm=("Diameter (Design)", "median"),
        Density=("Density", "median"),
        # Design
        Hole_Length_Design_mean=("Hole Length (Design)", "mean"),
        Explosive_kg_Design_total=("Explosive (kg) (Design)", "sum"),
        Explosive_kg_Design_mean=("Explosive (kg) (Design)", "mean"),
        Stemming_Design_mean=("Stemming (Design)", "mean"),
        Burden_Design=("Burden (Design)", "median"),
        Spacing_Design=("Spacing (Design)", "median"),
        Subdrill_Design=("Subdrill (Design)", "median"),
        # Actual
        Hole_Length_Actual_mean=("Hole Length (Actual)", "mean"),
        Explosive_kg_Actual_total=("Explosive (kg) (Actual)", "sum"),
        Explosive_kg_Actual_mean=("Explosive (kg) (Actual)", "mean"),
        Stemming_Actual_mean=("Stemming (Actual)", "mean"),
    ).reset_index()

    # Derive bench height from blast name
    agg["Bench_Height_m"] = agg["Blast"].apply(parse_bench_height)

    # Charge length  = Hole length − Stemming
    agg["Charge_Length_Design_m"] = (agg["Hole_Length_Design_mean"]
                                     - agg["Stemming_Design_mean"])
    agg["Charge_Length_Actual_m"] = (agg["Hole_Length_Actual_mean"]
                                     - agg["Stemming_Actual_mean"])

    # Powder factor (design)
    agg["PF_Design"] = agg.apply(
        lambda r: powder_factor(
            r["Explosive_kg_Design_mean"],
            r["Burden_Design"],
            r["Spacing_Design"],
            r["Bench_Height_m"] if pd.notna(r["Bench_Height_m"]) else 0
        ), axis=1
    )

    # Powder factor (actual)
    agg["PF_Actual"] = agg.apply(
        lambda r: powder_factor(
            r["Explosive_kg_Actual_mean"],
            r["Burden_Design"],
            r["Spacing_Design"],
            r["Bench_Height_m"] if pd.notna(r["Bench_Height_m"]) else 0
        ), axis=1
    )

    # Total drilled metres
    agg["Drilled_m_Design_total"] = df.groupby("Blast")["Hole Length (Design)"].sum().values
    agg["Drilled_m_Actual_total"] = df.groupby("Blast")["Hole Length (Actual)"].sum().values

    return agg


# ---------------------------------------------------------------------------
# Calibration:  merge fragmentation + back-calculate
# ---------------------------------------------------------------------------
def calibrate_rock_factor(blast_summary: pd.DataFrame,
                          frag_data: pd.DataFrame,
                          RWS: float = ANFO_RWS,
                          blast_col_frag: str = "Blast",
                          d50_col: str = "D50",
                          d80_col: str = "D80") -> pd.DataFrame:
    """Join fragmentation measurements to blast summaries and back-calculate A and n.

    Parameters
    ----------
    blast_summary : DataFrame from rollup_blast_data()
    frag_data     : DataFrame with at least [blast, D50, D80] columns
                    (D50, D80 in cm)
    RWS           : Relative Weight Strength of the explosive used

    Returns
    -------
    Merged DataFrame with added columns:
        Rock_Factor_A, n_backcalc, D50_predicted, D80_predicted
    """
    # Normalise keys
    bs = blast_summary.copy()
    fd = frag_data.copy()
    bs["_key"] = bs["Blast"].apply(parse_blast_key)
    fd["_key"] = fd[blast_col_frag].apply(parse_blast_key)

    merged = bs.merge(fd[["_key", d50_col, d80_col]],
                      on="_key", how="left", suffixes=("", "_frag"))
    merged.rename(columns={d50_col: "D50_measured", d80_col: "D80_measured"},
                  inplace=True)

    # Back-calculate Rock Factor A  (using actual PF & actual explosive per hole)
    merged["Rock_Factor_A"] = merged.apply(
        lambda r: back_calculate_A_from_D50(
            r["D50_measured"],
            r["PF_Actual"] if pd.notna(r["PF_Actual"]) and r["PF_Actual"] > 0
            else r["PF_Design"],
            r["Explosive_kg_Actual_mean"] if pd.notna(r["Explosive_kg_Actual_mean"])
            else r["Explosive_kg_Design_mean"],
            RWS
        ) if pd.notna(r.get("D50_measured")) else float("nan"),
        axis=1
    )

    # Back-calculate uniformity index n
    merged["n_backcalc"] = merged.apply(
        lambda r: back_calculate_n_from_D50_D80(
            r["D50_measured"], r["D80_measured"]
        ) if pd.notna(r.get("D50_measured")) and pd.notna(r.get("D80_measured"))
        else float("nan"),
        axis=1
    )

    merged.drop(columns=["_key"], inplace=True)
    return merged


# ---------------------------------------------------------------------------
# Scenario simulation  (Baseline vs Proposed)
# ---------------------------------------------------------------------------
def simulate_scenario(
    A: float,
    H: float,
    B: float,
    S: float,
    d_mm: float,
    hole_length: float,
    stemming: float,
    density: float,
    RWS: float = ANFO_RWS,
    W: float = 0.0,
    label: str = ""
) -> Dict:
    """Run the Kuz-Ram model for a single scenario and return all metrics.

    Parameters
    ----------
    A           : Rock Factor (calibrated)
    H           : Bench height (m)
    B           : Burden (m)
    S           : Spacing (m)
    d_mm        : Hole diameter (mm)
    hole_length : Total hole length (m)
    stemming    : Stemming length (m)
    density     : Explosive density (g/cm³ or t/m³)
    RWS         : Relative Weight Strength
    W           : Drilling accuracy std-dev (m)
    label       : Scenario name

    Returns
    -------
    dict with all computed parameters
    """
    d_m = d_mm / 1000.0
    Lc = hole_length - stemming                     # charge length (m)
    hole_area = math.pi * (d_m / 2.0) ** 2          # m²
    Qe = hole_area * Lc * density * 1000.0           # kg  (density in t/m³)

    K = powder_factor(Qe, B, S, H)
    Xm = kuznetsov_xm(A, K, Qe, RWS)
    n = cunningham_n(B, S, d_mm, H, Lc, W)
    Xc = characteristic_size(Xm, n)
    D50 = predict_D50(Xm)
    D80 = predict_D80(Xm, n)

    volume_per_hole = B * S * H                      # m³
    drilled_m_per_m3 = hole_length / volume_per_hole if volume_per_hole > 0 else 0
    expl_per_m3 = K                                   # kg/m³

    return {
        "Label": label,
        "Bench_Height_m": H,
        "Burden_m": B,
        "Spacing_m": S,
        "Diameter_mm": d_mm,
        "Hole_Length_m": hole_length,
        "Stemming_m": stemming,
        "Charge_Length_m": Lc,
        "Explosive_kg_per_hole": round(Qe, 2),
        "Density_t_m3": density,
        "RWS": RWS,
        "Powder_Factor_kg_m3": round(K, 4),
        "Rock_Factor_A": round(A, 2),
        "Uniformity_n": round(n, 3),
        "Xc_cm": round(Xc, 2),
        "D50_cm": round(D50, 2),
        "D80_cm": round(D80, 2),
        "Volume_per_hole_m3": round(volume_per_hole, 2),
        "Drilled_m_per_m3": round(drilled_m_per_m3, 4),
        "Explosive_kg_per_m3": round(expl_per_m3, 4),
    }


def compare_scenarios(scenario_a: Dict, scenario_b: Dict) -> Dict:
    """Compute deltas and percentage changes between two scenarios.

    Positive % = an increase from A to B.
    """
    comparison = {"Metric": [], "Baseline (A)": [], "Proposed (B)": [],
                  "Delta": [], "Change_%": []}

    keys_to_compare = [
        ("Powder_Factor_kg_m3", "Powder Factor (kg/m³)"),
        ("Explosive_kg_per_hole", "Explosive per hole (kg)"),
        ("D50_cm", "D50 (cm)"),
        ("D80_cm", "D80 (cm)"),
        ("Uniformity_n", "Uniformity Index n"),
        ("Drilled_m_per_m3", "Drilled m per m³"),
        ("Volume_per_hole_m3", "Volume per hole (m³)"),
    ]

    for key, label in keys_to_compare:
        va = scenario_a.get(key, 0)
        vb = scenario_b.get(key, 0)
        delta = vb - va
        pct = (delta / va * 100) if va != 0 else float("nan")
        comparison["Metric"].append(label)
        comparison["Baseline (A)"].append(round(va, 4))
        comparison["Proposed (B)"].append(round(vb, 4))
        comparison["Delta"].append(round(delta, 4))
        comparison["Change_%"].append(round(pct, 2))

    return comparison


# ---------------------------------------------------------------------------
# Per-hole fragmentation  (hole-by-hole D80 with stemming correction)
# ---------------------------------------------------------------------------
def compute_hole_fragmentation(df: pd.DataFrame,
                                A: float,
                                RWS: float = ANFO_RWS,
                                mode: str = "actual") -> pd.DataFrame:
    """Compute per-hole fragmentation (Xm and D80_adjusted) for every hole.

    For each hole:
      1. K  = Explosive(kg) / (Burden × Spacing × Hole_Length)
      2. Xm = A · K^(−0.8) · Q^(1/6) · (115/RWS)^(19/30)
      3. D80_adjusted = Xm · 1.5 · (Stemming_Actual / Stemming_Design)^0.5

    Parameters
    ----------
    df   : hole-level DataFrame (Blast_QAQC schema)
    A    : Rock Factor (constant for the bench / pit)
    RWS  : Relative Weight Strength
    mode : "actual" uses Actual columns, "design" uses Design columns

    Returns
    -------
    Copy of df with added columns:
        K_hole, Xm_hole, D80_adj_hole, Frag_Category
    """
    out = df.copy()

    # Ensure numeric
    num_cols = [
        "Hole Length (Design)", "Hole Length (Actual)",
        "Explosive (kg) (Design)", "Explosive (kg) (Actual)",
        "Stemming (Design)", "Stemming (Actual)",
        "Burden (Design)", "Spacing (Design)",
        "Diameter (Design)",
    ]
    for c in num_cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")

    # Select columns based on mode
    if mode == "actual":
        hl_col = "Hole Length (Actual)"
        qe_col = "Explosive (kg) (Actual)"
    else:
        hl_col = "Hole Length (Design)"
        qe_col = "Explosive (kg) (Design)"

    B = out["Burden (Design)"]
    S = out["Spacing (Design)"]
    HL = out[hl_col]
    Qe = out[qe_col]
    St_design = out["Stemming (Design)"]
    St_actual = out["Stemming (Actual)"] if "Stemming (Actual)" in out.columns else St_design

    # 1. Powder factor per hole:  K = Qe / (B × S × H_hole)
    vol = B * S * HL
    out["K_hole"] = np.where(vol > 0, Qe / vol, np.nan)

    # 2. Kuznetsov mean fragment size  Xm per hole (cm)
    K_h = out["K_hole"]
    out["Xm_hole"] = np.where(
        (K_h > 0) & (Qe > 0),
        A * (K_h ** -0.8) * (Qe ** (1.0 / 6.0)) * ((115.0 / RWS) ** (19.0 / 30.0)),
        np.nan,
    )

    # 3. D80 adjusted with stemming correction factor
    #    D80_adj = Xm · 1.5 · (Stemming_Actual / Stemming_Design)^0.5
    stemming_ratio = np.where(
        St_design > 0,
        St_actual / St_design,
        1.0,
    )
    out["Stemming_Correction"] = np.clip(stemming_ratio, 0.5, 3.0)  # clamp outliers
    out["D80_adj_hole"] = out["Xm_hole"] * 1.5 * (out["Stemming_Correction"] ** 0.5)

    # 4. Categorise fragmentation quality
    # Use per-blast median D80 as the reference to define zones
    median_d80 = out.groupby("Blast")["D80_adj_hole"].transform("median")
    ratio_to_median = out["D80_adj_hole"] / median_d80
    out["Frag_Category"] = pd.cut(
        ratio_to_median,
        bins=[0, 0.7, 0.9, 1.1, 1.3, 999],
        labels=["Excessive Fines", "Fine", "Optimal", "Coarse", "Oversize"],
    )

    return out


def compute_hole_calibration_from_measured_d50(
    df: pd.DataFrame,
    RWS: float = ANFO_RWS,
    mode: str = "actual",
    d50_col: str = "D50_measured",
    d80_col: str = "D80_measured",
    uniformity_lift: float = 0.0,
) -> pd.DataFrame:
    """Back-calculate per-hole Rock Factor from measured blast D50.

    The measured D50/D80 values are normally blast-level fragmentation results
    linked back to each hole. A varies by hole because actual charge, length,
    stemming, burden, and spacing vary in the QAQC data.
    """
    out = df.copy()

    num_cols = [
        "Hole Length (Design)", "Hole Length (Actual)",
        "Explosive (kg) (Design)", "Explosive (kg) (Actual)",
        "Stemming (Design)", "Stemming (Actual)",
        "Burden (Design)", "Spacing (Design)",
        "Diameter (Design)", d50_col, d80_col,
    ]
    for c in num_cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")

    if mode == "actual":
        hl_col = "Hole Length (Actual)"
        qe_col = "Explosive (kg) (Actual)"
        st_col = "Stemming (Actual)"
    else:
        hl_col = "Hole Length (Design)"
        qe_col = "Explosive (kg) (Design)"
        st_col = "Stemming (Design)"

    B = out["Burden (Design)"]
    S = out["Spacing (Design)"]
    HL = out[hl_col]
    Qe = out[qe_col]
    St = out[st_col]
    charge_length = (HL - St).clip(lower=0.01)
    volume = B * S * HL

    out["K_hole"] = np.where(volume > 0, Qe / volume, np.nan)
    out["Rock_Factor_A_hole"] = np.where(
        (out[d50_col] > 0) & (out["K_hole"] > 0) & (Qe > 0),
        out[d50_col] * (out["K_hole"] ** 0.8) * (Qe ** (-1.0 / 6.0)) * ((RWS / 115.0) ** (19.0 / 30.0)),
        np.nan,
    )

    out["n_backcalc_hole"] = out.apply(
        lambda r: back_calculate_n_from_D50_D80(r[d50_col], r[d80_col])
        if pd.notna(r.get(d50_col)) and pd.notna(r.get(d80_col)) else float("nan"),
        axis=1,
    )
    out["n_geometry_hole"] = out.apply(
        lambda r: cunningham_n(
            r["Burden (Design)"], r["Spacing (Design)"], r["Diameter (Design)"],
            r[hl_col], max(r[hl_col] - r[st_col], 0.01)
        ),
        axis=1,
    )
    out["Uniformity_n_hole"] = out["n_backcalc_hole"].fillna(out["n_geometry_hole"])
    out["Uniformity_n_hole"] = out["Uniformity_n_hole"] * (1.0 + uniformity_lift)

    out["D50_recalc_cm"] = np.where(
        (out["Rock_Factor_A_hole"] > 0) & (out["K_hole"] > 0) & (Qe > 0),
        out["Rock_Factor_A_hole"] * (out["K_hole"] ** -0.8) * (Qe ** (1.0 / 6.0)) * ((115.0 / RWS) ** (19.0 / 30.0)),
        np.nan,
    )
    out["D80_recalc_cm"] = out.apply(
        lambda r: predict_D80(r["D50_recalc_cm"], r["Uniformity_n_hole"])
        if pd.notna(r.get("D50_recalc_cm")) and pd.notna(r.get("Uniformity_n_hole")) else float("nan"),
        axis=1,
    )
    out["D80_recalc_mm"] = out["D80_recalc_cm"] * 10.0

    return out


# ---------------------------------------------------------------------------
# Cost estimation helpers
# ---------------------------------------------------------------------------
def estimate_costs(
    scenario: Dict,
    rock_volume_m3: float,
    cost_explosive_per_kg: float = 0.0,
    cost_drilling_per_m: float = 0.0,
) -> Dict:
    """Estimate total blasting costs for a given rock volume.

    Parameters
    ----------
    scenario            : dict from simulate_scenario()
    rock_volume_m3      : total volume to blast (m³)
    cost_explosive_per_kg : unit cost of explosives ($/kg)
    cost_drilling_per_m   : unit cost of drilling ($/m)
    """
    pf = scenario["Powder_Factor_kg_m3"]
    drill_rate = scenario["Drilled_m_per_m3"]
    vol_per_hole = scenario["Volume_per_hole_m3"]

    total_explosive_kg = pf * rock_volume_m3
    total_drill_m = drill_rate * rock_volume_m3
    n_holes = rock_volume_m3 / vol_per_hole if vol_per_hole > 0 else 0

    cost_explosive = total_explosive_kg * cost_explosive_per_kg
    cost_drilling = total_drill_m * cost_drilling_per_m
    cost_total = cost_explosive + cost_drilling

    return {
        "Label": scenario.get("Label", ""),
        "Rock_Volume_m3": rock_volume_m3,
        "Total_Explosive_kg": round(total_explosive_kg, 1),
        "Total_Drilled_m": round(total_drill_m, 1),
        "N_Holes": int(round(n_holes)),
        "Cost_Explosive": round(cost_explosive, 2),
        "Cost_Drilling": round(cost_drilling, 2),
        "Cost_Total": round(cost_total, 2),
        "Cost_per_m3": round(cost_total / rock_volume_m3, 4) if rock_volume_m3 > 0 else 0,
    }


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== Kuz-Ram Engine Self-Test ===\n")

    # Example: Hn2_165-159 bench
    H = 6.0          # bench height (m)
    B = 4.2           # burden (m)
    S = 4.8           # spacing (m)
    d = 140.0         # diameter (mm)
    hl = 7.2          # hole length (m)
    st = 2.6          # stemming (m)
    rho = 1.19        # explosive density (t/m³)
    RWS = 100.0       # ANFO-equivalent
    A = 8.0           # assumed rock factor

    result = simulate_scenario(A, H, B, S, d, hl, st, rho, RWS, label="Test")
    for k, v in result.items():
        print(f"  {k}: {v}")

    print(f"\n  Bench height from name: {parse_bench_height('Hn2_165-159_106')}")
    print(f"  Back-calc A from D50=15cm: "
          f"{back_calculate_A_from_D50(15.0, result['Powder_Factor_kg_m3'], result['Explosive_kg_per_hole'], RWS):.2f}")
