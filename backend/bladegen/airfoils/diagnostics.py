"""Deterministic advisory diagnostics for embedded coordinate airfoils.

These checks screen source-definition density.  They do not predict OpenVSP
fidelity, mutate coordinates, or replace final STEP validation.
"""

from __future__ import annotations

from collections.abc import Sequence

MIN_POINTS_PER_SURFACE = 25
MAX_CHORDWISE_SPACING = 0.10
LEADING_EDGE_REGION_MAX_X = 0.10
MIN_LEADING_EDGE_POINTS = 3


def _maximum_spacing(points: Sequence[Sequence[float]]) -> float:
    x_values = sorted(float(point[0]) for point in points)
    return max((right - left for left, right in zip(x_values, x_values[1:])), default=0.0)


def coordinate_profile_diagnostics(
    upper: Sequence[Sequence[float]], lower: Sequence[Sequence[float]]
) -> dict:
    """Return conservative, non-blocking quality warnings without changing input."""

    upper_count = len(upper)
    lower_count = len(lower)
    maximum_spacing = max(_maximum_spacing(upper), _maximum_spacing(lower))
    upper_le_count = sum(float(point[0]) <= LEADING_EDGE_REGION_MAX_X for point in upper)
    lower_le_count = sum(float(point[0]) <= LEADING_EDGE_REGION_MAX_X for point in lower)
    warning_codes: list[str] = []
    if min(upper_count, lower_count) < MIN_POINTS_PER_SURFACE:
        warning_codes.append("low_coordinate_density")
    if maximum_spacing > MAX_CHORDWISE_SPACING:
        warning_codes.append("large_chordwise_spacing")
    if min(upper_le_count, lower_le_count) < MIN_LEADING_EDGE_POINTS:
        warning_codes.append("sparse_leading_edge_coverage")

    messages = {
        "low_coordinate_density": (
            f"Fewer than {MIN_POINTS_PER_SURFACE} supplied points occur on at least one surface."
        ),
        "large_chordwise_spacing": (
            f"Maximum adjacent chordwise spacing exceeds {MAX_CHORDWISE_SPACING:.2f} c."
        ),
        "sparse_leading_edge_coverage": (
            f"Fewer than {MIN_LEADING_EDGE_POINTS} points occur at x/c <= "
            f"{LEADING_EDGE_REGION_MAX_X:.2f} on at least one surface."
        ),
    }
    return {
        "upper_point_count": upper_count,
        "lower_point_count": lower_count,
        "maximum_chordwise_spacing": maximum_spacing,
        "upper_leading_edge_point_count": upper_le_count,
        "lower_leading_edge_point_count": lower_le_count,
        "warning_codes": warning_codes,
        "warnings": [messages[code] for code in warning_codes],
        "has_warning": bool(warning_codes),
        "advisory": (
            "Low coordinate density detected. OpenVSP surface reconstruction may deviate "
            "from the supplied polyline. Final STEP fidelity will be checked after generation."
            if warning_codes
            else "No coordinate-density warning was detected; final STEP validation remains required."
        ),
    }
