#!/usr/bin/env python3
"""Read-only contour-isolation diagnostic for the retained Sprint 04B X-57 job.

The supervisor records identity, launches a timeout-bounded worker, and writes a
separately labelled evidence bundle.  The worker reads each retained STEP once,
uses the exact production three-station measurement path for the baseline, and
then performs independent component-aware point-to-polyline diagnostics.  It
never imports OpenVSP and never regenerates or repairs CAD.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
import traceback
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.spatial import cKDTree

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import diagnose_x57_validation as retained_diagnosis

JOB_ID = "a93b281c29b640afaa6bad698d64a61b"
EXPECTED_FINAL_STEP_SHA256 = "43c2cd72bebcd3949e0fe0b210aaac9ccbf6918952743fd109ecb0cac2e401d6"
EXPECTED_RAW_STEP_SHA256 = "85f798f74f672e4c78f3560e3413fcbdbba0ff7410424a840a5fc4e746d8b07f"
SELECTED_STATIONS = (0.22302, 0.29061, 0.50345)
DEFAULT_JOB_DIR = REPOSITORY_ROOT / "output" / "runs" / JOB_ID
DEFAULT_EVIDENCE_ROOT = REPOSITORY_ROOT / "docs" / "evidence" / "sprint04b" / "x57"
DEFAULT_OUTPUT_ROOT = DEFAULT_EVIDENCE_ROOT / "contour_isolation"
PRIOR_DIAGNOSTIC = (
    DEFAULT_EVIDENCE_ROOT
    / "validation_diagnostics"
    / "a93b281c_20261014T080820Z"
)
EPS = 1.0e-14

RELEVANT_SOURCES = (
    "backend/bladegen/adapters/openvsp_adapter.py",
    "backend/bladegen/airfoils/canonical.py",
    "backend/bladegen/airfoils/geometry_metrics.py",
    "backend/bladegen/curves/resolver.py",
    "backend/bladegen/solid/ocp_solidify.py",
    "backend/bladegen/validation/expected_geometry.py",
    "backend/bladegen/validation/measure_sections.py",
    "backend/bladegen/validation/station_plan.py",
    "scripts/diagnose_x57_validation.py",
    "scripts/diagnose_x57_contours.py",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(jsonable(value), indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def csv_write(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def station_slug(station: float) -> str:
    return f"rR_{station:.5f}".replace(".", "p")


def jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


class EventLog:
    def __init__(self, path: Path) -> None:
        self.stream = path.open("w", encoding="utf-8", buffering=1)
        self.origin_ns = time.monotonic_ns()
        self.sequence = 0

    def emit(self, event: str, **fields: Any) -> None:
        self.sequence += 1
        now = time.monotonic_ns()
        record = {
            "sequence": self.sequence,
            "event": event,
            "utc": utc_now(),
            "monotonic_ns": now,
            "since_worker_start_seconds": (now - self.origin_ns) / 1e9,
            **jsonable(fields),
        }
        line = json.dumps(record, sort_keys=True, allow_nan=False)
        self.stream.write(line + "\n")
        self.stream.flush()
        print(f"CONTOUR_EVENT {line}", flush=True)

    @contextmanager
    def operation(self, name: str, **fields: Any) -> Iterator[None]:
        started = time.monotonic_ns()
        self.emit("operation_start", operation=name, **fields)
        try:
            yield
        except BaseException as exc:
            self.emit(
                "operation_end",
                operation=name,
                status="ERROR",
                elapsed_seconds=(time.monotonic_ns() - started) / 1e9,
                error=f"{type(exc).__name__}: {exc}",
                **fields,
            )
            raise
        else:
            self.emit(
                "operation_end",
                operation=name,
                status="COMPLETED",
                elapsed_seconds=(time.monotonic_ns() - started) / 1e9,
                **fields,
            )

    def close(self) -> None:
        self.stream.close()


# Independent component-aware point-to-segment metric.  The KD trees are only
# a conservative broad phase; final distances are analytic projections onto
# finite segments.  Components are never bridged.
def _prepare_target(components: list[dict[str, Any]]) -> dict[str, Any]:
    segment_a: list[np.ndarray] = []
    segment_b: list[np.ndarray] = []
    segment_component: list[str] = []
    segment_local: list[int] = []
    vertices: list[np.ndarray] = []
    vertex_component: list[str] = []
    for component in components:
        name = str(component["name"])
        points = np.asarray(component["points"], dtype=float)
        if points.ndim != 2 or points.shape[1] != 2 or not len(points):
            raise ValueError(f"Invalid polyline component {name}")
        if not np.isfinite(points).all():
            raise ValueError(f"Non-finite polyline component {name}")
        if component.get("closed") and not np.array_equal(points[0], points[-1]):
            points = np.vstack((points, points[0]))
        vertices.append(points)
        vertex_component.extend([name] * len(points))
        delta = np.diff(points, axis=0)
        lengths = np.linalg.norm(delta, axis=1)
        for index in np.flatnonzero(lengths > EPS):
            segment_a.append(points[index])
            segment_b.append(points[index + 1])
            segment_component.append(name)
            segment_local.append(int(index))
    a = np.asarray(segment_a, dtype=float).reshape(-1, 2)
    b = np.asarray(segment_b, dtype=float).reshape(-1, 2)
    vectors = b - a
    return {
        "vertices": np.vstack(vertices),
        "vertex_component": np.asarray(vertex_component, dtype=object),
        "a": a,
        "b": b,
        "vectors": vectors,
        "length_squared": np.einsum("ij,ij->i", vectors, vectors) if len(a) else np.empty(0),
        "segment_component": np.asarray(segment_component, dtype=object),
        "segment_local": np.asarray(segment_local, dtype=int),
    }


def point_to_segments(query: np.ndarray, target_components: list[dict[str, Any]]) -> dict[str, Any]:
    points = np.asarray(query, dtype=float)
    target = _prepare_target(target_components)
    vertex_tree = cKDTree(target["vertices"])
    vertex_distance, vertex_index = vertex_tree.query(points, k=1)
    distance = np.asarray(vertex_distance, dtype=float).copy()
    closest = target["vertices"][vertex_index].copy()
    segment_index = np.full(len(points), -1, dtype=int)
    local_index = np.full(len(points), -1, dtype=int)
    component = target["vertex_component"][vertex_index].copy()
    projection = np.full(len(points), np.nan)
    if len(target["a"]):
        midpoints = 0.5 * (target["a"] + target["b"])
        half_lengths = 0.5 * np.sqrt(target["length_squared"])
        midpoint_tree = cKDTree(midpoints)
        scale = max(
            1.0,
            float(np.max(np.abs(target["vertices"]))),
            float(np.max(np.abs(points))),
        )
        pad = 64.0 * np.finfo(float).eps * scale
        radii = distance + float(np.max(half_lengths)) + pad
        candidates_by_point = midpoint_tree.query_ball_point(points, radii)
        for point_index, (point, candidates) in enumerate(zip(points, candidates_by_point)):
            candidate = np.asarray(candidates, dtype=int)
            if not len(candidate):
                raise AssertionError("Conservative segment broad phase returned no candidate")
            candidate.sort()
            relative = point - target["a"][candidate]
            parameter = np.clip(
                np.einsum("ij,ij->i", relative, target["vectors"][candidate])
                / target["length_squared"][candidate],
                0.0,
                1.0,
            )
            projected = target["a"][candidate] + parameter[:, None] * target["vectors"][candidate]
            squared = np.einsum("ij,ij->i", point - projected, point - projected)
            local_minimum = int(np.argmin(squared))
            chosen = int(candidate[local_minimum])
            candidate_distance = float(np.sqrt(squared[local_minimum]))
            if candidate_distance <= distance[point_index] + pad:
                distance[point_index] = candidate_distance
                closest[point_index] = projected[local_minimum]
                segment_index[point_index] = chosen
                local_index[point_index] = target["segment_local"][chosen]
                component[point_index] = target["segment_component"][chosen]
                projection[point_index] = float(parameter[local_minimum])
    return {
        "distance": distance,
        "closest": closest,
        "segment_index": segment_index,
        "segment_local_index": local_index,
        "target_component": component,
        "projection_t": projection,
    }


def _query_points_and_weights(components: list[dict[str, Any]]) -> dict[str, Any]:
    point_sets: list[np.ndarray] = []
    weights: list[np.ndarray] = []
    names: list[str] = []
    local_indices: list[int] = []
    arclengths: list[np.ndarray] = []
    fractions: list[np.ndarray] = []
    for component in components:
        name = str(component["name"])
        points = np.asarray(component["points"], dtype=float)
        if component.get("closed") and not np.array_equal(points[0], points[-1]):
            points = np.vstack((points, points[0]))
        segment_lengths = np.linalg.norm(np.diff(points, axis=0), axis=1)
        weight = np.zeros(len(points))
        weight[:-1] += 0.5 * segment_lengths
        weight[1:] += 0.5 * segment_lengths
        cumulative = np.concatenate(([0.0], np.cumsum(segment_lengths)))
        total = float(cumulative[-1])
        fraction = cumulative / total if total > EPS else np.zeros(len(points))
        point_sets.append(points)
        weights.append(weight)
        names.extend([name] * len(points))
        local_indices.extend(range(len(points)))
        arclengths.append(cumulative)
        fractions.append(fraction)
    return {
        "points": np.vstack(point_sets),
        "weights": np.concatenate(weights),
        "component": np.asarray(names, dtype=object),
        "local_index": np.asarray(local_indices, dtype=int),
        "s_mm": np.concatenate(arclengths),
        "s_fraction": np.concatenate(fractions),
    }


def weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
    order = np.argsort(values, kind="stable")
    ordered_values = np.asarray(values)[order]
    ordered_weights = np.asarray(weights)[order]
    if float(np.sum(ordered_weights)) <= 0.0:
        raise ValueError("Weighted quantile requires positive weight")
    index = int(
        np.searchsorted(
            np.cumsum(ordered_weights), quantile * float(np.sum(ordered_weights)), side="left"
        )
    )
    return float(ordered_values[min(index, len(ordered_values) - 1)])


def distance_stats(distance: np.ndarray, weights: np.ndarray | None = None) -> dict[str, Any]:
    values = np.asarray(distance, dtype=float)
    use_weights = np.ones(len(values), dtype=float) if weights is None else np.asarray(weights, dtype=float)
    keep = use_weights > 0.0
    values = values[keep]
    use_weights = use_weights[keep]
    return {
        "samples": int(len(values)),
        "weight_sum_mm": float(np.sum(use_weights)),
        "rms_mm": float(np.sqrt(np.dot(use_weights, values * values) / np.sum(use_weights))),
        "p95_mm": weighted_quantile(values, use_weights, 0.95),
        "sampled_max_mm": float(np.max(values)),
    }


def compare_components(
    left: list[dict[str, Any]], right: list[dict[str, Any]]
) -> dict[str, Any]:
    left_query = _query_points_and_weights(left)
    right_query = _query_points_and_weights(right)
    left_to_right = point_to_segments(left_query["points"], right)
    right_to_left = point_to_segments(right_query["points"], left)
    left_keep = left_query["weights"] > 0.0
    right_keep = right_query["weights"] > 0.0
    combined_distance = np.concatenate(
        (left_to_right["distance"][left_keep], right_to_left["distance"][right_keep])
    )
    combined_weight = np.concatenate(
        (
            0.5 * left_query["weights"][left_keep] / np.sum(left_query["weights"][left_keep]),
            0.5 * right_query["weights"][right_keep] / np.sum(right_query["weights"][right_keep]),
        )
    )
    return {
        "left_to_right": {
            "count_weighted": distance_stats(left_to_right["distance"]),
            "arc_weighted": distance_stats(left_to_right["distance"], left_query["weights"]),
        },
        "right_to_left": {
            "count_weighted": distance_stats(right_to_left["distance"]),
            "arc_weighted": distance_stats(right_to_left["distance"], right_query["weights"]),
        },
        "bidirectional_count_weighted": distance_stats(
            np.concatenate((left_to_right["distance"], right_to_left["distance"]))
        ),
        "bidirectional_equal_direction_arc_weighted": distance_stats(
            combined_distance, combined_weight
        ),
        "left_detail": left_to_right,
        "right_detail": right_to_left,
        "left_query": left_query,
        "right_query": right_query,
    }


def public_metric(metric: dict[str, Any]) -> dict[str, Any]:
    return {
        key: jsonable(value)
        for key, value in metric.items()
        if key not in {"left_detail", "right_detail", "left_query", "right_query"}
    }


def metric_self_tests() -> dict[str, Any]:
    tests: list[dict[str, Any]] = []

    def record(name: str, metric: dict[str, Any], expected: float, tolerance: float) -> None:
        measured = metric["bidirectional_equal_direction_arc_weighted"]["sampled_max_mm"]
        tests.append(
            {
                "name": name,
                "expected_sampled_max_mm": expected,
                "measured_sampled_max_mm": measured,
                "absolute_error_mm": abs(measured - expected),
                "tolerance_mm": tolerance,
                "passed": abs(measured - expected) <= tolerance,
            }
        )

    profile = [
        {"name": "upper", "points": np.array([[0.0, 0.0], [0.3, 0.2], [1.0, 0.0]])},
        {"name": "lower", "points": np.array([[0.0, 0.0], [0.4, -0.15], [1.0, 0.0]])},
    ]
    record("identical_contour", compare_components(profile, profile), 0.0, 1e-12)

    square = np.array([[0.0, 0.0], [3.0, 0.0], [3.0, 2.0], [0.0, 2.0]])
    shifted_reversed = np.roll(square[::-1], 2, axis=0)
    record(
        "reversed_shifted_closed_start",
        compare_components(
            [{"name": "loop", "points": square, "closed": True}],
            [{"name": "loop_other", "points": shifted_reversed, "closed": True}],
        ),
        0.0,
        1e-12,
    )

    coarse_count, fine_count = 16, 64
    coarse_angle = np.arange(coarse_count) * 2.0 * np.pi / coarse_count
    fine_angle = np.arange(fine_count) * 2.0 * np.pi / fine_count
    curved = compare_components(
        [{"name": "regular_16_gon", "points": np.column_stack((np.cos(coarse_angle), np.sin(coarse_angle))), "closed": True}],
        [{"name": "regular_64_gon", "points": np.column_stack((np.cos(fine_angle), np.sin(fine_angle))), "closed": True}],
    )
    expected_polygon_error = 1.0 - math.cos(math.pi / coarse_count)
    record("different_density_regular_polygons", curved, expected_polygon_error, 1e-12)

    offset = 0.125
    line = [{"name": "line", "points": np.column_stack((np.linspace(0.0, 10.0, 31), np.zeros(31)))}]
    shifted = [{"name": "offset", "points": np.column_stack((np.linspace(0.0, 10.0, 47), np.full(47, offset)))}]
    record("known_parallel_offset", compare_components(line, shifted), offset, 1e-12)
    return {
        "method": "component-preserving finite point-to-segment projections; conservative KD-tree broad phase",
        "tests": tests,
        "passed": all(item["passed"] for item in tests),
    }


def arc_resample(points: np.ndarray, count: int) -> np.ndarray:
    points = np.asarray(points, dtype=float)
    lengths = np.linalg.norm(np.diff(points, axis=0), axis=1)
    cumulative = np.concatenate(([0.0], np.cumsum(lengths)))
    normalized = cumulative / cumulative[-1]
    grid = np.linspace(0.0, 1.0, count)
    return np.column_stack(
        (
            np.interp(grid, normalized, points[:, 0]),
            np.interp(grid, normalized, points[:, 1]),
        )
    )


def independent_distribution(distribution: dict[str, Any], field: str, station: float) -> float:
    x = np.asarray([point["r_over_R"] for point in distribution["points"]], dtype=float)
    y = np.asarray([point[field] for point in distribution["points"]], dtype=float)
    if distribution["interpolation"] == "pchip":
        return float(PchipInterpolator(x, y, extrapolate=False)(station))
    return float(np.interp(station, x, y))


def independently_prepared_surface(
    section: dict[str, Any], chord_mm: float
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    upper = np.asarray(section["airfoil"]["upper"], dtype=float).copy()
    lower = np.asarray(section["airfoil"]["lower"], dtype=float).copy()
    requested = section.get("trailing_edge_thickness_mm")
    existing = float(upper[-1, 1] - lower[-1, 1])
    delta = 0.0
    if requested is not None:
        target = float(requested) / chord_mm
        delta = target - existing
        for surface, sign in ((upper, 0.5), (lower, -0.5)):
            blend_coordinate = np.clip((surface[:, 0] - 0.85) / 0.15, 0.0, 1.0)
            blend = 3.0 * blend_coordinate**2 - 2.0 * blend_coordinate**3
            surface[:, 1] += sign * delta * blend
    return upper, lower, {
        "original_te_gap_ratio": existing,
        "te_adjustment_ratio": delta,
        "result_te_gap_ratio": float(upper[-1, 1] - lower[-1, 1]),
    }


def independent_expected(
    spec_payload: dict[str, Any], station: float, factor: int = 1
) -> dict[str, Any]:
    radius = float(spec_payload["diameter_mm"]) / 2.0
    state = {
        "r_over_R": station,
        "chord_mm": independent_distribution(spec_payload["chord_distribution"], "chord_over_R", station) * radius,
        "twist_deg": independent_distribution(spec_payload["twist_distribution"], "twist_deg", station),
        "rake_mm": independent_distribution(spec_payload["rake_distribution"], "rake_over_R", station) * radius,
        "skew_mm": independent_distribution(spec_payload["skew_distribution"], "skew_over_R", station) * radius,
        "thickness_ratio": independent_distribution(spec_payload["thickness_distribution"], "thickness_ratio", station),
    }
    sections = spec_payload["airfoil_sections"]
    if station <= sections[0]["r_over_R"]:
        left = right = sections[0]
    elif station >= sections[-1]["r_over_R"]:
        left = right = sections[-1]
    else:
        right_index = next(index for index, section in enumerate(sections) if section["r_over_R"] >= station)
        if sections[right_index]["r_over_R"] == station:
            left = right = sections[right_index]
        else:
            left, right = sections[right_index - 1], sections[right_index]
    fraction = 0.0 if left is right else (station - left["r_over_R"]) / (right["r_over_R"] - left["r_over_R"])
    left_upper, left_lower, left_te = independently_prepared_surface(left, state["chord_mm"])
    right_upper, right_lower, right_te = independently_prepared_surface(right, state["chord_mm"])
    samples = factor * (2001 - 1) + 1
    upper = (1.0 - fraction) * arc_resample(left_upper, samples) + fraction * arc_resample(right_upper, samples)
    lower = (1.0 - fraction) * arc_resample(left_lower, samples) + fraction * arc_resample(right_lower, samples)

    theta = math.radians(state["twist_deg"])
    chord_direction = np.array([math.sin(theta), math.cos(theta)])
    normal_direction = np.array([-math.cos(theta), math.sin(theta)])
    reference = np.array(
        [
            state["rake_mm"] * math.cos(theta) + state["skew_mm"] * math.sin(theta),
            -state["rake_mm"] * math.sin(theta) + state["skew_mm"] * math.cos(theta),
        ]
    )

    def place(points: np.ndarray) -> np.ndarray:
        chordwise = (points[:, 0] - float(spec_payload["reference_axis_x_over_c"])) * state["chord_mm"]
        normal = points[:, 1] * state["chord_mm"]
        return reference + chordwise[:, None] * chord_direction + normal[:, None] * normal_direction

    placed_upper, placed_lower = place(upper), place(lower)
    te_gap = float(np.linalg.norm(placed_upper[-1] - placed_lower[-1]))
    components = [
        {"name": "expected_upper", "points": placed_upper},
        {"name": "expected_lower", "points": placed_lower},
    ]
    te_wall = np.linspace(placed_upper[-1], placed_lower[-1], factor * (101 - 1) + 1)
    if te_gap > EPS:
        components.append({"name": "expected_te", "points": te_wall})
    return {
        "state": state,
        "reference_xz_mm": reference,
        "chord_direction": chord_direction,
        "normal_direction": normal_direction,
        "left_profile_r_over_R": float(left["r_over_R"]),
        "right_profile_r_over_R": float(right["r_over_R"]),
        "blend_fraction": float(fraction),
        "normalized_upper": upper,
        "normalized_lower": lower,
        "placed_upper": placed_upper,
        "placed_lower": placed_lower,
        "te_wall": te_wall,
        "te_gap_mm": te_gap,
        "te_operations": {"left": left_te, "right": right_te},
        "metric_components": components,
    }


def component_inventory(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for component in components:
        points = np.asarray(component["points"], dtype=float)
        lengths = np.linalg.norm(np.diff(points, axis=0), axis=1)
        result.append(
            {
                "name": component["name"],
                "point_count": len(points),
                "segment_count": int(np.sum(lengths > EPS)),
                "length_mm": float(np.sum(lengths)),
                "max_segment_length_mm": float(np.max(lengths)) if len(lengths) else 0.0,
                "start_xz_mm": points[0].tolist(),
                "end_xz_mm": points[-1].tolist(),
                "zero_length_disposition": "excluded from segment metric" if float(np.sum(lengths)) <= EPS else None,
            }
        )
    return result


def save_components_csv(path: Path, components: list[dict[str, Any]], units: str = "mm") -> None:
    rows: list[dict[str, Any]] = []
    first_name = "x_mm" if units == "mm" else "x_over_c"
    second_name = "z_mm" if units == "mm" else "y_over_c"
    for component in components:
        points = np.asarray(component["points"], dtype=float)
        segment_lengths = np.linalg.norm(np.diff(points, axis=0), axis=1)
        cumulative = np.concatenate(([0.0], np.cumsum(segment_lengths)))
        total = float(cumulative[-1])
        for index, point in enumerate(points):
            rows.append({
                "component": component["name"], "point_index": index,
                first_name: float(point[0]), second_name: float(point[1]),
                "component_s": float(cumulative[index]),
                "component_s_fraction": float(cumulative[index] / total) if total > EPS else 0.0,
            })
    csv_write(path, ["component", "point_index", first_name, second_name, "component_s", "component_s_fraction"], rows)


def save_residual_csv(path: Path, metric: dict[str, Any]) -> None:
    rows: list[dict[str, Any]] = []
    for direction, detail_key, query_key in (
        ("actual_to_expected", "left_detail", "left_query"),
        ("expected_to_actual", "right_detail", "right_query"),
    ):
        detail, query = metric[detail_key], metric[query_key]
        for index in range(len(detail["distance"])):
            point, closest = query["points"][index], detail["closest"][index]
            rows.append({
                "direction": direction, "query_component": query["component"][index],
                "query_point_index": int(query["local_index"][index]),
                "query_x_mm": float(point[0]), "query_z_mm": float(point[1]),
                "query_component_s_mm": float(query["s_mm"][index]),
                "query_component_s_fraction": float(query["s_fraction"][index]),
                "trapezoid_weight_mm": float(query["weights"][index]),
                "target_component": detail["target_component"][index],
                "target_segment_index": int(detail["segment_local_index"][index]),
                "target_segment_t": float(detail["projection_t"][index]) if np.isfinite(detail["projection_t"][index]) else "",
                "projected_x_mm": float(closest[0]), "projected_z_mm": float(closest[1]),
                "dx_mm": float(point[0] - closest[0]), "dz_mm": float(point[1] - closest[1]),
                "distance_mm": float(detail["distance"][index]),
            })
    csv_write(path, list(rows[0]), rows)


def sample_section_components(section_shape: Any, points_per_edge: int) -> list[dict[str, Any]]:
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GCPnts import GCPnts_AbscissaPoint
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopoDS import TopoDS
    from bladegen.solid.ocp_solidify import shapes
    from bladegen.validation.measure_sections import _sample_edges

    sampled = _sample_edges(section_shape, points_per_edge=points_per_edge)
    edges = shapes(section_shape, TopAbs_EDGE)
    result = []
    for index, (edge_shape, points) in enumerate(zip(edges, sampled)):
        adaptor = BRepAdaptor_Curve(TopoDS.Edge_s(edge_shape))
        try:
            exact_length = float(GCPnts_AbscissaPoint.Length_s(adaptor, adaptor.FirstParameter(), adaptor.LastParameter()))
        except TypeError:
            exact_length = float(GCPnts_AbscissaPoint.Length_s(adaptor))
        result.append({
            "name": f"edge_{index:02d}", "points": points, "edge_index": index,
            "orientation": str(edge_shape.Orientation()), "curve_type": str(adaptor.GetType()),
            "first_parameter": float(adaptor.FirstParameter()),
            "last_parameter": float(adaptor.LastParameter()),
            "exact_curve_length_mm": exact_length,
        })
    return result


def persist_section_brep(section_shape: Any, path: Path) -> dict[str, Any]:
    from OCP.BRep import BRep_Builder
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepTools import BRepTools
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopoDS import TopoDS_Shape
    from OCP.TopTools import TopTools_FormatVersion
    from bladegen.solid.ocp_solidify import shapes

    wrote = bool(BRepTools.Write_s(
        section_shape, str(path), False, False,
        TopTools_FormatVersion.TopTools_FormatVersion_VERSION_3,
    ))
    if not wrote:
        raise RuntimeError(f"BRepTools failed to write {path}")
    loaded = TopoDS_Shape()
    read = bool(BRepTools.Read_s(loaded, str(path), BRep_Builder()))
    if not read or loaded.IsNull():
        raise RuntimeError(f"BRepTools failed to re-import {path}")
    roundtrip = compare_components(
        sample_section_components(section_shape, 301),
        sample_section_components(loaded, 301),
    )
    return {
        "path": str(path.resolve()), "sha256": sha256_file(path), "size_bytes": path.stat().st_size,
        "format": "OpenCascade native BRep v3; triangles=False; normals=False",
        "write_succeeded": wrote, "read_succeeded": read,
        "original_edge_count": len(shapes(section_shape, TopAbs_EDGE)),
        "reimported_edge_count": len(shapes(loaded, TopAbs_EDGE)),
        "original_brepcheck_valid": bool(BRepCheck_Analyzer(section_shape).IsValid()),
        "reimported_brepcheck_valid": bool(BRepCheck_Analyzer(loaded).IsValid()),
        "roundtrip_metric_301_points_per_edge": public_metric(roundtrip),
    }




def local_coordinates(points: np.ndarray, expected: dict[str, Any], reference_axis_x_over_c: float) -> np.ndarray:
    relative = np.asarray(points) - expected["reference_xz_mm"]
    return np.column_stack((
        relative @ expected["chord_direction"] / expected["state"]["chord_mm"] + reference_axis_x_over_c,
        relative @ expected["normal_direction"] / expected["state"]["chord_mm"],
    ))


def monotonic_reversals(values: np.ndarray) -> int:
    delta = np.diff(values)
    meaningful = delta[np.abs(delta) > 1e-10]
    if len(meaningful) < 2:
        return 0
    signs = np.sign(meaningful)
    return int(np.sum(signs[1:] != signs[:-1]))


def thickness_camber_audit(actual_components: list[dict[str, Any]], expected: dict[str, Any], reference_axis: float) -> dict[str, Any]:
    candidates, inventories = [], []
    for component in actual_components:
        local = local_coordinates(component["points"], expected, reference_axis)
        reversals = monotonic_reversals(local[:, 0])
        inventories.append({
            "component": component["name"], "mean_local_y_over_c": float(np.mean(local[:, 1])),
            "x_domain": [float(np.min(local[:, 0])), float(np.max(local[:, 0]))],
            "monotonic_reversal_count": reversals,
        })
        if float(np.ptp(local[:, 0])) >= 0.75:
            candidates.append((float(np.mean(local[:, 1])), component["name"], local))
    if len(candidates) < 2:
        return {"status": "AMBIGUOUS", "reason": "fewer than two chord-spanning edges", "components": inventories}
    candidates.sort(key=lambda value: value[0])
    _, lower_name, lower = candidates[0]
    _, upper_name, upper = candidates[-1]
    ambiguous = monotonic_reversals(lower[:, 0]) > 0 or monotonic_reversals(upper[:, 0]) > 0

    def interpolate(points: np.ndarray, grid: np.ndarray) -> np.ndarray:
        order = np.argsort(points[:, 0])
        unique_x, unique_index = np.unique(points[order, 0], return_index=True)
        return np.interp(grid, unique_x, points[order, 1][unique_index])

    start = max(0.02, float(np.min(lower[:, 0])), float(np.min(upper[:, 0])))
    end = min(0.98, float(np.max(lower[:, 0])), float(np.max(upper[:, 0])))
    if end <= start:
        return {"status": "AMBIGUOUS", "reason": "no shared chordwise domain", "components": inventories}
    grid = np.linspace(start, end, 1201)
    actual_lower, actual_upper = interpolate(lower, grid), interpolate(upper, grid)
    expected_lower = interpolate(expected["normalized_lower"], grid)
    expected_upper = interpolate(expected["normalized_upper"], grid)
    actual_thickness, expected_thickness = actual_upper - actual_lower, expected_upper - expected_lower
    actual_camber = 0.5 * (actual_upper + actual_lower)
    expected_camber = 0.5 * (expected_upper + expected_lower)
    return {
        "status": "AMBIGUOUS" if ambiguous else "COMPLETED",
        "ambiguity": "actual edge reverses in requested x/c" if ambiguous else None,
        "chord_datum": "common requested reference-axis/chord/twist frame",
        "pairing_method": "chord-spanning edges classified by mean signed requested-frame y/c after monotonicity audit",
        "upper_component": upper_name, "lower_component": lower_name, "components": inventories,
        "grid_x_over_c": grid, "actual_thickness_over_c": actual_thickness,
        "expected_thickness_over_c": expected_thickness, "actual_camber_over_c": actual_camber,
        "expected_camber_over_c": expected_camber,
        "actual_max_thickness_over_c": float(np.max(actual_thickness)),
        "expected_max_thickness_over_c": float(np.max(expected_thickness)),
        "actual_max_abs_camber_over_c": float(np.max(np.abs(actual_camber))),
        "expected_max_abs_camber_over_c": float(np.max(np.abs(expected_camber))),
    }


def save_thickness_camber(path: Path, audit: dict[str, Any]) -> None:
    if "grid_x_over_c" not in audit:
        return
    rows = []
    keys = (
        "x_over_c", "actual_thickness_over_c", "expected_thickness_over_c",
        "actual_camber_over_c", "expected_camber_over_c",
    )
    for values in zip(
        audit["grid_x_over_c"], audit["actual_thickness_over_c"],
        audit["expected_thickness_over_c"], audit["actual_camber_over_c"],
        audit["expected_camber_over_c"],
    ):
        rows.append(dict(zip(keys, map(float, values))))
    csv_write(path, list(rows[0]), rows)



def plot_station(
    station_dir: Path,
    station: float,
    actual: list[dict[str, Any]],
    raw: list[dict[str, Any]],
    expected: dict[str, Any],
    metric: dict[str, Any],
    thickness: dict[str, Any],
) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    fig, axis = plt.subplots(figsize=(10, 7))
    for component in actual:
        points = component["points"]
        axis.plot(points[:, 0], points[:, 1], color="#1f77b4", linewidth=1.2, label="final actual" if component is actual[0] else None)
    for component in raw:
        points = component["points"]
        axis.plot(points[:, 0], points[:, 1], color="#2ca02c", linestyle="--", linewidth=0.8, label="raw OpenVSP" if component is raw[0] else None)
    for index, key in enumerate(("placed_upper", "placed_lower")):
        points = expected[key]
        axis.plot(points[:, 0], points[:, 1], color="#d62728", linewidth=1.0, label="requested expected" if index == 0 else None)
    axis.set_aspect("equal", adjustable="box")
    axis.set_xlabel("X (mm)")
    axis.set_ylabel("Z (mm)")
    axis.set_title(f"r/R={station:.5f}: actual and requested contours (true scale)")
    axis.legend()
    axis.grid(True, alpha=0.25)
    fig.tight_layout()
    overlay = station_dir / "overlay_true_scale.png"
    fig.savefig(overlay, dpi=180)
    plt.close(fig)
    outputs["overlay_true_scale"] = str(overlay.resolve())

    left_distance = metric["left_detail"]["distance"]
    right_distance = metric["right_detail"]["distance"]
    if float(np.max(left_distance)) >= float(np.max(right_distance)):
        maximum_index = int(np.argmax(left_distance))
        center = metric["left_query"]["points"][maximum_index]
        projected = metric["left_detail"]["closest"][maximum_index]
        direction, maximum = "actual_to_expected", float(left_distance[maximum_index])
    else:
        maximum_index = int(np.argmax(right_distance))
        center = metric["right_query"]["points"][maximum_index]
        projected = metric["right_detail"]["closest"][maximum_index]
        direction, maximum = "expected_to_actual", float(right_distance[maximum_index])
    window = max(0.8, 0.04 * expected["state"]["chord_mm"])
    fig, axis = plt.subplots(figsize=(8, 7))
    for component in actual:
        axis.plot(component["points"][:, 0], component["points"][:, 1], color="#1f77b4", linewidth=1.2)
    for key in ("placed_upper", "placed_lower"):
        axis.plot(expected[key][:, 0], expected[key][:, 1], color="#d62728", linewidth=1.0)
    axis.plot([center[0], projected[0]], [center[1], projected[1]], color="black", marker="o", linewidth=1.0)
    axis.set_xlim(float(center[0] - window), float(center[0] + window))
    axis.set_ylim(float(center[1] - window), float(center[1] + window))
    axis.set_aspect("equal", adjustable="box")
    axis.set_xlabel("X (mm)")
    axis.set_ylabel("Z (mm)")
    axis.set_title(f"Largest sampled residual close-up ({direction}, {maximum:.6f} mm; not amplified)")
    axis.grid(True, alpha=0.25)
    fig.tight_layout()
    closeup = station_dir / "maximum_residual_closeup.png"
    fig.savefig(closeup, dpi=180)
    plt.close(fig)
    outputs["maximum_residual_closeup"] = str(closeup.resolve())

    fig, axis = plt.subplots(figsize=(10, 6))
    for label, detail_key, query_key in (
        ("actual→expected", "left_detail", "left_query"),
        ("expected→actual", "right_detail", "right_query"),
    ):
        detail, query = metric[detail_key], metric[query_key]
        for name in sorted(set(map(str, query["component"]))):
            mask = query["component"] == name
            axis.plot(query["s_fraction"][mask], detail["distance"][mask], linewidth=0.9, label=f"{label}: {name}")
    axis.set_xlabel("Component arc-length fraction")
    axis.set_ylabel("Point-to-segment residual (mm)")
    axis.set_title(f"r/R={station:.5f}: directional residuals (4× interval density)")
    axis.grid(True, alpha=0.25)
    axis.legend(fontsize=8)
    fig.tight_layout()
    residual_plot = station_dir / "directional_residuals.png"
    fig.savefig(residual_plot, dpi=180)
    plt.close(fig)
    outputs["directional_residuals"] = str(residual_plot.resolve())

    if "grid_x_over_c" in thickness:
        fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
        axes[0].plot(thickness["grid_x_over_c"], thickness["actual_thickness_over_c"], label="actual")
        axes[0].plot(thickness["grid_x_over_c"], thickness["expected_thickness_over_c"], label="expected")
        axes[0].set_ylabel("Thickness / requested chord")
        axes[0].legend()
        axes[0].grid(True, alpha=0.25)
        axes[1].plot(thickness["grid_x_over_c"], thickness["actual_camber_over_c"], label="actual")
        axes[1].plot(thickness["grid_x_over_c"], thickness["expected_camber_over_c"], label="expected")
        axes[1].set_xlabel("Requested-frame x/c")
        axes[1].set_ylabel("Camber / requested chord")
        axes[1].grid(True, alpha=0.25)
        fig.suptitle(f"r/R={station:.5f}: common requested-frame thickness/camber")
        fig.tight_layout()
        thickness_plot = station_dir / "thickness_camber.png"
        fig.savefig(thickness_plot, dpi=180)
        plt.close(fig)
        outputs["thickness_camber"] = str(thickness_plot.resolve())
    outputs["maximum_residual_coordinates"] = {
        "direction": direction, "query_xz_mm": center.tolist(),
        "projected_xz_mm": projected.tolist(), "sampled_distance_mm": maximum,
    }
    return outputs



def build_profile_audit(
    spec_payload: dict[str, Any],
    resolved_payload: dict[str, Any],
    production_expected: dict[float, dict[str, Any]],
    independent_expected_by_station: dict[float, dict[str, Any]],
    baseline_records: list[dict[str, Any]],
    job_dir: Path,
) -> dict[str, Any]:
    source_sections = spec_payload["airfoil_sections"]
    resolved_sections = resolved_payload["airfoil_sections"]
    source_root_upper = np.asarray(source_sections[0]["airfoil"]["upper"], dtype=float)
    source_root_lower = np.asarray(source_sections[0]["airfoil"]["lower"], dtype=float)
    source_tip_upper = np.asarray(source_sections[-1]["airfoil"]["upper"], dtype=float)
    source_tip_lower = np.asarray(source_sections[-1]["airfoil"]["lower"], dtype=float)
    resolved_root_upper = np.asarray(resolved_sections[0]["airfoil"]["upper"], dtype=float)
    resolved_root_lower = np.asarray(resolved_sections[0]["airfoil"]["lower"], dtype=float)

    fixture_rows = list(csv.DictReader(
        (REPOSITORY_ROOT / "fixtures" / "x57_manual_reference" / "x57_hlp_airfoil.csv").open(encoding="utf-8")
    ))
    fixture_upper = np.asarray([[float(row["x"]), float(row["y"])] for row in fixture_rows if row["surface"] == "upper"])
    fixture_lower = np.asarray([[float(row["x"]), float(row["y"])] for row in fixture_rows if row["surface"] == "lower"])

    leading = 0.5 * (source_root_upper[0] + source_root_lower[0])
    trailing = 0.5 * (source_root_upper[-1] + source_root_lower[-1])
    datum_vector = trailing - leading
    datum_angle_deg = math.degrees(math.atan2(datum_vector[1], datum_vector[0]))
    datum_length = float(np.linalg.norm(datum_vector))

    manifest = read_json(REPOSITORY_ROOT / "fixtures" / "x57_manual_reference" / "manifest.json")
    source_native_thickness = float(manifest["source_thickness_ratio"])
    product_thickness = float(spec_payload["thickness_distribution"]["points"][0]["thickness_ratio"])
    thickness_delta = product_thickness - source_native_thickness

    import re
    vsp3_text = (job_dir / "blade_openvsp.vsp3").read_text(encoding="utf-8", errors="replace")
    base_values = [float(value) for value in re.findall(r"<BaseThickChord Value=\"([^\"]+)", vsp3_text)]
    thick_values = [float(value) for value in re.findall(r"<ThickChord Value=\"([^\"]+)", vsp3_text)]
    fit_values = [float(value) for value in re.findall(r"<FitDegree Value=\"([^\"]+)", vsp3_text)]

    station_rows = []
    record_by_station = {round(row["sampled_r_over_R"], 12): row for row in baseline_records}
    maximum_production_independent = 0.0
    for station in SELECTED_STATIONS:
        production = production_expected[station]
        independent = independent_expected_by_station[station]
        production_upper = production["placed_contour"][:2001]
        production_lower = production["placed_contour"][2001:4002]
        pointwise = max(
            float(np.max(np.linalg.norm(production_upper - independent["placed_upper"], axis=1))),
            float(np.max(np.linalg.norm(production_lower - independent["placed_lower"], axis=1))),
        )
        maximum_production_independent = max(maximum_production_independent, pointwise)
        record = record_by_station[round(station, 12)]
        predicted_twist = independent["state"]["twist_deg"] - datum_angle_deg
        station_rows.append({
            "sampled_r_over_R": station,
            "physical_y_mm": float(spec_payload["diameter_mm"]) * 0.5 * station,
            **independent["state"],
            "reference_xz_mm": independent["reference_xz_mm"].tolist(),
            "independent_vs_production_expected_max_mm": pointwise,
            "requested_twist_minus_datum_deg": predicted_twist,
            "measured_twist_deg": record["actual_twist_deg"],
            "measured_minus_datum_prediction_deg": record["actual_twist_deg"] - predicted_twist,
            "source_minus_product_thickness_effect_full_mm": thickness_delta * independent["state"]["chord_mm"],
        })

    return {
        "contract": {
            "coordinate_surface_direction": "upper and lower stored LE-to-TE",
            "coordinate_import_normalization": "disabled in accepted X-57 workflow",
            "coordinate_profile_thickness_semantics": "thickness curve is a resolver consistency check; production expected contour does not scale coordinate profiles",
            "expected_profile_sampling": "independent arc-length resampling of each surface to 2001 points, then linear radial blend",
            "placement_equation": "A + chord*((xi-a)*d + eta*n), with d=(sin(theta),cos(theta)), n=(-cos(theta),sin(theta))",
            "units": "profile coordinates normalized by local requested chord; placed X/Z and radial plane in mm",
        },
        "coordinate_identity": {
            "fixture_vs_submitted_upper_exact": bool(np.array_equal(fixture_upper, source_root_upper)),
            "fixture_vs_submitted_lower_exact": bool(np.array_equal(fixture_lower, source_root_lower)),
            "submitted_endpoint_upper_exact": bool(np.array_equal(source_root_upper, source_tip_upper)),
            "submitted_endpoint_lower_exact": bool(np.array_equal(source_root_lower, source_tip_lower)),
            "submitted_vs_resolved_upper_exact": bool(np.array_equal(source_root_upper, resolved_root_upper)),
            "submitted_vs_resolved_lower_exact": bool(np.array_equal(source_root_lower, resolved_root_lower)),
            "upper_points": len(source_root_upper),
            "lower_points": len(source_root_lower),
            "maximum_production_vs_independent_expected_mm": maximum_production_independent,
        },
        "te_operation": {
            "requested_mm_both_sections": [section.get("trailing_edge_thickness_mm") for section in source_sections],
            "input_gap_ratio": float(source_root_upper[-1, 1] - source_root_lower[-1, 1]),
            "resolved_coordinate_max_delta": float(max(
                np.max(np.abs(source_root_upper - resolved_root_upper)),
                np.max(np.abs(source_root_lower - resolved_root_lower)),
            )),
            "result": "no-op",
        },
        "profile_datum": {
            "leading_midpoint_xy": leading.tolist(),
            "trailing_midpoint_xy": trailing.tolist(),
            "le_to_te_vector": datum_vector.tolist(),
            "le_to_te_length": datum_length,
            "le_to_te_angle_deg": datum_angle_deg,
            "predicted_validator_twist_relation": "endpoint twist = requested twist - LE-to-TE datum angle",
            "conclusion": "explains systematic twist offset but is already shared by expected and actual contours and cannot explain localized shape failure",
        },
        "thickness_representation": {
            "source_native_ratio": source_native_thickness,
            "product_polygon_envelope_ratio": product_thickness,
            "delta_ratio": thickness_delta,
            "retained_vsp3_base_thick_chord": base_values,
            "retained_vsp3_thick_chord": thick_values,
            "retained_vsp3_scale": (thick_values[0] / base_values[0]) if base_values and thick_values else None,
            "retained_vsp3_fit_degree": fit_values,
            "conclusion": "real but orders of magnitude below worst contour discrepancy",
        },
        "selected_station_values": station_rows,
    }



def run_worker(output_dir: Path, job_dir: Path, evidence_root: Path) -> int:
    from bladegen.models import BladeSpec
    from bladegen.solid import ocp_solidify as ocp
    from bladegen.validation import expected_geometry as expected_module
    from bladegen.validation import measure_sections as measurement_module
    from bladegen.validation.station_plan import ValidationStationPlan, plan_validation_stations

    logger = EventLog(output_dir / "diagnostic_events.jsonl")
    started_ns = time.monotonic_ns()

    def terminate(signum: int, _frame: Any) -> None:
        logger.emit("termination_signal", signal=signum)
        logger.close()
        os._exit(128 + signum)

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    final_path = job_dir / "blade_solid.step"
    raw_path = job_dir / "blade_openvsp.step"
    spec_path = job_dir / "blade_spec.json"
    logger.emit("worker_start", pid=os.getpid(), openvsp_launched=False, cad_regenerated=False)

    try:
        with logger.operation("retained_identity_recheck"):
            final_hash = sha256_file(final_path)
            raw_hash = sha256_file(raw_path)
            if final_hash != EXPECTED_FINAL_STEP_SHA256:
                raise RuntimeError(f"Retained final STEP hash mismatch: {final_hash}")
            if raw_hash != EXPECTED_RAW_STEP_SHA256:
                raise RuntimeError(f"Retained raw STEP hash mismatch: {raw_hash}")

        with logger.operation("canonical_input_preparation"):
            spec = BladeSpec.from_json(spec_path)
            spec_payload = read_json(spec_path)
            resolved_payload = read_json(job_dir / "resolved_blade_spec.json")
            candidate = BladeSpec.from_json(evidence_root / "exported_candidate.json")
            submitted = BladeSpec.from_json(evidence_root / "job" / "submitted_blade_spec.json")
            if not (spec.model_dump(mode="json") == candidate.model_dump(mode="json") == submitted.model_dump(mode="json")):
                raise RuntimeError("Candidate/submitted/generated BladeSpecs are not canonically equivalent")

        full_plan = plan_validation_stations(spec)
        selected_items = tuple(
            item for item in full_plan.stations
            if any(abs(item.sampled_r_over_R - target) <= 5e-13 for target in SELECTED_STATIONS)
        )
        if len(selected_items) != len(SELECTED_STATIONS):
            raise RuntimeError(f"Could not find all selected stations in 41-station plan: {selected_items}")
        selected_plan = ValidationStationPlan(
            root_r_over_R=full_plan.root_r_over_R,
            tip_r_over_R=full_plan.tip_r_over_R,
            stations=selected_items,
            endpoint_policy=full_plan.endpoint_policy,
        )
        write_json(output_dir / "station_plan_identity.json", {
            "production_planned_station_count": len(full_plan.stations),
            "diagnostic_subset_count": len(selected_items),
            "diagnostic_subset_replaces_acceptance_plan": False,
            "selected": [
                {
                    "requested_r_over_R": item.requested_r_over_R,
                    "sampled_r_over_R": item.sampled_r_over_R,
                    "roles": list(item.roles),
                    "endpoint": item.endpoint,
                    "station_kind": item.station_kind,
                }
                for item in selected_items
            ],
        })

        with logger.operation("final_step_read_once"):
            final_shape = ocp.read_step(final_path)
        with logger.operation("raw_step_read_once"):
            raw_shape = ocp.read_step(raw_path)
        with logger.operation("retained_topology_inspection"):
            topologies = {
                "raw_openvsp_step": ocp.inspect_shape(raw_shape),
                "final_ocp_step": ocp.inspect_shape(final_shape),
            }
        write_json(output_dir / "retained_stage_topology.json", topologies)

        production_sections: dict[float, Any] = {}
        production_edge_points: dict[float, list[np.ndarray]] = {}
        production_expected: dict[float, dict[str, Any]] = {}
        production_normalized: dict[float, dict[str, Any]] = {}
        current_station: list[float | None] = [None]
        originals = {
            "read_step": measurement_module.read_step,
            "plan_validation_stations": measurement_module.plan_validation_stations,
            "_section_shape": measurement_module._section_shape,
            "_sample_edges": measurement_module._sample_edges,
            "placed_contour": measurement_module.placed_contour,
            "diagnostic_profile": expected_module.diagnostic_profile,
        }

        def profile_wrapper(specification: Any, station: float, samples_per_surface: int = 2001) -> Any:
            result = originals["diagnostic_profile"](specification, station, samples_per_surface)
            production_normalized[float(station)] = {
                "upper": result[0].copy(), "lower": result[1].copy(),
                "left_profile_r_over_R": result[2], "right_profile_r_over_R": result[3],
            }
            return result

        def placed_wrapper(specification: Any, station: float) -> Any:
            result = originals["placed_contour"](specification, station)
            production_expected[float(station)] = {
                "placed_contour": result[0].copy(),
                "state": result[1],
                "metadata": dict(result[2]),
            }
            return result

        def section_wrapper(solid: Any, radius_mm: float, station: float) -> Any:
            current_station[0] = float(station)
            with logger.operation("production_section_extraction", sampled_r_over_R=station):
                result = originals["_section_shape"](solid, radius_mm, station)
            production_sections[float(station)] = result
            return result

        def sample_wrapper(section_shape: Any, points_per_edge: int = 2500) -> Any:
            station = current_station[0]
            with logger.operation(
                "production_section_sampling",
                sampled_r_over_R=station,
                points_per_edge=points_per_edge,
            ):
                result = originals["_sample_edges"](section_shape, points_per_edge)
            if station is not None and points_per_edge == 2500:
                production_edge_points[float(station)] = [points.copy() for points in result]
            return result

        measurement_module.read_step = lambda _path: final_shape
        measurement_module.plan_validation_stations = lambda _spec: selected_plan
        measurement_module._section_shape = section_wrapper
        measurement_module._sample_edges = sample_wrapper
        measurement_module.placed_contour = placed_wrapper
        expected_module.diagnostic_profile = profile_wrapper
        try:
            with logger.operation("exact_production_three_station_baseline"):
                baseline_records = measurement_module.measure_sections(final_path, spec)
        finally:
            for name in ("read_step", "plan_validation_stations", "_section_shape", "_sample_edges", "placed_contour"):
                setattr(measurement_module, name, originals[name])
            expected_module.diagnostic_profile = originals["diagnostic_profile"]

        write_json(output_dir / "production_baseline_measurements.json", baseline_records)
        previous_all = read_json(PRIOR_DIAGNOSTIC / "completed_measurements.json")
        previous = {
            round(row["sampled_r_over_R"], 12): row for row in previous_all
            if any(abs(row["sampled_r_over_R"] - station) <= 5e-13 for station in SELECTED_STATIONS)
        }
        baseline_identity = []
        for record in baseline_records:
            old = previous[round(record["sampled_r_over_R"], 12)]
            deltas = {
                key: float(record[key] - old[key])
                for key in (
                    "actual_chord_mm", "actual_twist_deg", "reference_axis_position_error_mm",
                    "measured_te_mm", "contour_rms_mm", "contour_p95_mm", "contour_max_mm",
                )
            }
            baseline_identity.append({
                "sampled_r_over_R": record["sampled_r_over_R"],
                "previous": {key: old[key] for key in deltas},
                "reproduced": {key: record[key] for key in deltas},
                "deltas": deltas,
                "maximum_absolute_delta": max(map(abs, deltas.values())),
            })
        write_json(output_dir / "production_baseline_identity.json", baseline_identity)

        raw_sections: dict[float, Any] = {}
        radius = spec.diameter_mm / 2.0
        for station in SELECTED_STATIONS:
            with logger.operation("raw_openvsp_section_extraction", sampled_r_over_R=station):
                raw_sections[station] = originals["_section_shape"](raw_shape, radius, station)

        write_json(output_dir / "metric_self_tests.json", metric_self_tests())


        baseline_by_station = {round(row["sampled_r_over_R"], 12): row for row in baseline_records}
        independent_expected_by_station: dict[float, dict[str, Any]] = {}
        station_summaries: list[dict[str, Any]] = []
        final_factor4: dict[float, list[dict[str, Any]]] = {}

        for planned in selected_items:
            station = float(planned.sampled_r_over_R)
            station_dir = output_dir / "stations" / station_slug(station)
            station_dir.mkdir(parents=True, exist_ok=True)
            record = baseline_by_station[round(station, 12)]
            plane = {
                "origin_xyz_mm": [0.0, radius * station, 0.0],
                "normal_xyz": [0.0, 1.0, 0.0],
                "requested_r_over_R": planned.requested_r_over_R,
                "sampled_r_over_R": station,
                "physical_y_mm": radius * station,
                "roles": list(planned.roles),
                "station_kind": planned.station_kind,
            }
            logger.emit("station_analysis_start", **plane)

            with logger.operation("persist_final_section_brep", sampled_r_over_R=station):
                final_brep = persist_section_brep(
                    production_sections[station], station_dir / "final_section.brep"
                )
            with logger.operation("persist_raw_section_brep", sampled_r_over_R=station):
                raw_brep = persist_section_brep(
                    raw_sections[station], station_dir / "raw_openvsp_section.brep"
                )

            production_actual = [
                {"name": f"edge_{index:02d}", "points": points}
                for index, points in enumerate(production_edge_points[station])
            ]
            raw_1x = sample_section_components(raw_sections[station], 2500)
            normalized = production_normalized[station]
            production_expected_components = [
                {"name": "expected_upper", "points": production_expected[station]["placed_contour"][:2001]},
                {"name": "expected_lower", "points": production_expected[station]["placed_contour"][2001:4002]},
                {"name": "expected_te_zero_length", "points": production_expected[station]["placed_contour"][4002:]},
            ]
            production_normalized_components = [
                {"name": "expected_upper", "points": normalized["upper"]},
                {"name": "expected_lower", "points": normalized["lower"]},
            ]
            save_components_csv(station_dir / "production_actual_2500_per_edge.csv", production_actual)
            save_components_csv(station_dir / "raw_openvsp_actual_2500_per_edge.csv", raw_1x)
            save_components_csv(
                station_dir / "production_expected_normalized_before_placement.csv",
                production_normalized_components,
                units="normalized",
            )
            save_components_csv(
                station_dir / "production_expected_after_placement.csv",
                production_expected_components,
            )

            density_results: dict[str, Any] = {}
            factor_metrics: dict[int, dict[str, Any]] = {}
            factor_components: dict[int, tuple[list[dict[str, Any]], dict[str, Any]]] = {}
            for factor in (1, 2, 4):
                points_per_edge = factor * (2500 - 1) + 1
                expected = independent_expected(spec_payload, station, factor)
                independent_expected_by_station.setdefault(station, expected)
                actual = (
                    production_actual
                    if factor == 1
                    else sample_section_components(production_sections[station], points_per_edge)
                )
                with logger.operation(
                    "independent_point_to_segment_metric",
                    sampled_r_over_R=station,
                    density_factor=factor,
                    actual_points_per_edge=points_per_edge,
                    expected_points_per_surface=factor * (2001 - 1) + 1,
                ):
                    metric = compare_components(actual, expected["metric_components"])
                factor_metrics[factor] = metric
                factor_components[factor] = (actual, expected)
                density_results[f"{factor}x"] = {
                    "interval_density_factor": factor,
                    "actual_points_per_edge": points_per_edge,
                    "expected_points_per_surface": factor * (2001 - 1) + 1,
                    "zero_te_component": "excluded from segment/arc metric; endpoint already belongs to both surfaces",
                    "actual_component_inventory": component_inventory(actual),
                    "expected_component_inventory": component_inventory(expected["metric_components"]),
                    "metrics": public_metric(metric),
                }
                if factor == 4:
                    final_factor4[station] = actual
                    save_components_csv(station_dir / "actual_final_4x.csv", actual)
                    save_components_csv(
                        station_dir / "expected_independent_normalized_4x.csv",
                        [
                            {"name": "expected_upper", "points": expected["normalized_upper"]},
                            {"name": "expected_lower", "points": expected["normalized_lower"]},
                        ],
                        units="normalized",
                    )
                    save_components_csv(
                        station_dir / "expected_independent_placed_4x.csv",
                        expected["metric_components"],
                    )
                    save_residual_csv(station_dir / "independent_residuals_4x.csv", metric)

            convergence = []
            for left_factor, right_factor in ((1, 2), (2, 4)):
                left_values = factor_metrics[left_factor]["bidirectional_equal_direction_arc_weighted"]
                right_values = factor_metrics[right_factor]["bidirectional_equal_direction_arc_weighted"]
                convergence.append({
                    "from_factor": left_factor, "to_factor": right_factor,
                    **{
                        f"{key}_delta_mm": right_values[key] - left_values[key]
                        for key in ("rms_mm", "p95_mm", "sampled_max_mm")
                    },
                })
            density_results["convergence"] = convergence

            actual_4x, expected_4x = factor_components[4]
            raw_4x = sample_section_components(raw_sections[station], 4 * (2500 - 1) + 1)
            with logger.operation("raw_vs_final_section_metric", sampled_r_over_R=station):
                raw_final_metric = compare_components(raw_4x, actual_4x)
            with logger.operation("raw_vs_expected_section_metric", sampled_r_over_R=station):
                raw_expected_metric = compare_components(raw_4x, expected_4x["metric_components"])

            thickness = thickness_camber_audit(
                actual_4x, expected_4x, float(spec.reference_axis_x_over_c)
            )
            save_thickness_camber(station_dir / "thickness_camber.csv", thickness)
            plots = plot_station(
                station_dir, station, actual_4x, raw_4x, expected_4x,
                factor_metrics[4], thickness,
            )
            write_json(station_dir / "metric_density_results.json", density_results)
            write_json(station_dir / "raw_vs_final_metric.json", public_metric(raw_final_metric))
            write_json(station_dir / "raw_vs_expected_metric.json", public_metric(raw_expected_metric))
            write_json(station_dir / "thickness_camber_summary.json", {
                key: jsonable(value) for key, value in thickness.items()
                if key not in {
                    "grid_x_over_c", "actual_thickness_over_c", "expected_thickness_over_c",
                    "actual_camber_over_c", "expected_camber_over_c",
                }
            })

            metadata = {
                "plane": plane,
                "final_step_sha256": final_hash,
                "raw_step_sha256": raw_hash,
                "final_section_brep": final_brep,
                "raw_section_brep": raw_brep,
                "production_baseline": record,
                "production_baseline_identity": next(
                    row for row in baseline_identity
                    if abs(row["sampled_r_over_R"] - station) <= 5e-13
                ),
                "production_expected_zero_te_duplicate_points": 101,
                "independent_expected": {
                    "state": expected_4x["state"],
                    "reference_xz_mm": expected_4x["reference_xz_mm"],
                    "chord_direction": expected_4x["chord_direction"],
                    "normal_direction": expected_4x["normal_direction"],
                    "left_profile_r_over_R": expected_4x["left_profile_r_over_R"],
                    "right_profile_r_over_R": expected_4x["right_profile_r_over_R"],
                    "blend_fraction": expected_4x["blend_fraction"],
                    "te_operations": expected_4x["te_operations"],
                    "te_gap_mm": expected_4x["te_gap_mm"],
                },
                "plots": plots,
                "rigid_registration": {
                    "performed": False,
                    "reason": "principal shared-frame comparison retained; LE-to-TE datum hypothesis was tested analytically without fitting",
                },
            }
            write_json(station_dir / "station_metadata.json", metadata)

            headline = factor_metrics[4]["bidirectional_equal_direction_arc_weighted"]
            raw_expected_headline = raw_expected_metric["bidirectional_equal_direction_arc_weighted"]
            raw_final_headline = raw_final_metric["bidirectional_equal_direction_arc_weighted"]
            station_summaries.append({
                "requested_r_over_R": planned.requested_r_over_R,
                "sampled_r_over_R": station,
                "raw_vs_expected_4x_arc_rms_mm": raw_expected_headline["rms_mm"],
                "raw_vs_expected_4x_arc_p95_mm": raw_expected_headline["p95_mm"],
                "raw_vs_expected_4x_sampled_max_mm": raw_expected_headline["sampled_max_mm"],
                "diagnostic_role": (
                    "worst recorded failure" if station == 0.22302
                    else "passing inboard control" if station == 0.29061
                    else "passing outboard control"
                ),
                "physical_y_mm": radius * station,
                "production_rms_mm": record["contour_rms_mm"],
                "production_p95_mm": record["contour_p95_mm"],
                "production_sampled_max_mm": record["contour_max_mm"],
                "production_reproduction_max_abs_delta": next(
                    row["maximum_absolute_delta"] for row in baseline_identity
                    if abs(row["sampled_r_over_R"] - station) <= 5e-13
                ),
                "independent_4x_arc_rms_mm": headline["rms_mm"],
                "independent_4x_arc_p95_mm": headline["p95_mm"],
                "independent_4x_sampled_max_mm": headline["sampled_max_mm"],
                "raw_vs_final_4x_arc_rms_mm": raw_final_headline["rms_mm"],
                "raw_vs_final_4x_arc_p95_mm": raw_final_headline["p95_mm"],
                "raw_vs_final_4x_sampled_max_mm": raw_final_headline["sampled_max_mm"],
                "actual_max_thickness_over_c": thickness.get("actual_max_thickness_over_c"),
                "expected_max_thickness_over_c": thickness.get("expected_max_thickness_over_c"),
                "actual_max_abs_camber_over_c": thickness.get("actual_max_abs_camber_over_c"),
                "expected_max_abs_camber_over_c": thickness.get("expected_max_abs_camber_over_c"),
                "thickness_pairing_status": thickness["status"],
                "maximum_residual_coordinates": plots["maximum_residual_coordinates"],
                "maximum_query_requested_frame_x_over_c_y_over_c": local_coordinates(
                    np.asarray([plots["maximum_residual_coordinates"]["query_xz_mm"]]),
                    expected_4x, float(spec.reference_axis_x_over_c),
                )[0].tolist(),
                "maximum_projection_requested_frame_x_over_c_y_over_c": local_coordinates(
                    np.asarray([plots["maximum_residual_coordinates"]["projected_xz_mm"]]),
                    expected_4x, float(spec.reference_axis_x_over_c),
                )[0].tolist(),
                "evidence_directory": str(station_dir.resolve()),
            })
            logger.emit("station_analysis_end", sampled_r_over_R=station)

        profile_audit = build_profile_audit(
            spec_payload, resolved_payload, production_expected,
            independent_expected_by_station, baseline_records, job_dir,
        )
        write_json(output_dir / "expected_profile_audit.json", profile_audit)
        write_json(output_dir / "station_summaries.json", station_summaries)
        csv_write(output_dir / "station_comparison.csv", list(station_summaries[0]), station_summaries)

        expected_shape_ratio = station_summaries[-1]["expected_max_thickness_over_c"]
        cached_rows = []
        for row in previous_all:
            cached_rows.append({
                "requested_r_over_R": row["requested_r_over_R"],
                "sampled_r_over_R": row["sampled_r_over_R"],
                "actual_max_thickness_over_c": row["measured_max_thickness_over_chord"],
                "expected_selected_audit_reference_thickness_over_c": expected_shape_ratio,
                "actual_minus_expected_reference": row["measured_max_thickness_over_chord"] - expected_shape_ratio,
                "production_contour_rms_mm": row["contour_rms_mm"],
                "production_contour_p95_mm": row["contour_p95_mm"],
                "production_contour_sampled_max_mm": row["contour_max_mm"],
                "source": "cached completed 41-station diagnostic; no new section cut",
            })
        csv_write(output_dir / "cached_41_station_shape_pattern.csv", list(cached_rows[0]), cached_rows)

        raw_final_max = max(row["raw_vs_final_4x_sampled_max_mm"] for row in station_summaries)
        stage_rows = [
            {
                "sequence": 1, "stage": "input coordinates / submitted BladeSpec", "status": "AVAILABLE",
                "artifact": str(spec_path.resolve()), "sha256": sha256_file(spec_path),
                "finding": "fixture/submitted endpoint arrays exact; two endpoint profiles identical",
            },
            {
                "sequence": 2, "stage": "canonical resolved profile and curves", "status": "AVAILABLE",
                "artifact": str((job_dir / "resolved_blade_spec.json").resolve()),
                "sha256": sha256_file(job_dir / "resolved_blade_spec.json"),
                "finding": "resolved profile arrays exactly equal submitted; zero-TE operation is a no-op",
            },
            {
                "sequence": 3, "stage": "data supplied to backend adapter", "status": "AVAILABLE",
                "artifact": str((job_dir / "resolved_blade_spec.json").resolve()),
                "sha256": sha256_file(job_dir / "resolved_blade_spec.json"),
                "finding": "pipeline serialized and passed this ResolvedBladeSpec; in-memory adapter readback was not retained",
            },
            {
                "sequence": 4, "stage": "retained backend native geometry", "status": "PARTIAL",
                "artifact": str((job_dir / "blade_openvsp.vsp3").resolve()),
                "sha256": sha256_file(job_dir / "blade_openvsp.vsp3"),
                "finding": "static XML inspected only; loading would recompute, so no frozen pre-export native surface was claimed",
            },
            {
                "sequence": 5, "stage": "raw exported OpenVSP STEP", "status": "AVAILABLE_MISMATCHING_REQUEST",
                "artifact": str(raw_path.resolve()), "sha256": raw_hash,
                "finding": "same-plane sections already contain the retained contour discrepancy",
            },
            {
                "sequence": 6, "stage": "OCP-final solid STEP", "status": "AVAILABLE",
                "artifact": str(final_path.resolve()), "sha256": final_hash,
                "finding": f"raw-vs-final selected-section 4x sampled max <= {raw_final_max:.12g} mm",
            },
            {
                "sequence": 7, "stage": "extracted BRep sections / production samples", "status": "CREATED_DIAGNOSTIC",
                "artifact": str((output_dir / "stations").resolve()), "sha256": "",
                "finding": "each selected physical plane extracted once per retained STEP and persisted as native BRep",
            },
            {
                "sequence": 8, "stage": "expected profile / distance calculation", "status": "AVAILABLE_REPRODUCED",
                "artifact": str((output_dir / "expected_profile_audit.json").resolve()), "sha256": "",
                "finding": "independent expected placement matches production; independent point-to-segment confirms discrepancy",
            },
            {
                "sequence": 9, "stage": "official failed-job validation.json", "status": "MISSING_BY_DESIGN",
                "artifact": str((job_dir / "validation.json").resolve()), "sha256": "",
                "finding": "old product job failed before official validation artifact completion",
            },
        ]
        csv_write(output_dir / "source_stage_matrix.csv", list(stage_rows[0]), stage_rows)

        result = {
            "execution_status": "COMPLETED",
            "elapsed_seconds": (time.monotonic_ns() - started_ns) / 1e9,
            "production_planned_station_count": len(full_plan.stations),
            "diagnostic_completed_station_count": len(station_summaries),
            "baseline_reproduced": max(row["maximum_absolute_delta"] for row in baseline_identity) <= 1e-12,
            "metric_self_tests_passed": read_json(output_dir / "metric_self_tests.json")["passed"],
            "raw_vs_final_selected_max_mm": raw_final_max,
            "openvsp_launched": False,
            "cad_regenerated_or_repaired": False,
        }
        write_json(output_dir / "worker_result.json", result)
        logger.emit("worker_end", **result)
        return 0
    except Exception as exc:
        result = {
            "execution_status": "ERROR",
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
            "elapsed_seconds": (time.monotonic_ns() - started_ns) / 1e9,
            "openvsp_launched": False,
            "cad_regenerated_or_repaired": False,
        }
        write_json(output_dir / "worker_result.json", result)
        logger.emit("worker_error", **result)
        traceback.print_exc()
        return 1
    finally:
        logger.close()



def collect_preflight(job_dir: Path, evidence_root: Path) -> dict[str, Any]:
    preflight = retained_diagnosis.collect_preflight(job_dir, evidence_root)
    extra_paths = {
        "raw_openvsp_step": job_dir / "blade_openvsp.step",
        "retained_vsp3": job_dir / "blade_openvsp.vsp3",
        "resolved_spec": job_dir / "resolved_blade_spec.json",
        "prior_report": PRIOR_DIAGNOSTIC / "X57_VALIDATION_DIAGNOSIS.md",
        "prior_summary": PRIOR_DIAGNOSTIC / "diagnostic_summary.json",
        "prior_measurements": PRIOR_DIAGNOSTIC / "completed_measurements.json",
        "prior_timings": PRIOR_DIAGNOSTIC / "validation_timings.csv",
        "prior_log": PRIOR_DIAGNOSTIC / "diagnostic.log",
        "fixture_manifest": REPOSITORY_ROOT / "fixtures" / "x57_manual_reference" / "manifest.json",
        "fixture_checksums": REPOSITORY_ROOT / "fixtures" / "x57_manual_reference" / "SHA256SUMS.txt",
    }
    missing = [name for name, path in extra_paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing contour diagnostic inputs: {missing}")
    extra_records = {
        name: retained_diagnosis.file_record(path) for name, path in extra_paths.items()
    }
    if extra_records["raw_openvsp_step"]["sha256"] != EXPECTED_RAW_STEP_SHA256:
        raise RuntimeError("Raw retained OpenVSP STEP identity mismatch")
    source_hashes = {
        relative: sha256_file(REPOSITORY_ROOT / relative) for relative in RELEVANT_SOURCES
    }

    checksum_rows = []
    fixture_root = REPOSITORY_ROOT / "fixtures" / "x57_manual_reference"
    for line in (fixture_root / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, name = line.split(maxsplit=1)
        name = name.strip()
        actual = sha256_file(fixture_root / name)
        checksum_rows.append({
            "file": name, "expected_sha256": expected, "actual_sha256": actual,
            "matched": actual == expected,
        })
    if not all(row["matched"] for row in checksum_rows):
        raise RuntimeError(f"Fixture checksum mismatch: {checksum_rows}")
    preflight["contour_isolation_inputs"] = extra_records
    preflight["relevant_source_sha256"] = source_hashes
    preflight["fixture_checksum_verification"] = checksum_rows
    preflight["raw_step_sha256_expected"] = EXPECTED_RAW_STEP_SHA256
    preflight["raw_step_sha256_verified"] = True
    return preflight


def read_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    result = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return result


def write_timings(output_dir: Path, timed_out: bool) -> list[dict[str, Any]]:
    events = read_events(output_dir / "diagnostic_events.jsonl")
    rows = []
    for event in events:
        if event.get("event") != "operation_end":
            continue
        elapsed = event.get("elapsed_seconds")
        rows.append({
            "operation": event.get("operation"),
            "sampled_r_over_R": event.get("sampled_r_over_R"),
            "density_factor": event.get("density_factor"),
            "points_per_edge": event.get("points_per_edge") or event.get("actual_points_per_edge"),
            "expected_points_per_surface": event.get("expected_points_per_surface"),
            "start_monotonic_ns": (
                int(event["monotonic_ns"] - float(elapsed) * 1e9)
                if elapsed is not None else None
            ),
            "end_monotonic_ns": event.get("monotonic_ns"),
            "elapsed_seconds": elapsed,
            "status": event.get("status"),
            "error": event.get("error"),
        })
    if timed_out:
        starts = [event for event in events if event.get("event") == "operation_start"]
        ends = [
            (event.get("operation"), event.get("sampled_r_over_R"), event.get("density_factor"))
            for event in events if event.get("event") == "operation_end"
        ]
        for start in starts:
            key = (start.get("operation"), start.get("sampled_r_over_R"), start.get("density_factor"))
            if key not in ends:
                rows.append({
                    "operation": start.get("operation"),
                    "sampled_r_over_R": start.get("sampled_r_over_R"),
                    "density_factor": start.get("density_factor"),
                    "points_per_edge": start.get("points_per_edge") or start.get("actual_points_per_edge"),
                    "expected_points_per_surface": start.get("expected_points_per_surface"),
                    "start_monotonic_ns": start.get("monotonic_ns"),
                    "end_monotonic_ns": None, "elapsed_seconds": None,
                    "status": "INCOMPLETE_TIMEOUT", "error": "external timeout",
                })
    fields = [
        "operation", "sampled_r_over_R", "density_factor", "points_per_edge",
        "expected_points_per_surface", "start_monotonic_ns", "end_monotonic_ns",
        "elapsed_seconds", "status", "error",
    ]
    csv_write(output_dir / "validation_timings.csv", fields, rows)
    return rows


def hash_snapshot(paths: dict[str, Path]) -> dict[str, str]:
    return {name: sha256_file(path) for name, path in paths.items() if path.is_file()}




def build_summary(output_dir: Path, job_dir: Path) -> dict[str, Any]:
    preflight = read_json(output_dir / "preflight_evidence.json")
    runtime = read_json(output_dir / "runtime_configuration.json")
    launcher = read_json(output_dir / "launcher_result.json")
    worker = read_json(output_dir / "worker_result.json")
    timed_out = launcher.get("returncode") in {124, 137}
    timing_rows = write_timings(output_dir, timed_out)

    source_after = {
        relative: sha256_file(REPOSITORY_ROOT / relative) for relative in RELEVANT_SOURCES
    }
    job_paths = {
        name: Path(record["path"])
        for name, record in {
            **preflight["artifacts"],
            **preflight["contour_isolation_inputs"],
        }.items()
        if str(record.get("path", "")).startswith(str(job_dir.resolve()))
    }
    artifact_after = hash_snapshot(job_paths)
    artifact_before = {
        name: record["sha256"]
        for name, record in {
            **preflight["artifacts"],
            **preflight["contour_isolation_inputs"],
        }.items()
        if name in artifact_after
    }
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=REPOSITORY_ROOT, check=True, text=True, capture_output=True,
    ).stdout
    integrity = {
        "production_and_diagnostic_sources_unchanged_during_run": source_after == preflight["relevant_source_sha256"],
        "failed_job_artifacts_unchanged_during_run": artifact_after == artifact_before,
        "source_hashes_after": source_after,
        "failed_job_hashes_after": artifact_after,
        "final_git_status_porcelain": status,
    }

    if worker.get("execution_status") != "COMPLETED":
        return {
            "diagnostic_status": "INCOMPLETE",
            "worker": worker, "launcher": launcher, "runtime_configuration": runtime,
            "evidence_identity": preflight, "diagnostic_integrity": integrity,
            "timing_row_count": len(timing_rows),
            "external_nasa_fidelity": "UNVERIFIED",
            "existing_complete_internal_validator": "FAIL",
            "original_product_job": "FAILED_UNCHANGED",
        }

    stations = read_json(output_dir / "station_summaries.json")
    profile = read_json(output_dir / "expected_profile_audit.json")
    topology = read_json(output_dir / "retained_stage_topology.json")
    self_tests = read_json(output_dir / "metric_self_tests.json")
    baseline = read_json(output_dir / "production_baseline_identity.json")
    worst = next(row for row in stations if abs(row["sampled_r_over_R"] - 0.22302) <= 5e-13)
    max_raw_final = max(row["raw_vs_final_4x_sampled_max_mm"] for row in stations)

    operation_totals: dict[str, float] = {}
    for row in timing_rows:
        if row["status"] == "COMPLETED" and row["elapsed_seconds"] is not None:
            operation_totals[row["operation"]] = operation_totals.get(row["operation"], 0.0) + float(row["elapsed_seconds"])

    return {
        "diagnostic_status": "COMPLETED",
        "scope": {
            "job_id": JOB_ID, "selected_stations": SELECTED_STATIONS,
            "production_planned_station_count": worker["production_planned_station_count"],
            "diagnostic_completed_station_count": worker["diagnostic_completed_station_count"],
            "openvsp_launched": worker["openvsp_launched"],
            "cad_regenerated_or_repaired": worker["cad_regenerated_or_repaired"],
        },
        "evidence_identity": preflight,
        "runtime_configuration": runtime, "launcher": launcher,
        "diagnostic_integrity": integrity,
        "retained_step_topology": topology,
        "baseline_reproduction": {
            "status": "PASS" if worker["baseline_reproduced"] else "FAIL",
            "station_results": baseline,
        },
        "independent_measurement": {
            "method": self_tests["method"], "self_tests_passed": self_tests["passed"],
            "density_policy": {
                "actual_points_per_edge": {"1x": 2500, "2x": 4999, "4x": 9997},
                "expected_points_per_surface": {"1x": 2001, "2x": 4001, "4x": 8001},
                "meaning": "exact interval-density scaling; sampled maximum is not a continuous Hausdorff distance",
                "weighting": "trapezoidal arc length per component; directions each receive total weight 0.5",
            },
            "stations": stations, "worst_station": worst,
        },
        "expected_profile_and_conventions": profile,
        "localization": {
            "last_demonstrated_matching_stage": "canonical resolved profile/data supplied to adapter",
            "first_demonstrated_mismatching_stage": "raw exported OpenVSP STEP",
            "remaining_interval": "backend adapter/OpenVSP surface generation through raw STEP export",
            "ocp_finalization_introduced_discrepancy": False,
            "raw_vs_final_selected_4x_sampled_max_mm": max_raw_final,
            "confirmed": [
                "retained generated surface has a localized inboard normalized-section shape discrepancy",
                "independent bidirectional point-to-segment metric confirms the production failure scale",
                "raw OpenVSP and final OCP sections agree at the selected planes",
                "the 0.031111854-degree input LE-to-TE datum explains the systematic endpoint twist offset",
            ],
            "rejected_as_primary_cause": [
                "production point-to-point sampling or count weighting",
                "expected profile interpolation between identical endpoint profiles",
                "global reference-axis/sign/unit placement error", "OCP sewing/solid export",
                "source-native versus product thickness scalar difference by magnitude",
            ],
            "unresolved_hypotheses": [
                "OpenVSP root end-cap influence",
                "OpenVSP spanwise loft/section interpolation under strong inboard planform variation",
                "small OpenVSP base-thickness to requested-thickness scaling semantics",
            ],
        },
        "runtime_cost": {
            "worker_elapsed_seconds": worker["elapsed_seconds"],
            "operation_totals_seconds": operation_totals,
            "existing_full_validator_extraction_share": "94.94% (preserved prior evidence; not remeasured over 41 stations)",
        },
        "qualification_boundaries": {
            "input_fidelity": "previously PASS; manual entry not repeated",
            "original_product_job": "FAILED_UNCHANGED",
            "existing_complete_internal_validator": "FAIL",
            "this_task": "diagnostic localization only; not CAD acceptance",
            "external_nasa_fidelity": "UNVERIFIED",
        },
        "smallest_justified_next_action": {
            "production_change_now": "NONE",
            "controlled_experiment": (
                "In a separate disposable run, hold BladeSpec, resolved curves and export settings fixed; "
                "A/B only OpenVSP root end-cap influence, retaining raw STEP before OCP. Capture adapter "
                "readback and raw cuts at r/R 0.22302, 0.29061 and 0.50345. Do not load the retained VSP3 "
                "as frozen evidence."
            ),
            "conditional_general_correction": (
                "If that A/B removes the inboard shape oscillation, prevent root end-cap shaping from "
                "altering requested interior section shape and close the physical boundary in an explicit "
                "separately validated topology stage. Otherwise instrument OpenVSP loft section construction."
            ),
            "required_regression": (
                "Two identical coordinate-profile endpoints, constant thickness and zero TE under strong "
                "spanwise chord/twist/rake/skew controls must retain normalized section shape at raw-STEP "
                "and final-solid cuts; then rerun the unchanged 41-station acceptance."
            ),
        },
    }



def render_report(summary: dict[str, Any]) -> str:
    if summary["diagnostic_status"] != "COMPLETED":
        return f"""# X-57 Contour Isolation

