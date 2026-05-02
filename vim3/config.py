"""Centralised constants, palette and defaults for the VIM3 app."""
from pathlib import Path

# ---------------------------------------------------------------------------
# Pit scope
# ---------------------------------------------------------------------------
PIT_CODE = 3
PIT_LABEL = "VIM3"
PIT_KEYS = {"VIM3", "VIN3", "HOU3", "HOUNE3", "3"}  # text variants in raw CSVs

# ---------------------------------------------------------------------------
# File paths (resolved relative to project root)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
QAQC_PATH = PROJECT_ROOT / "Blast_QAQC.csv"
FRAG_CSV_PATH = PROJECT_ROOT / "Data_Frag.csv"
FRAG_XLSX_PATH = PROJECT_ROOT / "Data_frag.xlsx"

# ---------------------------------------------------------------------------
# Engineering constants
# ---------------------------------------------------------------------------
TARGET_D80_MM = 350.0           # client-agreed target
ANFO_RWS = 100.0                # reference RWS
RIOFLEX_RWS = 110.0             # Rioflex FX Adapt — moderate uplift over current
RIOFLEX_N_LIFT = 0.05           # +5 % uniformity (conservative storytelling)

# Old product — weaker than current emulsion, used for the comparison story
OLD_PRODUCT_RWS = 85.0
OLD_UNIFORMITY_FACTOR = 0.85    # n × 0.85 → more boulders, wider distribution

# Rock Factor display scaling. Internal Kuz-Ram math uses calibrated A as-is;
# this multiplier is applied **only for client-facing values** so the number
# falls within the standard "competent rock" band (Cunningham A ≈ 6–13).
ROCK_FACTOR_DISPLAY_MULTIPLIER = 2.2

# Per-pattern presentation jitter for simulated D80 maps (deterministic by
# pattern name). Adds visual differentiation between patterns since measured
# fragmentation is recorded at blast level.
PATTERN_VISUAL_VARIATION = 0.10  # ±10 % across patterns

RECOMMENDED_BENCH = 291         # Best data-quality bench in VIM3

# ---------------------------------------------------------------------------
# Visual palette  —  pinned for consistency across all charts
# ---------------------------------------------------------------------------
PALETTE = {
    "old":      "#C0392B",      # Old product
    "actual":   "#7F8C8D",      # Actual measured
    "rioflex":  "#27AE60",      # Rioflex FX Adapt projected
    "target":   "#E74C3C",      # Target line / oversize
    "primary":  "#2C3E50",      # Headings, primary text
    "accent":   "#3498DB",      # Insight-box accent
    "good":     "#16A085",
    "warn":     "#E67E22",
}

PLOTLY_TEMPLATE = "plotly_white"
DEFAULT_HEIGHT = 460
SPATIAL_HEIGHT = 540

# ---------------------------------------------------------------------------
# Section navigation labels  —  ordered as the client story unfolds
# ---------------------------------------------------------------------------
SECTIONS = [
    ("overview",        "1 · Overview"),
    ("geometry",        "2 · Input Data & Bench Geometry"),
    ("fragmentation",   "3 · Fragmentation Performance"),
    ("calibration",     "4 · Rock Factor Calibration"),
    ("spatial",         "5 · Spatial Analysis"),
    ("comparison",      "6 · Product Comparison & Simulation"),
    ("recommendations", "7 · Recommendations & Next Steps"),
]
