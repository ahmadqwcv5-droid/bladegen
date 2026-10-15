#!/usr/bin/env python3
"""X57-LOC-02: live OpenVSP surface versus same-run raw STEP diagnosis.

This is an isolated evidence harness.  It imports the production adapter and
resolver, observes the normal build/export path, and does not modify production
source or the retained failed job.
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
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SCRIPTS = ROOT / "scripts"
for entry in (BACKEND, SCRIPTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import diagnose_x57_contours as contour
import run_x57_root_cap_ab as prior_ab

JOB_ID = "a93b281c29b640afaa6bad698d64a61b"
JOB_DIR = ROOT / "output" / "runs" / JOB_ID
EVIDENCE_ROOT = ROOT / "docs" / "evidence" / "sprint04b" / "x57"
OUTPUT_ROOT = EVIDENCE_ROOT / "live_surface_localization"
RETAINED_RAW = JOB_DIR / "blade_openvsp.step"
RETAINED_FINAL = JOB_DIR / "blade_solid.step"
EXPECTED_RAW_SHA = "85f798f74f672e4c78f3560e3413fcbdbba0ff7410424a840a5fc4e746d8b07f"
EXPECTED_FINAL_SHA = "43c2cd72bebcd3949e0fe0b210aaac9ccbf6918952743fd109ecb0cac2e401d6"
STATIONS = (0.22302, 0.29061, 0.50345)
FACTORS = (1, 2, 4)
MM_PER_INCH = 25.4
PLANE_TARGET_MM = 1.0e-6
STABILITY_TARGET_MM = 1.0e-4
STAGE_AGREEMENT_MM = 1.0e-3
BASELINE_REPEAT_MM = 1.0e-4
RECORDED_PRODUCTION = prior_ab.RECORDED_PRODUCTION
OPENVSP_SOURCE = Path("/tmp/openvsp-src-354-live")

PRODUCTION_SOURCES = (
    "backend/bladegen/adapters/openvsp_adapter.py",
    "backend/bladegen/curves/resolver.py",
    "backend/bladegen/solid/ocp_solidify.py",
    "backend/bladegen/validation/expected_geometry.py",
    "backend/bladegen/validation/measure_sections.py",
    "backend/bladegen/validation/station_plan.py",
    "scripts/diagnose_x57_contours.py",
    "scripts/run_x57_root_cap_ab.py",
)
OPENVSP_SOURCE_FILES = (
    "src/geom_api/VSP_Geom_API.cpp",
    "src/geom_core/Geom.cpp",
    "src/geom_core/Geom.h",
    "src/geom_core/PropGeom.cpp",
    "src/geom_core/Vehicle.cpp",
    "src/util/VspSurf.cpp",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(item) for item in value]
    return value


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(jsonable(value), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        write_text(path, "")
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def command_output(argv: list[str], cwd: Path = ROOT) -> str:
    return subprocess.run(
        argv, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False,
    ).stdout.strip()


def file_identity(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": sha256_file(path),
    }


class EventLog:
    def __init__(self, path: Path) -> None:
        self.path = path
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
            "since_start_seconds": (now - self.origin_ns) / 1e9,
            **jsonable(fields),
        }
        line = json.dumps(record, sort_keys=True, allow_nan=False)
        self.stream.write(line + "\n")
        self.stream.flush()
        print(f"LIVE_SURFACE_EVENT {line}", flush=True)

    @contextmanager
    def operation(self, name: str, **fields: Any) -> Iterator[None]:
        started = time.monotonic_ns()
        self.emit("operation_start", operation=name, **fields)
        try:
            yield
        except BaseException as exc:
            self.emit(
                "operation_end", operation=name, status="ERROR",
                elapsed_seconds=(time.monotonic_ns() - started) / 1e9,
                error=f"{type(exc).__name__}: {exc}", **fields,
            )
            raise
        else:
            self.emit(
                "operation_end", operation=name, status="COMPLETED",
                elapsed_seconds=(time.monotonic_ns() - started) / 1e9, **fields,
            )

    def close(self) -> None:
        self.stream.close()


def vec_array(values: Any) -> np.ndarray:
    return np.asarray([(p.x(), p.y(), p.z()) for p in values], dtype=float)


def eval_points(vsp: Any, geom_id: str, surface_index: int, u: np.ndarray, w: np.ndarray) -> np.ndarray:
    if len(u) != len(w):
        raise ValueError("u/w vectors differ in length")
    return vec_array(
        vsp.CompVecPnt01(
            geom_id, int(surface_index), [float(x) for x in u], [float(x) for x in w]
        )
    ) * MM_PER_INCH


def solve_plane_branch(vsp: Any, geom_id: str, surface_index: int,
                       target_y_mm: float, w: np.ndarray
                       ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized bracketed solve of S(u,w).Y=target for one proven branch."""
    w = np.asarray(w, dtype=float)
    lo, hi = np.zeros_like(w), np.ones_like(w)
    flo = eval_points(vsp, geom_id, surface_index, lo, w)[:, 1] - target_y_mm
    fhi = eval_points(vsp, geom_id, surface_index, hi, w)[:, 1] - target_y_mm
    bad = np.flatnonzero(flo * fhi > 0.0)
    if len(bad):
        raise RuntimeError(f"Full u domain fails to bracket plane at {len(bad)}/{len(w)} w samples")
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        fmid = eval_points(vsp, geom_id, surface_index, mid, w)[:, 1] - target_y_mm
        left = flo * fmid <= 0.0
        hi, lo = np.where(left, mid, hi), np.where(left, lo, mid)
        flo = np.where(left, flo, fmid)
    u = 0.5 * (lo + hi)
    xyz = eval_points(vsp, geom_id, surface_index, u, w)
    return u, xyz, xyz[:, 1] - target_y_mm


def analyze_plane_intersection(vsp: Any, geom_id: str, surface_index: int,
                               target_y_mm: float) -> dict[str, Any]:
    """Prove root multiplicity, and reject or accept a constant-u shortcut."""
    probe_w, probe_u = np.linspace(0.0, 1.0, 129), np.linspace(0.0, 1.0, 257)
    residual = (eval_points(
        vsp, geom_id, surface_index,
        np.tile(probe_u, len(probe_w)), np.repeat(probe_w, len(probe_u)),
    )[:, 1].reshape(len(probe_w), len(probe_u)) - target_y_mm)
    def count_roots(row: np.ndarray) -> int:
        zero = np.abs(row) <= 1.0e-10
        signs = np.sign(row[~zero])
        crossings = int(np.sum(signs[:-1] * signs[1:] < 0.0)) if len(signs) > 1 else 0
        return crossings if crossings else int(np.any(zero))
    root_counts = np.asarray([count_roots(row) for row in residual], dtype=int)
    if np.any(root_counts != 1):
        values, counts = np.unique(root_counts, return_counts=True)
        raise RuntimeError(
            f"Plane is not one continuous root branch: {dict(zip(values.tolist(), counts.tolist()))}"
        )
    ref_u, _, ref_residual = solve_plane_branch(
        vsp, geom_id, surface_index, target_y_mm, np.asarray([0.25])
    )
    dense_w = np.linspace(0.0, 1.0, 2049)
    constant_xyz = eval_points(
        vsp, geom_id, surface_index, np.full_like(dense_w, ref_u[0]), dense_w
    )
    constant_max = float(np.max(np.abs(constant_xyz[:, 1] - target_y_mm)))
    branch_u, branch_xyz, branch_residual = solve_plane_branch(
        vsp, geom_id, surface_index, target_y_mm, dense_w
    )
    return {
        "method": "129x257 root-topology scan; one bracket per w; 60-step vectorized bisection/continuation",
        "surface_index": surface_index,
        "native_domain": {"u01": [0.0, 1.0], "w01": [0.0, 1.0]},
        "target_y_mm": target_y_mm,
        "root_topology_probe": {
            "w_count": len(probe_w), "u_count": len(probe_u),
            "root_count_min": int(np.min(root_counts)),
            "root_count_max": int(np.max(root_counts)),
            "all_w_have_one_root": bool(np.all(root_counts == 1)),
        },
        "constant_u_test": {
            "reference_w": 0.25, "reference_u": float(ref_u[0]),
            "reference_residual_mm": float(ref_residual[0]),
            "whole_curve_probe_count": len(dense_w),
            "whole_curve_max_abs_plane_residual_mm": constant_max,
            "accepted": constant_max <= PLANE_TARGET_MM,
        },
        "selected_method": "constant_u" if constant_max <= PLANE_TARGET_MM else "solved_u_of_w",
        "solved_branch_probe": {
            "point_count": len(dense_w), "u_min": float(np.min(branch_u)),
            "u_max": float(np.max(branch_u)), "u_span": float(np.ptp(branch_u)),
            "max_abs_plane_residual_mm": float(np.max(np.abs(branch_residual))),
            "x_span_mm": float(np.ptp(branch_xyz[:, 0])),
            "z_span_mm": float(np.ptp(branch_xyz[:, 2])),
        },
        "multiple_roots_observed": False, "missing_branches": 0,
    }


