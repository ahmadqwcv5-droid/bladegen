"""Compare a fresh UI X-57 job with the user's original successful job.

This reports the project's existing direct OCP STEP comparison without registration.
It does not generate, repair, or revalidate CAD.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from bladegen.validation.geometry_validation import compare_steps


ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "output/runs/3970dc6383f1425b9726d5a9a00f4202"
CONTRACT = ROOT / "qualification/l1a_01/repeatability_contract.json"
METRICS = {
    "actual_chord_mm": "per_station_actual_chord_mm",
    "actual_twist_deg": "per_station_actual_twist_deg",
    "reference_axis_position_error_mm": "per_station_reference_axis_error_mm",
    "measured_te_mm": "per_station_measured_te_mm",
    "contour_rms_mm": "per_station_contour_rms_mm",
    "contour_p95_mm": "per_station_contour_p95_mm",
    "contour_max_mm": "per_station_contour_sampled_max_mm",
}
FLAGS = (
    "wire_count_pass", "wire_valid_pass", "wire_closed_pass", "chord_pass",
    "twist_pass", "reference_axis_pass", "contour_rms_pass",
    "contour_p95_pass", "contour_max_pass", "te_pass",
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def topology_good(record: dict) -> bool:
    return all((
        record.get("solids") == 1,
        record.get("shells") == 1,
        record.get("free_edges") == 0,
        record.get("closed_shell") is True,
        record.get("brepcheck_valid") is True,
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("new_job", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    old, new = OLD, args.new_job.resolve()
    contract = read_json(CONTRACT)
    limits = contract["comparison_limits"]
    old_input, new_input = read_json(old / "blade_spec_input.json"), read_json(new / "blade_spec_input.json")
    old_resolved, new_resolved = read_json(old / "resolved_blade_spec.json"), read_json(new / "resolved_blade_spec.json")
    old_manifest, new_manifest = read_json(old / "engine_manifest.json"), read_json(new / "engine_manifest.json")
    old_validation, new_validation = read_json(old / "validation.json"), read_json(new / "validation.json")
    old_solid = old_validation["solidification"]["solid_after_reimport"]
    new_solid = new_validation["solidification"]["solid_after_reimport"]
    old_stations = old_validation["geometry_validation"]["stations"]
    new_stations = new_validation["geometry_validation"]["stations"]
    plan_keys = ("requested_r_over_R", "sampled_r_over_R", "station_kind", "station_roles", "endpoint", "sample_offset_r_over_R")
    plan_equal = len(old_stations) == len(new_stations) == 41 and all(
        all(left.get(key) == right.get(key) for key in plan_keys)
        for left, right in zip(old_stations, new_stations)
    )
    metric_diffs = {
        metric: max(abs(float(a[metric]) - float(b[metric])) for a, b in zip(old_stations, new_stations))
        for metric in METRICS
    } if len(old_stations) == len(new_stations) else {}
    all_station_flags = all(
        all(station.get(flag) is True for flag in FLAGS)
        and (station.get("imported_profile_acceptance") is None or station["imported_profile_acceptance"].get("passed") is True)
        for station in new_stations
    )
    bbox_delta = max(
        abs(a - b)
        for key in ("min_mm", "max_mm")
        for a, b in zip(old_solid["bbox"][key], new_solid["bbox"][key])
    )
    volume_delta = abs(old_solid["volume_mm3"] - new_solid["volume_mm3"])
    area_delta = abs(old_solid["surface_area_mm2"] - new_solid["surface_area_mm2"])
    direct = compare_steps(old / "blade_solid.step", new / "blade_solid.step", samples=41)
    old_def = old_manifest["definition_hashes"]
    new_def = new_manifest["definition_hashes"]
    identity = {
        "raw_input_sha256_old": digest(old / "blade_spec_input.json"),
        "raw_input_sha256_new": digest(new / "blade_spec_input.json"),
        "raw_input_bytes_equal": (old / "blade_spec_input.json").read_bytes() == (new / "blade_spec_input.json").read_bytes(),
        "parsed_input_equal": old_input == new_input,
        "resolved_json_equal": old_resolved == new_resolved,
        "canonical_submitted_equal": old_def["canonical_submitted_sha256"] == new_def["canonical_submitted_sha256"],
        "canonical_resolved_equal": old_def["canonical_resolved_sha256"] == new_def["canonical_resolved_sha256"],
        "runtime_fingerprint_equal": old_manifest["actually_loaded_runtime"]["fingerprint"] == new_manifest["actually_loaded_runtime"]["fingerprint"],
        "production_source_set_equal": old_manifest["implementation"]["source_set"]["aggregate_sha256"] == new_manifest["implementation"]["source_set"]["aggregate_sha256"],
        "old_source_set_sha256": old_manifest["implementation"]["source_set"]["aggregate_sha256"],
        "new_source_set_sha256": new_manifest["implementation"]["source_set"]["aggregate_sha256"],
    }
    checks = {
        **{key: value for key, value in identity.items() if isinstance(value, bool)},
        "old_validation_pass": old_validation["status"] == "PASS",
        "new_validation_pass": new_validation["status"] == "PASS" and new_validation["geometry_validation"]["passed"] is True,
        "station_plan_equal": plan_equal,
        "all_41_station_measurement_records_equal": old_stations == new_stations,
        "new_station_flags_pass": all_station_flags,
        "old_topology_pass": topology_good(old_solid),
        "new_topology_pass": topology_good(new_solid),
        "new_roundtrip_pass": all(new_validation["solidification"]["roundtrip"].get(key) is True for key in ("one_solid", "one_shell", "zero_free_edges", "closed_shell", "brepcheck_valid")),
        "station_measurements_within_frozen_limits": all(metric_diffs[metric] <= limits[limit] for metric, limit in METRICS.items()) if metric_diffs else False,
        "bbox_within_frozen_limit": bbox_delta <= limits["bbox_max_abs_difference_mm"],
        "volume_within_frozen_limit": volume_delta <= limits["volume_absolute_difference_mm3"],
        "surface_area_within_frozen_limit": area_delta <= limits["surface_area_absolute_difference_mm2"],
        "direct_step_within_frozen_limits": all((
            direct["rms_mm"] <= limits["direct_step_same_frame_rms_mm"],
            direct["p95_mm"] <= limits["direct_step_same_frame_p95_mm"],
            direct["max_mm"] <= limits["direct_step_same_frame_sampled_max_mm"],
        )),
    }
    result = {
        "schema": "bladegen.l1a-01-same-blade-comparison.v1",
        "reference_job_id": OLD.name,
        "new_job_id": new.name,
        "frozen_contract": str(CONTRACT.relative_to(ROOT)),
        "identity": identity,
        "station_plan_count_old": len(old_stations),
        "station_plan_count_new": len(new_stations),
        "per_station_max_absolute_differences": metric_diffs,
        "topology_old": old_solid,
        "topology_new": new_solid,
        "bbox_max_abs_difference_mm": bbox_delta,
        "volume_absolute_difference_mm3": volume_delta,
        "surface_area_absolute_difference_mm2": area_delta,
        "direct_step_comparison": direct,
        "checks": checks,
        "passed": all(checks.values()),
        "external_nasa_fidelity": "UNVERIFIED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"passed": result["passed"], "checks": checks, "direct_step": {key: direct[key] for key in ("rms_mm", "p95_mm", "max_mm")}}, indent=2), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
