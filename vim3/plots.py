"""Plotly figure factory.

Every chart in the app is built here. Keeping plots pure functions means
sections only orchestrate, palette/theme stay consistent, and figures can
be reused or unit-tested.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from kuzram_engine import full_curve

from .config import (
    DEFAULT_HEIGHT, PALETTE, PLOTLY_TEMPLATE, SPATIAL_HEIGHT, TARGET_D80_MM,
)


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def fig_bench_geometry(holes: pd.DataFrame, bench: int) -> go.Figure:
    """Plan-view of the chosen bench, holes coloured by Pattern."""
    df = holes.dropna(subset=["Local X (Design)", "Local Y (Design)"]).copy()
    df["Pattern"] = df.get("Pattern", "—").fillna("—").astype(str)
    fig = px.scatter(
        df, x="Local X (Design)", y="Local Y (Design)",
        color="Pattern",
        hover_data=["Blast", "Borehole", "Pattern",
                    "Hole Length (Actual)", "Explosive (kg) (Actual)"],
        title=f"Bench {bench} — drill pattern layout",
    )
    fig.update_traces(marker=dict(size=7, line=dict(width=0.4, color="white")))
    fig.update_layout(
        template=PLOTLY_TEMPLATE, height=SPATIAL_HEIGHT,
        xaxis_title="Easting (Local X, m)",
        yaxis_title="Northing (Local Y, m)",
        yaxis_scaleanchor="x",
        legend_title="Pattern",
    )
    return fig


# ---------------------------------------------------------------------------
# Fragmentation performance
# ---------------------------------------------------------------------------
def fig_d80_per_blast(frag_bench: pd.DataFrame, target: float = TARGET_D80_MM) -> go.Figure:
    """Bar chart of measured D50 / D80 per blast for the chosen bench."""
    df = frag_bench.dropna(subset=["D80"]).copy()
    df = df.sort_values("D80")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["BLAST"], y=df["D80"], name="D80 (mm)",
        marker_color=PALETTE["accent"]))
    if "D50" in df.columns:
        fig.add_trace(go.Bar(
            x=df["BLAST"], y=df["D50"], name="D50 (mm)",
            marker_color=PALETTE["good"]))
    fig.add_hline(
        y=target, line=dict(color=PALETTE["target"], dash="dash"),
        annotation_text=f"Target {target:.0f} mm",
        annotation_position="top right")
    fig.update_layout(
        template=PLOTLY_TEMPLATE, height=DEFAULT_HEIGHT,
        title="Measured fragmentation per blast",
        yaxis_title="Size (mm)", xaxis_title="Blast",
        barmode="group", legend_title="",
    )
    return fig


def fig_d80_distribution(frag_pit: pd.DataFrame, target: float = TARGET_D80_MM) -> go.Figure:
    """Histogram of all measured D80 values in VIM3."""
    fig = px.histogram(
        frag_pit.dropna(subset=["D80"]),
        x="D80", nbins=20,
        title="VIM3 — measured D80 distribution across all blasts",
        color_discrete_sequence=[PALETTE["accent"]],
    )
    fig.add_vline(
        x=target, line=dict(color=PALETTE["target"], dash="dash"),
        annotation_text=f"Target {target:.0f} mm",
        annotation_position="top right")
    fig.update_layout(
        template=PLOTLY_TEMPLATE, height=DEFAULT_HEIGHT,
        xaxis_title="D80 (mm)", yaxis_title="Number of blasts",
    )
    return fig


# ---------------------------------------------------------------------------
# Rock-factor calibration
# ---------------------------------------------------------------------------
def fig_rf_histogram(cal: pd.DataFrame) -> go.Figure:
    df = cal.dropna(subset=["Rock_Factor_A"])
    fig = px.histogram(
        df, x="Rock_Factor_A", nbins=20,
        title="Rock Factor A — distribution across calibrated blasts",
        color_discrete_sequence=[PALETTE["primary"]],
    )
    fig.update_layout(
        template=PLOTLY_TEMPLATE, height=DEFAULT_HEIGHT,
        xaxis_title="Rock Factor A (—)", yaxis_title="Number of blasts",
    )
    return fig


def fig_rf_vs_d80(cal: pd.DataFrame) -> go.Figure:
    df = cal.dropna(subset=["Rock_Factor_A", "D80_measured"])
    fig = px.scatter(
        df, x="Rock_Factor_A", y="D80_measured",
        color="Bench" if "Bench" in df.columns else None,
        hover_data=[c for c in ["Blast", "Pattern", "PF_Actual"] if c in df.columns],
        title="Rock Factor A vs measured D80",
    )
    fig.update_traces(marker=dict(size=10, line=dict(width=0.5, color="white")))
    fig.update_layout(
        template=PLOTLY_TEMPLATE, height=DEFAULT_HEIGHT,
        xaxis_title="Rock Factor A",
        yaxis_title="Measured D80 (cm)",
    )
    return fig


# ---------------------------------------------------------------------------
# Spatial analysis
# ---------------------------------------------------------------------------
def _grey_base_layer(all_holes: pd.DataFrame) -> go.Scatter:
    """Translucent grey scatter of every hole on the bench (background layer)."""
    df = all_holes.dropna(subset=["Local X (Design)", "Local Y (Design)"])
    return go.Scatter(
        x=df["Local X (Design)"],
        y=df["Local Y (Design)"],
        mode="markers",
        marker=dict(size=4, color="#D5D8DC", opacity=0.65,
                    line=dict(width=0)),
        name="Bench (no measured frag)",
        hoverinfo="skip",
        showlegend=True,
    )


def fig_spatial_rf_grey_base(all_holes: pd.DataFrame,
                              measured_holes: pd.DataFrame,
                              bench: int,
                              col: str = "Rock_Factor_A_hole_display") -> go.Figure:
    """Plan view with the whole bench in grey + calibrated holes coloured."""
    fig = go.Figure()
    fig.add_trace(_grey_base_layer(all_holes))

    df = measured_holes.dropna(
        subset=[col, "Local X (Design)", "Local Y (Design)"]
    ).copy()
    if not df.empty:
        df["Pattern"] = df.get("Pattern", "—").fillna("—").astype(str)
        fig.add_trace(go.Scatter(
            x=df["Local X (Design)"], y=df["Local Y (Design)"],
            mode="markers",
            marker=dict(
                size=8, color=df[col],
                colorscale="Viridis",
                colorbar=dict(title="Rock Factor"),
                line=dict(width=0.4, color="white"),
            ),
            text=[
                f"Blast: {r['Blast']}<br>Pattern: {r['Pattern']}<br>"
                f"Rock Factor: {r[col]:.1f}<br>"
                f"D80 (recalc): {r.get('D80_recalc_mm', float('nan')):.0f} mm"
                for _, r in df.iterrows()
            ],
            hoverinfo="text",
            name="Calibrated holes",
        ))

    fig.update_layout(
        template=PLOTLY_TEMPLATE, height=SPATIAL_HEIGHT,
        title=f"Bench {bench} — Rock Factor (calibrated zones over the whole bench)",
        xaxis_title="Easting (m)", yaxis_title="Northing (m)",
        yaxis_scaleanchor="x",
    )
    return fig


def fig_spatial_d80_grey_base(all_holes: pd.DataFrame,
                               measured_holes: pd.DataFrame,
                               bench: int,
                               col: str = "D80_recalc_mm",
                               target: float = TARGET_D80_MM,
                               title_suffix: str = "") -> go.Figure:
    """Plan view with whole bench grey + measured/simulated D80 coloured."""
    fig = go.Figure()
    fig.add_trace(_grey_base_layer(all_holes))

    df = measured_holes.dropna(
        subset=[col, "Local X (Design)", "Local Y (Design)"]
    ).copy()
    if not df.empty:
        df["Pattern"] = df.get("Pattern", "—").fillna("—").astype(str)
        cmax = max(target * 1.8, df[col].quantile(0.95))
        fig.add_trace(go.Scatter(
            x=df["Local X (Design)"], y=df["Local Y (Design)"],
            mode="markers",
            marker=dict(
                size=8, color=df[col],
                colorscale="RdYlGn_r",
                cmin=100, cmax=cmax,
                colorbar=dict(title="D80 (mm)"),
                line=dict(width=0.4, color="white"),
            ),
            text=[
                f"Blast: {r['Blast']}<br>Pattern: {r['Pattern']}<br>"
                f"D80: {r[col]:.0f} mm"
                for _, r in df.iterrows()
            ],
            hoverinfo="text",
            name="D80 per hole",
        ))

    title = f"Bench {bench} — D80 per hole"
    if title_suffix:
        title += f" · {title_suffix}"
    fig.update_layout(
        template=PLOTLY_TEMPLATE, height=SPATIAL_HEIGHT,
        title=title,
        xaxis_title="Easting (m)", yaxis_title="Northing (m)",
        yaxis_scaleanchor="x",
    )
    return fig


def fig_spatial_rf_2d(cal_holes: pd.DataFrame, bench: int) -> go.Figure:
    df = cal_holes.dropna(subset=["Rock_Factor_A_hole",
                                  "Local X (Design)", "Local Y (Design)"]).copy()
    df["Pattern"] = df.get("Pattern", "—").fillna("—").astype(str)
    fig = px.scatter(
        df, x="Local X (Design)", y="Local Y (Design)",
        color="Rock_Factor_A_hole", symbol="Pattern",
        color_continuous_scale="Viridis",
        hover_data=["Blast", "Borehole",
                    "D50_measured_mm", "D80_measured_mm",
                    "K_hole", "Uniformity_n_hole"],
        title=f"Bench {bench} — calibrated Rock Factor A per hole",
    )
    fig.update_traces(marker=dict(size=8, line=dict(width=0.4, color="white")))
    fig.update_layout(
        template=PLOTLY_TEMPLATE, height=SPATIAL_HEIGHT, yaxis_scaleanchor="x",
        xaxis_title="Easting (m)", yaxis_title="Northing (m)",
    )
    return fig


def fig_spatial_d80_2d(cal_holes: pd.DataFrame, bench: int,
                        target: float = TARGET_D80_MM,
                        col: str = "D80_recalc_mm") -> go.Figure:
    df = cal_holes.dropna(subset=[col, "Local X (Design)", "Local Y (Design)"]).copy()
    df["Pattern"] = df.get("Pattern", "—").fillna("—").astype(str)
    cmax = max(target * 1.8, df[col].quantile(0.95))
    fig = px.scatter(
        df, x="Local X (Design)", y="Local Y (Design)",
        color=col, symbol="Pattern",
        color_continuous_scale="RdYlGn_r",
        range_color=[100, cmax],
        hover_data=["Blast", "Borehole",
                    "Rock_Factor_A_hole",
                    "D50_measured_mm", "D80_measured_mm"],
        title=f"Bench {bench} — recalculated D80 per hole (mm)",
    )
    fig.update_traces(marker=dict(size=8, line=dict(width=0.4, color="white")))
    fig.update_layout(
        template=PLOTLY_TEMPLATE, height=SPATIAL_HEIGHT, yaxis_scaleanchor="x",
        xaxis_title="Easting (m)", yaxis_title="Northing (m)",
    )
    return fig


def fig_spatial_3d_rf(cal_holes: pd.DataFrame, bench: int) -> go.Figure:
    df = cal_holes.dropna(
        subset=["Rock_Factor_A_hole", "Local X (Design)", "Local Y (Design)"]
    ).copy()
    df["Pattern"] = df.get("Pattern", "—").fillna("—").astype(str)
    df["_z"] = pd.to_numeric(df["Bench"], errors="coerce")
    fig = px.scatter_3d(
        df, x="Local X (Design)", y="Local Y (Design)", z="_z",
        color="Rock_Factor_A_hole", symbol="Pattern",
        color_continuous_scale="Viridis",
        hover_data=["Blast", "Borehole",
                    "D80_measured_mm", "D80_recalc_mm"],
        title=f"3D Rock Factor map — bench {bench}",
    )
    fig.update_traces(marker=dict(size=4))
    fig.update_layout(
        template=PLOTLY_TEMPLATE, height=620,
        scene=dict(
            xaxis_title="Easting", yaxis_title="Northing",
            zaxis_title="Bench", aspectmode="data",
        ),
    )
    return fig


# ---------------------------------------------------------------------------
# Product comparison
# ---------------------------------------------------------------------------
SCENARIO_SPECS = [
    ("Old product",      "D80_old_mm",     PALETTE["old"]),
    ("Actual",           "D80_actual_mm",  PALETTE["actual"]),
    ("Rioflex FX Adapt", "D80_rioflex_mm", PALETTE["rioflex"]),
]


def fig_scenario_plan_view(out: pd.DataFrame, scenario_name: str,
                            d_col: str, target: float = TARGET_D80_MM) -> go.Figure:
    df = out.dropna(subset=[d_col, "Local X (Design)", "Local Y (Design)"]).copy()
    df["Pattern"] = df.get("Pattern", "—").fillna("—").astype(str)
    cmax = max(target * 1.8, df[d_col].quantile(0.95)) if not df.empty else target * 1.8
    fig = px.scatter(
        df, x="Local X (Design)", y="Local Y (Design)",
        color=d_col, symbol="Pattern",
        color_continuous_scale="RdYlGn_r",
        range_color=[100, cmax],
        hover_data=["Blast", "Borehole", "A_use"],
        title=scenario_name,
    )
    fig.update_traces(marker=dict(size=7, line=dict(width=0.4, color="white")))
    fig.update_layout(
        template=PLOTLY_TEMPLATE, height=470, yaxis_scaleanchor="x",
        xaxis_title="Easting (m)", yaxis_title="Northing (m)",
        coloraxis_colorbar=dict(title="D80 (mm)"),
    )
    return fig


def fig_scenario_box(out: pd.DataFrame, target: float = TARGET_D80_MM) -> go.Figure:
    fig = go.Figure()
    for name, col, color in SCENARIO_SPECS:
        if col not in out.columns:
            continue
        v = out[col].dropna()
        if v.empty:
            continue
        fig.add_trace(go.Box(
            y=v, name=name, boxmean=True, marker_color=color))
    fig.add_hline(
        y=target, line=dict(color=PALETTE["target"], dash="dash"),
        annotation_text=f"Target {target:.0f} mm",
        annotation_position="top right")
    fig.update_layout(
        template=PLOTLY_TEMPLATE, height=DEFAULT_HEIGHT,
        yaxis_title="D80 (mm)",
        title="D80 distribution across the bench — three scenarios",
    )
    return fig


def fig_passing_curves(curves: Iterable[tuple], target: float = TARGET_D80_MM) -> go.Figure:
    """``curves`` = iterable of (name, Xm_cm, n, color)."""
    sizes_cm = np.geomspace(0.5, 200.0, 200)
    fig = go.Figure()
    for name, xm, n, color in curves:
        if pd.isna(xm) or pd.isna(n) or xm <= 0 or n <= 0:
            continue
        df = full_curve(xm, n, sizes_cm)
        fig.add_trace(go.Scatter(
            x=df["Size_cm"] * 10.0, y=df["Passing"] * 100.0,
            mode="lines", name=name, line=dict(color=color, width=3)))
    fig.add_vline(
        x=target, line=dict(color=PALETTE["target"], dash="dash"),
        annotation_text=f"Target {target:.0f} mm",
        annotation_position="top right")
    fig.update_layout(
        template=PLOTLY_TEMPLATE, height=DEFAULT_HEIGHT,
        xaxis=dict(title="Fragment size (mm)", type="log"),
        yaxis=dict(title="% Passing", range=[0, 100]),
        title="Predicted Rosin-Rammler curves — three scenarios",
    )
    return fig


def fig_pattern_grid(grid_df: pd.DataFrame, B_cur: float, S_cur: float,
                      target: float = TARGET_D80_MM) -> go.Figure:
    fig = px.scatter(
        grid_df, x="Burden", y="Spacing",
        color="D80_mm", symbol="Within_target",
        symbol_map={True: "circle", False: "x"},
        color_continuous_scale="RdYlGn_r",
        hover_data=["PF_kg_m3"],
        title=f"Pattern expansion sweep — Rioflex FX (target ≤ {target:.0f} mm)",
    )
    fig.add_trace(go.Scatter(
        x=[B_cur], y=[S_cur], mode="markers+text",
        marker=dict(size=18, color="black", symbol="star"),
        text=["Current"], textposition="top center",
        name="Current pattern"))
    fig.update_layout(
        template=PLOTLY_TEMPLATE, height=540, yaxis_scaleanchor="x",
        xaxis_title="Burden (m)", yaxis_title="Spacing (m)",
    )
    return fig
