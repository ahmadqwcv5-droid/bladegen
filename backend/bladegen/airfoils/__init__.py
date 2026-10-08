"""Backend-independent canonical airfoil mathematics."""

from .canonical import (
    apply_smooth_chord_normal_te,
    naca_4digit_coordinates,
    trailing_edge_gap_normalized,
)

__all__ = [
    "apply_smooth_chord_normal_te",
    "naca_4digit_coordinates",
    "trailing_edge_gap_normalized",
]