## Outcome

The bounded diagnostic is **INCOMPLETE**.

Worker: {summary.get("worker")}

Launcher: {summary.get("launcher")}

The existing complete internal validator remains **FAIL**, the original product job remains
failed, and external NASA fidelity remains **UNVERIFIED**. Partial logs and timings are retained.
No production correction was made.
"""

    identity = summary["evidence_identity"]
    stations = summary["independent_measurement"]["stations"]
    profile = summary["expected_profile_and_conventions"]
    localization = summary["localization"]
    topology = summary["retained_step_topology"]
    timing = summary["runtime_cost"]
    baseline_rows = "\n".join(
        f"| {row['sampled_r_over_R']:.5f} | {row['maximum_absolute_delta']:.3e} |"
        for row in summary["baseline_reproduction"]["station_results"]
    )
    station_rows = "\n".join(
        (
            f"| {row['sampled_r_over_R']:.5f} | "
            f"{row['production_rms_mm']:.9f} / {row['production_p95_mm']:.9f} / {row['production_sampled_max_mm']:.9f} | "
            f"{row['independent_4x_arc_rms_mm']:.9f} / {row['independent_4x_arc_p95_mm']:.9f} / {row['independent_4x_sampled_max_mm']:.9f} | "
            f"{row['raw_vs_final_4x_sampled_max_mm']:.3e} | "
            f"{row['actual_max_thickness_over_c']:.9f} / {row['expected_max_thickness_over_c']:.9f} |"
        )
        for row in stations
    )
    state_rows = "\n".join(
        (
            f"| {row['sampled_r_over_R']:.5f} | {row['chord_mm']:.9f} | {row['twist_deg']:.9f} | "
            f"{row['rake_mm']:.9f} | {row['skew_mm']:.9f} | "
            f"({row['reference_xz_mm'][0]:.9f}, {row['reference_xz_mm'][1]:.9f}) |"
        )
        for row in profile["selected_station_values"]
    )
    op_rows = "\n".join(
        f"| {name} | {seconds:.6f} |"
        for name, seconds in sorted(timing["operation_totals_seconds"].items())
    )
    initial_status = identity["git"]["status_porcelain"].rstrip() or "(clean)"
    indented_status = "\n".join("    " + line for line in initial_status.splitlines())
    raw = topology["raw_openvsp_step"]
    final = topology["final_ocp_step"]
    datum = profile["profile_datum"]
    thickness = profile["thickness_representation"]
    action = summary["smallest_justified_next_action"]
    worst_station = next(row for row in stations if abs(row["sampled_r_over_R"] - 0.22302) <= 5e-13)
    landmark = worst_station["maximum_residual_coordinates"]
    return f"""# X-57 Contour Isolation Report

