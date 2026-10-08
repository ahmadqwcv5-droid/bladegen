"""Independent validation of adapter readback and generated CAD geometry."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_FACE
from OCP.TopoDS import TopoDS

from bladegen.models import ResolvedBladeSpec
from bladegen.solid.ocp_solidify import inspect_shape, read_step, shapes


def validate_openvsp_readback(resolved: ResolvedBladeSpec, readback: dict) -> dict:
    spec = resolved.source_bladespec
    scalar_errors = {
        "diameter_mm": abs(spec.diameter_mm - readback["diameter_mm"]),
        "root_radius_ratio": abs(spec.root_radius_ratio - readback["root_radius_ratio"]),
        "reference_axis_x_over_c": abs(
            spec.reference_axis_x_over_c - readback["reference_axis_x_over_c"]
        ),
    }
    identity_checks = {
        "schema_version": readback["schema_version"] == spec.schema_version,
        "name": readback["name"] == spec.name,
        "units": readback["units"] == spec.units,
        "rotation_direction": readback["rotation_direction"] == spec.rotation_direction.value,
    }

    distribution_fields = {
        "chord_distribution": (resolved.chord_curve, "chord_over_R"),
        "twist_distribution": (resolved.twist_curve, "twist_deg"),
        "rake_distribution": (resolved.rake_curve, "rake_over_R"),
        "skew_distribution": (resolved.skew_curve, "skew_over_R"),
        "thickness_distribution": (resolved.thickness_curve, "thickness_ratio"),
    }
    distribution_results = {}
    maximum_curve_error = 0.0
    for name, (expected, value_name) in distribution_fields.items():
        actual = readback[name]
        radii = np.asarray(expected.parameter_vector)
        values = np.asarray(expected.value_vector)
        actual_radii = np.array([point["r_over_R"] for point in actual["points"]])
        actual_values = np.array([point[value_name] for point in actual["points"]])
        radius_error = (
            float(np.max(np.abs(radii - actual_radii)))
            if radii.shape == actual_radii.shape
            else math.inf
        )
        value_error = (
            float(np.max(np.abs(values - actual_values)))
            if values.shape == actual_values.shape
            else math.inf
        )
        maximum_curve_error = max(maximum_curve_error, radius_error, value_error)
        distribution_results[name] = {
            "interpolation_match": actual["interpolation"] == "linear",
            "point_count_match": len(expected.parameter_vector) == len(actual["points"]),
            "max_radius_error": radius_error,
            "max_value_error": value_error,
        }

    contour_distances_mm = []
    section_results = []
    if len(resolved.airfoil_sections) != len(readback["airfoil_sections"]):
        raise RuntimeError("OpenVSP changed the number of airfoil sections")
    for expected, actual in zip(resolved.airfoil_sections, readback["airfoil_sections"]):
        section_distances = []
        chord_mm = expected.local_chord_mm
        for surface in ("upper", "lower"):
            left = np.asarray(getattr(expected.airfoil, surface), dtype=float)
            right = np.asarray(actual["airfoil"][surface], dtype=float)
            if left.shape != right.shape:
                raise RuntimeError(f"OpenVSP changed {surface} airfoil point count")
            section_distances.extend(np.linalg.norm(left - right, axis=1) * chord_mm)
        contour_distances_mm.extend(section_distances)
        section_results.append(
            {
                "r_over_R": expected.r_over_R,
                "radius_error": abs(expected.r_over_R - actual["r_over_R"]),
                "max_contour_error_mm": float(max(section_distances, default=0.0)),
            }
        )

    all_distributions_pass = all(
        item["interpolation_match"]
        and item["point_count_match"]
        and item["max_radius_error"] <= 1e-12
        and item["max_value_error"] <= 1e-12
        for item in distribution_results.values()
    )
    result = {
        "scalar_errors": scalar_errors,
        "identity_checks": identity_checks,
        "distributions": distribution_results,
        "max_curve_control_error": maximum_curve_error,
        "all_pcurves_linear": all(
            item["interpolation_match"] for item in distribution_results.values()
        ),
        "airfoil_sections": section_results,
        "max_airfoil_coordinate_error_mm": float(max(contour_distances_mm, default=0.0)),
    }
    result["passed"] = (
        all(identity_checks.values())
        and max(scalar_errors.values()) <= 1e-10
        and all_distributions_pass
        and result["max_airfoil_coordinate_error_mm"] <= 1e-5
        and all(item["radius_error"] <= 1e-12 for item in section_results)
    )
    return result


def _surface_area(face) -> float:
    properties = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, properties)
    return float(properties.Mass())


def _sorted_faces(shape) -> list:
    faces = [TopoDS.Face_s(face) for face in shapes(shape, TopAbs_FACE)]
    return sorted(faces, key=_surface_area)


def _sample_corresponding_surfaces(reference_face, candidate_face, count: int) -> list[float]:
    reference = BRepAdaptor_Surface(reference_face)
    candidate = BRepAdaptor_Surface(candidate_face)
    left_bounds = (
        reference.FirstUParameter(),
        reference.LastUParameter(),
        reference.FirstVParameter(),
        reference.LastVParameter(),
    )
    right_bounds = (
        candidate.FirstUParameter(),
        candidate.LastUParameter(),
        candidate.FirstVParameter(),
        candidate.LastVParameter(),
    )
    distances = []
    for iu in range(count):
        left_u = left_bounds[0] + (left_bounds[1] - left_bounds[0]) * iu / (count - 1)
        right_u = right_bounds[0] + (right_bounds[1] - right_bounds[0]) * iu / (count - 1)
        for iv in range(count):
            left_v = left_bounds[2] + (left_bounds[3] - left_bounds[2]) * iv / (count - 1)
            right_v = right_bounds[2] + (right_bounds[3] - right_bounds[2]) * iv / (count - 1)
            distances.append(
                reference.Value(left_u, left_v).Distance(candidate.Value(right_u, right_v))
            )
    return distances


def compare_steps(reference_path: Path, candidate_path: Path, samples: int = 41) -> dict:
    reference_shape = read_step(reference_path)
    candidate_shape = read_step(candidate_path)
    reference_faces = _sorted_faces(reference_shape)
    candidate_faces = _sorted_faces(candidate_shape)
    if len(reference_faces) != len(candidate_faces):
        raise RuntimeError(
            f"Face count mismatch: {len(reference_faces)} versus {len(candidate_faces)}"
        )

    per_face = []
    distances = []
    for index, (reference_face, candidate_face) in enumerate(zip(reference_faces, candidate_faces)):
        face_distances = _sample_corresponding_surfaces(reference_face, candidate_face, samples)
        distances.extend(face_distances)
        per_face.append(
            {
                "face": index,
                "reference_area_mm2": _surface_area(reference_face),
                "candidate_area_mm2": _surface_area(candidate_face),
                "rms_mm": float(np.sqrt(np.mean(np.square(face_distances)))),
                "p95_mm": float(np.percentile(face_distances, 95)),
                "max_mm": float(np.max(face_distances)),
            }
        )

    array = np.asarray(distances)
    reference = inspect_shape(reference_shape)
    candidate = inspect_shape(candidate_shape)
    bbox_error = max(
        abs(left - right)
        for key in ("min_mm", "max_mm")
        for left, right in zip(reference["bbox"][key], candidate["bbox"][key])
    )
    result = {
        "sample_count": len(distances),
        "rms_mm": float(np.sqrt(np.mean(array * array))),
        "p95_mm": float(np.percentile(array, 95)),
        "max_mm": float(np.max(array)),
        "bbox_max_abs_error_mm": bbox_error,
        "tip_position_error_mm": abs(
            reference["bbox"]["max_mm"][1] - candidate["bbox"]["max_mm"][1]
        ),
        "root_position_error_mm": abs(
            reference["bbox"]["min_mm"][1] - candidate["bbox"]["min_mm"][1]
        ),
        "surface_area_difference_mm2": abs(
            reference["surface_area_mm2"] - candidate["surface_area_mm2"]
        ),
        "reference": reference,
        "candidate": candidate,
        "per_face": per_face,
        "targets_mm": {"rms": 0.10, "p95": 0.25, "max": 0.75},
    }
    result["passed"] = (
        result["rms_mm"] <= 0.10 and result["p95_mm"] <= 0.25 and result["max_mm"] <= 0.75
    )
    return result
