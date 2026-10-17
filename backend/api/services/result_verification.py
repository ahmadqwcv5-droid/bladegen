"""Strict worker-boundary verification for current BladeGen build reports."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bladegen.runtime.identity import implementation_source_identity
from bladegen.runtime.provenance import COMPLETION_CONTEXT_SCHEMA, ENGINE_MANIFEST_SCHEMA

BLADE_ARTIFACTS = (
    "blade_solid.step",
    "blade_preview.stl",
    "blade_spec.json",
    "resolved_blade_spec.json",
    "blade_openvsp.vsp3",
    "blade_openvsp.step",
    "validation.json",
    "validation.csv",
    "engine_manifest.json",
)
PROPELLER_ARTIFACTS = (
    "propeller_solid.step",
    "propeller_preview.stl",
    "propeller_spec.json",
    "blade_solid.step",
    "blade_preview.stl",
    "blade_spec.json",
    "resolved_blade_spec.json",
    "blade_openvsp.vsp3",
    "blade_openvsp.step",
    "blade_validation.json",
    "blade_validation.csv",
    "validation.json",
    "assembly_validation.csv",
    "engine_manifest.json",
)


class ResultVerificationError(RuntimeError):
    """A child exited zero but did not prove a current successful product result."""


@dataclass(frozen=True)
class CompletionExpectation:
    job_id: str
    run_id: str
    build_type: str
    definition_identity: dict[str, Any]
    runtime_fingerprint: str
    runtime_build_id: str
    runtime_contract: str
    worker_timeout_seconds: float
    requested_blade_count: int | None = None


def required_artifacts(build_type: str) -> tuple[str, ...]:
    if build_type == "blade":
        return BLADE_ARTIFACTS
    if build_type == "propeller":
        return PROPELLER_ARTIFACTS
    raise ResultVerificationError(f"Unsupported build type: {build_type}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact_signatures(output_dir: Path, names: tuple[str, ...]) -> dict[str, str]:
    return {
        name: _sha256(output_dir / name)
        for name in names
        if (output_dir / name).is_file()
    }


def _load_json(path: Path) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON number {value}")

    try:
        value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ResultVerificationError(f"Malformed {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ResultVerificationError(f"{path.name} must contain a JSON object")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ResultVerificationError(message)


def _true(mapping: dict[str, Any], key: str, where: str) -> None:
    _require(mapping.get(key) is True, f"{where}.{key} must be literal true")


def _finite(mapping: dict[str, Any], key: str, where: str) -> float:
    value = mapping.get(key)
    _require(
        not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value),
        f"{where}.{key} must be a finite number",
    )
    return float(value)


def _positive_int(mapping: dict[str, Any], key: str, where: str) -> int:
    value = mapping.get(key)
    _require(
        not isinstance(value, bool) and isinstance(value, int) and value > 0,
        f"{where}.{key} must be a positive integer",
    )
    return value


def _topology(value: Any, where: str) -> None:
    _require(isinstance(value, dict), f"{where} must be an object")
    _require(value.get("shape_type") == "SOLID", f"{where}.shape_type must be SOLID")
    _require(value.get("solids") == 1, f"{where}.solids must equal 1")
    _require(value.get("shells") == 1, f"{where}.shells must equal 1")
    _require(value.get("free_edges") == 0, f"{where}.free_edges must equal 0")
    _true(value, "closed_shell", where)
    _true(value, "brepcheck_valid", where)
    _positive_int(value, "faces", where)
    _finite(value, "surface_area_mm2", where)
    _finite(value, "volume_mm3", where)


def _roundtrip(value: Any, where: str, *, explicit_pass: bool = False) -> None:
    _require(isinstance(value, dict), f"{where} must be an object")
    for key in ("one_solid", "one_shell", "zero_free_edges", "closed_shell", "brepcheck_valid"):
        _true(value, key, where)
    if explicit_pass:
        _true(value, "passed", where)
    _finite(value, "volume_delta_mm3", where)
    _finite(value, "bbox_max_abs_delta_mm", where)


def _completion_context(
    value: Any,
    expectation: CompletionExpectation,
    *,
    build_type: str,
    definition_identity: dict[str, Any],
    station_count: int,
) -> None:
    where = "completion_context"
    _require(isinstance(value, dict), f"{where} must be an object")
    _require(value.get("schema") == COMPLETION_CONTEXT_SCHEMA, f"Unsupported {where} schema")
    _require(value.get("build_type") == build_type, f"{where}.build_type mismatch")
    _require(value.get("job_id") == expectation.job_id, f"{where}.job_id mismatch")
    _require(value.get("run_id") == expectation.run_id, f"{where}.run_id mismatch")
    _require(
        value.get("definition_identity") == definition_identity,
        f"{where}.definition_identity mismatch",
    )
    _require(value.get("planned_section_count") == station_count, f"{where} planned count mismatch")
    _require(value.get("completed_section_count") == station_count, f"{where} completed count mismatch")
    _require(
        value.get("worker_timeout_seconds") == expectation.worker_timeout_seconds,
        f"{where}.worker_timeout_seconds mismatch",
    )
    runtime = value.get("runtime")
    _require(isinstance(runtime, dict), f"{where}.runtime must be an object")
    _require(runtime.get("fingerprint") == expectation.runtime_fingerprint, "runtime fingerprint mismatch")
    _require(runtime.get("build_id") == expectation.runtime_build_id, "runtime build ID mismatch")
    _require(runtime.get("construction_contract") == expectation.runtime_contract, "runtime contract mismatch")


def _blade_result(
    result: dict[str, Any],
    expectation: CompletionExpectation,
    definition_identity: dict[str, Any],
) -> int:
    _require(result.get("status") == "PASS", "Blade status must be literal PASS")
    _require(result.get("build_type") == "blade", "Blade build_type mismatch")
    readback = result.get("openvsp_readback")
    _require(isinstance(readback, dict), "openvsp_readback must be an object")
    _true(readback, "passed", "openvsp_readback")
    identities = readback.get("identity_checks")
    _require(isinstance(identities, dict) and identities, "identity_checks must be nonempty")
    for key in ("schema_version", "name", "units", "rotation_direction"):
        _true(identities, key, "openvsp_readback.identity_checks")
    distributions = readback.get("distributions")
    _require(isinstance(distributions, dict) and distributions, "readback distributions must be nonempty")
    for name in (
        "chord_distribution",
        "twist_distribution",
        "rake_distribution",
        "skew_distribution",
        "thickness_distribution",
    ):
        item = distributions.get(name)
        _require(isinstance(item, dict), f"readback {name} missing")
        _true(item, "interpolation_match", f"readback.{name}")
        _true(item, "point_count_match", f"readback.{name}")
        _finite(item, "max_radius_error", f"readback.{name}")
        _finite(item, "max_value_error", f"readback.{name}")

    geometry = result.get("geometry_validation")
    _require(isinstance(geometry, dict), "geometry_validation must be an object")
    _true(geometry, "passed", "geometry_validation")
    count = _positive_int(geometry, "station_count", "geometry_validation")
    stations = geometry.get("stations")
    _require(isinstance(stations, list) and stations, "geometry stations must be nonempty")
    _require(len(stations) == count, "geometry station_count does not match station records")
    required_flags = (
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
    numeric_fields = (
        "requested_r_over_R",
        "sampled_r_over_R",
        "expected_chord_mm",
        "actual_chord_mm",
        "chord_absolute_error_mm",
        "expected_twist_deg",
        "actual_twist_deg",
        "twist_absolute_error_deg",
        "reference_axis_position_error_mm",
        "expected_te_at_sample_mm",
        "measured_te_mm",
        "te_absolute_error_mm",
        "contour_rms_mm",
        "contour_p95_mm",
        "contour_max_mm",
    )
    for index, station in enumerate(stations):
        where = f"geometry_validation.stations[{index}]"
        _require(isinstance(station, dict), f"{where} must be an object")
        _require(isinstance(station.get("station_roles"), list) and station["station_roles"], f"{where}.station_roles must be nonempty")
        for key in required_flags:
            _true(station, key, where)
        for key in numeric_fields:
            _finite(station, key, where)

    solidification = result.get("solidification")
    _require(isinstance(solidification, dict), "solidification must be an object")
    _topology(solidification.get("solid_after_reimport"), "solidification.solid_after_reimport")
    _roundtrip(solidification.get("roundtrip"), "solidification.roundtrip")
    regression = result.get("x57_regression")
    if regression is not None:
        _require(isinstance(regression, dict), "x57_regression must be an object")
        _true(regression, "passed", "x57_regression")
    _completion_context(
        result.get("completion_context"),
        expectation,
        build_type="blade",
        definition_identity=definition_identity,
        station_count=count,
    )
    return count


def _propeller_result(result: dict[str, Any], expectation: CompletionExpectation) -> None:
    _require(result.get("status") == "PASS", "Propeller status must be literal PASS")
    _require(result.get("build_type") == "propeller", "Propeller build_type mismatch")
    nested = result.get("reference_blade_validation")
    _require(isinstance(nested, dict), "reference_blade_validation must be an object")
    reference_identity = {
        "schema": expectation.definition_identity["schema"],
        "build_type": "blade",
        "canonical_submitted_sha256": expectation.definition_identity[
            "reference_blade_canonical_submitted_sha256"
        ],
        "normalized_model_sha256": expectation.definition_identity[
            "reference_blade_normalized_sha256"
        ],
    }
    count = _blade_result(nested, expectation, reference_identity)
    assembly = result.get("assembly_validation")
    _require(isinstance(assembly, dict), "assembly_validation must be an object")
    _true(assembly, "passed", "assembly_validation")
    blade_count = expectation.requested_blade_count
    _require(isinstance(blade_count, int), "Expected propeller blade count is missing")
    _require(assembly.get("requested_blade_count") == blade_count, "requested blade count mismatch")
    _require(assembly.get("actual_blade_placement_count") == blade_count, "actual blade count mismatch")
    for key in ("azimuth_angles_deg", "radial_directions", "copy_volumes_mm3", "hub_blade_overlap_mm3"):
        values = assembly.get(key)
        _require(isinstance(values, list) and len(values) == blade_count, f"assembly {key} count mismatch")
    minimum = _finite(assembly, "minimum_positive_overlap_mm3", "assembly_validation")
    for value in assembly["hub_blade_overlap_mm3"]:
        _require(not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and value > minimum, "hub overlap must be finite and above the existing minimum")
    collisions = assembly.get("blade_collisions")
    _require(isinstance(collisions, list) and len(collisions) == blade_count * (blade_count - 1) // 2, "blade collision record count mismatch")
    for index, row in enumerate(collisions):
        _require(isinstance(row, dict), "collision record must be an object")
        _true(row, "passed", f"assembly.blade_collisions[{index}]")
        _finite(row, "outside_hub_intersection_mm3", f"assembly.blade_collisions[{index}]")
    steps = assembly.get("fusion_steps")
    _require(isinstance(steps, list) and len(steps) == blade_count, "fusion step count mismatch")
    for index, row in enumerate(steps):
        _require(isinstance(row, dict) and row.get("solids") == 1, f"fusion step {index} must contain one solid")
        _true(row, "brepcheck_valid", f"assembly.fusion_steps[{index}]")
    _require(assembly.get("fusion_status") == "PASS", "fusion_status must be PASS")
    _require(assembly.get("bore_cut_status") == "PASS", "bore_cut_status must be PASS")
    _topology(assembly.get("reference_blade"), "assembly.reference_blade")
    _topology(assembly.get("hub"), "assembly.hub")
    _topology(assembly.get("final_before_export"), "assembly.final_before_export")
    _topology(assembly.get("final_after_reimport"), "assembly.final_after_reimport")
    bore = assembly.get("bore")
    _require(isinstance(bore, dict), "assembly.bore must be an object")
    _true(bore, "x_axis_aligned", "assembly.bore")
    _true(bore, "continuous_through_hole", "assembly.bore")
    _require(isinstance(bore.get("boundary_circle_count"), int) and bore["boundary_circle_count"] >= 2, "assembly.bore requires at least two boundary circles")
    _finite(bore, "maximum_radius_error_mm", "assembly.bore")
    _finite(bore, "residual_material_volume_mm3", "assembly.bore")
    _roundtrip(assembly.get("roundtrip"), "assembly.roundtrip", explicit_pass=True)
    _completion_context(
        result.get("completion_context"),
        expectation,
        build_type="propeller",
        definition_identity=expectation.definition_identity,
        station_count=count,
    )


def verify_completed_result(
    output_dir: Path,
    expectation: CompletionExpectation,
    before_signatures: dict[str, str],
) -> None:
    names = required_artifacts(expectation.build_type)
    for name in names:
        path = output_dir / name
        _require(path.is_file(), f"Build did not produce required artifact: {name}")
        _require(path.stat().st_size > 0, f"Required artifact is empty: {name}")
        current = _sha256(path)
        _require(before_signatures.get(name) != current, f"Required artifact is stale: {name}")

    manifest = _load_json(output_dir / "engine_manifest.json")
    _require(manifest.get("schema") == ENGINE_MANIFEST_SCHEMA, "Unsupported engine manifest schema")
    _require(manifest.get("state") == "COMPLETED", "Engine manifest is not completed")
    _require(manifest.get("definition_identity") == expectation.definition_identity, "Manifest definition identity mismatch")
    execution = manifest.get("execution")
    _require(isinstance(execution, dict), "Manifest execution must be an object")
    _require(execution.get("job_id") == expectation.job_id, "Manifest job ID mismatch")
    _require(execution.get("run_id") == expectation.run_id, "Manifest run ID mismatch")
    _require(execution.get("api_worker_timeout_seconds") == expectation.worker_timeout_seconds, "Manifest worker timeout mismatch")
    actual = manifest.get("actually_loaded_runtime")
    _require(isinstance(actual, dict), "Manifest loaded runtime is missing")
    _require(actual.get("fingerprint") == expectation.runtime_fingerprint, "Manifest runtime fingerprint mismatch")
    _require(actual.get("build_id") == expectation.runtime_build_id, "Manifest runtime build ID mismatch")
    _require(actual.get("construction_contract") == expectation.runtime_contract, "Manifest runtime contract mismatch")
    implementation = manifest.get("implementation")
    _require(isinstance(implementation, dict), "Manifest implementation metadata is missing")
    _require(implementation.get("source_set") == implementation_source_identity(), "Manifest implementation source set mismatch")

    result = _load_json(output_dir / "validation.json")
    if expectation.build_type == "blade":
        _blade_result(result, expectation, expectation.definition_identity)
    else:
        _propeller_result(result, expectation)