def live_components_all_factors(vsp: Any, geom_id: str, surface_index: int,
                                solution: dict[str, Any]) -> dict[str, Any]:
    count4 = 4 * (2500 - 1) + 1
    solved = {}
    for name, w in (
        ("live_lower_w_0_to_0p5", np.linspace(0.0, 0.5, count4)),
        ("live_upper_w_0p5_to_1", np.linspace(0.5, 1.0, count4)),
    ):
        u, xyz, _ = solve_plane_branch(
            vsp, geom_id, surface_index, float(solution["target_y_mm"]), w
        )
        solved[name] = (u, xyz, w)
    factors = {}
    for factor, stride in ((1, 4), (2, 2), (4, 1)):
        components, rows, residual_max = [], [], 0.0
        for name, (u4, xyz4, w4) in solved.items():
            u, w, xyz = u4[::stride], w4[::stride], xyz4[::stride]
            residual = xyz[:, 1] - float(solution["target_y_mm"])
            residual_max = max(residual_max, float(np.max(np.abs(residual))))
            components.append({"name": name, "points": xyz[:, (0, 2)]})
            if factor == 4:
                rows.extend({
                    "component": name, "point_index": index, "surface_index": surface_index,
                    "u01": float(ui), "w01": float(wi), "x_mm": float(point[0]),
                    "y_mm": float(point[1]), "z_mm": float(point[2]),
                    "plane_residual_mm": float(plane),
                } for index, (ui, wi, point, plane) in enumerate(zip(u, w, xyz, residual)))
        factors[f"{factor}x"] = {
            "components": components, "rows": rows,
            "max_abs_plane_residual_mm": residual_max,
            "point_count": sum(len(c["points"]) for c in components),
        }
    return factors


def live_capture(
    vsp: Any,
    geom_id: str,
    spec: Any,
    phase: str,
    output_dir: Path,
    logger: EventLog,
    sentinel_parameters: list[tuple[float, float]] | None = None,
) -> dict[str, Any]:
    phase_dir = output_dir / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    surface_index = 0
    surface_count = int(vsp.GetNumMainSurfs(geom_id))
    if surface_count != 1:
        raise RuntimeError(f"Expected one main prop surface; found {surface_count}")
    utess, wtess = vsp.GetUWTess01(geom_id, surface_index)
    stations: dict[str, Any] = {}
    for station in STATIONS:
        target_y = float(spec.diameter_mm / 2.0 * station)
        with logger.operation(
            "analyze_live_physical_plane", phase=phase, sampled_r_over_R=station,
            target_y_mm=target_y,
        ):
            solution = analyze_plane_intersection(vsp, geom_id, surface_index, target_y)
        station_dir = phase_dir / contour.station_slug(station)
        station_dir.mkdir(parents=True, exist_ok=False)
        with logger.operation(
            "solve_and_sample_live_contour", phase=phase, sampled_r_over_R=station,
            maximum_density_factor=4,
        ):
            factors = live_components_all_factors(
                vsp, geom_id, surface_index, solution
            )
        write_csv(station_dir / "live_parameters_xyz_4x.csv", factors["4x"]["rows"])
        write_json(station_dir / "plane_solution.json", solution)
        stations[f"{station:.5f}"] = {"solution": solution, "factors": factors}

    sentinel_w_pattern = np.asarray([0.0, 0.155, 0.5, 0.845, 1.0])
    if sentinel_parameters is None:
        parameters = []
        for station in STATIONS:
            target_y = float(spec.diameter_mm / 2.0 * station)
            solved_u, _, _ = solve_plane_branch(
                vsp, geom_id, surface_index, target_y, sentinel_w_pattern
            )
            parameters.extend(zip(solved_u.tolist(), sentinel_w_pattern.tolist()))
    else:
        parameters = list(sentinel_parameters)
    sentinel_u = np.asarray([item[0] for item in parameters], dtype=float)
    sentinel_w = np.asarray([item[1] for item in parameters], dtype=float)
    sentinel_xyz = eval_points(vsp, geom_id, surface_index, sentinel_u, sentinel_w)
    sentinels = [
        {
            "surface_index": surface_index, "u01": float(u), "w01": float(w),
            "x_mm": float(p[0]), "y_mm": float(p[1]), "z_mm": float(p[2]),
        }
        for u, w, p in zip(sentinel_u, sentinel_w, sentinel_xyz)
    ]
    write_csv(phase_dir / "sentinels.csv", sentinels)
    result = {
        "phase": phase, "geometry_id": geom_id, "surface_index": surface_index,
        "main_surface_count": surface_count,
        "normalized_domains": {"u01": [0.0, 1.0], "w01": [0.0, 1.0]},
        "uw_tessellation": {
            "u_count": len(utess), "w_count": len(wtess),
            "u_min_max": [float(min(utess)), float(max(utess))],
            "w_min_max": [float(min(wtess)), float(max(wtess))],
        },
        "stations": stations, "sentinels": sentinels,
        "sentinel_parameters": parameters,
    }
    compact = {
        key: jsonable(value) for key, value in result.items()
        if key != "stations"
    }
    compact["stations"] = {}
    for key, item in stations.items():
        compact["stations"][key] = {
            "solution": item["solution"],
            "factors": {
                factor: {
                    "max_abs_plane_residual_mm": value["max_abs_plane_residual_mm"],
                    "point_count": value["point_count"],
                }
                for factor, value in item["factors"].items()
            },
        }
    write_json(phase_dir / "capture_summary.json", compact)
    return result


