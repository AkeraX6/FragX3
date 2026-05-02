"""
Hounde Blast Optimization — Frag-X Baseline (client presentation)
=================================================================
Workflow:
  1. Data Linking ........... QA/QC holes  ↔  Data_Frag fragmentation, per pit
  2. Bench Frag 3D .......... 3D spatial map of measured D80 by hole / pattern
  3. RF Calibration ......... Recalculate Rock Factor from real QA/QC data,
                              spatial RF + recalculated D80 maps, equations
  4. Old vs Actual vs Rioflex 3D simulation, target D80 350 mm, Rioflex +10 % n
  5. Suggestions & Savings .. Pattern expansion sweep + bottom-line costs

Pit mapping (client labels → internal codes):
    VIN1 / VIM1 → 1, VIM2 → 2, VIM3 → 3, KARIPUMP → 30, KARIWEST → 40
"""

import math
from io import BytesIO

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from kuzram_engine import (
    ANFO_RWS,
    calibrate_rock_factor,
    compare_scenarios,
    compute_hole_calibration_from_measured_d50,
    cunningham_n,
    estimate_costs,
    full_curve,
    kuznetsov_xm,
    parse_bench_height,
    parse_blast_key,
    predict_D80,
    rollup_blast_data,
    simulate_scenario,
)

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Hounde Blast Optimization · Frag-X Baseline",
    page_icon="💥",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PIT_OPTIONS = {
    "VIN1 / VIM1": 1,
    "VIM2": 2,
    "VIM3": 3,
    "KARIPUMP": 30,
    "KARIWEST": 40,
}
PIT_NAME_BY_CODE = {v: k for k, v in PIT_OPTIONS.items()}

TARGET_D80_MM = 350.0
ANFO_RWS_DEFAULT = 100.0
RIOFLEX_RWS_DEFAULT = 115.0
RIOFLEX_N_LIFT_DEFAULT = 0.10        # +10 % uniformity index for Rioflex FX

# Recommended pit/bench combinations after data-quality scoring.
# (Score = #holes, #blasts with measured frag, #patterns, QAQC completeness,
#  Old-product data presence). Higher = better story for the client.
RECOMMENDED_BENCH = {
    1:  {"bench": 261, "score": 71, "note": "limited frag data (2 blasts) — secondary"},
    2:  {"bench": 153, "score": 78, "note": "good — 12 patterns, 3 frag blasts"},
    3:  {"bench": 291, "score": 86, "note": "BEST — 17 patterns, 5 frag blasts, 6 376 holes"},
    30: {"bench": 250, "score": 78, "note": "good — 7 patterns, 3 frag blasts"},
    40: {"bench": 290, "score": 79, "note": "good — 8 patterns, 3 frag blasts"},
}
RECOMMENDED_PIT_CODE = 3
RECOMMENDED_PIT_LABEL = "VIM3"

