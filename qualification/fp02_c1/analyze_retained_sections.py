#!/usr/bin/env python3
"""FP02-C1 retained-CAD and Q04.R1 authority diagnostics.

This is evidence tooling, not a product validator.  It intentionally keeps the
legacy expected calculation and the contract calculation side by side.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from bladegen.airfoils.geometry_metrics import measure_airfoil
from bladegen.models import BladeSpec
from bladegen.solid.ocp_solidify import read_step
from bladegen.validation.expected_geometry import (
    evaluate_state,
    resolved_control_profile,
    section_transform,
)
from bladegen.validation.measure_sections import (
    _endpoints,
    _identity_metrics,
    _sample_edges,
    _section_shape,
    _vertices,
    symmetric_distances,
)
from OCP.BRepTools import BRepTools
from scipy.interpolate import PchipInterpolator

RUN_ID = "fp02_c1_20261015T075331Z"
STATIONS = (0.30, 0.35, 0.40, 0.50)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def distribution_value(distribution: Any, field: str, station: float) -> float:
    points = distribution.points
    x = np.asarray([point.r_over_R for point in points], dtype=float)
    y = np.asarray([getattr(point, field) for point in points], dtype=float)
    if distribution.interpolation.value == "pchip":
        return float(PchipInterpolator(x, y, extrapolate=False)(station))
    return float(np.interp(station, x, y))


def arc_resample(points: np.ndarray, grid: np.ndarray) -> np.ndarray:
    lengths = np.linalg.norm(np.diff(points, axis=0), axis=1)
    cumulative = np.concatenate(([0.0], np.cumsum(lengths)))
    cumulative /= cumulative[-1]
    return np.column_stack(
        (
            np.interp(grid, cumulative, points[:, 0]),
            np.interp(grid, cumulative, points[:, 1]),
        )
    )


def bracket(spec: BladeSpec, station: float):
    sections = spec.airfoil_sections
    if station <= sections[0].r_over_R:
        return sections[0], sections[0], 0.0
    if station >= sections[-1].r_over_R:
        return sections[-1], sections[-1], 0.0
    index = next(i for i, section in enumerate(sections) if section.r_over_R >= station)
    if sections[index].r_over_R == station:
        return sections[index], sections[index], 0.0
    left, right = sections[index - 1], sections[index]
    fraction = (station - left.r_over_R) / (right.r_over_R - left.r_over_R)
    return left, right, fraction


def legacy_profile(
    spec: BladeSpec, station: float
) -> tuple[np.ndarray, np.ndarray, dict]:
    left, right, fraction = bracket(spec, station)
    grid = np.linspace(0.0, 1.0, 4001)
    result = []
    for left_surface, right_surface in zip(
        resolved_control_profile(spec, left), resolved_control_profile(spec, right)
    ):
        a = arc_resample(left_surface, grid)
        b = arc_resample(right_surface, grid)
        result.append((1.0 - fraction) * a + fraction * b)
    left_ratio = distribution_value(
        spec.thickness_distribution, "thickness_ratio", left.r_over_R
    )
    right_ratio = distribution_value(
        spec.thickness_distribution, "thickness_ratio", right.r_over_R
    )
    base_ratio = (1.0 - fraction) * left_ratio + fraction * right_ratio
    target_ratio = distribution_value(
        spec.thickness_distribution, "thickness_ratio", station
    )
    return (
        result[0],
        result[1],
        {
            "left_profile_r_over_R": left.r_over_R,
            "right_profile_r_over_R": right.r_over_R,
            "profile_interpolation_fraction": fraction,
            "left_control_thickness_ratio": left_ratio,
            "right_control_thickness_ratio": right_ratio,
            "linearly_interpolated_profile_thickness_ratio": base_ratio,
            "independent_curve_target_thickness_ratio": target_ratio,
            "post_blend_half_thickness_scale": target_ratio / base_ratio,
        },
    )


def _envelope_y(points: np.ndarray, query_x: np.ndarray, upper: bool) -> np.ndarray:
    buckets: dict[float, list[float]] = {}
    for x_value, y_value in points:
        buckets.setdefault(float(x_value), []).append(float(y_value))
    x_values = np.asarray(sorted(buckets), dtype=float)
    reducer = max if upper else min
    y_values = np.asarray([reducer(buckets[x]) for x in x_values], dtype=float)
    return np.interp(query_x, x_values, y_values)


def scale_half_thickness(
    upper: np.ndarray, lower: np.ndarray, scale: float
) -> tuple[np.ndarray, np.ndarray]:
    """Scale chord-normal half-thickness about the unmodified camber line."""
    if math.isclose(scale, 1.0, rel_tol=0.0, abs_tol=1e-14):
        return upper.copy(), lower.copy()
    corrected_upper = upper.copy()
    corrected_lower = lower.copy()
    lower_at_upper = _envelope_y(lower, upper[:, 0], upper=False)
    upper_at_lower = _envelope_y(upper, lower[:, 0], upper=True)
    upper_camber = 0.5 * (upper[:, 1] + lower_at_upper)
    lower_camber = 0.5 * (lower[:, 1] + upper_at_lower)
    corrected_upper[:, 1] = upper_camber + scale * (upper[:, 1] - upper_camber)
    corrected_lower[:, 1] = lower_camber + scale * (lower[:, 1] - lower_camber)
    return corrected_upper, corrected_lower


def place_profile(
    spec: BladeSpec, station: float, upper: np.ndarray, lower: np.ndarray
) -> tuple[np.ndarray, float]:
    state = evaluate_state(spec, station)
    reference, chord_direction, normal_direction = section_transform(state)

    def place(points: np.ndarray) -> np.ndarray:
        chordwise = (points[:, 0] - spec.reference_axis_x_over_c) * state.chord_mm
        normal = points[:, 1] * state.chord_mm
        return (
            reference
            + chordwise[:, None] * chord_direction
            + normal[:, None] * normal_direction
        )

    placed_upper = place(upper)
    placed_lower = place(lower)
    wall = np.linspace(placed_upper[-1], placed_lower[-1], 201)
    expected_te = abs(float(upper[-1, 1] - lower[-1, 1])) * state.chord_mm
    return np.vstack((placed_upper, placed_lower, wall)), expected_te


def metrics(cad: np.ndarray, expected: np.ndarray) -> dict[str, float]:
    distances = symmetric_distances(cad, expected)
    return {
        "rms_mm": float(np.sqrt(np.mean(distances * distances))),
        "p95_mm": float(np.percentile(distances, 95)),
        "sampled_max_mm": float(np.max(distances)),
    }


def csv_points(path: Path, groups: dict[str, np.ndarray]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("series", "x_mm", "z_mm"))
        for name, points in groups.items():
            writer.writerows((name, f"{x:.17g}", f"{z:.17g}") for x, z in points)


def plot_comparison(
    path: Path,
    station: float,
    cad: np.ndarray,
    legacy: np.ndarray,
    corrected: np.ndarray,
    *,
    closeup: bool,
) -> None:
    fig, axis = plt.subplots(figsize=(9.0, 5.2), constrained_layout=True)
    axis.plot(cad[:, 0], cad[:, 1], ".", ms=0.45, alpha=0.65, label="retained STEP")
    axis.plot(legacy[:, 0], legacy[:, 1], "--", lw=1.0, label="legacy expected")
    axis.plot(corrected[:, 0], corrected[:, 1], "-", lw=0.9, label="contract expected")
    axis.set_aspect("equal", adjustable="datalim")
    axis.grid(True, alpha=0.25)
    axis.set_xlabel("global X (mm)")
    axis.set_ylabel("global Z (mm)")
    axis.set_title(
        f"Retained section r/R={station:.2f}" + (" — trailing edge" if closeup else "")
    )
    axis.legend(loc="best")
    if closeup:
        tail = corrected[-201:]
        pad_x = max(float(np.ptp(tail[:, 0])) * 7.0, 0.35)
        pad_z = max(float(np.ptp(tail[:, 1])) * 0.8, 0.15)
        center = np.mean(tail, axis=0)
        axis.set_xlim(center[0] - pad_x, center[0] + pad_x)
        axis.set_ylim(center[1] - pad_z, center[1] + pad_z)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def locate_retained_record(records: list[dict], station: float) -> dict:
    return next(
        record
        for record in records
        if math.isclose(record["sampled_r_over_R"], station, abs_tol=1e-12)
    )


def diagnose_case(case_name: str, run_root: Path, output_root: Path) -> dict:
    case_root = run_root / "baseline" / case_name
    spec_path = case_root / f"{case_name}.json"
    input_path = case_root / "blade_spec_input.json"
    generated_path = case_root / "blade_spec.json"
    step_path = case_root / "blade_solid.step"
    failure_path = case_root / f"{case_name}_failed_geometry_validation.json"
    spec = BladeSpec.from_json(spec_path)
    retained = json.loads(failure_path.read_text(encoding="utf-8"))["stations"]
    case_output = output_root / case_name
    case_output.mkdir(parents=True, exist_ok=True)

    solid = read_step(step_path)
    records = []
    for station in STATIONS:
        state = evaluate_state(spec, station)
        old_upper, old_lower, operation = legacy_profile(spec, station)
        scale = operation["post_blend_half_thickness_scale"]
        new_upper, new_lower = scale_half_thickness(old_upper, old_lower, scale)
        old_expected, old_te = place_profile(spec, station, old_upper, old_lower)
        new_expected, new_te = place_profile(spec, station, new_upper, new_lower)

        section = _section_shape(solid, spec.diameter_mm / 2.0, station)
        brep_path = case_output / f"section_rR_{station:.2f}.brep"
        if not BRepTools.Write_s(section, str(brep_path)):
            raise RuntimeError(f"Unable to write {brep_path}")
        edge_points = _sample_edges(section, points_per_edge=5000)
        cad = np.vstack(edge_points)
        leading, _, chord_vector, measured_te = _endpoints(_vertices(section), state)
        measured_thickness, measured_camber = _identity_metrics(
            edge_points, leading, chord_vector
        )
        old_metrics = metrics(cad, old_expected)
        new_metrics = metrics(cad, new_expected)
        retained_record = locate_retained_record(retained, station)

        csv_points(
            case_output / f"section_rR_{station:.2f}.csv",
            {
                "retained_step": cad,
                "legacy_expected": old_expected,
                "contract_expected": new_expected,
            },
        )
        plot_comparison(
            case_output / f"section_rR_{station:.2f}_overlay.png",
            station,
            cad,
            old_expected,
            new_expected,
            closeup=False,
        )
        plot_comparison(
            case_output / f"section_rR_{station:.2f}_te_closeup.png",
            station,
            cad,
            old_expected,
            new_expected,
            closeup=True,
        )
        records.append(
            {
                "case": case_name,
                "station_r_over_R": station,
                "section_plane": {
                    "origin_mm": [0.0, state.r_over_R * spec.diameter_mm / 2.0, 0.0],
                    "normal": [0.0, 1.0, 0.0],
                },
                "sampling": {"points_per_edge": 5000, "bidirectional_kdtree": True},
                "operation": operation,
                "state": {
                    "chord_mm": state.chord_mm,
                    "twist_deg": state.twist_deg,
                    "rake_mm": state.rake_mm,
                    "skew_mm": state.skew_mm,
                    "submitted_thickness_ratio": distribution_value(
                        spec.thickness_distribution, "thickness_ratio", station
                    ),
                },
                "measured": {
                    "trailing_edge_mm": measured_te,
                    "max_thickness_over_chord": measured_thickness,
                    "max_camber_over_chord": measured_camber,
                },
                "legacy_expected": {"trailing_edge_mm": old_te, "contour": old_metrics},
                "contract_expected": {
                    "trailing_edge_mm": new_te,
                    "contour": new_metrics,
                },
                "retained_production_record": {
                    "trailing_edge_mm": retained_record["measured_te_mm"],
                    "expected_trailing_edge_mm": retained_record[
                        "expected_te_at_sample_mm"
                    ],
                    "max_thickness_over_chord": retained_record[
                        "measured_max_thickness_over_chord"
                    ],
                    "max_camber_over_chord": retained_record[
                        "measured_max_camber_over_chord"
                    ],
                    "contour_rms_mm": retained_record["contour_rms_mm"],
                    "contour_p95_mm": retained_record["contour_p95_mm"],
                    "contour_sampled_max_mm": retained_record["contour_max_mm"],
                    "flags": {
                        "rms": retained_record["contour_rms_pass"],
                        "p95": retained_record["contour_p95_pass"],
                        "sampled_max": retained_record["contour_max_pass"],
                        "te": retained_record["te_pass"],
                    },
                },
                "legacy_reproduction_delta": {
                    "measured_te_mm": measured_te - retained_record["measured_te_mm"],
                    "expected_te_mm": old_te
                    - retained_record["expected_te_at_sample_mm"],
                    "measured_thickness_ratio": measured_thickness
                    - retained_record["measured_max_thickness_over_chord"],
                    "contour_rms_mm": old_metrics["rms_mm"]
                    - retained_record["contour_rms_mm"],
                    "contour_p95_mm": old_metrics["p95_mm"]
                    - retained_record["contour_p95_mm"],
                    "contour_sampled_max_mm": old_metrics["sampled_max_mm"]
                    - retained_record["contour_max_mm"],
                },
                "artifacts": {
                    "brep": brep_path.name,
                    "csv": f"section_rR_{station:.2f}.csv",
                    "overlay": f"section_rR_{station:.2f}_overlay.png",
                    "te_closeup": f"section_rR_{station:.2f}_te_closeup.png",
                },
            }
        )

    result = {
        "case": case_name,
        "spec_identity": {
            "frozen_json_sha256": sha256(spec_path),
            "submitted_input_sha256": sha256(input_path),
            "generated_spec_sha256": sha256(generated_path),
            "frozen_equals_submitted_bytes": spec_path.read_bytes()
            == input_path.read_bytes(),
            "frozen_equals_submitted_canonical": canonical_hash(
                json.loads(spec_path.read_text())
            )
            == canonical_hash(json.loads(input_path.read_text())),
            "submitted_equals_generated_canonical": canonical_hash(
                json.loads(input_path.read_text())
            )
            == canonical_hash(json.loads(generated_path.read_text())),
            "retained_step_sha256": sha256(step_path),
        },
        "step_read_count": 1,
        "records": records,
    }
    write_json(case_output / "section_comparison.json", result)
    return result


def recursive_diff(left: Any, right: Any, path: str = "$") -> list[dict]:
    if type(left) is not type(right):
        return [{"path": path, "old": left, "new": right}]
    if isinstance(left, dict):
        result = []
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                result.append(
                    {
                        "path": f"{path}.{key}",
                        "old": left.get(key),
                        "new": right.get(key),
                    }
                )
            else:
                result.extend(recursive_diff(left[key], right[key], f"{path}.{key}"))
        return result
    if isinstance(left, list):
        if len(left) != len(right):
            return [{"path": path + ".length", "old": len(left), "new": len(right)}]
        result = []
        for index, (old, new) in enumerate(zip(left, right)):
            result.extend(recursive_diff(old, new, f"{path}[{index}]"))
        return result
    return [] if left == right else [{"path": path, "old": left, "new": right}]


def verify_q04(run_root: Path, qualification_root: Path, diagnostics: Path) -> dict:
    original_path = run_root / "baseline" / "Q04" / "Q04.json"
    revised_path = qualification_root / "cases" / "Q04.R1.json"
    original = json.loads(original_path.read_text(encoding="utf-8"))
    revised = json.loads(revised_path.read_text(encoding="utf-8"))
    diff = recursive_diff(original, revised)
    allowed = {"$.name"} | {
        f"$.thickness_distribution.points[{index}].thickness_ratio"
        for index in range(8)
    }
    actual = {item["path"] for item in diff}
    if actual != allowed:
        raise RuntimeError(f"Q04.R1 unexpected field diff: {sorted(actual ^ allowed)}")

    profile_records = []
    airfoil_hashes = []
    ratios = []
    for section in original["airfoil_sections"]:
        profile_hash = canonical_hash(section["airfoil"])
        airfoil_hashes.append(profile_hash)
        metrics_record = measure_airfoil(
            section["airfoil"]["upper"], section["airfoil"]["lower"]
        ).to_dict()
        refined_metrics = measure_airfoil(
            section["airfoil"]["upper"], section["airfoil"]["lower"], sample_count=20001
        ).to_dict()
        ratios.append(metrics_record["max_thickness_ratio"])
        profile_records.append(
            {
                "r_over_R": section["r_over_R"],
                "profile_sha256": profile_hash,
                "upper_count": len(section["airfoil"]["upper"]),
                "lower_count": len(section["airfoil"]["lower"]),
                "metrics": metrics_record,
                "refined_20001_sample_diagnostic_metrics": refined_metrics,
            }
        )
    if len(set(airfoil_hashes)) != 1:
        raise RuntimeError("Q04 profiles are not identical")
    natural_ratio = ratios[0]
    if max(abs(value - natural_ratio) for value in ratios) > 1e-15:
        raise RuntimeError("Identical Q04 profiles produced inconsistent thickness")

    revised_spec = BladeSpec.from_json(revised_path)
    assigned = [
        {
            "r_over_R": section.r_over_R,
            "curve_thickness_ratio": distribution_value(
                revised_spec.thickness_distribution, "thickness_ratio", section.r_over_R
            ),
            "natural_coordinate_thickness_ratio": natural_ratio,
        }
        for section in revised_spec.airfoil_sections
    ]
    dense = np.linspace(revised_spec.root_radius_ratio, 1.0, 10001)
    dense_values = np.asarray(
        [
            distribution_value(
                revised_spec.thickness_distribution, "thickness_ratio", float(x)
            )
            for x in dense
        ]
    )
    result = {
        "original_q04_sha256": sha256(original_path),
        "q04_r1_sha256_before_cad": sha256(revised_path),
        "q04_r1_canonical_sha256_before_cad": canonical_hash(revised),
        "field_diff": diff,
        "allowed_field_diff_exact": True,
        "coordinate_profile_identity": {
            "all_eight_identical": True,
            "unique_profile_count": 1,
            "profile_sha256": airfoil_hashes[0],
            "profiles": profile_records,
        },
        "full_precision_canonical_natural_thickness_ratio": natural_ratio,
        "canonical_calculation": "measure_airfoil default 2001-sample policy",
        "assigned_profile_compatibility": assigned,
        "supported_domain_compatibility": {
            "sample_count": len(dense),
            "maximum_absolute_error": float(
                np.max(np.abs(dense_values - natural_ratio))
            ),
            "minimum_ratio": float(np.min(dense_values)),
            "maximum_ratio": float(np.max(dense_values)),
        },
        "preserved": {
            "coordinates_and_order": all(
                old["airfoil"] == new["airfoil"]
                for old, new in zip(
                    original["airfoil_sections"], revised["airfoil_sections"]
                )
            ),
            "eight_station_radii": [
                section["r_over_R"] for section in revised["airfoil_sections"]
            ],
            "rotation_direction": revised["rotation_direction"],
            "reference_axis_x_over_c": revised["reference_axis_x_over_c"],
            "thickness_control_radii": [
                point["r_over_R"]
                for point in revised["thickness_distribution"]["points"]
            ],
            "thickness_interpolation": revised["thickness_distribution"][
                "interpolation"
            ],
        },
    }
    write_json(diagnostics / "q04_r1_authority_and_frozen_diff.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    repo = args.repo.resolve()
    qualification_root = repo / "qualification" / "fp02_c1"
    run_root = qualification_root / RUN_ID
    diagnostics = run_root / "diagnostics"
    diagnostics.mkdir(parents=True, exist_ok=True)
    q04 = verify_q04(run_root, qualification_root, diagnostics)
    cases = [diagnose_case(name, run_root, diagnostics) for name in ("Q02", "Q03")]
    summary = {
        "run_id": RUN_ID,
        "purpose": "retained STEP diagnosis before production correction or fresh CAD",
        "q04_r1": q04,
        "retained_cases": cases,
    }
    write_json(diagnostics / "retained_section_diagnosis.json", summary)
    print(json.dumps({"run_id": RUN_ID, "diagnostics": str(diagnostics)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