def extraction_self_tests() -> dict[str, Any]:
    """Analytic tests of bracketing/continuation logic independent of OpenVSP."""
    tests = []

    # Curved cylinder-like surface: y = u^2 + 0.2 sin(pi w), so native u is
    # explicitly not the physical y coordinate and the plane root varies with w.
    w = np.linspace(0.0, 1.0, 2001)
    target = 0.64
    expected_u = np.sqrt(target - 0.2 * np.sin(np.pi * w))
    lo = np.zeros_like(w)
    hi = np.ones_like(w)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        value = mid * mid + 0.2 * np.sin(np.pi * w) - target
        hi = np.where(value >= 0.0, mid, hi)
        lo = np.where(value < 0.0, mid, lo)
    solved = 0.5 * (lo + hi)
    residual = solved * solved + 0.2 * np.sin(np.pi * w) - target
    tests.append(
        {
            "name": "curved_surface_nonradial_parameter",
            "description": "curved analytic surface; plane root u(w), not u=r/R",
            "max_u_error": float(np.max(np.abs(solved - expected_u))),
            "max_plane_residual": float(np.max(np.abs(residual))),
            "passed": float(np.max(np.abs(residual))) <= 1.0e-12,
        }
    )

    # A constant-u curve is not accepted merely because one point lies on plane.
    u_ref = math.sqrt(target)
    whole_curve_residual = u_ref * u_ref + 0.2 * np.sin(np.pi * w) - target
    rejected = float(np.max(np.abs(whole_curve_residual))) > PLANE_TARGET_MM
    tests.append(
        {
            "name": "reject_false_constant_parameter_curve",
            "reference_point_residual": 0.0,
            "whole_curve_max_residual": float(np.max(np.abs(whole_curve_residual))),
            "passed": rejected,
        }
    )

    metric_tests = contour.metric_self_tests()
    return {
        "plane_extraction_tests": tests,
        "component_metric_tests": metric_tests,
        "passed": all(item["passed"] for item in tests) and metric_tests["passed"],
    }


def selected_production_measurements(step_path: Path, spec: Any, shape: Any) -> list[dict[str, Any]]:
    from bladegen.validation import measure_sections as measurement

    _, selected_plan = prior_ab._selected_plan(spec, STATIONS)
    originals = {
        "read_step": measurement.read_step,
        "plan_validation_stations": measurement.plan_validation_stations,
    }
    measurement.read_step = lambda _path: shape
    measurement.plan_validation_stations = lambda _spec: selected_plan
    try:
        return measurement.measure_sections(step_path, spec)
    finally:
        for name, value in originals.items():
            setattr(measurement, name, value)


def pair_metric(
    left: list[dict[str, Any]], right: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    full = contour.compare_components(left, right)
    return contour.public_metric(full), full


def plot_stage_overlay(
    path: Path,
    station: float,
    expected: list[dict[str, Any]],
    live: list[dict[str, Any]],
    step: list[dict[str, Any]],
) -> None:
    fig, ax = plt.subplots(figsize=(10, 6))
    for components, label, color, style in (
        (expected, "expected E", "black", "--"),
        (live, "live before L_before", "tab:blue", "-"),
        (step, "same-run STEP T", "tab:red", ":"),
    ):
        first = True
        for component in components:
            points = np.asarray(component["points"])
            ax.plot(points[:, 0], points[:, 1], color=color, linestyle=style,
                    linewidth=1.0, label=label if first else None)
            first = False
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("global X (mm)")
    ax.set_ylabel("global Z (mm)")
    ax.set_title(f"X-57 stage overlay at sampled r/R={station:.5f}")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_expected_residual(path: Path, metric: dict[str, Any], expected_info: dict[str, Any]) -> None:
    query = metric["right_query"]
    detail = metric["right_detail"]
    local = contour.local_coordinates(query["points"], expected_info, 0.5)
    mask = query["component"] == "expected_upper"
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(local[mask, 0], detail["distance"][mask], color="tab:purple", linewidth=1.0)
    ax.axvspan(0.13, 0.18, color="orange", alpha=0.18, label="requested x/c 0.13–0.18")
    ax.set_xlabel("requested-frame x/c")
    ax.set_ylabel("expected-to-live point/segment distance (mm)")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def compare_stages(
    output_dir: Path,
    spec: Any,
    pre: dict[str, Any],
    post: dict[str, Any],
    same_step: Path,
    logger: EventLog,
) -> dict[str, Any]:
    from bladegen.solid import ocp_solidify as ocp
    from bladegen.validation.measure_sections import _section_shape

    with logger.operation("read_same_run_raw_step", path=str(same_step)):
        same_shape = ocp.read_step(same_step)
    with logger.operation("read_retained_raw_step", path=str(RETAINED_RAW)):
        retained_shape = ocp.read_step(RETAINED_RAW)
    topology = ocp.inspect_shape(same_shape)
    write_json(output_dir / "same_run_raw_topology.json", topology)
    with logger.operation("three_station_production_measurements"):
        production = selected_production_measurements(same_step, spec, same_shape)
    write_json(output_dir / "production_measurements.json", production)
    production_by_station = {
        round(float(row["sampled_r_over_R"]), 12): row for row in production
    }

    stage_rows: list[dict[str, Any]] = []
    station_results: list[dict[str, Any]] = []
    radius = float(spec.diameter_mm) / 2.0
    payload = spec.model_dump(mode="json")
    for station in STATIONS:
        slug = contour.station_slug(station)
        station_dir = output_dir / "stations" / slug
        station_dir.mkdir(parents=True, exist_ok=False)
        with logger.operation("same_run_step_section", sampled_r_over_R=station):
            step_section = _section_shape(same_shape, radius, station)
        with logger.operation("retained_raw_step_section", sampled_r_over_R=station):
            retained_section = _section_shape(retained_shape, radius, station)
        same_brep = contour.persist_section_brep(step_section, station_dir / "same_run_raw_section.brep")
        retained_brep = contour.persist_section_brep(
            retained_section, station_dir / "retained_raw_section.brep"
        )
        density_results: dict[str, Any] = {}
        full_4x: dict[str, Any] = {}
        for factor in FACTORS:
            expected_info = contour.independent_expected(payload, station, factor)
            expected = expected_info["metric_components"]
            live_before = pre["stations"][f"{station:.5f}"]["factors"][f"{factor}x"]["components"]
            live_after = post["stations"][f"{station:.5f}"]["factors"][f"{factor}x"]["components"]
            points_per_edge = factor * (2500 - 1) + 1
            step_components = contour.sample_section_components(step_section, points_per_edge)
            retained_components = contour.sample_section_components(retained_section, points_per_edge)
            pairs = {
                "E_vs_L_before": (expected, live_before),
                "E_vs_T": (expected, step_components),
                "L_before_vs_T": (live_before, step_components),
                "L_before_vs_L_after": (live_before, live_after),
                "L_after_vs_T": (live_after, step_components),
                "T_vs_retained_raw": (step_components, retained_components),
            }
            public: dict[str, Any] = {}
            full: dict[str, Any] = {}
            for name, (left, right) in pairs.items():
                with logger.operation(
                    "component_preserving_metric", sampled_r_over_R=station,
                    density_factor=factor, comparison=name,
                ):
                    public[name], full[name] = pair_metric(left, right)
            density_results[f"{factor}x"] = {
                "actual_points_per_edge": points_per_edge,
                "expected_points_per_surface": factor * (2001 - 1) + 1,
                "comparisons": public,
            }
            if factor == 4:
                full_4x = {
                    "expected_info": expected_info,
                    "expected": expected,
                    "live_before": live_before,
                    "live_after": live_after,
                    "step": step_components,
                    "retained": retained_components,
                    "metrics": full,
                }
        headline: dict[str, Any] = {}
        for comparison in density_results["4x"]["comparisons"]:
            by_factor = {}
            for factor in FACTORS:
                by_factor[f"{factor}x"] = density_results[f"{factor}x"]["comparisons"][comparison][
                    "bidirectional_equal_direction_arc_weighted"
                ]
            stability = abs(by_factor["4x"]["sampled_max_mm"] - by_factor["2x"]["sampled_max_mm"])
            headline[comparison] = {
                "by_factor": by_factor,
                "refinement_2x_to_4x_sampled_max_delta_mm": stability,
                "stability_target_mm": STABILITY_TARGET_MM,
                "stable": stability <= STABILITY_TARGET_MM,
            }
            metric4 = by_factor["4x"]
            stage_rows.append(
                {
                    "sampled_r_over_R": station,
                    "comparison": comparison,
                    "rms_mm_4x": metric4["rms_mm"],
                    "p95_mm_4x": metric4["p95_mm"],
                    "sampled_max_mm_4x": metric4["sampled_max_mm"],
                    "sampled_max_2x_to_4x_delta_mm": stability,
                    "refinement_stable": stability <= STABILITY_TARGET_MM,
                    "stage_agreement_threshold_mm": STAGE_AGREEMENT_MM,
                    "stage_agrees": metric4["sampled_max_mm"] <= STAGE_AGREEMENT_MM,
                }
            )
        contour.save_components_csv(station_dir / "expected_4x.csv", full_4x["expected"])
        contour.save_components_csv(station_dir / "live_before_4x.csv", full_4x["live_before"])
        contour.save_components_csv(station_dir / "live_after_4x.csv", full_4x["live_after"])
        contour.save_components_csv(station_dir / "same_run_step_4x.csv", full_4x["step"])
        contour.save_components_csv(station_dir / "retained_raw_step_4x.csv", full_4x["retained"])
        contour.save_residual_csv(
            station_dir / "E_vs_L_before_residuals_4x.csv",
            full_4x["metrics"]["E_vs_L_before"],
        )
        contour.save_residual_csv(
            station_dir / "L_before_vs_T_residuals_4x.csv",
            full_4x["metrics"]["L_before_vs_T"],
        )
        plot_stage_overlay(
            station_dir / "stage_overlay.png", station,
            full_4x["expected"], full_4x["live_before"], full_4x["step"],
        )
        plot_expected_residual(
            station_dir / "expected_to_live_upper_residual.png",
            full_4x["metrics"]["E_vs_L_before"], full_4x["expected_info"],
        )
        write_json(station_dir / "density_comparisons.json", density_results)
        production_row = production_by_station[round(station, 12)]
        recorded = RECORDED_PRODUCTION[station]
        production_delta = {
            "contour_rms_mm": abs(float(production_row["contour_rms_mm"]) - recorded[0]),
            "contour_p95_mm": abs(float(production_row["contour_p95_mm"]) - recorded[1]),
            "contour_max_mm": abs(float(production_row["contour_max_mm"]) - recorded[2]),
        }
        plane_before = pre["stations"][f"{station:.5f}"]["factors"]["4x"][
            "max_abs_plane_residual_mm"
        ]
        plane_after = post["stations"][f"{station:.5f}"]["factors"]["4x"][
            "max_abs_plane_residual_mm"
        ]
        station_result = {
            "sampled_r_over_R": station,
            "physical_plane": {
                "origin_xyz_mm": [0.0, radius * station, 0.0],
                "normal_xyz": [0.0, 1.0, 0.0],
            },
            "plane_residual_before_max_abs_mm": plane_before,
            "plane_residual_after_max_abs_mm": plane_after,
            "plane_target_met": max(plane_before, plane_after) <= PLANE_TARGET_MM,
            "comparisons": headline,
            "production_measurement": production_row,
            "production_repeat_absolute_deltas": production_delta,
            "production_repeat_pass": max(production_delta.values()) <= BASELINE_REPEAT_MM,
            "same_run_vs_retained_raw_4x_pass": headline["T_vs_retained_raw"]["by_factor"]["4x"][
                "sampled_max_mm"
            ] <= BASELINE_REPEAT_MM,
            "section_breps": {"same_run": same_brep, "retained": retained_brep},
        }
        write_json(station_dir / "station_result.json", station_result)
        station_results.append(station_result)
    write_csv(output_dir / "stage_comparison.csv", stage_rows)
    return {
        "same_run_raw_step": file_identity(same_step),
        "same_run_raw_topology": topology,
        "production_measurements": production,
        "stations": station_results,
        "stage_rows": stage_rows,
    }


def sentinel_difference(pre: dict[str, Any], post: dict[str, Any]) -> dict[str, Any]:
    a = pre["sentinels"]
    b = post["sentinels"]
    if len(a) != len(b):
        raise RuntimeError("Pre/post sentinel counts differ")
    deltas = []
    for left, right in zip(a, b):
        if left["u01"] != right["u01"] or left["w01"] != right["w01"]:
            raise RuntimeError("Pre/post sentinel parameters differ")
        delta = np.asarray([right[key] - left[key] for key in ("x_mm", "y_mm", "z_mm")])
        deltas.append(float(np.linalg.norm(delta)))
    return {
        "count": len(deltas),
        "maximum_euclidean_change_mm": max(deltas),
        "rms_euclidean_change_mm": float(np.sqrt(np.mean(np.square(deltas)))),
        "unchanged_at_stage_threshold": max(deltas) <= STAGE_AGREEMENT_MM,
    }


def semantic_diff(left: Any, right: Any, prefix: str = "") -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right)):
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in left or key not in right:
                result.append({"path": path, "before": left.get(key), "after": right.get(key)})
            else:
                result.extend(semantic_diff(left[key], right[key], path))
    elif isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            result.append({"path": prefix, "before_length": len(left), "after_length": len(right)})
        else:
            for index, (a, b) in enumerate(zip(left, right)):
                result.extend(semantic_diff(a, b, f"{prefix}[{index}]"))
    elif left != right:
        result.append({"path": prefix, "before": left, "after": right})
    return result