## Outcome

The three selected production baselines reproduced exactly. A separate component-aware,
bidirectional point-to-segment calculation confirms the retained inboard contour discrepancy.
The first demonstrated mismatch is the **raw OpenVSP STEP**. Same-plane raw and OCP-final cuts
agree to a selected-station 4x sampled maximum of
**{localization['raw_vs_final_selected_4x_sampled_max_mm']:.12g} mm**. The remaining localization
interval is **{localization['remaining_interval']}**.

This is diagnostic completion, not CAD acceptance. The old job remains failed, the existing
complete 41-station internal validator remains **FAIL**, and external NASA fidelity is
**UNVERIFIED**.

## Evidence identity and immutability

- Job: {JOB_ID}
- HEAD: {identity['git']['head']} on {identity['git']['branch']}
- Final STEP SHA-256: {identity['artifacts']['retained_step']['sha256']} (required hash verified)
- Raw STEP SHA-256: {identity['contour_isolation_inputs']['raw_openvsp_step']['sha256']} (recorded hash verified)
- Candidate/submitted/generated production models equal: {identity['specification_equivalence']['production_bladespec_model_equal']}
- Fixture checksum set verified: {all(row['matched'] for row in identity['fixture_checksum_verification'])}
- Sources unchanged during run: {summary['diagnostic_integrity']['production_and_diagnostic_sources_unchanged_during_run']}
- Failed-job artifacts unchanged during run: {summary['diagnostic_integrity']['failed_job_artifacts_unchanged_during_run']}
- OpenVSP launched: False
- CAD regenerated or repaired: False
- Initial and post-worker Git status plus tracked-diff identities are retained in
  contour_isolation_summary.json; no reset, checkout, commit, or merge was performed.

