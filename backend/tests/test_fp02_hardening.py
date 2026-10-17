from __future__ import annotations

import json
import math
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

from api.services.jobs import Job, JobManager
from api.services.result_verification import (
    CompletionExpectation,
    ResultVerificationError,
    required_artifacts,
    verify_completed_result,
)
from bladegen.runtime.definitions import definition_identity
from bladegen.runtime.execution import DEFAULT_BUILD_TIMEOUT_SECONDS, resolve_build_timeout_seconds
from bladegen.runtime.identity import (
    PRODUCTION_CORE_FILES,
    ImplementationIdentityError,
    implementation_source_identity,
)
from bladegen.runtime.manager import CONSTRUCTION_CONTRACT, EXPECTED_BUILD_ID
from bladegen.runtime.provenance import COMPLETION_CONTEXT_SCHEMA, ENGINE_MANIFEST_SCHEMA

ROOT = Path(__file__).resolve().parents[2]
FINGERPRINT = "f" * 64


def _load(name: str) -> dict:
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))


def _expectation(payload: dict, build_type: str = "blade") -> CompletionExpectation:
    return CompletionExpectation(
        job_id="a" * 32,
        run_id="a" * 32,
        build_type=build_type,
        definition_identity=definition_identity(payload, build_type),
        runtime_fingerprint=FINGERPRINT,
        runtime_build_id=EXPECTED_BUILD_ID,
        runtime_contract=CONSTRUCTION_CONTRACT,
        worker_timeout_seconds=900.0,
        requested_blade_count=(payload["assembly"]["blade_count"] if build_type == "propeller" else None),
    )


def _topology() -> dict:
    return {
        "shape_type": "SOLID",
        "solids": 1,
        "shells": 1,
        "faces": 8,
        "free_edges": 0,
        "closed_shell": True,
        "brepcheck_valid": True,
        "surface_area_mm2": 10.0,
        "volume_mm3": 5.0,
    }


def _roundtrip(with_pass: bool = False) -> dict:
    value = {
        "one_solid": True,
        "one_shell": True,
        "zero_free_edges": True,
        "closed_shell": True,
        "brepcheck_valid": True,
        "volume_delta_mm3": 0.0,
        "bbox_max_abs_delta_mm": 0.0,
    }
    if with_pass:
        value["passed"] = True
    return value


def _context(expectation: CompletionExpectation, identity: dict, build_type: str) -> dict:
    return {
        "schema": COMPLETION_CONTEXT_SCHEMA,
        "build_type": build_type,
        "run_id": expectation.run_id,
        "job_id": expectation.job_id,
        "definition_identity": identity,
        "runtime": {
            "fingerprint": expectation.runtime_fingerprint,
            "build_id": expectation.runtime_build_id,
            "construction_contract": expectation.runtime_contract,
        },
        "planned_section_count": 1,
        "completed_section_count": 1,
        "worker_timeout_seconds": expectation.worker_timeout_seconds,
    }


def _blade_result(expectation: CompletionExpectation, identity: dict) -> dict:
    distribution = {
        "interpolation_match": True,
        "point_count_match": True,
        "max_radius_error": 0.0,
        "max_value_error": 0.0,
    }
    station = {
        "station_roles": ["airfoil_station"],
        "requested_r_over_R": 0.2,
        "sampled_r_over_R": 0.205,
        "expected_chord_mm": 20.0,
        "actual_chord_mm": 20.0,
        "chord_absolute_error_mm": 0.0,
        "expected_twist_deg": 10.0,
        "actual_twist_deg": 10.0,
        "twist_absolute_error_deg": 0.0,
        "reference_axis_position_error_mm": 0.0,
        "expected_te_at_sample_mm": 0.0,
        "measured_te_mm": 0.0,
        "te_absolute_error_mm": 0.0,
        "contour_rms_mm": 0.0,
        "contour_p95_mm": 0.0,
        "contour_max_mm": 0.0,
        "chord_pass": True,
        "twist_pass": True,
        "reference_axis_pass": True,
        "contour_rms_pass": True,
        "contour_p95_pass": True,
        "contour_max_pass": True,
        "te_pass": True,
        "wire_count_pass": True,
        "wire_valid_pass": True,
        "wire_closed_pass": True,
    }
    return {
        "status": "PASS",
        "build_type": "blade",
        "openvsp_readback": {
            "passed": True,
            "identity_checks": {
                "schema_version": True,
                "name": True,
                "units": True,
                "rotation_direction": True,
            },
            "distributions": {
                name: deepcopy(distribution)
                for name in (
                    "chord_distribution",
                    "twist_distribution",
                    "rake_distribution",
                    "skew_distribution",
                    "thickness_distribution",
                )
            },
        },
        "geometry_validation": {"passed": True, "station_count": 1, "stations": [station]},
        "solidification": {
            "solid_after_reimport": _topology(),
            "roundtrip": _roundtrip(),
        },
        "completion_context": _context(expectation, identity, "blade"),
    }