def run_worker(output_dir: Path) -> int:
    from bladegen.adapters import openvsp_adapter as adapter
    from bladegen.curves.resolver import resolve_blade_spec
    from bladegen.models import BladeSpec, ResolvedBladeSpec
    from bladegen.validation.geometry_validation import validate_openvsp_readback

    output_dir.mkdir(parents=True, exist_ok=True)
    logger = EventLog(output_dir / "diagnostic_events.jsonl")
    started = time.monotonic_ns()
    context: dict[str, Any] = {}
    originals: dict[str, Any] = {}

    def terminate(signum: int, _frame: Any) -> None:
        logger.emit("termination_signal", signal=signum)
        logger.close()
        os._exit(128 + signum)

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    try:
        self_tests = extraction_self_tests()
        write_json(output_dir / "self_tests.json", self_tests)
        if not self_tests["passed"]:
            raise RuntimeError("Live-plane or component-metric self-test failed")
        with logger.operation("canonical_input_preparation"):
            spec = BladeSpec.from_json(JOB_DIR / "blade_spec.json")
            resolved = resolve_blade_spec(spec)
            retained_resolved = ResolvedBladeSpec.model_validate(
                read_json(JOB_DIR / "resolved_blade_spec.json")
            )
            resolved_payload = resolved.model_dump(mode="json")
            retained_payload = retained_resolved.model_dump(mode="json")
            if jsonable(resolved_payload) != jsonable(retained_payload):
                raise RuntimeError("Fresh resolved BladeSpec differs from retained canonical input")
            shutil.copy2(JOB_DIR / "blade_spec.json", output_dir / "input_blade_spec.json")
            write_json(output_dir / "resolved_blade_spec.json", resolved_payload)
            write_json(
                output_dir / "input_identity.json",
                {
                    "input": file_identity(JOB_DIR / "blade_spec.json"),
                    "retained_resolved": file_identity(JOB_DIR / "resolved_blade_spec.json"),
                    "fresh_resolved_canonical_sha256": canonical_hash(resolved_payload),
                    "retained_resolved_canonical_sha256": canonical_hash(retained_payload),
                    "canonical_equal": True,
                },
            )

        originals = {
            "_configure_geometry": adapter._configure_geometry,
            "_configure_step_export": adapter._configure_step_export,
            "_drain_errors": adapter._drain_errors,
        }

        def geometry_wrapper(vsp: Any, prop_id: str, resolved_input: Any) -> None:
            originals["_configure_geometry"](vsp, prop_id, resolved_input)
            context["vsp"] = vsp
            context["prop_id"] = prop_id
            context["after_geometry_update"] = prior_ab._configuration_snapshot(vsp, prop_id)

        def step_wrapper(vsp: Any) -> None:
            originals["_configure_step_export"](vsp)
            context["step_settings"] = prior_ab._step_settings_snapshot(vsp)
            context["before_export_state"] = prior_ab._configuration_snapshot(vsp, context["prop_id"])
            context["before_export_errors"] = originals["_drain_errors"](vsp)
            context["pre"] = live_capture(
                vsp, context["prop_id"], spec, "L_before", output_dir, logger
            )
            context["after_pre_capture_errors"] = originals["_drain_errors"](vsp)

        adapter._configure_geometry = geometry_wrapper
        adapter._configure_step_export = step_wrapper
        with logger.operation("production_build_and_export_baseline"):
            result = adapter.build_and_export(resolved, output_dir)
        vsp = context["vsp"]
        prop_id = context["prop_id"]
        context["post"] = live_capture(
            vsp, prop_id, spec, "L_after", output_dir, logger,
            sentinel_parameters=context["pre"]["sentinel_parameters"],
        )
        context["after_export_state"] = prior_ab._configuration_snapshot(vsp, prop_id)
        context["after_export_errors"] = originals["_drain_errors"](vsp)
        readback_validation = validate_openvsp_readback(resolved, result.readback)
        if not readback_validation["passed"]:
            raise RuntimeError(f"Production readback validation failed: {readback_validation}")
        write_json(output_dir / "adapter_readback.json", result.readback)
        write_json(output_dir / "adapter_readback_validation.json", readback_validation)
        state_changes = semantic_diff(
            context["before_export_state"], context["after_export_state"]
        )
        write_json(
            output_dir / "export_state.json",
            {
                "step_settings": context["step_settings"],
                "before_export": context["before_export_state"],
                "after_export": context["after_export_state"],
                "semantic_changes": state_changes,
                "semantic_change_count": len(state_changes),
                "sentinel_difference": sentinel_difference(context["pre"], context["post"]),
                "api_errors": {
                    "before_capture": context["before_export_errors"],
                    "after_pre_capture": context["after_pre_capture_errors"],
                    "after_export_and_post_capture": context["after_export_errors"],
                },
                "no_update_or_reload_between_captures": True,
            },
        )
        with logger.operation("stage_comparison"):
            comparison = compare_stages(
                output_dir, spec, context["pre"], context["post"], result.step_path, logger
            )
        worker = {
            "status": "COMPLETED",
            "generation_runs": 1,
            "baseline_configuration": "unchanged production, FLAT_END_CAP",
            "adapter_entrypoint": "bladegen.adapters.openvsp_adapter.build_and_export",
            "raw_step": comparison["same_run_raw_step"],
            "vsp3": file_identity(result.vsp3_path),
            "readback_validation_passed": True,
            "state_change_count": len(state_changes),
            "sentinel_difference": sentinel_difference(context["pre"], context["post"]),
            "comparison": comparison,
            "elapsed_seconds": (time.monotonic_ns() - started) / 1e9,
            "completed_at_utc": utc_now(),
        }
        write_json(output_dir / "worker_result.json", worker)
        logger.emit("worker_complete", status="COMPLETED", elapsed_seconds=worker["elapsed_seconds"])
        return 0
    except Exception as exc:  # noqa: BLE001
        failure = {
            "status": "INCOMPLETE",
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
            "elapsed_seconds": (time.monotonic_ns() - started) / 1e9,
            "partial_files": [
                str(path.relative_to(output_dir))
                for path in sorted(output_dir.rglob("*")) if path.is_file()
            ],
        }
        write_json(output_dir / "worker_result.json", failure)
        logger.emit("worker_complete", status="INCOMPLETE", error=failure["error"])
        return 1
    finally:
        for name, value in originals.items():
            setattr(adapter, name, value)
        logger.close()


