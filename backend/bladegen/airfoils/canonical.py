"""Canonical NACA 4-digit generation and physical trailing-edge policy.

This module deliberately contains no geometry-backend imports.
"""

from __future__ import annotations

import math
import re

import numpy as np

NACA_4_DIGIT = re.compile(r"^(?:NACA\s*)?(\d)(\d)(\d{2})$", re.IGNORECASE)
TE_POLICY = "smooth_chord_normal"
TE_BLEND_START_X_OVER_C = 0.85


def naca_4digit_coordinates(
    code: str,
    points_per_surface: int = 161,
    thickness_ratio: float | None = None,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Return LE-to-TE upper/lower coordinates for a closed-TE NACA profile."""
    match = NACA_4_DIGIT.fullmatch(code.strip())
    if not match:
        raise ValueError(f"Invalid NACA 4-digit code: {code!r}")
    if points_per_surface < 3:
        raise ValueError("At least three points per surface are required")
    m = int(match.group(1)) / 100.0
    p = int(match.group(2)) / 10.0
    thickness = (
        float(thickness_ratio)
        if thickness_ratio is not None
        else int(match.group(3)) / 100.0
    )
    if not math.isfinite(thickness) or thickness <= 0.0:
        raise ValueError("Thickness ratio must be positive and finite")
    if m > 0.0 and p == 0.0:
        raise ValueError("Cambered NACA profile requires a nonzero camber position")

    beta = np.linspace(0.0, np.pi, points_per_surface)
    x = 0.5 * (1.0 - np.cos(beta))
    yt = (
        5.0
        * thickness
        * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1036 * x**4)
    )
    if m == 0.0:
        yc = np.zeros_like(x)
        slope = np.zeros_like(x)
    else:
        yc = np.where(
            x < p,
            m / p**2 * (2.0 * p * x - x**2),
            m / (1.0 - p) ** 2 * ((1.0 - 2.0 * p) + 2.0 * p * x - x**2),
        )
        slope = np.where(
            x < p,
            2.0 * m / p**2 * (p - x),
            2.0 * m / (1.0 - p) ** 2 * (p - x),
        )
    theta = np.arctan(slope)
    upper = np.column_stack((x - yt * np.sin(theta), yc + yt * np.cos(theta)))
    lower = np.column_stack((x + yt * np.sin(theta), yc - yt * np.cos(theta)))
    upper[0] = lower[0] = (0.0, 0.0)
    upper[-1] = lower[-1] = (1.0, 0.0)
    return (
        [(float(px), float(py)) for px, py in upper],
        [(float(px), float(py)) for px, py in lower],
    )


def trailing_edge_gap_normalized(
    upper: list[tuple[float, float]] | tuple[tuple[float, float], ...],
    lower: list[tuple[float, float]] | tuple[tuple[float, float], ...],
) -> float:
    """Return the chord-normal gap between the supplied TE endpoints."""
    return float(upper[-1][1] - lower[-1][1])


def _smoothstep_for_x(x_over_c: float, xi0: float) -> float:
    t = min(1.0, max(0.0, (x_over_c - xi0) / (1.0 - xi0)))
    return 3.0 * t * t - 2.0 * t * t * t


def apply_smooth_chord_normal_te(
    upper: list[tuple[float, float]] | tuple[tuple[float, float], ...],
    lower: list[tuple[float, float]] | tuple[tuple[float, float], ...],
    target_gap_mm: float,
    chord_mm: float,
    xi0: float = TE_BLEND_START_X_OVER_C,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Apply BladeSpec v0.2's symmetric smooth-chord-normal TE rule."""
    if not math.isfinite(chord_mm) or chord_mm <= 0.0:
        raise ValueError("Local chord must be positive and finite")
    if not math.isfinite(target_gap_mm) or target_gap_mm < 0.0:
        raise ValueError("Trailing-edge thickness must be nonnegative and finite")
    if not 0.0 <= xi0 < 1.0:
        raise ValueError("Trailing-edge blend start must satisfy 0 <= xi0 < 1")
    existing = trailing_edge_gap_normalized(upper, lower)
    target = target_gap_mm / chord_mm
    delta = target - existing

    resolved_upper = [
        (float(x), float(y + 0.5 * delta * _smoothstep_for_x(float(x), xi0))) for x, y in upper
    ]
    resolved_lower = [
        (float(x), float(y - 0.5 * delta * _smoothstep_for_x(float(x), xi0))) for x, y in lower
    ]
    return resolved_upper, resolved_lower