def _propeller_result(expectation: CompletionExpectation) -> dict:
    identity = expectation.definition_identity
    blade_identity = {
        "schema": identity["schema"],
        "build_type": "blade",
        "canonical_submitted_sha256": identity[
            "reference_blade_canonical_submitted_sha256"
        ],
        "normalized_model_sha256": identity["reference_blade_normalized_sha256"],
    }
    count = expectation.requested_blade_count or 2
    collisions = [
        {
            "blade_pair": [left + 1, right + 1],
            "outside_hub_intersection_mm3": 0.0,
            "passed": True,
        }
        for left in range(count)
        for right in range(left + 1, count)
    ]
    assembly = {
        "passed": True,
        "requested_blade_count": count,
        "actual_blade_placement_count": count,
        "azimuth_angles_deg": [360.0 * index / count for index in range(count)],
        "radial_directions": [[0.0, 1.0, 0.0] for _ in range(count)],
        "copy_volumes_mm3": [5.0] * count,
        "hub_blade_overlap_mm3": [1.0] * count,
        "minimum_positive_overlap_mm3": 0.00001,
        "blade_collisions": collisions,
        "fusion_steps": [
            {"blade_index": index + 1, "solids": 1, "brepcheck_valid": True}
            for index in range(count)
        ],
        "fusion_status": "PASS",
        "bore_cut_status": "PASS",
        "reference_blade": _topology(),
        "hub": _topology(),
        "final_before_export": _topology(),
        "final_after_reimport": _topology(),
        "bore": {
            "x_axis_aligned": True,
            "continuous_through_hole": True,
            "boundary_circle_count": 2,
            "maximum_radius_error_mm": 0.0,
            "residual_material_volume_mm3": 0.0,
        },
        "roundtrip": _roundtrip(with_pass=True),
    }
    return {
        "status": "PASS",
        "build_type": "propeller",
        "reference_blade_validation": _blade_result(expectation, blade_identity),
        "assembly_validation": assembly,
        "completion_context": _context(expectation, identity, "propeller"),
    }


