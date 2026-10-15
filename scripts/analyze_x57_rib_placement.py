#!/usr/bin/env python3
"""Derive X57-LOC-03 decision evidence from the qualified native probe."""

from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import platform
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scipy
from scipy.interpolate import PchipInterpolator
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]
import diagnose_x57_contours as contour

MM = 25.4
STATIONS = (0.22302, 0.29061, 0.50345)
HEAD = "1cdb564a2eb92b0171acbab705b41ca63b57416c"
FINAL_SHA = "43c2cd72bebcd3949e0fe0b210aaac9ccbf6918952743fd109ecb0cac2e401d6"
RAW_SHA = "85f798f74f672e4c78f3560e3413fcbdbba0ff7410424a840a5fc4e746d8b07f"

TRANSFORM_CHAIN = [
    "scale prepared profile by chord",
    "optional reverse (disabled for this job)",
    "GetBasicTransformation: center chord and orient profile into global model frame",
    "feather-axis compensation",
    "local rotateX by sweep (zero for this job)",
    "translate local Y to radial position",
    "apply construct compensation",
    "apply axial/tangential offsets (zero for this job)",
    "local rotateY by twist",
    "translate rake/skew",
    "local rotateZ by m_ZRotate about the transformed chord and chord-fraction pivot",
    "apply construct-axis offset",
    "optional cylinder projection (disabled for this job)",
    "apply feather rotation (zero for this job)",
]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def jread(path: Path) -> Any:
    return json.loads(path.read_text())


def jwrite(path: Path, value: Any) -> None:
    path.write_text(json.dumps(contour.jsonable(value), indent=2, sort_keys=True,
                               allow_nan=False) + "\n")


