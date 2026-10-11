"""Backend-neutral measurements for normalized airfoil coordinate contours."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class AirfoilMetrics:
    max_thickness_ratio: float
    max_thickness_x_over_c: float
    max_camber_ratio: float
    max_camber_x_over_c: float
    trailing_edge_gap_ratio: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def _surface_envelope(
    points: list[tuple[float, float]] | tuple[tuple[float, float], ...],
    *,
    upper: bool,
) -> tuple[np.ndarray, np.ndarray]:
    """Return sorted x values with deterministic handling of duplicate ordinates."""
    buckets: dict[float, list[float]] = {}
    for x_value, y_value in points:
        buckets.setdefault(float(x_value), []).append(float(y_value))
    x_values = np.asarray(sorted(buckets), dtype=float)
    y_values = np.asarray(
        [(max if upper else min)(buckets[x_value]) for x_value in x_values],
        dtype=float,
    )
    if len(x_values) < 2:
        raise ValueError("An airfoil surface requires at least two distinct x/c locations")
    return x_values, y_values


def measure_airfoil(
    upper: list[tuple[float, float]] | tuple[tuple[float, float], ...],
    lower: list[tuple[float, float]] | tuple[tuple[float, float], ...],
    *,
    sample_count: int = 2001,
) -> AirfoilMetrics:
    """Measure chord-normal thickness and camber without modifying the contour."""
    if sample_count < 101:
        raise ValueError("Airfoil measurement requires at least 101 samples")
    upper_x, upper_y = _surface_envelope(upper, upper=True)
    lower_x, lower_y = _surface_envelope(lower, upper=False)
    start = max(float(upper_x[0]), float(lower_x[0]))
    end = min(float(upper_x[-1]), float(lower_x[-1]))
    if end - start <= 1e-9:
        raise ValueError("Upper and lower surfaces do not share a usable chordwise domain")
    sample_x = np.linspace(start, end, sample_count)
    sampled_upper = np.interp(sample_x, upper_x, upper_y)
    sampled_lower = np.interp(sample_x, lower_x, lower_y)
    thickness = sampled_upper - sampled_lower
    if float(np.min(thickness[1:-1])) <= 0.0:
        raise ValueError("Upper and lower surfaces cross inside the chord domain")
    camber = 0.5 * (sampled_upper + sampled_lower)
    thickness_index = int(np.argmax(thickness))
    camber_index = int(np.argmax(np.abs(camber)))
    return AirfoilMetrics(
        max_thickness_ratio=float(thickness[thickness_index]),
        max_thickness_x_over_c=float(sample_x[thickness_index]),
        max_camber_ratio=float(camber[camber_index]),
        max_camber_x_over_c=float(sample_x[camber_index]),
        trailing_edge_gap_ratio=float(upper[-1][1] - lower[-1][1]),
    )
