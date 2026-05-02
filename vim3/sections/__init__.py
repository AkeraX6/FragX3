"""Section renderers used by the main router in app.py."""
from . import (
    overview,
    geometry,
    fragmentation,
    calibration,
    spatial,
    comparison,
    recommendations,
)

__all__ = [
    "overview",
    "geometry",
    "fragmentation",
    "calibration",
    "spatial",
    "comparison",
    "recommendations",
]