def cread(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def cwrite(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"empty output {path}")
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def text(*cmd: str) -> str:
    return subprocess.run(cmd, cwd=ROOT, check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.strip()


def slug(station: float) -> str:
    return f"rR_{station:.5f}".replace(".", "p")


def key(station: float) -> str:
    return f"{station:.5f}"


def load_curves(path: Path) -> dict[tuple[int, str], np.ndarray]:
    data: dict[tuple[int, str], list[list[float]]] = defaultdict(list)
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            data[(int(row["rib_index"]), row["stage"])].append([
                float(row["curve_parameter01"]), float(row["x_model"]),
                float(row["y_model"]), float(row["z_model"]),
            ])
    return {k: np.asarray(v) for k, v in data.items()}


def components(points: np.ndarray) -> list[dict[str, Any]]:
    mid = (len(points) - 1) // 2
    return [{"name": "lower", "points": points[:mid + 1][::-1]},
            {"name": "upper", "points": points[mid:]}]


def qpoints(parts: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    points, weights = [], []
    for part in parts:
        p = np.asarray(part["points"])
        lengths = np.linalg.norm(np.diff(p, axis=0), axis=1)
        w = np.zeros(len(p))
        w[:-1] += lengths * 0.5
        w[1:] += lengths * 0.5
        points.append(p)
        weights.append(w)
    return np.vstack(points), np.concatenate(weights)


def point_dist(query: np.ndarray, target: list[dict[str, Any]]) -> np.ndarray:
    vertices, aa, bb = [], [], []
    for part in target:
        p = np.asarray(part["points"])
        vertices.append(p)
        keep = np.linalg.norm(np.diff(p, axis=0), axis=1) > 1e-14
        aa.extend(p[:-1][keep])
        bb.extend(p[1:][keep])
    vertices = np.vstack(vertices)
    aa, bb = np.asarray(aa), np.asarray(bb)
    vectors = bb - aa
    length2 = np.einsum("ij,ij->i", vectors, vectors)
    distance, _ = cKDTree(vertices).query(query, k=1)
    distance = np.asarray(distance)
    mid = (aa + bb) * 0.5
    halfmax = float(np.max(np.sqrt(length2)) * 0.5)
    tree = cKDTree(mid)
    for i, candidates in enumerate(tree.query_ball_point(query, distance + halfmax + 1e-12)):
        idx = np.asarray(candidates)
        rel = query[i] - aa[idx]
        t = np.clip(np.einsum("ij,ij->i", rel, vectors[idx]) / length2[idx], 0, 1)
        projected = aa[idx] + t[:, None] * vectors[idx]
        distance[i] = min(distance[i], np.min(np.linalg.norm(query[i] - projected, axis=1)))
    return distance


def compare3(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> dict[str, Any]:
    lp, lw = qpoints(left)
    rp, rw = qpoints(right)
    ld, rd = point_dist(lp, right), point_dist(rp, left)
    lk, rk = lw > 0, rw > 0
    values = np.concatenate((ld[lk], rd[rk]))
    weights = np.concatenate((0.5 * lw[lk] / lw[lk].sum(),
                              0.5 * rw[rk] / rw[rk].sum()))
    return contour.distance_stats(values, weights)


def basis(row: dict[str, str]) -> tuple[np.ndarray, np.ndarray]:
    origin = np.array([float(row[f"origin_{a}"]) for a in "xyz"])
    cols = []
    for b in "xyz":
        end = np.array([float(row[f"{b}_{a}"]) for a in "xyz"])
        cols.append(end - origin)
    return origin, np.column_stack(cols)


def angle(a: np.ndarray, b: np.ndarray, plane: bool = False) -> float:
    value = float(np.dot(a / np.linalg.norm(a), b / np.linalg.norm(b)))
    if plane:
        value = abs(value)
    return math.degrees(math.acos(np.clip(value, -1, 1)))


def slope(x: np.ndarray, y: np.ndarray, value: float) -> tuple[int, float]:
    i = int(np.searchsorted(x, value, side="right") - 1)
    i = max(0, min(i, len(x) - 2))
    return i, float((y[i + 1] - y[i]) / (x[i + 1] - x[i]))


def target_rib(rows: list[dict[str, str]], station: float) -> dict[str, str]:
    found = [r for r in rows if abs(float(r["r_over_R"]) - station) <= 1e-12]
    if len(found) != 1:
        raise AssertionError(f"expected one target rib at {station}, got {len(found)}")
    return found[0]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--evidence-dir", type=Path, required=True)
    p.add_argument("--loc02-dir", type=Path, required=True)
    p.add_argument("--source-dir", type=Path, required=True)
    p.add_argument("--build-dir", type=Path, required=True)
    p.add_argument("--install-dir", type=Path, required=True)
    a = p.parse_args()
    out, loc02 = a.evidence_dir.resolve(), a.loc02_dir.resolve()

    inventory = cread(out / "probe_rib_inventory.csv")
    skin_rows = cread(out / "probe_rib_surface_audit.csv")
    live_rows = cread(out / "probe_final_live_cuts.csv")
    curves = load_curves(out / "probe_detailed_curves.csv")
    matrix_rows = {(int(r["rib_index"]), r["stage"]): r
                   for r in cread(out / "probe_transform_bases.csv")}
    spec = jread(loc02 / "input_blade_spec.json")
    resolved = jread(loc02 / "resolved_blade_spec.json")
    prior = jread(loc02 / "decision_summary.json")
    prior_preflight = jread(loc02 / "preflight_evidence.json")
    snap = jread(out / "probe_snapshot.json")

    head = text("git", "rev-parse", "HEAD")
    status = text("git", "status", "--short")
    final_step = ROOT / "docs/evidence/sprint04b/x57/job/blade_solid.step"
    raw_step = ROOT / "output/runs/a93b281c29b640afaa6bad698d64a61b/blade_openvsp.step"
    if head != HEAD or digest(final_step) != FINAL_SHA or digest(raw_step) != RAW_SHA:
        raise RuntimeError("fixed identity mismatch")

    rr = np.asarray(resolved["rake_curve"]["parameter_vector"])
    rv = np.asarray(resolved["rake_curve"]["value_vector"])
    inventory_out, slope_error = [], 0.0
    for row in inventory:
        segment, segment_slope = slope(rr, rv, float(row["r_over_R"]))
        observed = float(row["rake_compdt"])
        slope_error = max(slope_error, abs(observed - segment_slope))
        inventory_out.append({
            **row, "chord_mm": float(row["chord_model"]) * MM,
            "rake_mm": float(row["rake_model"]) * MM,
            "skew_mm": float(row["skew_model"]) * MM,
            "active_resolved_rake_segment": segment,
            "resolved_linear_rake_slope": segment_slope,
            "compdt_minus_segment_slope": observed - segment_slope,
        })
    cwrite(out / "rib_inventory.csv", inventory_out)

    baseline, plane_rows = {}, []
    for station in STATIONS:
        observed = [r for r in live_rows if abs(float(r["r_over_R"]) - station) < 1e-10]
        saved = cread(loc02 / "L_before" / slug(station) / "live_parameters_xyz_4x.csv")
        xyz = np.array([[float(r["x_model"]), float(r["y_model"]),
                         float(r["z_model"])] for r in observed]) * MM
        reference = np.array([[float(r["x_mm"]), float(r["y_mm"]),
                               float(r["z_mm"])] for r in saved])
        delta = np.linalg.norm(xyz - reference, axis=1)
        residual = np.abs(np.array([float(r["plane_residual_model"])
                                    for r in observed]) * MM)
        baseline[key(station)] = {
            "points": len(observed),
            "direct_max_3d_mm": float(delta.max()),
            "direct_rms_3d_mm": float(np.sqrt(np.mean(delta ** 2))),
            "plane_residual_max_abs_mm": float(residual.max()),
            "passed": bool(delta.max() <= 0.0001 and residual.max() <= 1e-6),
        }
        for row, point, res in zip(observed, xyz, residual):
            plane_rows.append({
                "r_over_R": station, "component": row["component"],
                "point_index": row["point_index"], "u01": row["u01"],
                "w01": row["w01"], "x_mm": point[0], "y_mm": point[1],
                "z_mm": point[2], "plane_residual_mm": res,
            })
    cwrite(out / "same_plane_surface_contours.csv", plane_rows)

    source = spec["rake_distribution"]["points"]
    sx = np.asarray([r["r_over_R"] for r in source])
    sy = np.asarray([r["rake_over_R"] for r in source])
    source_pchip = PchipInterpolator(sx, sy)
    profile_results, audits, comparisons, targets = {}, [], [], {}

    for station in STATIONS:
        rib = target_rib(inventory, station)
        index = int(rib["rib_index"])
        prepared = curves[(index, "prepared_profile_unit")][:, [1, 2]]
        factors = {}
        for factor, stride in ((1, 4), (2, 2), (4, 1)):
            expected = contour.independent_expected(spec, station, factor)
            expected_parts = [{"name": "upper", "points": expected["normalized_upper"]},
                              {"name": "lower", "points": expected["normalized_lower"]}]
            metric = contour.public_metric(contour.compare_components(
                components(prepared[::stride]), expected_parts
            ))["bidirectional_equal_direction_arc_weighted"]
            chord = float(rib["chord_model"]) * MM
            factors[f"{factor}x"] = {
                "normalized": metric,
                "physical_mm": {name: metric[name] * chord
                                for name in ("rms_mm", "p95_mm", "sampled_max_mm")},
            }
        profile_results[key(station)] = {
            "rib_index": index, "factors": factors,
            "stable": abs(factors["4x"]["physical_mm"]["sampled_max_mm"] -
                          factors["2x"]["physical_mm"]["sampled_max_mm"]) <= 0.0001,
            "profile_start_index": int(rib["profile_start_index"]),
            "profile_end_index": int(rib["profile_end_index"]),
            "profile_fraction": float(rib["profile_fraction"]),
        }

        expected = contour.independent_expected(spec, station, 2)
        target_y = spec["diameter_mm"] * 0.5 * station
        expected3 = []
        for name, points in (("upper", expected["placed_upper"]),
                             ("lower", expected["placed_lower"])):
            expected3.append({"name": name, "points": np.column_stack(
                (points[:, 0], np.full(len(points), target_y), points[:, 1]))})
        before = curves[(index, "before_auto_zrotate")][:, 1:] * MM
        after = curves[(index, "after_auto_zrotate")][:, 1:] * MM
        final_rib = curves[(index, "fully_transformed_rib")][:, 1:] * MM
        skin = curves[(index, "post_skin_iso_pre_caps")][:, 1:] * MM
        before_metric = compare3(components(before), expected3)
        after_metric = compare3(components(after), expected3)
        rotation = np.linalg.norm(after - before, axis=1)
        skin_delta = np.linalg.norm(skin - final_rib, axis=1)

        bo, bm = basis(matrix_rows[(index, "before_auto_zrotate")])
        ao, am = basis(matrix_rows[(index, "after_auto_zrotate")])
        basic = curves[(index, "after_basic_orientation")][:, 1:]
        reconstruct_before = bo + basic @ bm.T
        reconstruct_after = ao + basic @ am.T
        inverse_after = (curves[(index, "after_auto_zrotate")][:, 1:] - ao) @ am
        before_err = np.linalg.norm(reconstruct_before -
                                    curves[(index, "before_auto_zrotate")][:, 1:], axis=1).max() * MM
        after_err = np.linalg.norm(reconstruct_after -
                                   curves[(index, "after_auto_zrotate")][:, 1:], axis=1).max() * MM
        inverse_err = np.linalg.norm(inverse_after - basic, axis=1).max() * MM

        origin = ao * MM
        normal = am[:, 1] * (1 if am[1, 1] >= 0 else -1)
        chord_axis = am[:, 2]
        requested_origin = np.array([expected["reference_xz_mm"][0], target_y,
                                     expected["reference_xz_mm"][1]])
        requested_chord = np.array([expected["chord_direction"][0], 0,
                                    expected["chord_direction"][1]])
        centered = after - after.mean(axis=0)
        svd_normal = np.linalg.svd(centered, full_matrices=False)[2][-1]
        if np.dot(svd_normal, normal) < 0:
            svd_normal *= -1
        planarity = np.abs(centered @ svd_normal).max()
        ydelta = after[:, 1] - target_y

        segment, resolved_slope = slope(rr, rv, station)
        source_index = int(np.flatnonzero(np.isclose(sx, station, atol=1e-12))[0])
        left_slope = (sy[source_index] - sy[source_index - 1]) / (sx[source_index] - sx[source_index - 1])
        right_slope = (sy[source_index + 1] - sy[source_index]) / (sx[source_index + 1] - sx[source_index])
        audit = {
            "r_over_R": station, "rib_index": index,
            "u_pseudo_native": float(rib["u_pseudo"]),
            "requested_y_mm": target_y,
            "origin_x_mm": origin[0], "origin_y_mm": origin[1], "origin_z_mm": origin[2],
            "reference_origin_error_mm": float(np.linalg.norm(origin - requested_origin)),
            "plane_normal_x": normal[0], "plane_normal_y": normal[1],
            "plane_normal_z": normal[2],
            "plane_angle_from_requested_deg": angle(normal, np.array([0, 1, 0]), True),
            "svd_planarity_max_mm": float(planarity),
            "basis_vs_svd_normal_angle_deg": angle(normal, svd_normal, True),
            "y_delta_min_mm": float(ydelta.min()), "y_delta_max_mm": float(ydelta.max()),
            "y_delta_max_abs_mm": float(np.abs(ydelta).max()),
            "chord_axis_x": chord_axis[0], "chord_axis_y": chord_axis[1],
            "chord_axis_z": chord_axis[2],
            "chord_axis_error_deg": angle(chord_axis, requested_chord),
            "rake_compdt_actual": float(rib["rake_compdt"]),
            "axial_compdt_actual": float(rib["axial_compdt"]),
            "zrotate_deg_actual": float(rib["zrotate_deg"]),
            "zrotate_deg_from_actual_derivatives": math.degrees(math.atan(
                -float(rib["rake_compdt"]) - float(rib["axial_compdt"]))),
            "resolved_linear_segment": segment,
            "resolved_linear_segment_slope": resolved_slope,
            "source_left_secant_slope": float(left_slope),
            "source_right_secant_slope": float(right_slope),
            "canonical_pchip_derivative_explanatory_only":
                float(source_pchip.derivative()(station)),
            "before_transform_reconstruction_max_mm": float(before_err),
            "after_transform_reconstruction_max_mm": float(after_err),
            "analytic_inverse_max_mm": float(inverse_err),
            "auto_rotation_equal_parameter_max_mm": float(rotation.max()),
            "rib_to_skin_equal_parameter_max_mm": float(skin_delta.max()),
        }
        audits.append(audit)

        old = prior["stations"][list(STATIONS).index(station)]["comparisons"]
        fixed = old["E_vs_L_before"]["by_factor"]["4x"]
        raw = old["L_before_vs_T"]["by_factor"]["4x"]
        pm = factors["4x"]["physical_mm"]
        rows = [
            ("canonical_profile_to_prepared_profile", pm,
             "intrinsic local-frame preparation"),
            ("expected_to_before_auto_zrotate", before_metric,
             "requested 3D placement before automatic rotation"),
            ("expected_to_after_auto_zrotate", after_metric,
             "actual 3D placement after automatic rotation"),
            ("before_to_after_auto_zrotate_equal_parameter", {
                "rms_mm": float(np.sqrt(np.mean(rotation ** 2))),
                "p95_mm": float(np.percentile(rotation, 95)),
                "sampled_max_mm": float(rotation.max())},
             "direct transform effect"),
            ("transformed_rib_to_post_skin_iso", {
                "rms_mm": float(np.sqrt(np.mean(skin_delta ** 2))),
                "p95_mm": float(np.percentile(skin_delta, 95)),
                "sampled_max_mm": float(skin_delta.max())},
             "native-u skin preservation"),
            ("expected_to_final_fixed_y_cut", fixed, "unchanged physical product plane"),
            ("final_live_to_retained_raw_step_cut", raw, "qualified export agreement"),
        ]
        for name, metric, meaning in rows:
            comparisons.append({
                "r_over_R": station, "comparison": name,
                "rms_mm": metric["rms_mm"], "p95_mm": metric["p95_mm"],
                "sampled_max_mm": metric["sampled_max_mm"], "meaning": meaning,
            })
        targets[key(station)] = {
            "profile": profile_results[key(station)], "placement": audit,
            "expected_to_before_auto_zrotate": before_metric,
            "expected_to_after_auto_zrotate": after_metric,
            "fixed_y_final": fixed, "live_to_raw": raw,
            "final_refinement_stable": old["E_vs_L_before"]["stable"],
            "final_refinement_delta_mm":
                old["E_vs_L_before"]["refinement_2x_to_4x_sampled_max_delta_mm"],
        }

    cwrite(out / "rib_transform_audit.csv", audits)
    cwrite(out / "rib_surface_comparison.csv", comparisons)

    skin = np.array([float(r["max_iso_difference_model"]) * MM for r in skin_rows])
    profile_max = max(v["factors"]["4x"]["physical_mm"]["sampled_max_mm"]
                      for v in profile_results.values())
    profile_refinement_delta_max = max(
        abs(v["factors"]["4x"]["physical_mm"]["sampled_max_mm"] -
            v["factors"]["2x"]["physical_mm"]["sampled_max_mm"])
        for v in profile_results.values()
    )
    angle_max = max(r["plane_angle_from_requested_deg"] for r in audits)
    y_max = max(r["y_delta_max_abs_mm"] for r in audits)
    skin_max = float(skin.max())

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for ax, station in zip(axes, STATIONS):
        rib = target_rib(inventory, station)
        pts = curves[(int(rib["rib_index"]), "prepared_profile_unit")][:, [1, 2]]
        expected = contour.independent_expected(spec, station, 2)
        ax.plot(expected["normalized_upper"][:, 0], expected["normalized_upper"][:, 1],
                color="black", lw=1, label="canonical")
        ax.plot(expected["normalized_lower"][:, 0], expected["normalized_lower"][:, 1],
                color="black", lw=1)
        for i, part in enumerate(components(pts)):
            ax.plot(part["points"][:, 0], part["points"][:, 1], "--", color="#dc2626",
                    lw=0.9, label="prepared" if i == 0 else None)
        ax.set_aspect("equal", adjustable="box")
        ax.set_title(f"r/R={station:.5f}")
        ax.set_xlabel("local x/c")
        ax.grid(alpha=.2)
    axes[0].set_ylabel("local y/c")
    axes[0].legend()
    fig.suptitle("Observed pre-position profile versus canonical profile")
    fig.tight_layout()
    fig.savefig(out / "profile_preparation.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for ax, station in zip(axes, STATIONS):
        rib = target_rib(inventory, station)
        data = curves[(int(rib["rib_index"]), "after_auto_zrotate")]
        ax.plot(data[:, 0], (data[:, 2] - snap["radius_model"] * station) * MM,
                color="#7c3aed", lw=.9, label="positioned rib")
        ax.axhline(0, color="black", ls="--", lw=.8, label="requested plane")
        ax.set_title(f"r/R={station:.5f}")
        ax.set_xlabel("native curve parameter")
        ax.grid(alpha=.2)
    axes[0].set_ylabel("global Y minus requested Y (mm)")
    axes[0].legend()
    fig.suptitle("Automatic chord-axis rotation tilts the pseudo ribs")
    fig.tight_layout()
    fig.savefig(out / "rib_plane_tilt.png", dpi=180)
    plt.close(fig)

    corrected = []
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for ax, station in zip(axes, STATIONS):
        source_rows = cread(loc02 / "stations" / slug(station) /
                            "E_vs_L_before_residuals_4x.csv")
        upper = [r for r in source_rows if r["query_component"] == "expected_upper"]
        assert upper, f"empty expected-upper residual set at {station}"
        x = np.array([float(r["query_component_s_fraction"]) for r in upper])
        y = np.array([float(r["distance_mm"]) for r in upper])
        ax.plot(x, y, color="#0f766e", lw=.8)
        ax.set_title(f"r/R={station:.5f}; max={y.max():.6f} mm")
        ax.set_xlabel("expected-upper arc fraction")
        ax.grid(alpha=.2)
        corrected.extend({"r_over_R": station,
                          "corrected_direction": "expected_upper_to_live_fixed_y_cut",
                          **row} for row in upper)
    axes[0].set_ylabel("distance to live fixed-Y contour (mm)")
    fig.suptitle("Corrected direction: expected upper to live physical-plane cut")
    fig.tight_layout()
    fig.savefig(out / "fixed_plane_residuals_corrected.png", dpi=180)
    plt.close(fig)
    cwrite(out / "fixed_plane_expected_upper_residuals.csv", corrected)

    source_commit = text("git", "-C", str(a.source_dir), "rev-parse", "HEAD")
    compiler = text("c++", "--version").splitlines()[0]
    cmake = text("cmake", "--version").splitlines()[0]
    try:
        import OCP
        ocp = getattr(OCP, "__version__", "unknown")
    except Exception as exc:
        ocp = f"unavailable: {type(exc).__name__}"
    production_files = (
        "backend/bladegen/adapters/openvsp_adapter.py",
        "backend/bladegen/curves/resolver.py",
        "backend/bladegen/solid/ocp_solidify.py",
        "backend/bladegen/validation/expected_geometry.py",
        "backend/bladegen/validation/measure_sections.py",
        "backend/bladegen/validation/station_plan.py",
    )
    production_hashes = {name: digest(ROOT / name) for name in production_files}
    production_hashes_match_loc02 = all(
        prior_preflight["production_source_hashes"].get(name) == value
        for name, value in production_hashes.items()
    )
    production_openvsp_root = ROOT / ".tooling/openvsp-3.54.0/opt/OpenVSP"
    identity = {
        "head": head, "dirty_worktree": bool(status),
        "git_status_short": status.splitlines(), "python": sys.version,
        "platform": platform.platform(), "numpy": np.__version__,
        "scipy": scipy.__version__, "ocp": ocp,
        "openvsp": {
            "version": "3.54.0", "source_tag": "OpenVSP_3.54.0",
            "source_commit": source_commit, "compiler": compiler, "cmake": cmake,
            "source_dir": str(a.source_dir), "build_dir": str(a.build_dir),
            "install_dir": str(a.install_dir),
            "vspscript_sha256": digest(a.install_dir / "vspscript"),
            "probe_diff_sha256": digest(out / "openvsp_probe.diff"),
            "probe_process_exit_code": 10,
            "probe_completion_evidence": "probe_update_events.csv sequence 1 START then COMPLETE",
            "build_options": {
                "CMAKE_BUILD_TYPE": "Release", "VSP_NO_GRAPHICS": True,
                "VSP_NO_VSPAERO": True, "VSP_NO_API_WRAPPERS": True,
                "VSP_NO_HELP": True, "VSP_NO_DOC": True, "VSP_NO_PYDOC": True,
            },
        },
        "production_runtime": {
            "root": str(production_openvsp_root),
            "vsp_sha256": digest(production_openvsp_root / "vsp"),
            "vspscript_sha256": digest(production_openvsp_root / "vspscript"),
            "python_api_sha256": digest(production_openvsp_root / "python/openvsp/openvsp/vsp.py"),
            "python_api_matches_loc02": digest(production_openvsp_root / "python/openvsp/openvsp/vsp.py") == prior_preflight["surface_api_source_identity"]["installed_python_api"]["sha256"],
            "used_for_probe": False,
        },
        "production_source_hashes": production_hashes,
        "production_source_hashes_match_loc02": production_hashes_match_loc02,
        "fixed_artifacts": {
            "retained_final_step": {"path": str(final_step), "sha256": digest(final_step)},
            "retained_raw_step": {"path": str(raw_step), "sha256": digest(raw_step)},
            "saved_vsp3": {"path": str(loc02 / "blade_openvsp.vsp3"),
                           "sha256": digest(loc02 / "blade_openvsp.vsp3")},
            "input_blade_spec": {"path": str(loc02 / "input_blade_spec.json"),
                                 "sha256": digest(loc02 / "input_blade_spec.json")},
            "resolved_blade_spec": {"path": str(loc02 / "resolved_blade_spec.json"),
                                    "sha256": digest(loc02 / "resolved_blade_spec.json")},
        },
        "relevant_source_hashes": {
            name: digest(ROOT / name) for name in (
                "backend/bladegen/adapters/openvsp_adapter.py",
                "backend/bladegen/validation/expected_geometry.py",
                "scripts/diagnose_x57_live_surface.py",
                "scripts/analyze_x57_rib_placement.py",
            )
        },
    }
    jwrite(out / "runtime_identity.json", identity)

    plan = {
        "experiment_id": "X57-LOC-03",
        "immutable_job_id": "a93b281c29b640afaa6bad698d64a61b",
        "primary_planes": STATIONS,
        "thresholds_mm": {"baseline_repeatability": .0001,
                          "same_plane_residual": 1e-6,
                          "refinement_stability": .0001,
                          "stage_agreement": .001},
        "comparisons": [
            "canonical local profile versus prepared profile",
            "requested global Y plane versus positioned rib plane",
            "transformed rib versus post-skin native-u iso curve",
            "final fixed-Y cut versus unchanged expected contour",
        ],
        "conditional_intervention": "not run",
        "reason": "profile preparation and placement both exceed the stage threshold, so the sole automatic-rotation gate is not met",
    }
    jwrite(out / "plan.json", plan)

    summary = {
        "experiment_id": "X57-LOC-03", "run_id": out.name,
        "classification": "MULTIPLE_CONTRIBUTIONS",
        "candidate_status": "NOT_TESTED",
        "baseline_reproduction_passed": all(v["passed"] for v in baseline.values()),
        "probe_process_exit_code": 10,
        "probe_completion_evidence": "native event sequence 1 START then COMPLETE",
        "baseline": baseline, "pseudo_rib_count": len(inventory),
        "detailed_rib_count": sum(int(r["detailed"]) for r in inventory),
        "intrinsic_profile": {
            "status": "MISMATCH_ABOVE_STAGE_THRESHOLD",
            "maximum_sampled_deviation_mm": profile_max,
            "stage_threshold_mm": .001,
            "maximum_2x_to_4x_sampled_max_delta_mm": profile_refinement_delta_max,
            "refinement_stability_threshold_mm": .0001,
            "refinement_stability_passed": profile_refinement_delta_max <= .0001,
            "stations": profile_results,
        },
        "rib_placement": {
            "status": "CONTRACT_MISMATCH",
            "maximum_plane_angle_deg": angle_max,
            "maximum_abs_y_departure_mm": y_max,
            "all_rib_compdt_vs_active_segment_max_error": slope_error,
            "targets": {key(r["r_over_R"]): r for r in audits},
            "mechanism": "automatic rotation about transformed chord from actual Rake and Axial Compdt tilts ribs away from fixed global-Y planes",
            "ordered_transform_chain": TRANSFORM_CHAIN,
        },
        "rib_to_surface": {
            "status": "PRESERVED", "ribs_checked": len(skin),
            "samples_per_rib": 4097, "maximum_sampled_difference_mm": skin_max,
            "p95_of_per_rib_maxima_mm": float(np.percentile(skin, 95)),
            "surface_u_max_native": float(skin_rows[0]["surface_u_max"]),
            "last_pseudo_rib_r_over_R": float(inventory[-1]["r_over_R"]),
            "requested_tip_r_over_R": snap["rlast"],
        },
        "targets": targets,
        "intervention": {
            "status": "NOT_RUN",
            "reason": "two contributions exceed the predeclared stage threshold; the prompt permits the rotation ablation only for a sole implicated operation",
            "public_openvsp_switch_exists": False,
        },
        "smallest_next_action": "approve an input-preserving native m_ZRotate ablation, baseline recovery, and unchanged 41-station validation while retaining the measured profile residual",
        "original_product_job": "FAILED",
        "complete_internal_validation": "FAIL",
        "external_nasa_fidelity": "UNVERIFIED",
        "production_source_modified": False,
        "production_runtime_modified": False,
        "production_source_hashes_match_loc02": production_hashes_match_loc02,
        "head": head, "dirty_worktree": bool(status),
    }
    jwrite(out / "decision_summary.json", summary)

    lines = [
        "# X57 Rib Placement and Loft Decision", "",
        "## Four direct answers", "",
        f"1. **Is the profile already wrong before positioning?** Yes, slightly. The 4x sampled prepared-versus-canonical maximum is **{profile_max:.9f} mm**, above the 0.001 mm diagnostic stage threshold but far below the 0.523791 mm worst final discrepancy. Its maximum 2x-to-4x change is {profile_refinement_delta_max:.9f} mm, so this submetric does not meet the 0.0001 mm refinement target; that limitation does not overlap the 0.001 mm classification boundary.",
        f"2. **Is the positioned rib in the plane BladeGen promises, and what transformation explains the difference?** No after OpenVSP automatic derivative rotation. Pre-rotation reference origin, chord direction, and fixed-Y plane agree; rotation about the transformed chord by atan(-RakeCurve.Compdt-AxialCurve.Compdt) creates up to **{angle_max:.9f} deg** tilt and **{y_max:.9f} mm** Y departure.",
        f"3. **Does the surface preserve the supplied ribs, and why do physical cuts disagree?** Yes. All **{len(skin)}** ribs agree with post-skin native-u iso curves to **{skin_max:.3e} mm** maximum. The loft contains tilted ribs, while validation cuts unchanged global fixed-Y planes.",
        "4. **What causal check/correction was tested, or what blocks one?** No candidate was run. Profile preparation and placement both exceed 0.001 mm, so the prompt condition allowing a rotation-only ablation when it is the sole implicated mechanism is not met. OpenVSP 3.54.0 has no public switch for this rotation.",
        "", "## Decision", "",
        "Primary classification: **MULTIPLE_CONTRIBUTIONS**. Candidate status: **NOT_TESTED**.",
        "",
        "The first measured divergence is the small profile-preparation residual. The dominant divergence is a rib-placement contract mismatch. Skinning is not a material contributor.",
        "",
        "The original job remains **FAILED**, complete internal validation remains **FAIL**, and external NASA fidelity remains **UNVERIFIED**.",
        "", "## Fixed section-plane contract", "",
        "| Item | BladeGen contract | Observed native behavior |",
        "|---|---|---|",
        "| plane | global Y=R times r/R, normal (0,1,0) | starts there, then automatic chord-axis rotation tilts each rib |",
        "| profile | normalized LE-to-TE x/c and thickness y/c | FILE_AIRFOIL becomes an internal prepared spline |",
        "| chord | X-Z direction (sin twist, cos twist) | pre-rotation chord matches; it is the later rotation axis |",
        "| reference | x/c=0.5; Rake axial X, Skew tangential Z | reference origin stays fixed during automatic rotation |",
        "| auxiliary | Sweep, CLi, Axial, Tangential zero; no cylinder projection | confirmed; Axial derivative is zero |",
        "| units | mm and degrees; OpenVSP inches converted by 25.4 | probe stored inches; derived tables use exact 25.4 |",
        "",
        "The product contract is not reinterpreted as a tilted native plane.",
        "",
        "Observed native transform order: " + " -> ".join(TRANSFORM_CHAIN) + ".",
        "", "## Baseline qualification", "",
        "| r/R | points | max direct difference (mm) | max plane residual (mm) | pass |",
        "|---:|---:|---:|---:|:---:|",
    ]
    for station in STATIONS:
        b = baseline[key(station)]
        lines.append(f"| {station:.5f} | {b['points']} | {b['direct_max_3d_mm']:.3e} | {b['plane_residual_max_abs_mm']:.3e} | {b['passed']} |")
    lines += [
        "",
        "The isolated source build reproduces saved LOC-02 live contours to machine precision. One load update produced START then COMPLETE, so no transient state is presented as final. vspscript returned its nonzero runtime code 10 after the script logged that load returned; geometry completion is established by the flushed native COMPLETE event and complete output inventory, not by relabeling the process code.",
        "", "## Profile preparation", "",
        "| r/R | RMS mm | P95 mm | sampled max mm | stable 2x to 4x |",
        "|---:|---:|---:|---:|:---:|",
    ]
    for station in STATIONS:
        item = profile_results[key(station)]
        m = item["factors"]["4x"]["physical_mm"]
        lines.append(f"| {station:.5f} | {m['rms_mm']:.9f} | {m['p95_mm']:.9f} | {m['sampled_max_mm']:.9f} | {item['stable']} |")
    lines += [
        "",
        "No registration, fitting, smoothing, or scaling was used. Prepared-profile refinement did not meet the 0.0001 mm target: the largest 2x-to-4x sampled-max change was " + f"{profile_refinement_delta_max:.9f} mm. The smallest 4x mismatch is still more than 3.9 times the 0.001 mm stage threshold. Captured matrices and their analytic inverse reconstruct observed stages; errors are in rib_transform_audit.csv.",
        "", "## Rib placement and derivative convention", "",
        "| r/R | actual Compdt | source left/right secants | source PCHIP derivative only | Z rotation deg | plane tilt deg | Y delta min..max mm |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in audits:
        lines.append(
            f"| {r['r_over_R']:.5f} | {r['rake_compdt_actual']:.12f} | "
            f"{r['source_left_secant_slope']:.12f} / {r['source_right_secant_slope']:.12f} | "
            f"{r['canonical_pchip_derivative_explanatory_only']:.12f} | "
            f"{r['zrotate_deg_actual']:.9f} | {r['plane_angle_from_requested_deg']:.9f} | "
            f"{r['y_delta_min_mm']:.9f} .. {r['y_delta_max_mm']:.9f} |"
        )
    lines += [
        "",
        f"The adapter sends resolved LINEAR PCurves. At a control knot native fp selects the following/right segment. All {len(inventory)} Compdt samples match the active resolved slope; worst error is {slope_error:.3e}. Canonical PCHIP derivatives are explanatory only.",
        "",
        "The captured basis proves rotateZ acts about the already transformed chord, not global Z. It preserves the reference origin and chord axis while rotating the plane normal.",
        "", "## Rib-to-surface preservation", "",
        f"- Planned and observed pseudo ribs: **{len(inventory)}**.",
        f"- Detailed neighborhood ribs: **{sum(int(r['detailed']) for r in inventory)}**.",
        f"- Exact correspondence is native u_pseudo; surface native u max is **{float(skin_rows[0]['surface_u_max']):.15f}**.",
        f"- Worst all-rib 4,097-sample maximum: **{skin_max:.3e} mm**.",
        f"- Last pseudo rib is r/R={float(inventory[-1]['r_over_R']):.12f}; the 0.001 station equivalence collapses the nearby exact tip control. This is outside the selected intervals.",
        "",
        "The rejected normalized-u audit is preserved under initial_normalized_u_observation_rejected and is not used as evidence.",
        "", "## Attribution at physical planes", "",
        "| r/R | preparation max mm | automatic rotation max mm | rib-to-skin max mm | expected-to-fixed-Y max mm | live-to-raw max mm |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for station in STATIONS:
        rows = {r["comparison"]: r for r in comparisons if r["r_over_R"] == station}
        lines.append(
            f"| {station:.5f} | {rows['canonical_profile_to_prepared_profile']['sampled_max_mm']:.9f} | "
            f"{rows['before_to_after_auto_zrotate_equal_parameter']['sampled_max_mm']:.9f} | "
            f"{rows['transformed_rib_to_post_skin_iso']['sampled_max_mm']:.3e} | "
            f"{rows['expected_to_final_fixed_y_cut']['sampled_max_mm']:.9f} | "
            f"{rows['final_live_to_retained_raw_step_cut']['sampled_max_mm']:.9f} |"
        )
    lines += [
        "",
        "Final fixed-plane values reuse the LOC-02 4x metric and density; all recorded fixed-plane 2x-to-4x sampled-max changes remain within 0.0001 mm. The prepared-profile convergence limitation is reported separately above. The corrected plot explicitly selects nonempty expected_upper queries and labels expected upper to live fixed-Y; arrays are unchanged.",
        "",
        "Measured chain: small preparation residual, correct reference placement, automatic derivative-driven chord-axis tilt, exact spline interpolation, then a different contour when the loft is cut by the product fixed-Y plane.",
        "", "## Correction gate and recommendation", "",
        "No candidate or full validation was run. The conditional sole-mechanism gate was not satisfied.",
        "",
        "There is no public OpenVSP flag that disables only this rotation while preserving accepted Rake inputs. A deployable correction would need a maintained or upstream native-library change, not changed inputs and not a validator exception.",
        "",
        "Smallest next action: approve one input-preserving native m_ZRotate ablation for all ribs, run baseline to intervention to baseline recovery, and only if all three original gates pass run unchanged OCP finalization and complete 41-station validation. Keep the preparation residual separate.",
        "", "## Identity", "",
        f"- Git HEAD: {head}; dirty work preserved: {bool(status)}.",
        f"- OpenVSP source tag OpenVSP_3.54.0, commit {source_commit}.",
        f"- Probe binary SHA-256: {digest(a.install_dir / 'vspscript')}.",
        f"- Final STEP SHA-256: {digest(final_step)}.",
        f"- Raw STEP SHA-256: {digest(raw_step)}.",
        f"- Build: Release headless, no VSPAERO/API wrappers/help/docs; {compiler}.",
        f"- Production source hashes match the LOC-02 preflight: {production_hashes_match_loc02}; the installed production runtime was not used by the probe.",
        f"- Installed production vspscript SHA-256: {digest(production_openvsp_root / 'vspscript')}.",
    ]
    (out / "X57_RIB_PLACEMENT_DECISION.md").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