def _write_case(tmp_path: Path, payload: dict, build_type: str = "blade") -> tuple[CompletionExpectation, dict]:
    expectation = _expectation(payload, build_type)
    for name in required_artifacts(build_type):
        (tmp_path / name).write_bytes(b"fresh")
    result = (
        _blade_result(expectation, expectation.definition_identity)
        if build_type == "blade"
        else _propeller_result(expectation)
    )
    (tmp_path / "validation.json").write_text(json.dumps(result), encoding="utf-8")
    manifest = {
        "schema": ENGINE_MANIFEST_SCHEMA,
        "state": "COMPLETED",
        "definition_identity": expectation.definition_identity,
        "execution": {
            "job_id": expectation.job_id,
            "run_id": expectation.run_id,
            "api_worker_timeout_seconds": expectation.worker_timeout_seconds,
        },
        "actually_loaded_runtime": {
            "fingerprint": expectation.runtime_fingerprint,
            "build_id": expectation.runtime_build_id,
            "construction_contract": expectation.runtime_contract,
        },
        "implementation": {"source_set": implementation_source_identity()},
    }
    (tmp_path / "engine_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return expectation, result


def test_implementation_identity_changes_for_policy_and_fails_if_required_missing(tmp_path: Path) -> None:
    for relative in PRODUCTION_CORE_FILES:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    before = implementation_source_identity(tmp_path)
    policy = tmp_path / "backend/bladegen/validation/policy.py"
    policy.write_text(policy.read_text() + "\n# identity mutation\n", encoding="utf-8")
    after = implementation_source_identity(tmp_path)
    assert before["aggregate_sha256"] != after["aggregate_sha256"]
    (tmp_path / "backend/bladegen/validation/measure_sections.py").unlink()
    with pytest.raises(ImplementationIdentityError, match="measure_sections.py"):
        implementation_source_identity(tmp_path)


def test_timeout_default_environment_override_and_invalid(monkeypatch) -> None:
    monkeypatch.delenv("BLADEGEN_BUILD_TIMEOUT", raising=False)
    assert resolve_build_timeout_seconds() == DEFAULT_BUILD_TIMEOUT_SECONDS
    monkeypatch.setenv("BLADEGEN_BUILD_TIMEOUT", "900")
    assert resolve_build_timeout_seconds() == 900.0
    assert resolve_build_timeout_seconds(7) == 7.0
    for value in ("0", "-1", "nan", "inf", "not-a-number"):
        monkeypatch.setenv("BLADEGEN_BUILD_TIMEOUT", value)
        with pytest.raises(ValueError, match="positive finite"):
            resolve_build_timeout_seconds()


def test_valid_current_blade_and_propeller_reports_are_accepted(tmp_path: Path) -> None:
    blade_dir = tmp_path / "blade"
    blade_dir.mkdir()
    blade_expectation, _ = _write_case(blade_dir, _load("sprint02_case_a_three_section.json"))
    verify_completed_result(blade_dir, blade_expectation, {})
    prop_dir = tmp_path / "propeller"
    prop_dir.mkdir()
    prop_expectation, _ = _write_case(
        prop_dir, _load("propeller_two_blade.json"), "propeller"
    )
    verify_completed_result(prop_dir, prop_expectation, {})


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda result: result.update(status="FAIL"), "status"),
        (
            lambda result: result["geometry_validation"]["stations"][0].pop("te_pass"),
            "te_pass",
        ),
        (
            lambda result: result["geometry_validation"]["stations"][0].update(te_pass="false"),
            "literal true",
        ),
        (
            lambda result: result["geometry_validation"]["stations"][0].update(
                contour_rms_mm=math.inf
            ),
            "non-finite",
        ),
        (
            lambda result: result["completion_context"].update(job_id="wrong"),
            "job_id",
        ),
        (
            lambda result: result["geometry_validation"].update(
                station_count=0, stations=[]
            ),
            "positive integer",
        ),
    ],
)
def test_blade_report_fail_closed_cases(tmp_path: Path, mutation, match: str) -> None:
    expectation, result = _write_case(tmp_path, _load("sprint02_case_a_three_section.json"))
    mutation(result)
    (tmp_path / "validation.json").write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(ResultVerificationError, match=match):
        verify_completed_result(tmp_path, expectation, {})


def test_missing_empty_and_stale_artifacts_fail(tmp_path: Path) -> None:
    expectation, _ = _write_case(tmp_path, _load("sprint02_case_a_three_section.json"))
    (tmp_path / "validation.csv").unlink()
    with pytest.raises(ResultVerificationError, match="validation.csv"):
        verify_completed_result(tmp_path, expectation, {})
    (tmp_path / "validation.csv").write_bytes(b"")
    with pytest.raises(ResultVerificationError, match="empty"):
        verify_completed_result(tmp_path, expectation, {})
    (tmp_path / "validation.csv").write_bytes(b"fresh")
    with pytest.raises(ResultVerificationError, match="stale"):
        verify_completed_result(tmp_path, expectation, {"validation.csv": "d098ab5e44b9aabb755f76d806598f43573c662b35e4a2eab1e312ec9ad195e2"})