def source_identity() -> dict[str, Any]:
    runtime_root = Path(os.environ["OPENVSP_ROOT"])
    api_file = runtime_root / "python" / "openvsp" / "openvsp" / "vsp.py"
    source_files = {
        str(path): file_identity(path)
        for relative in OPENVSP_SOURCE_FILES
        if (path := OPENVSP_SOURCE / relative).is_file()
    }
    return {
        "installed_python_api": file_identity(api_file),
        "matching_source_root": str(OPENVSP_SOURCE),
        "matching_source_git_head": command_output(["git", "rev-parse", "HEAD"], OPENVSP_SOURCE),
        "matching_source_git_describe": command_output(
            ["git", "describe", "--tags", "--exact-match", "HEAD"], OPENVSP_SOURCE
        ),
        "source_files": source_files,
        "supported_api": {
            "point": "CompPnt01(geom_id, surf_index, u01, w01)",
            "vector_point": "CompVecPnt01(geom_id, surf_index, u01_vector, w01_vector)",
            "tessellation_parameters": "GetUWTess01(geom_id, surf_index)",
            "units": "OpenVSP model inches converted to global millimeters by x25.4",
        },
        "surface_export_boundary": {
            "normal_api_surface": "Geom::GetSurfPtr -> m_SurfVec while m_ExportMainSurf=false",
            "step_surface": "Vehicle::ExportFile temporarily SetExportPropMainSurf(true); GetSurfPtr -> m_MainSurfVec",
            "conversion": "VspSurf::ToSTEP_BSpline_Quilt -> local PrepCADSurfs copy -> SplitSurfs -> STEP B-spline serialization",
            "post_export": "Vehicle::ExportFile restores SetExportPropMainSurf(false); no Update call",
            "relevant_source_locations": [
                "src/geom_api/VSP_Geom_API.cpp:13726-13748",
                "src/geom_core/Geom.cpp:4937-4965",
                "src/geom_core/Vehicle.cpp:5284-5370",
                "src/geom_core/Vehicle.cpp:8020-8033",
                "src/util/VspSurf.cpp:4337-4385",
                "src/util/VspSurf.cpp:4555-4620",
            ],
        },
        "construction_interval": {
            "source": "src/geom_core/PropGeom.cpp",
            "profile_preparation": "InterpXSecCurve at lines 830+ and call at ~1298",
            "rib_positioning": "PropPositioner::Update; m_ZRotate applied about chord after rake/skew translation",
            "rake_alignment": "m_ZRotate = atan(-RakeCurve.Compdt(r)-AxialCurve.Compdt(r)) at ~1317",
            "loft": "SkinCubicSpline(rib_vec, m_UPseudo, tdisc, false) at ~1358",
        },
    }


def runtime_identity() -> dict[str, Any]:
    import OCP
    import scipy
    from bladegen.adapters.openvsp_adapter import _load_openvsp

    vsp = _load_openvsp()
    version = vsp.GetVSPVersion() if hasattr(vsp, "GetVSPVersion") else "unknown"
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "openvsp": version,
        "openvsp_root": os.environ.get("OPENVSP_ROOT"),
        "ocp": getattr(OCP, "__version__", "unknown"),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
    }


