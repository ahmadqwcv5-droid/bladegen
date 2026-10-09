"""Adaptive conversion of canonical BladeSpec curves to linear vectors."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from bladegen.airfoils.canonical import (
    TE_POLICY,
    apply_smooth_chord_normal_te,
    naca_4digit_coordinates,
    trailing_edge_gap_normalized,
)
from bladegen.curves.canonical import curve_data, evaluate_curve
from bladegen.models.blade_spec import AirfoilCoordinates, BladeSpec, Interpolation
from bladegen.models.resolved_blade_spec import (
    ResolvedAirfoilSection,
    ResolvedBladeSpec,
    ResolvedCurve,
)

RESOLVER_VERSION = "bladegen-canonical-resolver-2"
TOLERANCE_PROFILE = "bladespec-v0.1-engineering-1"
DENSE_VERIFICATION_LOCATIONS = 5001
MAX_SUBDIVISION_DEPTH = 30
MAX_RESOLVED_POINTS = 20000


@dataclass(frozen=True)
class CurveTolerance:
    engineering_value: float
    unit: str
    stored_value: float
    scale_to_engineering: float


def _canonical_values(curve_spec, locations: np.ndarray, value_name: str) -> np.ndarray:
    return np.asarray(
        [evaluate_curve(curve_spec, float(location), value_name) for location in locations],
        dtype=float,
    )


def _adaptive_segment(
    curve_spec,
    value_name: str,
    left: float,
    right: float,
    left_value: float,
    right_value: float,
    tolerance: float,
    depth: int,
) -> list[tuple[float, float]]:
    fractions = np.asarray((0.25, 0.50, 0.75), dtype=float)
    locations = left + fractions * (right - left)
    canonical = _canonical_values(curve_spec, locations, value_name)
    linear = left_value + fractions * (right_value - left_value)
    if float(np.max(np.abs(canonical - linear))) <= tolerance:
        return [(right, right_value)]
    if depth >= MAX_SUBDIVISION_DEPTH:
        raise RuntimeError("Canonical curve adaptive subdivision safety depth exceeded")
    midpoint = (left + right) / 2.0
    midpoint_value = evaluate_curve(curve_spec, midpoint, value_name)
    return _adaptive_segment(
        curve_spec,
        value_name,
        left,
        midpoint,
        left_value,
        midpoint_value,
        tolerance,
        depth + 1,
    ) + _adaptive_segment(
        curve_spec,
        value_name,
        midpoint,
        right,
        midpoint_value,
        right_value,
        tolerance,
        depth + 1,
    )


def resolve_curve(
    curve_spec,
    value_name: str,
    tolerance: CurveTolerance,
) -> ResolvedCurve:
    """Resolve one canonical curve adaptively, then verify it at 5001 points."""
    controls, values = curve_data(curve_spec, value_name)
    resolved: list[tuple[float, float]] = [(float(controls[0]), float(values[0]))]
    for index in range(len(controls) - 1):
        resolved.extend(
            _adaptive_segment(
                curve_spec,
                value_name,
                float(controls[index]),
                float(controls[index + 1]),
                float(values[index]),
                float(values[index + 1]),
                tolerance.stored_value,
                0,
            )
        )

    # Supplement interval probes with a deterministic whole-domain audit.
    dense = np.linspace(float(controls[0]), float(controls[-1]), DENSE_VERIFICATION_LOCATIONS)
    canonical = _canonical_values(curve_spec, dense, value_name)
    while True:
        parameters = np.asarray([point[0] for point in resolved], dtype=float)
        resolved_values = np.asarray([point[1] for point in resolved], dtype=float)
        errors = np.abs(canonical - np.interp(dense, parameters, resolved_values))
        maximum = float(np.max(errors))
        if maximum <= tolerance.stored_value:
            break
        worst = float(dense[int(np.argmax(errors))])
        if worst in set(parameters):
            raise RuntimeError("Dense resolver verification stalled above tolerance")
        resolved.append((worst, evaluate_curve(curve_spec, worst, value_name)))
        resolved.sort(key=lambda point: point[0])
        if len(resolved) > MAX_RESOLVED_POINTS:
            raise RuntimeError("Canonical curve resolved-point safety limit exceeded")

    # Every user control is an interval endpoint; restore its exact value after
    # refinement to make that preservation explicit and independently testable.
    control_map = {float(parameter): float(value) for parameter, value in zip(controls, values)}
    resolved = [(parameter, control_map.get(parameter, value)) for parameter, value in resolved]
    physical_error = maximum * tolerance.scale_to_engineering
    return ResolvedCurve(
        parameter_vector=tuple(point[0] for point in resolved),
        value_vector=tuple(point[1] for point in resolved),
        source_interpolation=Interpolation(curve_spec.interpolation),
        original_control_count=len(controls),
        tolerance=tolerance.engineering_value,
        tolerance_unit=tolerance.unit,
        stored_value_tolerance=tolerance.stored_value,
        verification_locations=DENSE_VERIFICATION_LOCATIONS,
        max_canonical_vs_resolved_error=physical_error,
        max_canonical_vs_resolved_error_stored=maximum,
    )


def tolerance_profile(spec: BladeSpec) -> dict[str, CurveTolerance]:
    radius_mm = spec.diameter_mm / 2.0
    return {
        "chord": CurveTolerance(0.005, "mm", 0.005 / radius_mm, radius_mm),
        "twist": CurveTolerance(0.002, "deg", 0.002, 1.0),
        "rake": CurveTolerance(0.005, "mm", 0.005 / radius_mm, radius_mm),
        "skew": CurveTolerance(0.005, "mm", 0.005 / radius_mm, radius_mm),
        "thickness": CurveTolerance(1e-5, "ratio", 1e-5, 1.0),
    }


def resolve_airfoil_sections(spec: BladeSpec) -> tuple[ResolvedAirfoilSection, ...]:
    """Resolve physical TE intent into exact normalized section coordinates."""
    radius_mm = spec.diameter_mm / 2.0
    result = []
    for section in spec.airfoil_sections:
        chord_mm = (
            evaluate_curve(spec.chord_distribution, section.r_over_R, "chord_over_R") * radius_mm
        )
        if section.airfoil.type == "naca4":
            nominal_ratio = int(section.airfoil.code[2:]) / 100.0
            expected_ratio = (
                section.thickness_override_ratio
                if section.thickness_override_ratio is not None
                else nominal_ratio
            )
            actual_ratio = evaluate_curve(
                spec.thickness_distribution, section.r_over_R, "thickness_ratio"
            )
            if not math.isclose(actual_ratio, expected_ratio, abs_tol=1e-6):
                choice = (
                    "explicit thickness_override_ratio"
                    if section.thickness_override_ratio is not None
                    else f"nominal NACA {section.airfoil.code} thickness {nominal_ratio:.4f}"
                )
                raise ValueError(
                    f"Thickness distribution at r/R={section.r_over_R:g} is "
                    f"{actual_ratio:.6f}, inconsistent with {choice}; update the curve "
                    "or declare thickness_override_ratio."
                )
            # Resolve the effective section geometry before handing it to a CAD
            # backend. This prevents OpenVSP from scaling finite TE gaps when a
            # NACA thickness override differs from the nominal code.
            upper, lower = naca_4digit_coordinates(
                section.airfoil.code, thickness_ratio=actual_ratio
            )
        else:
            upper = list(section.airfoil.upper)
            lower = list(section.airfoil.lower)
        if section.trailing_edge_thickness_mm is None:
            resolved_upper, resolved_lower = upper, lower
            requested_mm = trailing_edge_gap_normalized(upper, lower) * chord_mm
            policy = "unchanged"
        else:
            requested_mm = section.trailing_edge_thickness_mm
            resolved_upper, resolved_lower = apply_smooth_chord_normal_te(
                upper, lower, requested_mm, chord_mm
            )
            policy = TE_POLICY
        generated_mm = trailing_edge_gap_normalized(resolved_upper, resolved_lower) * chord_mm
        result.append(
            ResolvedAirfoilSection(
                r_over_R=section.r_over_R,
                airfoil=AirfoilCoordinates(
                    type="coordinates", upper=resolved_upper, lower=resolved_lower
                ),
                trailing_edge_policy=policy,
                local_chord_mm=chord_mm,
                requested_trailing_edge_thickness_mm=requested_mm,
                generated_trailing_edge_thickness_mm=generated_mm,
                mathematical_error_mm=abs(generated_mm - requested_mm),
            )
        )
    return tuple(result)


def resolve_blade_spec(spec: BladeSpec) -> ResolvedBladeSpec:
    """Create the backend-neutral representation consumed by geometry adapters."""
    tolerances = tolerance_profile(spec)
    return ResolvedBladeSpec(
        resolver_version=RESOLVER_VERSION,
        tolerance_profile=TOLERANCE_PROFILE,
        source_bladespec=spec,
        airfoil_sections=resolve_airfoil_sections(spec),
        chord_curve=resolve_curve(spec.chord_distribution, "chord_over_R", tolerances["chord"]),
        twist_curve=resolve_curve(spec.twist_distribution, "twist_deg", tolerances["twist"]),
        rake_curve=resolve_curve(spec.rake_distribution, "rake_over_R", tolerances["rake"]),
        skew_curve=resolve_curve(spec.skew_distribution, "skew_over_R", tolerances["skew"]),
        thickness_curve=resolve_curve(
            spec.thickness_distribution,
            "thickness_ratio",
            tolerances["thickness"],
        ),
    )