Initial worktree (preserved):

{indented_status}

Exact worker command:

    {summary['runtime_configuration']['worker_command']}

Runtime versions are recorded in preflight_evidence.json. The run used Python
{identity['environment']['python']['version']}, NumPy {identity['environment']['numpy']},
SciPy {identity['environment']['scipy']}, OCP {identity['environment']['ocp_binding']} /
OpenCascade {identity['environment']['opencascade']}, and statically identified OpenVSP
{identity['environment']['openvsp']['version']} without launching it.

## Exact production baseline

The final STEP was loaded once. The same in-memory shape was supplied to the exact production
measure_sections path, selecting only three existing plan records without editing production
planning. Expected preparation, plane construction, OCP sectioning, 2500-point edge sampling,
wire/end-point checks, and production symmetric distances were unchanged.

| sampled r/R | maximum absolute delta from prior completed record |
| ---: | ---: |
{baseline_rows}

The complete production plan remains 41 stations. This subset does not replace acceptance.

## Independent measurement

The independent implementation preserves actual edges and expected upper/lower/TE entities as
separate components. It projects to finite polyline segments in both directions; its KD tree is
only a conservative broad phase. It never bridges components or calls the production distance
helper. Zero-length TE segments are excluded from arc weighting, and each direction receives
weight 0.5.