def collect_preflight() -> dict[str, Any]:
    artifacts = {
        "retained_raw_step": file_identity(RETAINED_RAW),
        "retained_final_step": file_identity(RETAINED_FINAL),
        "submitted_spec": file_identity(JOB_DIR / "blade_spec.json"),
        "resolved_spec": file_identity(JOB_DIR / "resolved_blade_spec.json"),
    }
    if artifacts["retained_raw_step"]["sha256"] != EXPECTED_RAW_SHA:
        raise RuntimeError("Retained raw STEP checksum mismatch")
    if artifacts["retained_final_step"]["sha256"] != EXPECTED_FINAL_SHA:
        raise RuntimeError("Retained final STEP checksum mismatch")
    return {
        "captured_at_utc": utc_now(),
        "head": command_output(["git", "rev-parse", "HEAD"]),
        "git_status_porcelain": command_output(["git", "status", "--short"]),
        "tracked_diff_sha256": hashlib.sha256(
            command_output(["git", "diff", "--binary"]).encode()
        ).hexdigest(),
        "artifacts": artifacts,
        "production_source_hashes": {
            relative: sha256_file(ROOT / relative) for relative in PRODUCTION_SOURCES
        },
        "runtime": runtime_identity(),
        "surface_api_source_identity": source_identity(),
    }


def build_plan(output_dir: Path, command: list[str]) -> dict[str, Any]:
    return {
        "experiment_id": "X57-LOC-02",
        "run_id": output_dir.name,
        "mission": "live pre-export surface vs same-run raw STEP localization",
        "selected_sampled_r_over_R": list(STATIONS),
        "physical_plane": "global Y = (diameter_mm/2) * sampled_r_over_R; normal (0,1,0)",
        "stages": {
            "E": "unchanged expected contour from retained submitted BladeSpec",
            "L_before": "native CompVecPnt01 same-plane contour before ExportFile",
            "L_after": "same native evaluator and model state after ExportFile, without Update/reload",
            "T": "OCP physical-plane cut of same-run raw STEP",
        },
        "predeclared_targets": {
            "native_plane_max_abs_residual_mm": PLANE_TARGET_MM,
            "metric_2x_to_4x_sampled_max_stability_mm": STABILITY_TARGET_MM,
            "diagnostic_stage_agreement_sampled_max_mm": STAGE_AGREEMENT_MM,
            "same_run_vs_retained_raw_repeatability_mm": BASELINE_REPEAT_MM,
        },
        "densities": {
            f"{factor}x": {
                "live_and_step_points_per_component_or_edge": factor * (2500 - 1) + 1,
                "expected_points_per_upper_or_lower": factor * (2001 - 1) + 1,
            }
            for factor in FACTORS
        },
        "baseline": {
            "production_path": "bladegen.adapters.openvsp_adapter.build_and_export",
            "root_cap": "FLAT_END_CAP",
            "geometry_and_export_settings": "unchanged",
            "maximum_geometry_generation_runs": 3,
            "planned_initial_runs": 1,
        },
        "conditional_candidate": {
            "status_at_plan_time": "NOT_AUTHORIZED_UNLESS_ONE_SPECIFIC_GENERAL_CORRECTION_IS_JUSTIFIED",
            "maximum": "one candidate plus one repeat",
            "production_patch": False,
        },
        "worker_timeout_seconds": 900,
        "command": command,
        "classification_options": [
            "PRE_EXPORT_DISCREPANCY_LOCALIZED",
            "EXPORT_PATH_DISCREPANCY_LOCALIZED",
            "EXPORT_STATE_CHANGE_DETECTED",
            "MULTIPLE_STAGE_DISCREPANCIES",
            "INCONCLUSIVE_WITH_SPECIFIC_BLOCKER",
        ],
        "qualification_boundaries": {
            "three_cuts_are_full_acceptance": False,
            "original_job_status": "FAILED",
            "retained_internal_validation": "FAIL",
            "external_nasa_fidelity": "UNVERIFIED",
        },
    }


def public_headline(station: dict[str, Any], comparison: str) -> dict[str, Any]:
    return station["comparisons"][comparison]["by_factor"]["4x"]


