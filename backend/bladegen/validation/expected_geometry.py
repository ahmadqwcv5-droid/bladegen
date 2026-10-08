"""Independent SciPy/NACA reference; never imports or queries OpenVSP."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.interpolate import PchipInterpolator

from bladegen.models import BladeSpec


@dataclass(frozen=True)
class SectionState:
    r_over_R: float
    chord_mm: float
    twist_deg: float
    rake_mm: float
    skew_mm: float
    thickness_ratio: float


def evaluate_distribution(distribution, field: str, station: float) -> float:
    x = np.asarray([point.r_over_R for point in distribution.points], dtype=float)
    y = np.asarray([getattr(point, field) for point in distribution.points], dtype=float)
    if distribution.interpolation.value == "pchip":
        return float(PchipInterpolator(x, y, extrapolate=False)(station))
    return float(np.interp(station, x, y))


def evaluate_state(spec: BladeSpec, station: float) -> SectionState:
    radius = spec.diameter_mm / 2.0
    return SectionState(
        r_over_R=station,
        chord_mm=evaluate_distribution(spec.chord_distribution, "chord_over_R", station) * radius,
        twist_deg=evaluate_distribution(spec.twist_distribution, "twist_deg", station),
        rake_mm=evaluate_distribution(spec.rake_distribution, "rake_over_R", station) * radius,
        skew_mm=evaluate_distribution(spec.skew_distribution, "skew_over_R", station) * radius,
        thickness_ratio=evaluate_distribution(
            spec.thickness_distribution, "thickness_ratio", station
        ),
    )


def naca_coordinates(code: str, count: int = 161) -> tuple[np.ndarray, np.ndarray]:
    m = int(code[0]) / 100.0
    p = int(code[1]) / 10.0
    thickness = int(code[2:]) / 100.0
    beta = np.linspace(0.0, np.pi, count)
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
    angle = np.arctan(slope)
    upper = np.column_stack((x - yt * np.sin(angle), yc + yt * np.cos(angle)))
    lower = np.column_stack((x + yt * np.sin(angle), yc - yt * np.cos(angle)))
    upper[0] = lower[0] = (0.0, 0.0)
    upper[-1] = lower[-1] = (1.0, 0.0)
    return upper, lower


def _base_profile(section) -> tuple[np.ndarray, np.ndarray]:
    if section.airfoil.type == "naca4":
        return naca_coordinates(section.airfoil.code)
    return (
        np.asarray(section.airfoil.upper, dtype=float),
        np.asarray(section.airfoil.lower, dtype=float),
    )


def resolved_control_profile(spec: BladeSpec, section) -> tuple[np.ndarray, np.ndarray]:
    upper, lower = _base_profile(section)
    if section.trailing_edge_thickness_mm is None:
        return upper, lower
    chord = evaluate_state(spec, section.r_over_R).chord_mm
    target = section.trailing_edge_thickness_mm / chord
    existing = upper[-1, 1] - lower[-1, 1]
    delta = target - existing
    for surface, sign in ((upper, 0.5), (lower, -0.5)):
        t = np.clip((surface[:, 0] - 0.85) / 0.15, 0.0, 1.0)
        blend = 3.0 * t**2 - 2.0 * t**3
        surface[:, 1] += sign * delta * blend
    return upper, lower


def _arc_resample(points: np.ndarray, grid: np.ndarray) -> np.ndarray:
    lengths = np.linalg.norm(np.diff(points, axis=0), axis=1)
    cumulative = np.concatenate(([0.0], np.cumsum(lengths)))
    cumulative /= cumulative[-1]
    return np.column_stack(
        (np.interp(grid, cumulative, points[:, 0]), np.interp(grid, cumulative, points[:, 1]))
    )


def diagnostic_profile(
    spec: BladeSpec, station: float, samples_per_surface: int = 2001
) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Arc-length reparameterized, linearly interpolated profile at a station."""
    sections = spec.airfoil_sections
    if station <= sections[0].r_over_R:
        left = right = sections[0]
    elif station >= sections[-1].r_over_R:
        left = right = sections[-1]
    else:
        right_index = next(
            index for index, section in enumerate(sections) if section.r_over_R >= station
        )
        if sections[right_index].r_over_R == station:
            left = right = sections[right_index]
        else:
            left, right = sections[right_index - 1], sections[right_index]
    fraction = (
        0.0
        if left.r_over_R == right.r_over_R
        else (station - left.r_over_R) / (right.r_over_R - left.r_over_R)
    )
    grid = np.linspace(0.0, 1.0, samples_per_surface)
    left_profile = resolved_control_profile(spec, left)
    right_profile = resolved_control_profile(spec, right)
    blended = []
    for left_surface, right_surface in zip(left_profile, right_profile):
        a = _arc_resample(left_surface, grid)
        b = _arc_resample(right_surface, grid)
        blended.append((1.0 - fraction) * a + fraction * b)
    return blended[0], blended[1], left.r_over_R, right.r_over_R


def section_transform(state: SectionState) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    theta = math.radians(state.twist_deg)
    chord_direction = np.array([math.sin(theta), math.cos(theta)])
    normal_direction = np.array([-math.cos(theta), math.sin(theta)])
    reference_axis = np.array(
        [
            state.rake_mm * math.cos(theta) + state.skew_mm * math.sin(theta),
            -state.rake_mm * math.sin(theta) + state.skew_mm * math.cos(theta),
        ]
    )
    return reference_axis, chord_direction, normal_direction


def placed_contour(spec: BladeSpec, station: float) -> tuple[np.ndarray, SectionState, dict]:
    state = evaluate_state(spec, station)
    upper, lower, left, right = diagnostic_profile(spec, station)
    reference, chord_direction, normal_direction = section_transform(state)

    def place(points: np.ndarray) -> np.ndarray:
        chordwise = (points[:, 0] - spec.reference_axis_x_over_c) * state.chord_mm
        normal = points[:, 1] * state.chord_mm
        return reference + chordwise[:, None] * chord_direction + normal[:, None] * normal_direction

    placed_upper = place(upper)
    placed_lower = place(lower)
    te_wall = np.linspace(placed_upper[-1], placed_lower[-1], 101)
    contour = np.vstack((placed_upper, placed_lower, te_wall))
    metadata = {
        "left_profile_r_over_R": left,
        "right_profile_r_over_R": right,
        "expected_te_mm": float(abs(upper[-1, 1] - lower[-1, 1]) * state.chord_mm),
    }
    return contour, state, metadata