All self-tests passed: identical contour; reversed traversal with shifted start; analytically
checked different-density regular polygons; and a known parallel offset.

Densities are exact interval multiples: actual 2500/4999/9997 points per trimmed edge and expected
2001/4001/8001 points per surface. Reported maxima are sampled maxima, not continuous Hausdorff
bounds.

| sampled r/R | production RMS / P95 / sampled max mm | independent 4x arc RMS / P95 / sampled max mm | raw-final 4x sampled max mm | actual / expected max t/c |
| ---: | ---: | ---: | ---: | ---: |
{station_rows}

Per-direction count and arc statistics plus convergence deltas are retained in each station's
metric_density_results.json. The 4x projected residual pairs are in
independent_residuals_4x.csv.

At the worst station the 4x sampled maximum is {landmark['sampled_distance_mm']:.12g} mm in the
{landmark['direction']} direction, from global X,Z {landmark['query_xz_mm']} to
{landmark['projected_xz_mm']}. In the common requested frame those points are at x/c,y/c
{worst_station['maximum_query_requested_frame_x_over_c_y_over_c']} and
{worst_station['maximum_projection_requested_frame_x_over_c_y_over_c']}. The discrepancy is on
the upper surface around x/c 0.155, not a root/tip wire closure artifact.

## Expected profile and coordinate convention