def classify(worker: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    stations = worker["comparison"]["stations"]
    quality = all(
        item["plane_target_met"]
        and all(value["stable"] for value in item["comparisons"].values())
        for item in stations
    )
    baseline = all(
        item["production_repeat_pass"] and item["same_run_vs_retained_raw_4x_pass"]
        for item in stations
    )
    live_expected = max(public_headline(item, "E_vs_L_before")["sampled_max_mm"] for item in stations)
    live_step = max(public_headline(item, "L_before_vs_T")["sampled_max_mm"] for item in stations)
    mutation = max(public_headline(item, "L_before_vs_L_after")["sampled_max_mm"] for item in stations)
    expected_step = max(public_headline(item, "E_vs_T")["sampled_max_mm"] for item in stations)
    facts = {
        "measurement_quality_passed": quality,
        "baseline_reproduction_passed": baseline,
        "maximum_E_vs_L_before_sampled_max_mm": live_expected,
        "maximum_E_vs_T_sampled_max_mm": expected_step,
        "maximum_L_before_vs_T_sampled_max_mm": live_step,
        "maximum_L_before_vs_L_after_sampled_max_mm": mutation,
        "stage_agreement_threshold_mm": STAGE_AGREEMENT_MM,
    }
    if not quality or not baseline:
        return "INCONCLUSIVE_WITH_SPECIFIC_BLOCKER", facts
    if mutation > STAGE_AGREEMENT_MM:
        return "EXPORT_STATE_CHANGE_DETECTED", facts
    if live_expected > STAGE_AGREEMENT_MM and live_step <= STAGE_AGREEMENT_MM:
        return "PRE_EXPORT_DISCREPANCY_LOCALIZED", facts
    if live_expected <= STAGE_AGREEMENT_MM and expected_step > STAGE_AGREEMENT_MM:
        return "EXPORT_PATH_DISCREPANCY_LOCALIZED", facts
    if live_expected > STAGE_AGREEMENT_MM and live_step > STAGE_AGREEMENT_MM:
        return "MULTIPLE_STAGE_DISCREPANCIES", facts
    return "INCONCLUSIVE_WITH_SPECIFIC_BLOCKER", facts


def source_mechanism(summary: dict[str, Any]) -> dict[str, Any]:
    classification = summary["classification"]
    if classification != "PRE_EXPORT_DISCREPANCY_LOCALIZED":
        return {
            "demonstrated_interval": "see classification and stage comparisons",
            "specific_mechanism": "not established beyond the measured stage boundary",
        }
    spec = read_json(JOB_DIR / "blade_spec.json")
    rake = spec["rake_distribution"]["points"]
    def slopes_at(station: float) -> list[float]:
        result = []
        for a, b in zip(rake, rake[1:]):
            if a["r_over_R"] <= station <= b["r_over_R"]:
                result.append(
                    (b["rake_over_R"] - a["rake_over_R"])
                    / (b["r_over_R"] - a["r_over_R"])
                )
        return result
    return {
        "demonstrated_interval": (
            "production adapter configuration into OpenVSP PropGeom native profile preparation, rib positioning, and loft construction through m_MainSurfVec; "
            "the accepted input/readback is stable, the resulting live surface is already discrepant, and PrepCADSurfs/STEP agrees with it"
        ),
        "matching_source_facts": [
            "PropGeom builds pseudo ribs at the union of section and PCurve controls",
            "InterpXSecCurve prepares each profile",
            "PropPositioner sets m_ZRotate=atan(-RakeCurve.Compdt(r)-AxialCurve.Compdt(r))",
            "PropPositioner applies that rotation about chord during rib placement",
            "SkinCubicSpline constructs m_MainSurfVec[0] from transformed ribs",
            "STEP PrepCADSurfs copies, optionally splits, and serializes that already-built surface",
        ],
        "rake_segment_slopes_near_test_stations": {
            f"{station:.5f}": slopes_at(station) for station in STATIONS
        },
        "mechanism_status": (
            "SOURCE-SUPPORTED HYPOTHESIS, not isolated causal proof: automatic rake-derivative "
            "rib rotation is consistent with the strong inboard physical-plane discrepancy. "
            "This run localizes before export but does not separately capture pre-positioned ribs."
        ),
        "why_no_candidate": (
            "No public adapter flag disables only m_ZRotate while preserving rake/reference-axis "
            "semantics. Altering rake/axial controls would change accepted engineering vectors; "
            "changing expected geometry would weaken the contract. Therefore no specific general, "
            "input-preserving correction is established by this evidence."
        ),
        "one_next_action": (
            "Add a read-only matching-version source probe at PropGeom::UpdateSurf that persists "
            "each transformed pseudo rib immediately before SkinCubicSpline, including m_ZRotate, "
            "then intersect/compare that rib and the completed m_MainSurfVec at r/R=0.22302."
        ),
    }


def render_report(summary: dict[str, Any]) -> str:
    classification = summary["classification"]
    facts = summary["classification_facts"]
    stations = summary.get("stations", [])
    mechanism = summary["mechanism"]
    first = (
        "Yes" if classification == "PRE_EXPORT_DISCREPANCY_LOCALIZED" else
        "No" if classification == "EXPORT_PATH_DISCREPANCY_LOCALIZED" else "Inconclusive"
    )
    mutation_value = facts.get("maximum_L_before_vs_L_after_sampled_max_mm")
    export_change = (
        "No material change was measured"
        if mutation_value is not None and mutation_value <= STAGE_AGREEMENT_MM
        else "Inconclusive because the baseline diagnostic did not complete"
        if mutation_value is None
        else "A material pre/post export difference was measured"
    )
    def display_number(value: Any) -> str:
        return "unavailable" if value is None else f"{float(value):.12g}"
    lines = [
        "# X-57 Surface-to-STEP Decision",
        "",
        "## Four direct answers",
        "",
        f"1. **Is the discrepancy already present on the live pre-export surface?** {first}. Classification: **{classification}**.",
        f"2. **Does export materially change that surface or its represented geometry?** {export_change}. The maximum sampled L_before–L_after and L_before–T values are reported below.",
        f"3. **Which operation/interval is demonstrated responsible?** {mechanism['demonstrated_interval']}",
        f"4. **Is there a tested general correction?** **{summary['candidate_status']}**. {mechanism.get('why_no_candidate', 'No justified candidate was available.')}",
        "",
        "## Decision",
        "",
        f"Evidence-supported classification: **{classification}**.",
        f"Candidate status: **{summary['candidate_status']}**.",
        "",
        "The original product job remains **FAILED**. Its complete internal validation remains **FAIL**. External NASA geometry fidelity remains **UNVERIFIED**.",
        "",
        "## Stage comparison (4x)",
        "",
        "All maxima are sampled maxima, not continuous Hausdorff bounds. Values use the component-preserving bidirectional equal-direction arc-weighted metric without registration or scaling.",
        "",
        "| sampled r/R | E–L_before max mm | E–T max mm | L_before–T max mm | L_before–L_after max mm | L_after–T max mm | plane residual max mm | stable |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in stations:
        def value(name: str) -> float:
            return item["comparisons"][name]["by_factor"]["4x"]["sampled_max_mm"]
        stable = all(entry["stable"] for entry in item["comparisons"].values())
        lines.append(
            f"| {item['sampled_r_over_R']:.5f} | {value('E_vs_L_before'):.9g} | "
            f"{value('E_vs_T'):.9g} | {value('L_before_vs_T'):.9g} | "
            f"{value('L_before_vs_L_after'):.9g} | {value('L_after_vs_T'):.9g} | "
            f"{max(item['plane_residual_before_max_abs_mm'], item['plane_residual_after_max_abs_mm']):.9g} | {stable} |"
        )
    lines.extend(
        [
            "",
            "Predeclared targets: native plane residual <= 1e-6 mm; 2x→4x sampled-max stability <= 1e-4 mm; diagnostic stage agreement <= 0.001 mm. These are diagnostic quality thresholds, not product tolerances.",
            "",
            "## Baseline reproduction and export state",
            "",
            f"- Same-run baseline reproduced retained raw geometry and recorded production metrics at all three planes: **{facts.get('baseline_reproduction_passed')}** (0.0001 mm target).",
            f"- Maximum L_before–L_after sampled difference: `{display_number(facts.get('maximum_L_before_vs_L_after_sampled_max_mm'))}` mm.",
            f"- Maximum L_before–T sampled difference: `{display_number(facts.get('maximum_L_before_vs_T_sampled_max_mm'))}` mm.",
            f"- Semantic parameter/profile state changes across export: `{summary.get('export_state_change_count')}`.",
            f"- Sentinel maximum coordinate change: `{display_number(summary.get('sentinel_max_change_mm'))}` mm.",
            "- The baseline used the unchanged production adapter, original FLAT root/tip caps, and unchanged STEP settings.",
            "",
            "## Native-surface method and API boundary",
            "",
            "`CompVecPnt01` evaluated the actual generated prop surface. Each physical section solved `S(u,w).Y = R·station`; the native root topology was scanned on a 129x257 grid; constant-u was tested across 2,049 w samples and, when rejected, u(w) was solved by bracketed vector bisection. The retained CSVs include u/w, surface index, XYZ, and residual for every 4x live point.",
            "",
            "The stopped instrumentation attempt `a93b281c_20261014T152216Z` is preserved separately: it measured a 1.533993154 mm whole-curve plane miss and correctly rejected the original constant-u assumption before export. It is not combined with the successful baseline result.",
            "",
            "OpenVSP model coordinates are inches and were converted to the validator's global millimetre frame by exactly 25.4. The normal API path returns `m_SurfVec`; STEP export temporarily returns `m_MainSurfVec`, sends a local copy through `PrepCADSurfs`/surface splitting, writes STEP, then restores the flag without `Update`.",
            "",
            "## Source interval and correction gate",
            "",
        ]
    )
    for fact in mechanism.get("matching_source_facts", []):
        lines.append(f"- {fact}.")
    lines.extend(
        [
            "",
            mechanism.get("mechanism_status", ""),
            "",
            "No candidate geometry run was made because a general input-preserving correction was not established. This avoids changing rake, auxiliary PCurves, expected geometry, or acceptance policy merely to fit three cuts.",
            "",
            "## Smallest justified next action",
            "",
            mechanism.get("one_next_action", "Review the exact measured blocker."),
            "",
            "## Scope and evidence",
            "",
            f"- Tested Git HEAD: `{summary['head']}`.",
            f"- Worker status/runtime: `{summary['worker_status']}` / `{summary.get('worker_elapsed_seconds')}` seconds.",
            f"- Geometry-generation runs: `{summary.get('generation_runs')}` (baseline only).",
            "- Production source was not patched; no UI, timeout, topology, cap, or NASA comparison work was performed.",
            "- Exact commands, runtime/source identities, self-tests, station coordinates, BReps, overlays, residuals, timings, and SHA-256 manifest are retained beside this report.",
            "",
        ]
    )
    return "\n".join(lines)


def timing_rows(events_path: Path) -> list[dict[str, Any]]:
    starts: dict[tuple[str, str], dict[str, Any]] = {}
    rows = []
    if not events_path.exists():
        return rows
    for line in events_path.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        if item["event"] not in {"operation_start", "operation_end"}:
            continue
        context = json.dumps(
            {k: v for k, v in item.items() if k not in {
                "sequence", "event", "utc", "monotonic_ns", "since_start_seconds",
                "elapsed_seconds", "status", "error",
            }}, sort_keys=True,
        )
        key = (item["operation"], context)
        if item["event"] == "operation_start":
            starts[key] = item
        else:
            start = starts.pop(key, None)
            rows.append(
                {
                    "operation": item["operation"],
                    "status": item.get("status"),
                    "elapsed_seconds": item.get("elapsed_seconds"),
                    "start_utc": start.get("utc") if start else "",
                    "end_utc": item.get("utc"),
                    "context": context,
                }
            )
    for item in starts.values():
        rows.append(
            {
                "operation": item["operation"], "status": "INCOMPLETE",
                "elapsed_seconds": "", "start_utc": item["utc"], "end_utc": "",
                "context": json.dumps(item, sort_keys=True),
            }
        )
    return rows


def finalize(output_dir: Path, preflight: dict[str, Any], launcher: dict[str, Any]) -> dict[str, Any]:
    worker = read_json(output_dir / "worker_result.json")
    if worker.get("status") == "COMPLETED":
        classification, facts = classify(worker)
        export_state = read_json(output_dir / "export_state.json")
        summary = {
            "experiment_id": "X57-LOC-02",
            "run_id": output_dir.name,
            "classification": classification,
            "classification_facts": facts,
            "candidate_status": "NOT_TESTED",
            "mechanism": {},
            "stations": worker["comparison"]["stations"],
            "head": preflight["head"],
            "dirty_worktree": bool(preflight["git_status_porcelain"]),
            "worker_status": worker["status"],
            "worker_elapsed_seconds": worker["elapsed_seconds"],
            "generation_runs": worker["generation_runs"],
            "export_state_change_count": export_state["semantic_change_count"],
            "sentinel_max_change_mm": export_state["sentinel_difference"]["maximum_euclidean_change_mm"],
            "original_product_job": "FAILED",
            "complete_internal_validation": "FAIL",
            "external_nasa_fidelity": "UNVERIFIED",
            "production_patch": False,
            "launcher": launcher,
        }
        summary["mechanism"] = source_mechanism(summary)
    else:
        summary = {
            "experiment_id": "X57-LOC-02",
            "run_id": output_dir.name,
            "classification": "INCONCLUSIVE_WITH_SPECIFIC_BLOCKER",
            "classification_facts": {"blocker": worker.get("error")},
            "candidate_status": "NOT_TESTED",
            "mechanism": {
                "demonstrated_interval": "not established because diagnostic worker was incomplete",
                "why_no_candidate": worker.get("error", "worker incomplete"),
                "one_next_action": "Resolve the recorded worker error without changing geometry inputs, then rerun the single baseline.",
            },
            "stations": [],
            "head": preflight["head"],
            "worker_status": worker.get("status"),
            "worker_elapsed_seconds": worker.get("elapsed_seconds"),
            "generation_runs": 1 if (output_dir / "blade_openvsp.step").exists() else 0,
            "export_state_change_count": None,
            "sentinel_max_change_mm": None,
            "original_product_job": "FAILED",
            "complete_internal_validation": "FAIL",
            "external_nasa_fidelity": "UNVERIFIED",
            "production_patch": False,
            "launcher": launcher,
        }
    write_json(output_dir / "decision_summary.json", summary)
    write_text(output_dir / "X57_SURFACE_TO_STEP_DECISION.md", render_report(summary))
    write_csv(output_dir / "timings.csv", timing_rows(output_dir / "diagnostic_events.jsonl"))
    return summary


def manifest_and_zip(output_dir: Path) -> dict[str, Any]:
    zip_path = output_dir.with_suffix(".zip")
    excluded = {"evidence_manifest.json", "bundle_result.json", zip_path.name}
    files = [
        path for path in sorted(output_dir.rglob("*"))
        if path.is_file() and path.name not in excluded
    ]
    manifest = {
        "created_at_utc": utc_now(),
        "root": str(output_dir.resolve()),
        "files": [
            {
                "relative_path": str(path.relative_to(output_dir)),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
        ],
        "external_large_artifacts_not_duplicated": [
            file_identity(RETAINED_RAW), file_identity(RETAINED_FINAL)
        ],
    }
    write_json(output_dir / "evidence_manifest.json", manifest)
    archive_files = files + [output_dir / "evidence_manifest.json"]
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in archive_files:
            archive.write(path, arcname=str(Path(output_dir.name) / path.relative_to(output_dir)))
    archive_test = None
    with zipfile.ZipFile(zip_path) as archive:
        archive_test = archive.testzip()
    result = {
        "zip": file_identity(zip_path),
        "member_count": len(archive_files),
        "testzip_first_bad_member": archive_test,
        "verified": archive_test is None,
    }
    write_json(output_dir / "bundle_result.json", result)
    return result


def run_supervisor(output_root: Path) -> int:
    run_id = f"a93b281c_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    output_dir = output_root / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    preflight = collect_preflight()
    write_json(output_dir / "preflight_evidence.json", preflight)
    command = [
        sys.executable, str(Path(__file__).resolve()), "worker", "--output-dir", str(output_dir)
    ]
    write_json(output_dir / "plan.json", build_plan(output_dir, command))
    write_text(
        output_dir / "commands.txt",
        "Environment: source scripts/openvsp_env.sh\n"
        f"Supervisor: {' '.join(sys.argv)}\n"
        f"Worker (external timeout 900s): {' '.join(command)}\n",
    )
    started = time.monotonic_ns()
    process = subprocess.Popen(
        command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, start_new_session=True,
    )
    timed_out = False
    output = ""
    try:
        output, _ = process.communicate(timeout=900)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGTERM)
        try:
            tail, _ = process.communicate(timeout=10)
            output += tail
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            tail, _ = process.communicate()
            output += tail
    elapsed = (time.monotonic_ns() - started) / 1e9
    write_text(output_dir / "diagnostic.log", output)
    if not (output_dir / "worker_result.json").exists():
        write_json(
            output_dir / "worker_result.json",
            {
                "status": "INCOMPLETE",
                "error": "external 900-second timeout" if timed_out else "worker exited without result",
                "returncode": process.returncode,
                "elapsed_seconds": elapsed,
            },
        )
    launcher = {
        "command": command,
        "returncode": process.returncode,
        "timed_out": timed_out,
        "timeout_seconds": 900,
        "elapsed_seconds": elapsed,
        "process_group_terminated_on_timeout": timed_out,
    }
    write_json(output_dir / "launcher_result.json", launcher)
    summary = finalize(output_dir, preflight, launcher)
    post = {
        "captured_at_utc": utc_now(),
        "git_status_porcelain": command_output(["git", "status", "--short"]),
        "production_source_hashes": {
            relative: sha256_file(ROOT / relative) for relative in PRODUCTION_SOURCES
        },
        "retained_artifacts": {
            "raw": file_identity(RETAINED_RAW), "final": file_identity(RETAINED_FINAL),
        },
    }
    post["production_sources_unchanged"] = (
        post["production_source_hashes"] == preflight["production_source_hashes"]
    )
    post["retained_artifacts_unchanged"] = (
        post["retained_artifacts"]["raw"]["sha256"] == EXPECTED_RAW_SHA
        and post["retained_artifacts"]["final"]["sha256"] == EXPECTED_FINAL_SHA
    )
    write_json(output_dir / "integrity_recheck.json", post)
    shutil.copy2(Path(__file__).resolve(), output_dir / Path(__file__).name)
    bundle = manifest_and_zip(output_dir)
    print(json.dumps({
        "output_dir": str(output_dir),
        "classification": summary["classification"],
        "candidate_status": summary["candidate_status"],
        "bundle": bundle,
    }, indent=2), flush=True)
    return 0 if summary["worker_status"] == "COMPLETED" and bundle["verified"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode")
    supervise = sub.add_parser("supervise")
    supervise.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    worker = sub.add_parser("worker")
    worker.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.mode in (None, "supervise"):
        return run_supervisor(getattr(args, "output_root", OUTPUT_ROOT))
    if args.mode == "worker":
        return run_worker(args.output_dir)
    raise AssertionError(args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