def test_propeller_blade_pass_with_assembly_fail_is_rejected(tmp_path: Path) -> None:
    expectation, result = _write_case(tmp_path, _load("propeller_two_blade.json"), "propeller")
    result["assembly_validation"]["passed"] = False
    (tmp_path / "validation.json").write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(ResultVerificationError, match="assembly_validation.passed"):
        verify_completed_result(tmp_path, expectation, {})


def test_malformed_result_and_wrong_runtime_are_rejected(tmp_path: Path) -> None:
    expectation, _ = _write_case(tmp_path, _load("sprint02_case_a_three_section.json"))
    (tmp_path / "validation.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(ResultVerificationError, match="Malformed validation.json"):
        verify_completed_result(tmp_path, expectation, {})
    expectation, _ = _write_case(tmp_path, _load("sprint02_case_a_three_section.json"))
    manifest = json.loads((tmp_path / "engine_manifest.json").read_text(encoding="utf-8"))
    manifest["actually_loaded_runtime"]["fingerprint"] = "wrong"
    (tmp_path / "engine_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ResultVerificationError, match="runtime fingerprint"):
        verify_completed_result(tmp_path, expectation, {})


def test_zero_exit_fail_report_is_rejected_at_worker_boundary(monkeypatch, tmp_path: Path) -> None:
    payload = _load("sprint02_case_a_three_section.json")
    output = tmp_path / ("a" * 32)
    output.mkdir()
    input_path = output / "blade_spec_input.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    expected = _expectation(payload)
    job = Job(
        expected.job_id,
        output_dir=output,
        runtime_root=str(tmp_path / "runtime"),
        runtime_fingerprint=expected.runtime_fingerprint,
        runtime_build_id=expected.runtime_build_id,
        runtime_contract=expected.runtime_contract,
        definition_identity=expected.definition_identity,
        worker_timeout_seconds=expected.worker_timeout_seconds,
    )

    def child(command, **kwargs):
        _, result = _write_case(output, payload)
        result["status"] = "FAIL"
        (output / "validation.json").write_text(json.dumps(result), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    manager = JobManager(timeout_seconds=900, run_root=tmp_path / "runs")
    monkeypatch.setattr(subprocess, "run", child)
    manager._run(job, input_path)
    manager._executor.shutdown(wait=False)
    assert job.status == "failed"
    assert "status must be literal PASS" in (job.error or "")


def test_manager_timeout_snapshot_reaches_supervisor_worker_context_and_manifest(
    monkeypatch, tmp_path: Path
) -> None:
    payload = _load("sprint02_case_a_three_section.json")
    output = tmp_path / ("a" * 32)
    output.mkdir()
    input_path = output / "blade_spec_input.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    expected = _expectation(payload)
    job = Job(
        expected.job_id,
        output_dir=output,
        runtime_root=str(tmp_path / "runtime"),
        runtime_fingerprint=expected.runtime_fingerprint,
        runtime_build_id=expected.runtime_build_id,
        runtime_contract=expected.runtime_contract,
        definition_identity=expected.definition_identity,
        worker_timeout_seconds=expected.worker_timeout_seconds,
    )
    captured: dict = {}

    def child(command, **kwargs):
        captured.update(kwargs)
        _write_case(output, payload)
        return subprocess.CompletedProcess(command, 0, "", "")

    manager = JobManager(timeout_seconds=900, run_root=tmp_path / "runs")
    monkeypatch.setattr(subprocess, "run", child)
    manager._run(job, input_path)
    manager._executor.shutdown(wait=False)
    assert job.status == "succeeded"
    assert captured["timeout"] == 900.0
    assert captured["env"]["BLADEGEN_BUILD_TIMEOUT"] == "900"
    manifest = json.loads((output / "engine_manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output / "validation.json").read_text(encoding="utf-8"))
    assert manifest["execution"]["api_worker_timeout_seconds"] == 900.0
    assert report["completion_context"]["worker_timeout_seconds"] == 900.0