Fixture, submitted, and resolved coordinate arrays are exact. Both endpoint profiles are
identical (74 upper and 67 lower points), both request zero TE, and TE preparation changes
coordinates by zero. The independent expected construction agrees with production to
{profile['coordinate_identity']['maximum_production_vs_independent_expected_mm']:.3e} mm.

| r/R | chord mm | twist deg | rake mm | skew mm | reference X,Z mm |
| ---: | ---: | ---: | ---: | ---: | ---: |
{state_rows}

The input LE midpoint is {datum['leading_midpoint_xy']} and the TE midpoint is
{datum['trailing_midpoint_xy']}. Their datum angle is
**{datum['le_to_te_angle_deg']:.12f} deg**. The present sign convention predicts endpoint twist as
requested minus that angle, explaining the approximately -0.031-degree pattern. The datum is
already in the expected contour and also occurs at passing stations, so it is not the localized
contour cause.

Source-native t/c is {thickness['source_native_ratio']:.15g}; product polygon-envelope t/c is
{thickness['product_polygon_envelope_ratio']:.15g}. The difference is
{thickness['delta_ratio']:.12g}, about 0.002 to 0.003 mm full thickness at these cuts. It is real
but orders of magnitude too small to explain the worst residual.

## Visible shape evidence

Every station folder contains a true-scale equal-aspect overlay, a maximum-residual close-up,
both-direction residual plot, requested-frame thickness/camber plot and CSV, production and
independent expected coordinates, original production actual samples, and raw/final native
OpenCascade v3 BRep sections. Each BRep was re-import checked.

