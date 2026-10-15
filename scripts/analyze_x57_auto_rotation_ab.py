#!/usr/bin/env python3
"""Build X57-AB-02 A/B/A2 comparison evidence from completed arm artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]

import diagnose_x57_contours as contour  # noqa: E402
from bladegen.solid.ocp_solidify import read_step  # noqa: E402
from bladegen.validation.measure_sections import _section_shape  # noqa: E402

MM = 25.4
STATIONS = (0.22302, 0.29061, 0.50345)
ARMS = ("A_native", "B_rotation_bypassed", "A2_native_recovery")
NONEXPERIMENTAL_EXCLUSIONS = {
    "applied_zrotate_deg",
    "applied_zrotate_rad",
    "rotation_mode",
}
PASS_KEYS = (
    "chord_pass",
    "twist_pass",
    "reference_axis_pass",
    "contour_rms_pass",
    "contour_p95_pass",
    "contour_max_pass",
    "te_pass",
    "wire_count_pass",
    "wire_valid_pass",
    "wire_closed_pass",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def jread(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def jwrite(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(contour.jsonable(value), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def cread(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def cwrite(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing empty CSV: {path}")
    fields: list[str] = []
    for row in rows:
        for name in row:
            if name not in fields:
                fields.append(name)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def key(station: float) -> str:
    return f"{station:.5f}"


def slug(station: float) -> str:
    return f"rR_{station:.5f}".replace(".", "p")


def components_from_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[list[float]]] = defaultdict(list)
    for row in rows:
        grouped[row["component"]].append(
            [float(row["x_model"]) * MM, float(row["z_model"]) * MM]
        )
    return [{"name": name, "points": np.asarray(points)} for name, points in grouped.items()]


def components_array(parts: list[dict[str, Any]]) -> np.ndarray:
    return np.vstack([np.asarray(part["points"]) for part in parts])


def subsample(parts: list[dict[str, Any]], stride: int) -> list[dict[str, Any]]:
    return [{**part, "points": np.asarray(part["points"])[::stride]} for part in parts]


def public_bidirectional(metric: dict[str, Any]) -> dict[str, Any]:
    return contour.public_metric(metric)["bidirectional_equal_direction_arc_weighted"]


def basis(row: dict[str, str]) -> tuple[np.ndarray, np.ndarray]:
    origin = np.asarray([float(row[f"origin_{axis}"]) for axis in "xyz"])
    columns = []
    for basis_axis in "xyz":
        endpoint = np.asarray([float(row[f"{basis_axis}_{axis}"]) for axis in "xyz"])
        columns.append(endpoint - origin)
    return origin, np.column_stack(columns)


def plane_angle_deg(normal: np.ndarray) -> float:
    cosine = abs(float(np.dot(normal / np.linalg.norm(normal), np.asarray([0.0, 1.0, 0.0]))))
    return math.degrees(math.acos(np.clip(cosine, -1.0, 1.0)))


def target_rib(inventory: list[dict[str, str]], station: float) -> dict[str, str]:
    matches = [row for row in inventory if abs(float(row["r_over_R"]) - station) <= 1e-12]
    if len(matches) != 1:
        raise RuntimeError(f"expected one rib at {station}, found {len(matches)}")
    return matches[0]


def selected_curve_rows(
    path: Path, wanted: dict[int, set[str]]
) -> dict[tuple[int, str], np.ndarray]:
    values: dict[tuple[int, str], list[list[float]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            rib = int(row["rib_index"])
            stage = row["stage"]
            if stage in wanted.get(rib, set()):
                values[(rib, stage)].append(
                    [
                        float(row["curve_parameter01"]),
                        float(row["x_model"]),
                        float(row["y_model"]),
                        float(row["z_model"]),
                    ]
                )
    return {name: np.asarray(points) for name, points in values.items()}


def canonical_row_hashes(path: Path, stages: set[str]) -> dict[str, Any]:
    hashes = {stage: hashlib.sha256() for stage in stages}
    counts = defaultdict(int)
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            stage = row["stage"]
            if stage not in stages:
                continue
            payload = json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
            hashes[stage].update(payload + b"\n")
            counts[stage] += 1
    return {
        stage: {"rows": counts[stage], "canonical_row_sha256": hashes[stage].hexdigest()}
        for stage in sorted(stages)
    }


def direct_ordered(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> dict[str, Any]:
    if [part["name"] for part in left] != [part["name"] for part in right]:
        raise RuntimeError("live component order mismatch")
    distances = []
    for lpart, rpart in zip(left, right):
        lpoints, rpoints = np.asarray(lpart["points"]), np.asarray(rpart["points"])
        if lpoints.shape != rpoints.shape:
            raise RuntimeError("live point inventory mismatch")
        distances.append(np.linalg.norm(lpoints - rpoints, axis=1))
    values = np.concatenate(distances)
    return {
        "points": len(values),
        "rms_mm": float(np.sqrt(np.mean(values * values))),
        "p95_mm": float(np.percentile(values, 95)),
        "sampled_max_mm": float(np.max(values)),
    }


def plane_and_region(
    arm: str,
    station: float,
    rib: dict[str, str],
    curves: dict[tuple[int, str], np.ndarray],
    matrices: dict[tuple[int, str], dict[str, str]],
    expected: dict[str, Any],
    live_metric: dict[str, Any],
    reference_axis: float,
    radius_mm: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    rib_index = int(rib["rib_index"])
    after = curves[(rib_index, "after_auto_zrotate")][:, 1:] * MM
    _, matrix = basis(matrices[(rib_index, "after_auto_zrotate")])
    normal = matrix[:, 1]
    if normal[1] < 0:
        normal = -normal
    y_departure = after[:, 1] - radius_mm * station
    direct_plane_residual = np.abs(y_departure)
    plane = {
        "arm": arm,
        "r_over_R": station,
        "rib_index": rib_index,
        "computed_zrotate_deg": float(rib["zrotate_deg"]),
        "applied_zrotate_deg": float(rib["applied_zrotate_deg"]),
        "rotation_mode": rib["rotation_mode"],
        "plane_normal_x": float(normal[0]),
        "plane_normal_y": float(normal[1]),
        "plane_normal_z": float(normal[2]),
        "plane_angle_from_global_y_deg": plane_angle_deg(normal),
        "rib_y_departure_min_mm": float(np.min(y_departure)),
        "rib_y_departure_max_mm": float(np.max(y_departure)),
        "rib_y_departure_max_abs_mm": float(np.max(direct_plane_residual)),
    }

    query = live_metric["right_query"]
    detail = live_metric["right_detail"]
    expected_mask = query["component"] == "expected_upper"
    expected_points = query["points"][expected_mask]
    local = contour.local_coordinates(expected_points, expected, reference_axis)
    distance = detail["distance"][expected_mask]
    band = (local[:, 0] >= 0.13) & (local[:, 0] <= 0.18)
    if not np.any(band):
        raise RuntimeError("no expected-upper samples in x/c 0.13..0.18")
    band_indices = np.flatnonzero(band)
    local_max_index = band_indices[int(np.argmax(distance[band]))]
    region = {
        "arm": arm,
        "r_over_R": station,
        "region": "expected upper x/c in [0.13, 0.18]",
        "sample_count": int(np.sum(band)),
        "sampled_max_mm": float(distance[local_max_index]),
        "x_over_c_at_sampled_max": float(local[local_max_index, 0]),
        "y_over_c_at_sampled_max": float(local[local_max_index, 1]),
    }
    return plane, region


def all_pass(record: dict[str, Any]) -> bool:
    return all(bool(record[name]) for name in PASS_KEYS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--loc02-dir", type=Path, required=True)
    parser.add_argument("--loc03-dir", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--install-dir", type=Path, required=True)
    args = parser.parse_args()
    run = args.run_dir.resolve()
    started = time.monotonic()
    spec = jread(args.loc02_dir / "input_blade_spec.json")
    radius_mm = float(spec["diameter_mm"]) / 2.0
    reference_axis = float(spec["reference_axis_x_over_c"])

    inventories = {arm: cread(run / arm / "probe_rib_inventory.csv") for arm in ARMS}
    live_rows = {arm: cread(run / arm / "probe_final_live_cuts.csv") for arm in ARMS}
    production = {arm: jread(run / arm / "production_selected_raw.json") for arm in ARMS}
    snapshots = {arm: jread(run / arm / "probe_snapshot.json") for arm in ARMS}
    matrices = {
        arm: {
            (int(row["rib_index"]), row["stage"]): row
            for row in cread(run / arm / "probe_transform_bases.csv")
        }
        for arm in ARMS
    }
    ribs_by_arm = {
        arm: {station: target_rib(inventories[arm], station) for station in STATIONS}
        for arm in ARMS
    }
    wanted_by_arm = {
        arm: {
            int(ribs_by_arm[arm][station]["rib_index"]): {
                "prepared_profile_unit",
                "after_auto_zrotate",
                "fully_transformed_rib",
                "post_skin_iso_pre_caps",
            }
            for station in STATIONS
        }
        for arm in ARMS
    }
    selected_curves = {
        arm: selected_curve_rows(run / arm / "probe_detailed_curves.csv", wanted_by_arm[arm])
        for arm in ARMS
    }

    inventory_fields = list(inventories["A_native"][0])
    invariant_fields = [name for name in inventory_fields if name not in NONEXPERIMENTAL_EXCLUSIONS]
    inventory_exact_ab = all(
        all(a[name] == b[name] for name in invariant_fields)
        for a, b in zip(inventories["A_native"], inventories["B_rotation_bypassed"])
    ) and len(inventories["A_native"]) == len(inventories["B_rotation_bypassed"])
    inventory_exact_aa2 = all(
        all(a[name] == b[name] for name in inventory_fields)
        for a, b in zip(inventories["A_native"], inventories["A2_native_recovery"])
    ) and len(inventories["A_native"]) == len(inventories["A2_native_recovery"])
    computed_angles_ab = all(
        a["zrotate_deg"] == b["zrotate_deg"] and a["zrotate_rad"] == b["zrotate_rad"]
        for a, b in zip(inventories["A_native"], inventories["B_rotation_bypassed"])
    )
    b_applied_zero = all(
        float(row["applied_zrotate_deg"]) == 0.0 and float(row["applied_zrotate_rad"]) == 0.0
        for row in inventories["B_rotation_bypassed"]
    )

    preparation_identity = {
        arm: canonical_row_hashes(
            run / arm / "probe_detailed_curves.csv", {"prepared_profile_unit"}
        )
        for arm in ARMS
    }
    preparation_hashes = [
        preparation_identity[arm]["prepared_profile_unit"]["canonical_row_sha256"]
        for arm in ARMS
    ]

    live: dict[str, dict[float, list[dict[str, Any]]]] = {}
    for arm in ARMS:
        live[arm] = {}
        for station in STATIONS:
            rows = [
                row for row in live_rows[arm]
                if abs(float(row["r_over_R"]) - station) <= 1e-12
            ]
            live[arm][station] = components_from_rows(rows)

    raw_sections: dict[str, dict[float, Any]] = {arm: {} for arm in ARMS}
    raw_components: dict[str, dict[float, dict[int, list[dict[str, Any]]]]] = {
        arm: {} for arm in ARMS
    }
    raw_read_timings = []
    for arm in ARMS:
        read_started = time.monotonic()
        shape = read_step(run / arm / "blade_openvsp.step")
        raw_read_timings.append({"arm": arm, "operation": "raw_step_read", "elapsed_seconds": time.monotonic() - read_started})
        for station in STATIONS:
            section_started = time.monotonic()
            section = _section_shape(shape, radius_mm, station)
            raw_sections[arm][station] = section
            raw_components[arm][station] = {
                factor: contour.sample_section_components(section, factor * (2500 - 1) + 1)
                for factor in (1, 2, 4)
            }
            raw_read_timings.append({
                "arm": arm,
                "operation": "raw_section_and_sampling",
                "r_over_R": station,
                "elapsed_seconds": time.monotonic() - section_started,
            })

    station_rows: list[dict[str, Any]] = []
    plane_rows: list[dict[str, Any]] = []
    region_rows: list[dict[str, Any]] = []
    recovery_stations: dict[str, Any] = {}
    independent: dict[str, Any] = {}
    profile_preparation: dict[str, Any] = {}

    for station in STATIONS:
        station_dir = run / "stations" / slug(station)
        station_dir.mkdir(parents=True, exist_ok=True)
        expected_by_factor = {
            factor: contour.independent_expected(spec, station, factor) for factor in (1, 2, 4)
        }
        expected4 = expected_by_factor[4]
        contour.save_components_csv(station_dir / "expected_4x.csv", expected4["metric_components"])

        metrics: dict[str, dict[int, dict[str, Any]]] = {arm: {} for arm in ARMS}
        live_raw_metrics: dict[str, dict[int, dict[str, Any]]] = {arm: {} for arm in ARMS}
        for arm in ARMS:
            for factor, stride in ((1, 4), (2, 2), (4, 1)):
                metric = contour.compare_components(
                    subsample(live[arm][station], stride),
                    expected_by_factor[factor]["metric_components"],
                )
                metrics[arm][factor] = metric
                live_raw_metrics[arm][factor] = contour.compare_components(
                    subsample(live[arm][station], stride), raw_components[arm][station][factor]
                )
            contour.save_components_csv(
                station_dir / f"{arm}_live_4x.csv", live[arm][station]
            )
            contour.save_components_csv(
                station_dir / f"{arm}_raw_step_4x.csv", raw_components[arm][station][4]
            )
            contour.save_residual_csv(
                station_dir / f"expected_vs_{arm}_live_residuals_4x.csv",
                metrics[arm][4],
            )
            brep = contour.persist_section_brep(
                raw_sections[arm][station], station_dir / f"{arm}_raw_section.brep"
            )
            jwrite(station_dir / f"{arm}_raw_section_identity.json", brep)

            plane, region = plane_and_region(
                arm,
                station,
                ribs_by_arm[arm][station],
                selected_curves[arm],
                matrices[arm],
                expected4,
                metrics[arm][4],
                reference_axis,
                radius_mm,
            )
            plane_rows.append(plane)
            region_rows.append(region)

        direct_ab = direct_ordered(live["A_native"][station], live["B_rotation_bypassed"][station])
        direct_aa2 = direct_ordered(live["A_native"][station], live["A2_native_recovery"][station])
        recovery_stations[key(station)] = direct_aa2

        prep_factors = {}
        prepared = selected_curves["A_native"][
            (int(ribs_by_arm["A_native"][station]["rib_index"]), "prepared_profile_unit")
        ][:, [1, 2]]
        chord_mm = float(ribs_by_arm["A_native"][station]["chord_model"]) * MM
        midpoint = (len(prepared) - 1) // 2
        prepared_components = [
            {"name": "lower", "points": prepared[: midpoint + 1][::-1]},
            {"name": "upper", "points": prepared[midpoint:]},
        ]
        for factor, stride in ((1, 4), (2, 2), (4, 1)):
            normalized_expected = [
                {"name": "upper", "points": expected_by_factor[factor]["normalized_upper"]},
                {"name": "lower", "points": expected_by_factor[factor]["normalized_lower"]},
            ]
            metric = public_bidirectional(
                contour.compare_components(subsample(prepared_components, stride), normalized_expected)
            )
            prep_factors[f"{factor}x"] = {
                "normalized": metric,
                "physical_mm": {
                    name: metric[name] * chord_mm
                    for name in ("rms_mm", "p95_mm", "sampled_max_mm")
                },
            }
        profile_preparation[key(station)] = {
            "unchanged_A_B_A2": len(set(preparation_hashes)) == 1,
            "factors": prep_factors,
            "sampled_max_refinement_2x_to_4x_mm": abs(
                prep_factors["4x"]["physical_mm"]["sampled_max_mm"]
                - prep_factors["2x"]["physical_mm"]["sampled_max_mm"]
            ),
        }

        for arm in ARMS:
            prod = next(
                row for row in production[arm]
                if abs(float(row["sampled_r_over_R"]) - station) <= 1e-12
            )
            independent_metric = public_bidirectional(metrics[arm][4])
            live_raw_metric = public_bidirectional(live_raw_metrics[arm][4])
            station_rows.append({
                "r_over_R": station,
                "arm": arm,
                "rotation_mode": snapshots[arm]["rotation_mode"],
                "production_rms_mm": prod["contour_rms_mm"],
                "production_p95_mm": prod["contour_p95_mm"],
                "production_sampled_max_mm": prod["contour_max_mm"],
                "chord_error_mm": prod["chord_absolute_error_mm"],
                "twist_error_deg": prod["twist_absolute_error_deg"],
                "axis_error_mm": prod["reference_axis_position_error_mm"],
                "te_error_mm": prod["te_absolute_error_mm"],
                "wire_count": prod["resulting_wires"],
                "wire_valid": prod["wire_valid"],
                "wire_closed": prod["wire_closed"],
                "chord_pass": prod["chord_pass"],
                "twist_pass": prod["twist_pass"],
                "axis_pass": prod["reference_axis_pass"],
                "te_pass": prod["te_pass"],
                "contour_rms_pass": prod["contour_rms_pass"],
                "contour_p95_pass": prod["contour_p95_pass"],
                "contour_max_pass": prod["contour_max_pass"],
                "wire_count_pass": prod["wire_count_pass"],
                "wire_valid_pass": prod["wire_valid_pass"],
                "wire_closed_pass": prod["wire_closed_pass"],
                "all_original_gates_pass": all_pass(prod),
                "independent_live_rms_mm": independent_metric["rms_mm"],
                "independent_live_p95_mm": independent_metric["p95_mm"],
                "independent_live_sampled_max_mm": independent_metric["sampled_max_mm"],
                "independent_live_refinement_2x_to_4x_mm": abs(
                    public_bidirectional(metrics[arm][4])["sampled_max_mm"]
                    - public_bidirectional(metrics[arm][2])["sampled_max_mm"]
                ),
                "live_to_raw_rms_mm": live_raw_metric["rms_mm"],
                "live_to_raw_p95_mm": live_raw_metric["p95_mm"],
                "live_to_raw_sampled_max_mm": live_raw_metric["sampled_max_mm"],
                "direct_A_to_B_sampled_max_mm": direct_ab["sampled_max_mm"],
                "direct_A_to_A2_sampled_max_mm": direct_aa2["sampled_max_mm"],
            })

        independent[key(station)] = {
            "E_vs_A": {f"{factor}x": public_bidirectional(metrics["A_native"][factor]) for factor in (1, 2, 4)},
            "E_vs_B": {f"{factor}x": public_bidirectional(metrics["B_rotation_bypassed"][factor]) for factor in (1, 2, 4)},
            "E_vs_A2": {f"{factor}x": public_bidirectional(metrics["A2_native_recovery"][factor]) for factor in (1, 2, 4)},
            "A_vs_B_direct_equal_parameter": direct_ab,
            "A_vs_A2_direct_equal_parameter": direct_aa2,
            "live_to_raw": {
                arm: {f"{factor}x": public_bidirectional(live_raw_metrics[arm][factor]) for factor in (1, 2, 4)}
                for arm in ARMS
            },
        }

        fig, ax = plt.subplots(figsize=(8.2, 6.2))
        for component in expected4["metric_components"]:
            ax.plot(component["points"][:, 0], component["points"][:, 1], color="black", lw=1.1, label="Expected" if component is expected4["metric_components"][0] else None)
        colors = {"A_native": "#dc2626", "B_rotation_bypassed": "#16a34a", "A2_native_recovery": "#f59e0b"}
        labels = {"A_native": "A native", "B_rotation_bypassed": "B bypassed", "A2_native_recovery": "A2 restored"}
        for arm in ARMS:
            for index, component in enumerate(live[arm][station]):
                ax.plot(component["points"][:, 0], component["points"][:, 1], color=colors[arm], lw=.7, alpha=.85, label=labels[arm] if index == 0 else None)
        for index, component in enumerate(raw_components["B_rotation_bypassed"][station][4]):
            ax.plot(component["points"][:, 0], component["points"][:, 1], color="#2563eb", ls="--", lw=.65, label="B raw STEP" if index == 0 else None)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("global X (mm)")
        ax.set_ylabel("global Z (mm)")
        ax.set_title(f"True-scale fixed-plane overlay, r/R={station:.5f}")
        ax.grid(alpha=.2)
        ax.legend()
        fig.tight_layout()
        fig.savefig(station_dir / "same_frame_true_scale_overlay.png", dpi=190)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(8.2, 4.8))
        for arm, color, label in (
            ("A_native", "#dc2626", "E to A"),
            ("B_rotation_bypassed", "#16a34a", "E to B"),
            ("A2_native_recovery", "#f59e0b", "E to A2"),
        ):
            metric = metrics[arm][4]
            query, detail = metric["right_query"], metric["right_detail"]
            mask = query["component"] == "expected_upper"
            local = contour.local_coordinates(query["points"][mask], expected4, reference_axis)
            ax.plot(local[:, 0], detail["distance"][mask], color=color, lw=.8, label=label)
        ax.axvspan(.13, .18, color="#94a3b8", alpha=.18, label="x/c 0.13–0.18")
        ax.set_xlabel("expected upper x/c")
        ax.set_ylabel("sampled point-to-segment residual (mm)")
        ax.set_title(f"Expected-upper residual, r/R={station:.5f}")
        ax.grid(alpha=.2)
        ax.legend()
        fig.tight_layout()
        fig.savefig(station_dir / "expected_upper_residual.png", dpi=190)
        plt.close(fig)

    cwrite(run / "station_comparison.csv", station_rows)
    cwrite(run / "rib_plane_comparison.csv", plane_rows)
    cwrite(run / "upper_surface_residual_region.csv", region_rows)
    cwrite(run / "analysis_timings.csv", raw_read_timings)
    jwrite(run / "independent_metrics.json", independent)
    jwrite(run / "profile_preparation_fixed_background.json", profile_preparation)

    production_recovery = {}
    for station in STATIONS:
        a_record = next(row for row in production["A_native"] if abs(row["sampled_r_over_R"] - station) <= 1e-12)
        a2_record = next(row for row in production["A2_native_recovery"] if abs(row["sampled_r_over_R"] - station) <= 1e-12)
        production_recovery[key(station)] = {
            field: abs(float(a_record[field]) - float(a2_record[field]))
            for field in ("contour_rms_mm", "contour_p95_mm", "contour_max_mm")
        }
    recovery = {
        "inventory_exact_all_fields": inventory_exact_aa2,
        "direct_live": recovery_stations,
        "production_stat_absolute_deltas_mm": production_recovery,
        "live_repeatability_threshold_mm": .0001,
        "production_stat_repeatability_threshold_mm": .0001,
        "passed": inventory_exact_aa2
        and max(item["sampled_max_mm"] for item in recovery_stations.values()) <= .0001
        and max(max(item.values()) for item in production_recovery.values()) <= .0001,
    }
    jwrite(run / "A2_recovery.json", recovery)

    input_settings = {
        "arms": {
            arm: {
                "snapshot": snapshots[arm],
                "inventory_rows": len(inventories[arm]),
                "inventory_sha256": digest(run / arm / "probe_rib_inventory.csv"),
                "prepared_profile_identity": preparation_identity[arm],
                "vsp3_sha256": digest(run / arm / "blade_openvsp.vsp3"),
                "raw_step_sha256": digest(run / arm / "blade_openvsp.step"),
            }
            for arm in ARMS
        },
        "invariants": {
            "A_B_nonexperimental_inventory_exact": inventory_exact_ab,
            "A_A2_inventory_exact_all_fields": inventory_exact_aa2,
            "A_B_computed_angles_exact": computed_angles_ab,
            "B_all_applied_angles_zero": b_applied_zero,
            "prepared_profile_rows_A_B_A2_exact": len(set(preparation_hashes)) == 1,
            "prepared_profile_canonical_sha256": preparation_hashes[0],
            "pseudo_rib_count_each": {arm: len(inventories[arm]) for arm in ARMS},
        },
        "only_intended_difference": "applied automatic m_ZRotate is zero in B; computed angle retained",
    }
    jwrite(run / "settings_input_comparison.json", input_settings)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for ax, station in zip(axes, STATIONS):
        for arm, color, label in (
            ("A_native", "#dc2626", "A"),
            ("B_rotation_bypassed", "#16a34a", "B"),
            ("A2_native_recovery", "#f59e0b", "A2"),
        ):
            rib_index = int(ribs_by_arm[arm][station]["rib_index"])
            values = selected_curves[arm][(rib_index, "after_auto_zrotate")]
            ax.plot(values[:, 0], (values[:, 2] - snapshots[arm]["radius_model"] * station) * MM, color=color, lw=.8, label=label)
        ax.axhline(0.0, color="black", ls="--", lw=.7)
        ax.set_title(f"r/R={station:.5f}")
        ax.set_xlabel("native curve parameter")
        ax.grid(alpha=.2)
    axes[0].set_ylabel("global Y minus requested Y (mm)")
    axes[0].legend()
    fig.suptitle("Automatic rib-plane rotation ablation and A2 recovery")
    fig.tight_layout()
    fig.savefig(run / "rib_plane_ablation.png", dpi=190)
    plt.close(fig)

    full_dir = run / "B_rotation_bypassed" / "full_validation"
    full_result = jread(full_dir / "geometry_validation_result.json")
    full_measurements = jread(full_dir / "completed_measurements.json", [])
    launcher = jread(full_dir / "launcher_result.json", {})
    topology = jread(full_dir / "retained_step_topology.json", {})
    ocp = jread(run / "B_rotation_bypassed" / "ocp_solidification.json")
    full_status = (
        "FULL_INTERNAL_DIAGNOSTIC_PASS"
        if full_result and full_result.get("passed")
        else "FULL_INTERNAL_DIAGNOSTIC_FAIL"
        if full_result
        else "THREE_STATION_PASS_FULL_VALIDATION_INCOMPLETE"
    )
    b_rows = [row for row in station_rows if row["arm"] == "B_rotation_bypassed"]
    effect = max(row["direct_A_to_B_sampled_max_mm"] for row in b_rows)
    all_invariants = all(
        (
            inventory_exact_ab,
            computed_angles_ab,
            b_applied_zero,
            len(set(preparation_hashes)) == 1,
            recovery["passed"],
        )
    )
    summary = {
        "experiment_id": "X57-AB-02",
        "run_id": run.name,
        "causal_outcome": "ROTATION_EFFECT_REPRODUCED" if all_invariants and effect >= .001 else "CONFOUNDED_OR_BASELINE_RECOVERY_FAILED",
        "candidate_outcome": full_status,
        "B_actually_run": snapshots["B_rotation_bypassed"]["rotation_mode"] == "BYPASSED",
        "only_applied_auto_rotation_bypassed": inventory_exact_ab and computed_angles_ab and b_applied_zero,
        "A2_restored_A": recovery["passed"],
        "profile_preparation_unchanged": len(set(preparation_hashes)) == 1,
        "engineer_inputs_unchanged": inventory_exact_ab,
        "pseudo_rib_count": len(inventories["A_native"]),
        "three_station_B_all_original_gates_pass": all(row["all_original_gates_pass"] for row in b_rows),
        "maximum_direct_A_B_effect_mm": effect,
        "material_effect_threshold_mm": .001,
        "profile_preparation_fixed_background": profile_preparation,
        "full_validation": {
            "planned_station_count": launcher.get("planned_station_count"),
            "completed_station_count": launcher.get("completed_station_count", len(full_measurements)),
            "passed_station_count": sum(all_pass(row) for row in full_measurements),
            "failed_station_count": sum(not all_pass(row) for row in full_measurements),
            "production_geometry_summary": full_result,
            "launcher": launcher,
        },
        "topology": topology,
        "ocp_solidification": ocp,
        "candidate_step": {
            "path": str((run / "B_rotation_bypassed" / "candidate_solid.step").resolve()),
            "sha256": digest(run / "B_rotation_bypassed" / "candidate_solid.step"),
            "size_bytes": (run / "B_rotation_bypassed" / "candidate_solid.step").stat().st_size,
        },
        "original_product_job": "FAILED",
        "original_retained_blade_validation": "FAIL",
        "external_nasa_fidelity": "UNVERIFIED",
        "scope": "isolated native diagnostic prototype; not deployed",
        "analysis_elapsed_seconds": time.monotonic() - started,
    }
    jwrite(run / "experiment_summary.json", summary)

    environment = {
        "captured_at": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], text=True, capture_output=True, check=True).stdout.strip(),
        "head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip(),
        "git_status_short": subprocess.run(["git", "status", "--short"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.splitlines(),
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "diagnostic_binary": {
            "path": str((args.install_dir / "vspscript").resolve()),
            "sha256": digest(args.install_dir / "vspscript"),
        },
        "native_source": {
            "path": str(args.source_dir.resolve()),
            "commit": subprocess.run(["git", "-C", str(args.source_dir), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip(),
            "dirty_status": subprocess.run(["git", "-C", str(args.source_dir), "status", "--short"], text=True, capture_output=True, check=True).stdout.splitlines(),
        },
        "production_runtime_vspscript": {
            "path": str((ROOT / ".tooling/openvsp-3.54.0/opt/OpenVSP/vspscript").resolve()),
            "sha256": digest(ROOT / ".tooling/openvsp-3.54.0/opt/OpenVSP/vspscript"),
            "used_for_arms": False,
        },
        "analysis_script_sha256": digest(Path(__file__)),
    }
    try:
        import OCP
        import scipy

        environment["ocp"] = getattr(OCP, "__version__", "unknown")
        environment["scipy"] = scipy.__version__
    except Exception as error:  # pragma: no cover - evidence only
        environment["dependency_error"] = f"{type(error).__name__}: {error}"
    jwrite(run / "environment_identity.json", environment)

    print(json.dumps({
        "causal_outcome": summary["causal_outcome"],
        "candidate_outcome": summary["candidate_outcome"],
        "max_A_B_effect_mm": effect,
        "full_planned": summary["full_validation"]["planned_station_count"],
        "full_completed": summary["full_validation"]["completed_station_count"],
    }, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