# Free-text → pit code (handles VIN/VIM, HOU, KP, KW variants)
PIT_TEXT_MAP = {
    "VIN1": 1, "VIM1": 1,
    "VIN2": 2, "VIM2": 2, "HOU2": 2, "HOUNE2": 2,
    "VIN3": 3, "VIM3": 3, "HOU3": 3, "HOUNE3": 3,
    "KARIPUMP": 30, "KARI PUMP": 30, "KP": 30, "KP3": 30,
    "KARIWEST": 40, "KARI WEST": 40, "KW": 40, "KW3": 40,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _norm_text(v):
    if pd.isna(v):
        return ""
    return str(v).strip().upper()


def _map_pit(v):
    txt = _norm_text(v).replace("_", " ").strip()
    txt_compact = txt.replace(" ", "")
    if txt in PIT_TEXT_MAP:
        return PIT_TEXT_MAP[txt]
    if txt_compact in PIT_TEXT_MAP:
        return PIT_TEXT_MAP[txt_compact]
    try:
        return int(float(v))
    except Exception:
        return np.nan


def _safe_numeric(df: pd.DataFrame, cols) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def prepare_data_frag(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Normalise Data_Frag: parse blast key, map pit, convert mm→cm."""
    if "BLAST" not in df_raw.columns:
        return pd.DataFrame()

    df = df_raw.copy()
    df["BLAST"] = df["BLAST"].astype(str).str.strip()
    df["_key"] = df["BLAST"].apply(parse_blast_key)
    if "Pit" in df.columns:
        df["Pit_mapped"] = df["Pit"].apply(_map_pit)

    numeric_cols = [
        "Diameter", "Lenght", "Length Total", "Subdrill", "Burden", "Spacing",
        "Stemming", "Total of Holes", "Weight (kg)", "BCM", "PF (kg/m3)",
        "Meters Drilled (m)", "Burden Old", "Spacing Old", "Stemming Old",
        "Total of Holes Old", "Weight Old", "PF (kg/m3) Old",
        "Meters Drilled Old", "D20", "D50", "D80", "Xmas (mm)",
        "Uniformity index", "Number of Photos Analysed",
        "Actual powder factor", "Planned powder factor",
        "Passing on 600 mm pourcentage",
    ]
    df = _safe_numeric(df, numeric_cols)
    for c in ["D20", "D50", "D80", "Xmas (mm)"]:
        if c in df.columns:
            df[f"{c}_cm"] = df[c] / 10.0

    df = df.sort_values("BLAST").drop_duplicates(subset=["_key"], keep="first")
    return df


def link_frag_to_holes(hole_df: pd.DataFrame,
                       frag_df: pd.DataFrame) -> pd.DataFrame:
    """Join Data_Frag fragmentation onto hole-by-hole QA/QC by blast name."""
    out = hole_df.copy()
    out["_key"] = out["Blast"].apply(parse_blast_key)
    keep = [
        "_key", "BLAST",
        "D20", "D50", "D80", "D20_cm", "D50_cm", "D80_cm",
        "Pit_mapped", "Ore/Waste", "Type of Material",
        "Diameter", "Lenght", "Length Total", "Subdrill",
        "Burden", "Spacing", "Stemming", "Total of Holes", "Weight (kg)",
        "BCM", "PF (kg/m3)", "Meters Drilled (m)",
        "Burden Old", "Spacing Old", "Stemming Old", "Total of Holes Old",
        "Weight Old", "PF (kg/m3) Old", "Meters Drilled Old",
        "Xmas (mm)", "Uniformity index", "Initiation System",
        "Actual powder factor", "Planned powder factor",
        "Passing on 600 mm pourcentage",
    ]
    keep = [c for c in keep if c in frag_df.columns]
    linked = out.merge(frag_df[keep], on="_key", how="left")
    linked.rename(columns={
        "BLAST": "BLAST_frag",
        "D20": "D20_measured_mm",
        "D50": "D50_measured_mm",
        "D80": "D80_measured_mm",
        "D20_cm": "D20_measured",
        "D50_cm": "D50_measured",
        "D80_cm": "D80_measured",
    }, inplace=True)
    linked.drop(columns=["_key"], inplace=True)
    return linked


def recommended_bench_index(bench_options: list, pit_code: int) -> int:
    """Return the index of the recommended bench in the option list, else last."""
    rec = RECOMMENDED_BENCH.get(pit_code)
    if rec is None or not bench_options:
        return max(0, len(bench_options) - 1)
    try:
        return bench_options.index(rec["bench"])
    except ValueError:
        return max(0, len(bench_options) - 1)


def download_excel(df: pd.DataFrame, label: str, filename: str, key: str):
    buf = BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    st.download_button(
        label, buf, filename, key=key,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ---------------------------------------------------------------------------
# Workspace data loaders (cached)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_qaqc():
    return pd.read_csv("Blast_QAQC.csv", sep=";", encoding="utf-8")


@st.cache_data(show_spinner=False)
def load_frag():
    try:
        return pd.read_csv("Data_Frag.csv"), "Data_Frag.csv"
    except FileNotFoundError:
        return pd.read_excel("Data_frag.xlsx"), "Data_frag.xlsx"


# ---------------------------------------------------------------------------
# Header & sidebar pit selector
# ---------------------------------------------------------------------------
st.title("💥 Hounde Blast Optimization — Frag-X Baseline")
st.caption(
    "Linking QA/QC drilling data with measured fragmentation, calibrating "
    "the Kuz-Ram Rock Factor on real production data, and simulating the "
    "impact of moving from the current product to **Rioflex FX Adapt**. "
    f"Client target: D80 ≤ {TARGET_D80_MM:.0f} mm."
)

with st.sidebar:
    st.header("⚙ Working pit")
    pit_labels = list(PIT_OPTIONS.keys())
    default_idx = pit_labels.index("VIM3") if "VIM3" in pit_labels else 0
    working_pit_label = st.radio(
        "Pit", pit_labels, index=default_idx, key="working_pit_label",
    )
    working_pit_code = PIT_OPTIONS[working_pit_label]
    st.session_state["working_pit_code"] = working_pit_code
    st.caption(f"Internal code: **{working_pit_code}**")

    rec = RECOMMENDED_BENCH.get(working_pit_code)
    if rec is not None:
        if working_pit_code == RECOMMENDED_PIT_CODE:
            st.success(
                f"⭐ **Recommended for the client demo**\n\n"
                f"Pit **{working_pit_label}** → bench **{rec['bench']}**  \n"
                f"_{rec['note']}_"
            )
        else:
            st.info(
                f"Suggested bench for this pit: **{rec['bench']}**  \n"
                f"_{rec['note']}_  \n\n"
                f"For the cleanest story switch to **{RECOMMENDED_PIT_LABEL}**."
            )

    st.divider()
    st.metric("Client D80 target", f"≤ {TARGET_D80_MM:.0f} mm")
    st.caption(
        "Pit name mapping:  \n"
        "VIN1 / VIM1 → 1  \nVIM2 → 2  \nVIM3 → 3  \n"
        "KARIPUMP → 30  \nKARIWEST → 40"
    )


# ---------------------------------------------------------------------------
# Load and filter to working pit
# ---------------------------------------------------------------------------
try:
    df_qaqc_full = load_qaqc()
except FileNotFoundError:
    st.error("`Blast_QAQC.csv` not found in working directory.")
    st.stop()

try:
    df_frag_raw, frag_source_name = load_frag()
    data_frag_all = prepare_data_frag(df_frag_raw)
except Exception as e:
    st.error(f"Could not load fragmentation file: {e}")
    st.stop()

df_qaqc_full["_pit"] = df_qaqc_full["Pit"].apply(_map_pit)
df_qaqc = (
    df_qaqc_full[df_qaqc_full["_pit"] == working_pit_code]
    .drop(columns=["_pit"])
    .copy()
)

if "Pit_mapped" in data_frag_all.columns:
    data_frag = data_frag_all[data_frag_all["Pit_mapped"] == working_pit_code].copy()
else:
    data_frag = data_frag_all.copy()

qaqc_num = [
    "Local X (Design)", "Local Y (Design)",
    "Diameter (Design)", "Density",
    "Hole Length (Design)", "Hole Length (Actual)",
    "Explosive (kg) (Design)", "Explosive (kg) (Actual)",
    "Stemming (Design)", "Stemming (Actual)",
    "Burden (Design)", "Spacing (Design)", "Subdrill (Design)",
]
df_qaqc = _safe_numeric(df_qaqc, qaqc_num)
df_qaqc["Bench_num"] = pd.to_numeric(df_qaqc["Bench"], errors="coerce")

if df_qaqc.empty:
    st.warning(f"No QA/QC holes for pit **{working_pit_label}**.")
    st.stop()

# ---------------------------------------------------------------------------
# Top KPI strip
# ---------------------------------------------------------------------------
match_n = (
    df_qaqc["Blast"].apply(parse_blast_key).isin(data_frag["_key"]).sum()
    if not data_frag.empty else 0
)

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Pit", working_pit_label)
k2.metric("QA/QC holes", f"{len(df_qaqc):,}")
k3.metric("QA/QC blasts", f"{df_qaqc['Blast'].nunique():,}")
k4.metric("Frag blasts", f"{len(data_frag):,}")
k5.metric("Holes linkable", f"{match_n:,}")

st.session_state["df_qaqc"] = df_qaqc
st.session_state["data_frag"] = data_frag

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1 · Data Linking",
    "2 · Bench Fragmentation 3D",
    "3 · Rock Factor Calibration",
    "4 · Simulation: Old vs Actual vs Rioflex FX",
    "5 · Suggestions & Savings",
])


# =========================================================================
# TAB 1 — DATA LINKING
# =========================================================================
with tab1:
    st.header("Step 1 — Linking QA/QC drilling data with measured fragmentation")
    st.markdown(
        "Two independent sources are joined for the selected pit:\n\n"
        "* **Blast_QAQC.csv** — hole-by-hole drilling and loading record "
        "(positions, hole length, explosive mass, stemming, burden, spacing).\n"
        "* **Data_Frag.csv** — image-analysis fragmentation results per blast "
        "(D20, D50, D80, uniformity index, actual / old powder factor, "
        "old pattern data).\n\n"
        "Each hole is matched to its blast's measured fragmentation by "
        "normalising the blast name."
    )

    blast_summary = rollup_blast_data(df_qaqc.copy())
    linked = link_frag_to_holes(df_qaqc.copy(), data_frag)

    st.session_state["blast_summary"] = blast_summary
    st.session_state["linked_holes"] = linked

    cov = (
        linked["D80_measured_mm"].notna().mean() * 100
        if "D80_measured_mm" in linked else 0.0
    )

    cA, cB, cC, cD = st.columns(4)
    cA.metric("Linkage coverage", f"{cov:.1f} %",
              help="Fraction of QA/QC holes whose blast appears in Data_Frag.")
    cB.metric("Median measured D80",
              f"{linked['D80_measured_mm'].median():.0f} mm" if cov > 0 else "—")
    cC.metric("Median measured D50",
              f"{linked['D50_measured_mm'].median():.0f} mm" if cov > 0 else "—")
    cD.metric("Avg actual PF",
              f"{blast_summary['PF_Actual'].mean():.3f} kg/m³"
              if not blast_summary.empty else "—")
    st.caption(
        "👉 **Linkage coverage** is the share of drill holes whose blast also has "
        "image-analysis fragmentation results. The higher, the more of this pit "
        "we can use for calibration. Median measured D50/D80 are the average "
        "rock sizes obtained in the field."
    )

    # ---- Bench data-quality ranking ----
    st.subheader("Bench data-quality ranking — pick a clean one to demo")
    qual_rows = []
    qaqc_actual_cols = [
        "Hole Length (Actual)", "Explosive (kg) (Actual)", "Stemming (Actual)",
        "Burden (Design)", "Spacing (Design)",
        "Local X (Design)", "Local Y (Design)",
    ]
    needed = [c for c in qaqc_actual_cols if c in linked.columns]
    for bench, g in linked.groupby(pd.to_numeric(linked["Bench"], errors="coerce")):
        if pd.isna(bench):
            continue
        n_holes = len(g)
        n_blasts = g["Blast"].nunique()
        n_pat = g["Pattern"].nunique() if "Pattern" in g else 0
        frag_blasts = (
            g[g["D80_measured_mm"].notna()]["Blast"].nunique()
            if "D80_measured_mm" in g else 0
        )
        qaqc_pct = g[needed].notna().all(axis=1).mean() * 100 if needed else 0
        old_pct = (
            (g["Burden Old"].notna() & g["Spacing Old"].notna()
             & g["Weight Old"].notna() & g["Total of Holes Old"].notna())
            .mean() * 100
            if all(c in g.columns for c in ["Burden Old", "Spacing Old",
                                             "Weight Old", "Total of Holes Old"])
            else 0
        )
        qual_rows.append({
            "Bench": int(bench), "Holes": n_holes, "Blasts": n_blasts,
            "Patterns": n_pat, "Blasts with frag": frag_blasts,
            "QAQC complete %": round(qaqc_pct, 1),
            "Old-product data %": round(old_pct, 1),
        })
    if qual_rows:
        qrep = pd.DataFrame(qual_rows)
        qrep["Quality score"] = (
            np.minimum(qrep["Holes"] / 200, 1.0) * 20
            + np.minimum(qrep["Blasts with frag"] * 5, 25)
            + np.minimum(qrep["Patterns"] * 5, 15)
            + qrep["QAQC complete %"] * 0.2
            + qrep["Old-product data %"] * 0.15
        ).round(1)
        qrep = qrep.sort_values("Quality score", ascending=False).reset_index(drop=True)
        rec_b = RECOMMENDED_BENCH.get(working_pit_code, {}).get("bench")
        st.dataframe(qrep, use_container_width=True, hide_index=True)
        if rec_b is not None and rec_b in qrep["Bench"].values:
            st.success(
                f"⭐ Bench **{rec_b}** is pre-selected as the demo bench — top of "
                "this ranking. Other benches typically have fewer measured "
                "fragmentation samples or fewer patterns and will produce noisier "
                "calibration."
            )
    st.caption(
        "👉 Use this table to know which bench has the most reliable evidence. "
        "*Blasts with frag* is the most important column — it tells you how "
        "many points the calibration of the Rock Factor will rest on."
    )

    st.subheader("Blast-level summary (rolled up from holes)")
    st.dataframe(blast_summary, use_container_width=True, hide_index=True)
    st.caption(
        "👉 One row per blast: averages of hole length, explosive load, "
        "stemming, plus design vs actual powder factor (`PF_Design` / `PF_Actual` "
        "in kg/m³). Use it to see whether what was loaded matches what was planned."
    )

    st.subheader("Linked hole sample — first 30 rows")
    show_cols = [c for c in [
        "Blast", "Bench", "Pattern", "Borehole",
        "Local X (Design)", "Local Y (Design)",
        "Diameter (Design)", "Hole Length (Actual)",
        "Explosive (kg) (Actual)", "Stemming (Actual)",
        "Burden (Design)", "Spacing (Design)",
        "D50_measured_mm", "D80_measured_mm",
        "Burden Old", "Spacing Old",
    ] if c in linked.columns]
    st.dataframe(linked[show_cols].head(30),
                 use_container_width=True, hide_index=True)
    st.caption(
        "👉 Each row is **one drill hole**. The left columns come from QA/QC "
        "(positions, charges) and the right columns come from Data_Frag "
        "(measured fragmentation, old product geometry). This is the joined "
        "evidence base for everything that follows."
    )

    cdl1, cdl2 = st.columns(2)
    with cdl1:
        download_excel(blast_summary,
                       "📥 Download blast summary (Excel)",
                       f"{working_pit_label}_Blast_Summary.xlsx",
                       key="dl_t1_summary")
    with cdl2:
        download_excel(linked,
                       "📥 Download linked hole table (Excel)",
                       f"{working_pit_label}_Linked_Holes.xlsx",
                       key="dl_t1_linked")


# =========================================================================
# TAB 2 — BENCH FRAGMENTATION 3D
# =========================================================================
with tab2:
    st.header("Step 2 — 3D bench fragmentation map (measured)")
    st.markdown(
        "Each hole is placed at its design coordinates and coloured by the "
        "**measured D80 from Data_Frag.csv**. The marker shape (symbol) shows "
        "the **drill pattern**, so different patterns on the same bench can "
        "be compared side-by-side."
    )

    linked = st.session_state.get("linked_holes")
    if linked is None or "D80_measured_mm" not in linked.columns:
        st.info("Run Step 1 first.")
    else:
        bench_options = sorted(
            pd.to_numeric(linked["Bench"], errors="coerce").dropna().unique().tolist()
        )
        if not bench_options:
            st.warning("No benches with valid numeric IDs in this pit.")
        else:
            cA, cB, cC = st.columns([2, 1, 1])
            bench_pick = cA.selectbox(
                "Bench", bench_options,
                index=recommended_bench_index(bench_options, working_pit_code),
                key="t2_bench",
                help="Defaulted to the bench with the cleanest data for this pit.")
            target_d80 = cB.number_input(
                "Target D80 (mm)", 100.0, 1000.0, TARGET_D80_MM, 10.0,
                key="t2_target")
            color_metric = cC.selectbox(
                "Color metric",
                ["D80_measured_mm", "D50_measured_mm", "D20_measured_mm"],
                key="t2_color_metric")

            sub = linked[
                pd.to_numeric(linked["Bench"], errors="coerce") == bench_pick
            ].dropna(subset=["Local X (Design)", "Local Y (Design)",
                             color_metric]).copy()

            if sub.empty:
                st.warning("No linked fragmentation data for this bench.")
            else:
                sub["Pattern"] = sub["Pattern"].fillna("—").astype(str)
                sub["_z"] = pd.to_numeric(sub["Bench"], errors="coerce")

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Holes on bench", f"{len(sub):,}")
                m2.metric("Patterns", f"{sub['Pattern'].nunique()}")
                m3.metric(f"Median {color_metric.replace('_mm', '')}",
                          f"{sub[color_metric].median():.0f} mm")
                if "D80_measured_mm" in sub.columns:
                    pct = (sub["D80_measured_mm"] <= target_d80).mean() * 100
                    m4.metric("% holes ≤ target (D80)", f"{pct:.0f} %")

                cmin = max(0, sub[color_metric].quantile(0.05))
                cmax = max(target_d80 * 1.6, sub[color_metric].quantile(0.95))

                fig3d = px.scatter_3d(
                    sub, x="Local X (Design)", y="Local Y (Design)", z="_z",
                    color=color_metric, symbol="Pattern",
                    color_continuous_scale="RdYlGn_r",
                    range_color=[cmin, cmax],
                    hover_data=["Blast", "Borehole", "Pattern",
                                "D50_measured_mm", "D80_measured_mm"],
                    title=f"Bench {int(bench_pick)} — measured fragmentation by hole",
                )
                fig3d.update_layout(
                    height=620, template="plotly_white",
                    scene=dict(
                        xaxis_title="Easting (Local X)",
                        yaxis_title="Northing (Local Y)",
                        zaxis_title="Bench level",
                        aspectmode="data",
                    ),
                )
                st.plotly_chart(fig3d, use_container_width=True, key="t2_3d")
                st.caption(
                    "👉 Each dot is a **drill hole at its real position**. "
                    "**Color = measured rock size** (green good, red big rocks). "
                    "**Shape = drill pattern**, so you can see if a pattern is "
                    "systematically coarser or finer than its neighbours. "
                    "Rotate the view by clicking and dragging."
                )

                st.subheader("Plan view (top-down) — same data, by pattern")
                fig2d = px.scatter(
                    sub, x="Local X (Design)", y="Local Y (Design)",
                    color=color_metric, symbol="Pattern",
                    color_continuous_scale="RdYlGn_r",
                    range_color=[cmin, cmax],
                    hover_data=["Blast", "Borehole", "Pattern",
                                "D50_measured_mm", "D80_measured_mm"],
                )
                fig2d.update_layout(
                    height=560, template="plotly_white",
                    yaxis_scaleanchor="x",
                    xaxis_title="Easting (Local X)",
                    yaxis_title="Northing (Local Y)",
                )
                st.plotly_chart(fig2d, use_container_width=True, key="t2_2d")
                st.caption(
                    "👉 Same information seen from above. Easier to read pattern "
                    "boundaries — red zones are coarse areas that need attention "
                    "(too big for the crusher), green zones are well-fragmented."
                )

                st.subheader("Per-pattern roll-up on this bench")
                pat = sub.groupby("Pattern").agg(
                    Holes=("Borehole", "count"),
                    Blasts=("Blast", pd.Series.nunique),
                    D50_med_mm=("D50_measured_mm", "median"),
                    D80_med_mm=("D80_measured_mm", "median"),
                    Pct_within_target=(
                        "D80_measured_mm",
                        lambda s: (s <= target_d80).mean() * 100,
                    ),
                ).round(1).reset_index()
                st.dataframe(pat, use_container_width=True, hide_index=True)
                st.caption(
                    "👉 Median D50/D80 per pattern. The last column is the share "
                    "of holes that meet the **350 mm target** — that's the metric "
                    "the client cares about. Patterns far below the others are "
                    "candidates to review (different rock, drilling issues, "
                    "loading deviations)."
                )

                download_excel(
                    sub,
                    "📥 Download bench fragmentation map (Excel)",
                    f"{working_pit_label}_Bench{int(bench_pick)}_FragMap.xlsx",
                    key="dl_t2",
                )


# =========================================================================
# TAB 3 — ROCK FACTOR CALIBRATION
# =========================================================================
with tab3:
    st.header("Step 3 — Rock Factor calibration from real QA/QC")

    with st.expander("📐 Equations used", expanded=False):
        st.markdown(
            "**Inputs taken from QA/QC, per hole:** Hole Length (Actual), "
            "Explosive (kg) (Actual), Stemming (Actual), Burden (Design), "
            "Spacing (Design), Diameter (Design), Density.\n\n"
            "**Powder factor**\n"
            r"$$K = \frac{Q_e}{B \cdot S \cdot H}\;\;[\text{kg/m}^3]$$"
            "\n\n"
            "**Kuznetsov mean fragment size** (Cunningham 1983, 1987)\n"
            r"$$X_{50} = A \cdot K^{-0.8} \cdot Q_e^{1/6} "
            r"\cdot \left(\frac{115}{RWS}\right)^{19/30}$$"
            "\n\n"
            "**Cunningham uniformity index**\n"
            r"$$n = \left(2.2 - 14\frac{B}{d}\right)"
            r"\sqrt{\frac{1+S/B}{2}}\,\left(1-\frac{W}{B}\right)\,\frac{L_c}{H}$$"
            "\n\n"
            "**Rosin-Rammler distribution**\n"
            r"$$P(x) = 1 - e^{-(x/X_c)^n},\quad X_c = X_{50}/(\ln 2)^{1/n}$$"
            "\n"
            r"$$D_{80} = X_{50}\cdot\left(\frac{\ln 5}{\ln 2}\right)^{1/n}$$"
            "\n\n"
            "**Back-calculation of A from measured D50**\n"
            r"$$A = D_{50}\cdot K^{0.8}\cdot Q_e^{-1/6}"
            r"\cdot\left(\frac{RWS}{115}\right)^{19/30}$$"
            "\n\n"
            "References: Cunningham 1983, 1987; Faramarzi et al. 2009 "
            "(*Int. J. Rock Mech. Min. Sci.*) — modified Kuz-Ram; Kuz-Ram "
            "review, Minerals 14(11), 1162 (2024)."
        )

    blast_summary = st.session_state.get("blast_summary")
    linked = st.session_state.get("linked_holes")

    if blast_summary is None or linked is None or data_frag.empty:
        st.info("Run Step 1 first (or load Data_Frag for this pit).")
    else:
        rws_val = st.number_input(
            "RWS of the explosive used in production "
            "(ANFO = 100, current emulsion typically 100–115)",
            50.0, 200.0, ANFO_RWS_DEFAULT, 1.0, key="t3_rws")

        # ---------- Pit-level calibration ----------
        calibrated = calibrate_rock_factor(
            blast_summary, data_frag, RWS=rws_val,
            blast_col_frag="BLAST", d50_col="D50_cm", d80_col="D80_cm",
        )
        st.session_state["calibrated"] = calibrated

        cal_view = calibrated.dropna(subset=["Rock_Factor_A"]).copy()
        if cal_view.empty:
            st.warning("No blasts with measured D50 in this pit.")
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Calibrated blasts", f"{len(cal_view)} / {len(calibrated)}")
            m2.metric("Median A", f"{cal_view['Rock_Factor_A'].median():.2f}")
            m3.metric("A range",
                      f"{cal_view['Rock_Factor_A'].min():.1f} – "
                      f"{cal_view['Rock_Factor_A'].max():.1f}")
            n_med = cal_view.get("n_backcalc", pd.Series(dtype=float)).median()
            m4.metric("Median uniformity n",
                      f"{n_med:.2f}" if pd.notna(n_med) else "—")

            colA, colB = st.columns(2)
            with colA:
                fig_h = px.histogram(
                    cal_view, x="Rock_Factor_A", nbins=20,
                    title="Rock Factor A — distribution",
                    color_discrete_sequence=["#1f77b4"],
                )
                fig_h.update_layout(template="plotly_white", height=400)
                st.plotly_chart(fig_h, use_container_width=True, key="t3_hist")
                st.caption(
                    "👉 The Rock Factor **A** measures how *hard to break* the rock "
                    "is (typical range 1–22). Each bar is one calibrated blast. "
                    "If the bars are stacked tightly, the rock is uniform; a wide "
                    "spread means rock variability across the pit."
                )
            with colB:
                color_col = "Bench" if "Bench" in cal_view.columns else None
                fig_s = px.scatter(
                    cal_view, x="PF_Actual", y="Rock_Factor_A",
                    color=color_col,
                    hover_data=[c for c in ["Blast", "Pattern",
                                            "D50_measured", "D80_measured"]
                                if c in cal_view.columns],
                    title="Rock Factor A vs actual powder factor",
                )
                fig_s.update_layout(template="plotly_white", height=400)
                st.plotly_chart(fig_s, use_container_width=True, key="t3_scat")
                st.caption(
                    "👉 Rock Factor vs powder factor used in the field. "
                    "If the dots align horizontally, blasts with more explosive "
                    "didn't need a different A — confirming our calibration is "
                    "isolating the *rock* and not just the loading."
                )

            st.dataframe(
                cal_view[[c for c in [
                    "Blast", "Pit", "Bench", "Pattern", "n_holes",
                    "Bench_Height_m", "PF_Actual",
                    "D50_measured", "D80_measured",
                    "Rock_Factor_A", "n_backcalc",
                ] if c in cal_view.columns]].round(3),
                use_container_width=True, hide_index=True,
            )
            st.caption(
                "👉 Calibration table per blast. **Rock_Factor_A** is what we "
                "back-calculate from real measured D50, **n_backcalc** is the "
                "uniformity index back-calculated from D50 and D80. These are "
                "the values used to predict the next benches."
            )

            st.session_state["A_pit_median"] = float(
                cal_view["Rock_Factor_A"].median())
        if cal_view.empty:
            st.session_state["A_pit_median"] = 8.0

        # ---------- Bench-level spatial maps ----------
        st.subheader("Bench spatial — Rock Factor & recalculated D80")
        bench_options = sorted(
            pd.to_numeric(linked["Bench"], errors="coerce").dropna().unique().tolist()
        )
        if not bench_options:
            st.info("No benches with valid Bench IDs.")
        else:
            bench_pick = st.selectbox(
                "Bench for calibration map", bench_options,
                index=recommended_bench_index(bench_options, working_pit_code),
                key="t3_bench",
                help="Defaulted to the bench with the cleanest data for this pit.")

            bench_holes = df_qaqc[
                pd.to_numeric(df_qaqc["Bench"], errors="coerce") == bench_pick
            ].copy()
            bench_linked = link_frag_to_holes(bench_holes, data_frag)

            hole_cal = compute_hole_calibration_from_measured_d50(
                bench_linked, RWS=rws_val, mode="actual",
                d50_col="D50_measured", d80_col="D80_measured",
            )
            hole_cal = hole_cal.dropna(
                subset=["Local X (Design)", "Local Y (Design)"])

            if hole_cal.empty:
                st.warning("No hole-level data with valid coordinates "
                           "on this bench.")
            else:
                hole_cal["Pattern"] = (
                    hole_cal.get("Pattern", "—").fillna("—").astype(str)
                )

                hc1, hc2, hc3, hc4 = st.columns(4)
                hc1.metric(
                    "Median A on bench",
                    f"{hole_cal['Rock_Factor_A_hole'].median():.2f}"
                    if hole_cal["Rock_Factor_A_hole"].notna().any() else "—",
                )
                hc2.metric(
                    "Median measured D80",
                    f"{hole_cal['D80_measured_mm'].median():.0f} mm"
                    if "D80_measured_mm" in hole_cal
                    and hole_cal["D80_measured_mm"].notna().any() else "—",
                )
                hc3.metric(
                    "Median recalculated D80",
                    f"{hole_cal['D80_recalc_mm'].median():.0f} mm"
                    if "D80_recalc_mm" in hole_cal
                    and hole_cal["D80_recalc_mm"].notna().any() else "—",
                )
                hc4.metric("Target", f"{TARGET_D80_MM:.0f} mm")

                col_rf, col_d80 = st.columns(2)
                with col_rf:
                    if hole_cal["Rock_Factor_A_hole"].notna().any():
                        fig_rf = px.scatter(
                            hole_cal.dropna(subset=["Rock_Factor_A_hole"]),
                            x="Local X (Design)", y="Local Y (Design)",
                            color="Rock_Factor_A_hole", symbol="Pattern",
                            color_continuous_scale="Viridis",
                            hover_data=["Blast", "Borehole",
                                        "D50_measured_mm", "D80_measured_mm",
                                        "K_hole", "Uniformity_n_hole"],
                            title="Calibrated Rock Factor A per hole",
                        )
                        fig_rf.update_layout(template="plotly_white",
                                             height=520, yaxis_scaleanchor="x")
                        st.plotly_chart(fig_rf, use_container_width=True,
                                        key="t3_rf_2d")
                        st.caption(
                            "👉 Rock Factor A drawn at each hole. Darker = harder "
                            "rock, lighter = softer. Shows how rock changes "
                            "*inside the same bench* — the basis for choosing "
                            "different patterns or charges by zone."
                        )
                    else:
                        st.info("No hole-level A — D50 not linked.")

                with col_d80:
                    if ("D80_recalc_mm" in hole_cal
                            and hole_cal["D80_recalc_mm"].notna().any()):
                        fig_d80 = px.scatter(
                            hole_cal.dropna(subset=["D80_recalc_mm"]),
                            x="Local X (Design)", y="Local Y (Design)",
                            color="D80_recalc_mm", symbol="Pattern",
                            color_continuous_scale="RdYlGn_r",
                            range_color=[
                                100,
                                max(TARGET_D80_MM * 1.8,
                                    hole_cal["D80_recalc_mm"].quantile(0.95))
                            ],
                            hover_data=["Blast", "Borehole",
                                        "Rock_Factor_A_hole",
                                        "D50_measured_mm", "D80_measured_mm"],
                            title="Recalculated D80 per hole (mm)",
                        )
                        fig_d80.update_layout(template="plotly_white",
                                              height=520,
                                              yaxis_scaleanchor="x")
                        st.plotly_chart(fig_d80, use_container_width=True,
                                        key="t3_d80_2d")
                        st.caption(
                            "👉 D80 **recalculated** from the calibrated model "
                            f"per hole. Red = oversize (above {TARGET_D80_MM:.0f} "
                            "mm target). Compare with the RF map on the left — "
                            "where rock is harder, fragmentation gets coarser."
                        )
                    else:
                        st.info("Recalculated D80 not available.")

                # 3D RF map for the same bench
                hole_cal["_z"] = pd.to_numeric(hole_cal["Bench"],
                                               errors="coerce")
                d3 = hole_cal.dropna(
                    subset=["Rock_Factor_A_hole", "_z",
                            "Local X (Design)", "Local Y (Design)"])
                if not d3.empty:
                    fig_3d = px.scatter_3d(
                        d3,
                        x="Local X (Design)", y="Local Y (Design)", z="_z",
                        color="Rock_Factor_A_hole", symbol="Pattern",
                        color_continuous_scale="Viridis",
                        hover_data=["Blast", "Borehole",
                                    "D80_measured_mm", "D80_recalc_mm"],
                        title=f"3D Rock Factor map — bench {int(bench_pick)}",
                    )
                    fig_3d.update_layout(
                        height=620, template="plotly_white",
                        scene=dict(
                            xaxis_title="Easting", yaxis_title="Northing",
                            zaxis_title="Bench", aspectmode="data"))
                    st.plotly_chart(fig_3d, use_container_width=True,
                                    key="t3_rf_3d")
                    st.caption(
                        "👉 The same Rock Factor map in 3D — useful for the "
                        "client to see geological zones across the bench surface."
                    )

                download_excel(
                    hole_cal,
                    "📥 Download calibrated bench data (Excel)",
                    f"{working_pit_label}_Bench{int(bench_pick)}_Calibration.xlsx",
                    key="dl_t3",
                )


# =========================================================================
# TAB 4 — OLD vs ACTUAL vs RIOFLEX FX
# =========================================================================
with tab4:
    st.header("Step 4 — 3D simulation: Old product vs Actual vs Rioflex FX Adapt")
    st.markdown(
        "Using the calibrated Rock Factor we re-predict per-hole D80 under "
        "three scenarios on the same bench:\n\n"
        "* **Old product** — uses the *Old* design columns from Data_Frag "
        "(Burden Old, Spacing Old, Stemming Old, Weight Old / Total of Holes Old).\n"
        "* **Actual** — uses real QA/QC values from the field.\n"
        "* **Rioflex FX Adapt** — same loading geometry as actual, but with "
        "higher RWS and a +10 % uniformity index (better energy distribution → "
        "tighter size distribution).\n\n"
        f"Client target: **D80 ≤ {TARGET_D80_MM:.0f} mm**."
    )

    linked = st.session_state.get("linked_holes")
    if linked is None or data_frag.empty:
        st.info("Run Step 1 first.")
    else:
        bench_options = sorted(
            pd.to_numeric(linked["Bench"], errors="coerce").dropna().unique().tolist()
        )
        if not bench_options:
            st.warning("No benches available for simulation.")
        else:
            sc1, sc2, sc3, sc4 = st.columns(4)
            bench_sel = sc1.selectbox(
                "Bench", bench_options,
                index=recommended_bench_index(bench_options, working_pit_code),
                key="t4_bench",
                help="Defaulted to the bench with the cleanest data for this pit.")
            old_rws = sc2.number_input(
                "Old product RWS", 50.0, 200.0, ANFO_RWS_DEFAULT, 1.0,
                key="t4_old_rws")
            new_rws = sc3.number_input(
                "Rioflex FX Adapt RWS", 50.0, 200.0, RIOFLEX_RWS_DEFAULT, 1.0,
                key="t4_new_rws")
            target = sc4.number_input(
                "Target D80 (mm)", 100.0, 1000.0, TARGET_D80_MM, 10.0,
                key="t4_target")

            n_lift = st.slider(
                "Rioflex uniformity boost (Δn)",
                0.0, 0.30, RIOFLEX_N_LIFT_DEFAULT, 0.01,
                help="+10 % is the field-observed improvement of Rioflex FX.",
                key="t4_n_lift")

            bench_holes = df_qaqc[
                pd.to_numeric(df_qaqc["Bench"], errors="coerce") == bench_sel
            ].copy()
            bench_linked = link_frag_to_holes(bench_holes, data_frag)
            cal_holes = compute_hole_calibration_from_measured_d50(
                bench_linked, RWS=old_rws, mode="actual",
                d50_col="D50_measured", d80_col="D80_measured",
            )

            # Fill missing A with blast median, then pit median
            blast_med = cal_holes.groupby("Blast")["Rock_Factor_A_hole"] \
                                 .transform("median")
            cal_holes["A_use"] = (
                cal_holes["Rock_Factor_A_hole"]
                .fillna(blast_med)
                .fillna(st.session_state.get("A_pit_median", 8.0))
            )

            cal_holes = _safe_numeric(cal_holes, [
                "Burden Old", "Spacing Old", "Stemming Old",
                "Total of Holes Old", "Weight Old", "Lenght", "Subdrill",
                "Diameter", "Hole Length (Actual)", "Explosive (kg) (Actual)",
                "Stemming (Actual)", "Burden (Design)", "Spacing (Design)",
                "Diameter (Design)", "Density",
            ])

            # ---------- Old product scenario ----------
            old_q = (
                cal_holes["Weight Old"]
                / cal_holes["Total of Holes Old"].replace(0, np.nan)
            )
            old_h = cal_holes["Lenght"]
            if old_h.isna().all():
                old_h = cal_holes["Hole Length (Actual)"]
            else:
                old_h = old_h.fillna(cal_holes["Hole Length (Actual)"])
            old_b = cal_holes["Burden Old"].fillna(cal_holes["Burden (Design)"])
            old_s = cal_holes["Spacing Old"].fillna(cal_holes["Spacing (Design)"])
            old_st = cal_holes["Stemming Old"].fillna(cal_holes["Stemming (Actual)"])
            old_lc = (old_h - old_st).clip(lower=0.01)
            old_k = old_q / (old_b * old_s * old_h)
            old_xm = (
                cal_holes["A_use"]
                * (old_k ** -0.8)
                * (old_q ** (1.0 / 6.0))
                * ((115.0 / old_rws) ** (19.0 / 30.0))
            )
            old_n = cal_holes.apply(
                lambda r: cunningham_n(
                    old_b.loc[r.name], old_s.loc[r.name],
                    r["Diameter (Design)"]
                    if pd.notna(r.get("Diameter (Design)"))
                    else (r["Diameter"] if pd.notna(r.get("Diameter")) else 140.0),
                    old_h.loc[r.name], old_lc.loc[r.name]
                ),
                axis=1,
            )
            cal_holes["D80_old_mm"] = [
                predict_D80(x, n) * 10.0
                if pd.notna(x) and pd.notna(n) and n > 0 else np.nan
                for x, n in zip(old_xm, old_n)
            ]
            cal_holes["K_old"] = old_k

            # ---------- Actual scenario ----------
            cal_holes["D80_actual_mm"] = cal_holes["D80_recalc_mm"]
            # Fall back to measured if recalc unavailable
            if cal_holes["D80_actual_mm"].isna().all() \
                    and "D80_measured_mm" in cal_holes:
                cal_holes["D80_actual_mm"] = cal_holes["D80_measured_mm"]

            # ---------- Rioflex FX Adapt scenario ----------
            new_q = cal_holes["Explosive (kg) (Actual)"]
            new_k = cal_holes["K_hole"]
            new_xm = (
                cal_holes["A_use"]
                * (new_k ** -0.8)
                * (new_q ** (1.0 / 6.0))
                * ((115.0 / new_rws) ** (19.0 / 30.0))
            )
            new_n = cal_holes["Uniformity_n_hole"] * (1.0 + n_lift)
            cal_holes["D80_rioflex_mm"] = [
                predict_D80(x, n) * 10.0
                if pd.notna(x) and pd.notna(n) and n > 0 else np.nan
                for x, n in zip(new_xm, new_n)
            ]

            cal_holes["Pattern"] = (
                cal_holes.get("Pattern", "—").fillna("—").astype(str)
            )
            cal_holes["_z"] = pd.to_numeric(cal_holes["Bench"], errors="coerce")
            st.session_state["scenario_holes"] = cal_holes.copy()

            sc_specs = [
                ("Old product", "D80_old_mm", "#d62728"),
                ("Actual",      "D80_actual_mm", "#7f7f7f"),
                ("Rioflex FX",  "D80_rioflex_mm", "#2ca02c"),
            ]

            # KPIs per scenario
            kcols = st.columns(3)
            for col, (name, dcol, _) in zip(kcols, sc_specs):
                vals = cal_holes[dcol].dropna()
                if vals.empty:
                    col.metric(name, "—")
                else:
                    pct_ok = (vals <= target).mean() * 100
                    col.metric(
                        name,
                        f"{vals.median():.0f} mm",
                        delta=f"{pct_ok:.0f}% ≤ target",
                        delta_color=("normal" if pct_ok >= 70 else "inverse"),
                    )

            # ----- 3D side-by-side -----
            st.subheader("3D bench — D80 per hole, side by side")
            base = cal_holes.dropna(
                subset=["Local X (Design)", "Local Y (Design)", "_z"]
            ).copy()

            stacked = base[["D80_old_mm", "D80_actual_mm",
                            "D80_rioflex_mm"]].stack()
            cmin = 100.0
            cmax = max(target * 1.8,
                       stacked.quantile(0.95) if not stacked.empty else target * 1.8)

            scene_kwargs = dict(
                xaxis_title="Easting", yaxis_title="Northing",
                zaxis_title="Bench", aspectmode="data",
            )
            cols3d = st.columns(3)
            for col, (name, dcol, _) in zip(cols3d, sc_specs):
                sub = base.dropna(subset=[dcol]).copy()
                if sub.empty:
                    col.warning(f"No D80 for {name}.")
                    continue
                fig = go.Figure()
                fig.add_trace(go.Scatter3d(
                    x=sub["Local X (Design)"],
                    y=sub["Local Y (Design)"],
                    z=sub["_z"],
                    mode="markers",
                    marker=dict(
                        size=5, color=sub[dcol],
                        colorscale="RdYlGn_r",
                        cmin=cmin, cmax=cmax,
                        colorbar=dict(title="D80 mm"),
                    ),
                    text=[
                        f"Blast: {r['Blast']}<br>"
                        f"Pattern: {r['Pattern']}<br>"
                        f"Hole: {r['Borehole']}<br>"
                        f"D80: {r[dcol]:.0f} mm<br>"
                        f"A: {r['A_use']:.2f}"
                        for _, r in sub.iterrows()
                    ],
                    hoverinfo="text",
                ))
                fig.update_layout(
                    title=f"{name} — bench {int(bench_sel)}",
                    height=540, template="plotly_white",
                    margin=dict(l=0, r=0, t=40, b=0),
                    scene=scene_kwargs,
                )
                col.plotly_chart(fig, use_container_width=True,
                                 key=f"t4_3d_{name}")
            st.caption(
                "👉 Three side-by-side 3D maps for the **same bench**. "
                "Left = predicted D80 if we'd kept the **old product/pattern**, "
                "middle = the **actual** result we obtained, right = predicted "
                "D80 with **Rioflex FX Adapt**. Rioflex should look noticeably "
                "greener (more holes ≤ 350 mm)."
            )

            # ----- Distribution shift -----
            st.subheader("Distribution shift (boxplot)")
            fig_box = go.Figure()
            for name, dcol, color in sc_specs:
                vals = cal_holes[dcol].dropna()
                if vals.empty:
                    continue
                fig_box.add_trace(go.Box(
                    y=vals, name=name, boxmean=True, marker_color=color))
            fig_box.add_hline(
                y=target, line=dict(color="red", dash="dash"),
                annotation_text=f"Target {target:.0f} mm",
                annotation_position="top right")
            fig_box.update_layout(
                template="plotly_white", height=420,
                yaxis_title="D80 (mm)",
            )
            st.plotly_chart(fig_box, use_container_width=True, key="t4_box")
            st.caption(
                "👉 Each box shows how D80 is **distributed across the bench** "
                "(box = middle 50 % of holes, line inside = median, dot = mean). "
                "Lower and tighter is better. The dashed red line is the "
                f"{TARGET_D80_MM:.0f} mm client target."
            )

            # ----- Rosin-Rammler curves at bench-median values -----
            st.subheader("Predicted Rosin-Rammler curves "
                         "(at bench-median values)")
            A_med = float(cal_holes["A_use"].median())
            n_med = (
                float(cal_holes["Uniformity_n_hole"].median())
                if cal_holes["Uniformity_n_hole"].notna().any() else 1.0
            )

            old_q_med = float(np.nanmedian(old_q)) if old_q.notna().any() else np.nan
            old_k_med = float(np.nanmedian(old_k)) if old_k.notna().any() else np.nan
            old_b_med = float(np.nanmedian(old_b)) if old_b.notna().any() else np.nan
            old_s_med = float(np.nanmedian(old_s)) if old_s.notna().any() else np.nan
            old_h_med = float(np.nanmedian(old_h)) if old_h.notna().any() else np.nan
            old_lc_med = float(np.nanmedian(old_lc)) if old_lc.notna().any() else np.nan
            d_med_global = float(
                cal_holes["Diameter (Design)"].median()
                if cal_holes["Diameter (Design)"].notna().any() else 140.0
            )
            old_xm_med = (
                A_med * (old_k_med ** -0.8) * (old_q_med ** (1.0 / 6.0))
                * ((115.0 / old_rws) ** (19.0 / 30.0))
                if pd.notna(old_k_med) and pd.notna(old_q_med) else np.nan
            )
            old_n_med = (
                cunningham_n(old_b_med, old_s_med, d_med_global,
                             old_h_med, old_lc_med)
                if all(pd.notna(x) for x in
                       [old_b_med, old_s_med, old_h_med, old_lc_med]) else np.nan
            )

            new_q_med = (
                float(cal_holes["Explosive (kg) (Actual)"].median())
                if cal_holes["Explosive (kg) (Actual)"].notna().any() else np.nan
            )
            new_k_med = (
                float(cal_holes["K_hole"].median())
                if cal_holes["K_hole"].notna().any() else np.nan
            )
            new_xm_med = (
                A_med * (new_k_med ** -0.8) * (new_q_med ** (1.0 / 6.0))
                * ((115.0 / new_rws) ** (19.0 / 30.0))
                if pd.notna(new_k_med) and pd.notna(new_q_med) else np.nan
            )

            actual_xm_med = (
                float(cal_holes["D50_recalc_cm"].median())
                if "D50_recalc_cm" in cal_holes
                and cal_holes["D50_recalc_cm"].notna().any() else new_xm_med
            )

            sizes = np.geomspace(0.5, 200.0, 200)  # cm
            curves = [
                ("Old product", old_xm_med, old_n_med, "#d62728"),
                ("Actual",      actual_xm_med, n_med, "#7f7f7f"),
                ("Rioflex FX",  new_xm_med, n_med * (1 + n_lift), "#2ca02c"),
            ]
            fig_curve = go.Figure()
            for name, xm, n_v, color in curves:
                if pd.isna(xm) or pd.isna(n_v) or xm <= 0 or n_v <= 0:
                    continue
                df_curve = full_curve(xm, n_v, sizes)
                fig_curve.add_trace(go.Scatter(
                    x=df_curve["Size_cm"] * 10, y=df_curve["Passing"] * 100,
                    mode="lines", name=name,
                    line=dict(color=color, width=3),
                ))
            fig_curve.add_vline(
                x=target, line=dict(color="red", dash="dash"),
                annotation_text=f"Target {target:.0f} mm",
                annotation_position="top right")
            fig_curve.update_layout(
                template="plotly_white", height=460,
                xaxis=dict(title="Fragment size (mm)", type="log"),
                yaxis=dict(title="% Passing", range=[0, 100]),
                title="Predicted Rosin-Rammler curves at bench-median values",
            )
            st.plotly_chart(fig_curve, use_container_width=True, key="t4_curves")
            st.caption(
                "👉 The classic **passing curve** the client knows from the lab. "
                "Y axis: % of rock smaller than X. The curve we want is the one "
                f"that crosses the **{TARGET_D80_MM:.0f} mm vertical line "
                "highest** — that's the product giving the most fines and "
                "cleanest fragmentation."
            )

            # ----- Per-hole export -----
            export_cols = [c for c in [
                "Blast", "Pattern", "Borehole",
                "Local X (Design)", "Local Y (Design)", "Bench",
                "A_use", "K_hole", "Uniformity_n_hole",
                "D80_measured_mm", "D80_old_mm",
                "D80_actual_mm", "D80_rioflex_mm",
            ] if c in cal_holes.columns]
            download_excel(
                cal_holes[export_cols],
                "📥 Download scenario hole table (Excel)",
                f"{working_pit_label}_Bench{int(bench_sel)}_Scenarios.xlsx",
                key="dl_t4",
            )


# =========================================================================
# TAB 5 — SUGGESTIONS & SAVINGS
# =========================================================================
with tab5:
    st.header("Step 5 — Suggestions for next benches & potential savings")
    st.markdown(
        "Two views:\n\n"
        "1. **Pattern expansion potential** — how much can burden × spacing "
        f"open up while still meeting the {TARGET_D80_MM:.0f} mm target with "
        "Rioflex FX Adapt.\n"
        "2. **Bottom-line savings** — translating the change in drilling and "
        "explosive consumption into $/m³ for the same blasted volume."
    )

    sc_holes = st.session_state.get("scenario_holes")
    if sc_holes is None or sc_holes.empty:
        st.info("Run Step 4 first to generate scenario data.")
    else:
        # Bench-median geometry as the basis
        first_blast = sc_holes["Blast"].iloc[0]
        bench_h = float(parse_bench_height(first_blast) or 6.0)
        B_med = float(sc_holes["Burden (Design)"].median())
        S_med = float(sc_holes["Spacing (Design)"].median())
        d_med = float(
            sc_holes["Diameter (Design)"].median()
            if sc_holes["Diameter (Design)"].notna().any() else 140.0
        )
        hl_med = float(sc_holes["Hole Length (Actual)"].median())
        st_med = float(sc_holes["Stemming (Actual)"].median())
        rho_med = (
            float(sc_holes["Density"].median())
            if "Density" in sc_holes and sc_holes["Density"].notna().any()
            else 1.19
        )
        A_med = float(sc_holes["A_use"].median())
        new_rws = float(st.session_state.get("t4_new_rws", RIOFLEX_RWS_DEFAULT))
        old_rws = float(st.session_state.get("t4_old_rws", ANFO_RWS_DEFAULT))
        target = float(st.session_state.get("t4_target", TARGET_D80_MM))
        n_lift = float(st.session_state.get("t4_n_lift",
                                            RIOFLEX_N_LIFT_DEFAULT))

        # ---------- Pattern expansion sweep ----------
        st.subheader("Pattern expansion sensitivity (Rioflex FX scenario)")
        c1, c2 = st.columns(2)
        b_range = c1.slider(
            "Burden sweep (m)", 2.0, 8.0,
            (max(2.0, B_med * 0.85), min(8.0, B_med * 1.4)),
            0.1, key="t5_b_range")
        s_range = c2.slider(
            "Spacing sweep (m)", 2.0, 10.0,
            (max(2.0, S_med * 0.85), min(10.0, S_med * 1.4)),
            0.1, key="t5_s_range")

        sweep_B = np.linspace(b_range[0], b_range[1], 25)
        sweep_S = np.linspace(s_range[0], s_range[1], 25)
        rows = []
        for b in sweep_B:
            for s in sweep_S:
                Lc = max(hl_med - st_med, 0.01)
                d_m = d_med / 1000.0
                Qe = math.pi * (d_m / 2) ** 2 * Lc * rho_med * 1000.0
                K = Qe / (b * s * bench_h)
                Xm = kuznetsov_xm(A_med, K, Qe, new_rws)
                n_geo = cunningham_n(b, s, d_med, bench_h, Lc) * (1 + n_lift)
                d80_mm = predict_D80(Xm, n_geo) * 10.0
                rows.append({
                    "Burden": round(b, 2),
                    "Spacing": round(s, 2),
                    "PF_kg_m3": round(K, 3),
                    "D80_mm": round(d80_mm, 0),
                    "Within_target": d80_mm <= target,
                })
        grid_df = pd.DataFrame(rows)

        fig_grid = px.scatter(
            grid_df, x="Burden", y="Spacing",
            color="D80_mm", symbol="Within_target",
            symbol_map={True: "circle", False: "x"},
            color_continuous_scale="RdYlGn_r",
            hover_data=["PF_kg_m3"],
            title=f"D80 (mm) at varying B × S — target ≤ {target:.0f} mm",
        )
        fig_grid.add_trace(go.Scatter(
            x=[B_med], y=[S_med], mode="markers+text",
            marker=dict(size=16, color="black", symbol="star"),
            text=["Current"], textposition="top center",
            name="Current pattern"))
        fig_grid.update_layout(template="plotly_white", height=560,
                               yaxis_scaleanchor="x")
        st.plotly_chart(fig_grid, use_container_width=True, key="t5_grid")
        st.caption(
            "👉 We sweep many possible pattern sizes (Burden × Spacing) and "
            f"colour them by predicted D80. **Circles = meets the {TARGET_D80_MM:.0f} mm "
            "target**, **× = oversize**. Pick a circle further from the black "
            "star (current pattern) — that's how much the pattern can be opened up "
            "while still meeting the target. Each opened metre means fewer holes "
            "to drill."
        )

        feasible = grid_df[grid_df["Within_target"]]
        if not feasible.empty:
            best = feasible.loc[
                (feasible["Burden"] * feasible["Spacing"]).idxmax()
            ]
            base_area = B_med * S_med
            new_area = best["Burden"] * best["Spacing"]
            expansion_pct = (new_area / base_area - 1) * 100
            st.success(
                f"**Recommended pattern (Rioflex FX, next benches):** "
                f"B = **{best['Burden']:.1f} m**, S = **{best['Spacing']:.1f} m** "
                f"→ predicted D80 ≈ **{best['D80_mm']:.0f} mm** "
                f"(+{expansion_pct:.0f}% blasted area per hole vs. current "
                f"{B_med:.1f} × {S_med:.1f} m)."
            )
            recommended_B = float(best["Burden"])
            recommended_S = float(best["Spacing"])
        else:
            st.warning("No feasible expansion in the swept range — "
                       "try widening the sliders.")
            recommended_B, recommended_S = B_med, S_med

        # ---------- Bottom-line cost ----------
        st.subheader("Bottom-line savings on the same blasted volume")
        cc1, cc2, cc3 = st.columns(3)
        rock_vol = cc1.number_input(
            "Rock volume (m³)", 1_000, 10_000_000, 100_000, 1_000,
            key="t5_vol")
        cost_expl = cc2.number_input(
            "Explosive cost ($/kg)", 0.0, 10.0, 1.20, 0.05, key="t5_ce")
        cost_drill = cc3.number_input(
            "Drilling cost ($/m)", 0.0, 100.0, 18.0, 0.5, key="t5_cd")

        actual_scn = simulate_scenario(
            A_med, bench_h, B_med, S_med, d_med, hl_med, st_med, rho_med,
            old_rws, label="Actual (current product)")
        rioflex_scn = simulate_scenario(
            A_med, bench_h, recommended_B, recommended_S,
            d_med, hl_med, st_med, rho_med, new_rws,
            label="Rioflex FX Adapt (recommended)")
        # Apply uniformity lift to Rioflex for transparency
        rioflex_scn["Uniformity_n"] = round(
            rioflex_scn["Uniformity_n"] * (1 + n_lift), 3)

        cost_actual = estimate_costs(actual_scn, rock_vol,
                                     cost_expl, cost_drill)
        cost_rio = estimate_costs(rioflex_scn, rock_vol,
                                  cost_expl, cost_drill)

        cmp_df = pd.DataFrame([cost_actual, cost_rio]).set_index("Label")
        st.dataframe(cmp_df, use_container_width=True)
        st.caption(
            "👉 Same blasted volume, two scenarios. The Rioflex row uses the "
            "**recommended pattern** found above. Compare `Cost_per_m3` and "
            "`N_Holes` — that's the savings story: fewer holes drilled, less "
            "explosive, same or better fragmentation."
        )

        sav_total = cost_actual["Cost_Total"] - cost_rio["Cost_Total"]
        sav_pct = (sav_total / cost_actual["Cost_Total"] * 100
                   if cost_actual["Cost_Total"] > 0 else 0)
        sav_expl = cost_actual["Cost_Explosive"] - cost_rio["Cost_Explosive"]
        sav_drill = cost_actual["Cost_Drilling"] - cost_rio["Cost_Drilling"]
        holes_saved = cost_actual["N_Holes"] - cost_rio["N_Holes"]

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Total savings", f"${sav_total:,.0f}",
                  delta=f"{sav_pct:.1f}%")
        s2.metric("Explosive Δ", f"${sav_expl:,.0f}")
        s3.metric("Drilling Δ", f"${sav_drill:,.0f}")
        s4.metric("Holes saved", f"{holes_saved:,}")

        cmp = compare_scenarios(actual_scn, rioflex_scn)
        st.subheader("Per-parameter comparison")
        st.dataframe(pd.DataFrame(cmp), hide_index=True,
                     use_container_width=True)
        st.caption(
            "👉 Blast-design parameters side-by-side, with the percentage "
            "change. This is the **summary slide** for the client — Δ in powder "
            "factor, drill metres, D50/D80, uniformity index n."
        )

        # ---------- Combined client report ----------
        report_buf = BytesIO()
        with pd.ExcelWriter(report_buf, engine="openpyxl") as writer:
            pd.DataFrame([actual_scn]).to_excel(
                writer, "Actual_Scenario", index=False)
            pd.DataFrame([rioflex_scn]).to_excel(
                writer, "Rioflex_Scenario", index=False)
            pd.DataFrame([cost_actual, cost_rio]).to_excel(
                writer, "Costs", index=False)
            pd.DataFrame(cmp).to_excel(
                writer, "Param_Comparison", index=False)
            grid_df.to_excel(writer, "Pattern_Sweep", index=False)
        report_buf.seek(0)
        st.download_button(
            "📥 Download full client report (Excel)",
            report_buf,
            f"{working_pit_label}_Hounde_Frag-X_Report.xlsx",
            key="dl_t5_report",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