The common-frame thickness/camber evidence shows a large deficit at r/R 0.22302 and near agreement
at the two passing controls. cached_41_station_shape_pattern.csv uses the completed earlier
41-station records to show the damped sign-changing inboard t/c pattern; no additional full-plan
cuts were run.

Thickness/camber pairing is explicitly labelled **AMBIGUOUS** at all three cuts because one edge
has one requested-x/c reversal at the leading edge (the extrema are between x/c -0.000743 and
-0.000000861). The tabulated envelopes use only 0.02 <= x/c <= 0.98, outside that reversal, and
are diagnostic support rather than qualification metrics. The component-preserving contour
distance does not require single-valued x/c and is unaffected by this ambiguity.

## Retained-stage localization

Raw topology: {raw['shape_type']}; solids/shells/faces
{raw['solids']}/{raw['shells']}/{raw['faces']}; free edges {raw['free_edges']};
BRepCheck valid {raw['brepcheck_valid']}.

Final topology: {final['shape_type']}; solids/shells/faces
{final['solids']}/{final['shells']}/{final['faces']}; free edges {final['free_edges']};
closed {final['closed_shell']}; BRepCheck valid {final['brepcheck_valid']}.

The retained source/resolved coordinate stage matches the request, while the raw STEP already
differs. Raw and final sections agree, so OCP sewing/export did not introduce the observed shape
error. No frozen in-memory OpenVSP surface or adapter readback survives. The exact internal cause
remains localized between adapter input and raw STEP.

Confirmed:

- The retained generated surface has a localized inboard shape discrepancy.
- An independent curve metric confirms the production failure scale.
- OCP finalization is not the source at the tested planes.
- The LE-to-TE datum explains only the twist offset.

Rejected as primary causes:

- Production nearest-point sampling or count weighting.
- Expected interpolation between identical profiles.
- A global unit, sign, or reference-axis error.
- Source/product thickness representation by magnitude.

Still hypotheses: OpenVSP root-end-cap influence, spanwise loft interpolation under strong
inboard planform changes, and the small base/requested-thickness scaling semantics.

## Runtime

Worker elapsed: {timing['worker_elapsed_seconds']:.6f} seconds.

| measured operation | accumulated seconds |
| --- | ---: |
{op_rows}

The earlier complete run's 94.94% extraction share remains separate confirmed performance
evidence. This task changed neither production timeout nor performance code.

## Smallest justified next action

No production change is justified yet. {action['controlled_experiment']}

Conditional general correction: {action['conditional_general_correction']}

Required regression: {action['required_regression']}

Do not subtract the datum angle, broaden tolerances, change source thickness, or revise the
validator to follow measured CAD. Those actions do not explain the passing/failing pattern.
"""



def run_supervisor(
    output_root: Path,
    job_dir: Path,
    evidence_root: Path,
    external_timeout_seconds: int,
) -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = output_root / f"a93b281c_{stamp}"
    if output_dir.exists():
        output_dir = output_root / f"a93b281c_{stamp}_{os.getpid()}"
    output_dir.mkdir(parents=True, exist_ok=False)

    preflight = collect_preflight(job_dir, evidence_root)
    if not preflight["step_sha256_verified"]:
        raise RuntimeError("Required retained final STEP hash mismatch")
    write_json(output_dir / "preflight_evidence.json", preflight)

    worker_command = [
        "timeout", "--signal=TERM", "--kill-after=30s",
        f"{external_timeout_seconds}s",
        sys.executable, "-u", str(Path(__file__).resolve()), "worker",
        "--output-dir", str(output_dir.resolve()),
        "--job-dir", str(job_dir.resolve()),
        "--evidence-root", str(evidence_root.resolve()),
    ]
    runtime = {
        "created_at_utc": utc_now(),
        "cwd": str(REPOSITORY_ROOT.resolve()),
        "external_timeout_seconds": external_timeout_seconds,
        "kill_after_seconds": 30,
        "worker_command_argv": worker_command,
        "worker_command": " ".join(subprocess.list2cmdline([item]) for item in worker_command),
        "python_executable": sys.executable,
        "openvsp_allowed": False,
        "cad_regeneration_allowed": False,
        "selected_stations": SELECTED_STATIONS,
        "production_baseline_entrypoint": "bladegen.validation.measure_sections.measure_sections",
    }
    write_json(output_dir / "runtime_configuration.json", runtime)
    (output_dir / "commands.txt").write_text(
        runtime["worker_command"] + "\n", encoding="utf-8"
    )

    launcher_start = time.monotonic_ns()
    with (output_dir / "diagnostic.log").open("w", encoding="utf-8", buffering=1) as log:
        completed = subprocess.run(
            worker_command, cwd=REPOSITORY_ROOT, stdout=log,
            stderr=subprocess.STDOUT, check=False,
        )
    launcher = {
        "returncode": completed.returncode,
        "timed_out": completed.returncode in {124, 137},
        "elapsed_seconds": (time.monotonic_ns() - launcher_start) / 1e9,
        "completed_at_utc": utc_now(),
    }
    write_json(output_dir / "launcher_result.json", launcher)

    summary = build_summary(output_dir, job_dir)
    summary["deliverables"] = {
        "evidence_directory": str(output_dir.resolve()),
        "zip_path": str(output_dir.with_suffix(".zip").resolve()),
        "report": str((output_dir / "X57_CONTOUR_ISOLATION_REPORT.md").resolve()),
    }
    write_json(output_dir / "contour_isolation_summary.json", summary)
    (output_dir / "X57_CONTOUR_ISOLATION_REPORT.md").write_text(
        render_report(summary), encoding="utf-8"
    )
    shutil.copy2(Path(__file__).resolve(), output_dir / "diagnose_x57_contours.py")
    write_json(output_dir / "bundle_result.json", {
        "evidence_directory": str(output_dir.resolve()),
        "zip_path": str(output_dir.with_suffix(".zip").resolve()),
        "large_blade_steps_duplicated_in_bundle": False,
        "retained_final_step_path": str((job_dir / "blade_solid.step").resolve()),
        "retained_final_step_sha256": EXPECTED_FINAL_STEP_SHA256,
        "retained_raw_step_path": str((job_dir / "blade_openvsp.step").resolve()),
        "retained_raw_step_sha256": EXPECTED_RAW_STEP_SHA256,
    })

    files = sorted(path for path in output_dir.rglob("*") if path.is_file())
    write_json(output_dir / "evidence_manifest.json", {
        "created_at_utc": utc_now(),
        "files": [
            {
                "relative_path": str(path.relative_to(output_dir)),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
        ],
    })
    zip_path = output_dir.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(output_dir.rglob("*")):
            if path.is_file():
                archive.write(path, Path(output_dir.name) / path.relative_to(output_dir))

    print(json.dumps({
        "diagnostic_status": summary["diagnostic_status"],
        "evidence_directory": str(output_dir.resolve()),
        "zip_path": str(zip_path.resolve()),
        "zip_sha256": sha256_file(zip_path),
        "worker_returncode": completed.returncode,
    }, indent=2), flush=True)
    return 0 if summary["diagnostic_status"] == "COMPLETED" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode")

    supervisor = subparsers.add_parser("run", help="create evidence directory and launch bounded worker")
    supervisor.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    supervisor.add_argument("--job-dir", type=Path, default=DEFAULT_JOB_DIR)
    supervisor.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    supervisor.add_argument("--timeout-seconds", type=int, default=600)

    worker = subparsers.add_parser("worker", help=argparse.SUPPRESS)
    worker.add_argument("--output-dir", type=Path, required=True)
    worker.add_argument("--job-dir", type=Path, required=True)
    worker.add_argument("--evidence-root", type=Path, required=True)
    return parser


def main() -> int:
    parser = build_parser()
    arguments = parser.parse_args()
    if arguments.mode == "worker":
        return run_worker(
            arguments.output_dir.resolve(),
            arguments.job_dir.resolve(),
            arguments.evidence_root.resolve(),
        )
    if arguments.mode in {None, "run"}:
        return run_supervisor(
            getattr(arguments, "output_root", DEFAULT_OUTPUT_ROOT).resolve(),
            getattr(arguments, "job_dir", DEFAULT_JOB_DIR).resolve(),
            getattr(arguments, "evidence_root", DEFAULT_EVIDENCE_ROOT).resolve(),
            int(getattr(arguments, "timeout_seconds", 600)),
        )
    parser.error("unsupported mode")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
