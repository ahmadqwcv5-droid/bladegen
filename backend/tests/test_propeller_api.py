from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routes import propellers
from bladegen.runtime.manager import RuntimeReadinessError

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = json.loads(
    (WORKSPACE_ROOT / "examples/propeller_three_blade.json").read_text(encoding="utf-8")
)
client = TestClient(app)


@pytest.fixture(autouse=True)
def ready_runtime(monkeypatch):
    identity = SimpleNamespace(
        root=Path("/test/fixed-plane-runtime"),
        fingerprint="f" * 64,
        build_id="openvsp-3.54.0-bladegen-fixed-plane.1",
        construction_contract="bladegen.fixed-radial-sections.v1",
    )
    monkeypatch.setattr(propellers.jobs, "_readiness_checker", lambda: identity)


def test_propeller_validation_reports_contract_and_nominal_overlap():
    response = client.post("/api/propellers/validate", json=EXAMPLE)
    assert response.status_code == 200
    payload = response.json()
    assert payload["blade_count"] == 3
    assert payload["airfoil_sections_per_blade"] == 5
    assert payload["rotation_axis"] == "X"
    assert payload["nominal_radial_overlap_mm"] == 5.0
    assert payload["nominal_hub_guidance"]["required_hub_diameter_bound_mm"] == 80.0
    assert payload["capabilities"]["supported_blade_counts"] == [2, 3, 4]


def test_propeller_capabilities_are_exposed_without_ocp_work():
    response = client.get("/api/propellers/capabilities")
    assert response.status_code == 200
    assert response.json() == {
        "contract_blade_count_min": 2,
        "contract_blade_count_max": 8,
        "supported_blade_counts": [2, 3, 4],
        "release_policy": (
            "Blade counts 2, 3, and 4 are qualified in this release; "
            "higher contract-valid counts are not yet qualified."
        ),
    }


def test_propeller_validation_rejects_bore_and_tangential_hub_contact():
    bore = {**EXAMPLE, "assembly": {**EXAMPLE["assembly"], "shaft_bore_diameter_mm": 90}}
    response = client.post("/api/propellers/validate", json=bore)
    assert response.status_code == 422
    assert "smaller than hub" in response.json()["detail"]
    assert response.json()["issues"][0]["code"] == "bore_smaller_than_hub_required"
    contact = {**EXAMPLE, "assembly": {**EXAMPLE["assembly"], "hub_diameter_mm": 80}}
    response = client.post("/api/propellers/validate", json=contact)
    assert response.status_code == 422
    body = response.json()
    assert body["issues"][0]["code"] == "hub_root_nominal_overlap_required"
    assert body["issues"][0]["field"] == "assembly.hub_diameter_mm"
    assert body["issues"][0]["context"]["required_diameter_bound_mm"] == 80
    assert "greater than 80 mm" in body["detail"]
    assert "errors.pydantic.dev" not in body["detail"]


def test_propeller_validation_returns_structured_issue_for_non_object_document():
    response = client.post("/api/propellers/validate", json=["not", "a", "document"])
    assert response.status_code == 422
    assert response.json() == {
        "detail": "PropellerSpec must be a JSON object.",
        "issues": [
            {
                "code": "invalid_document",
                "field": "",
                "message": "PropellerSpec must be a JSON object.",
            }
        ],
    }


def test_unsupported_count_is_rejected_before_job_submission(monkeypatch):
    candidate = {**EXAMPLE, "assembly": {**EXAMPLE["assembly"], "blade_count": 5}}
    submitted = []
    monkeypatch.setattr(propellers.jobs, "submit", lambda *args, **kwargs: submitted.append(args))
    validate_response = client.post("/api/propellers/validate", json=candidate)
    build_response = client.post("/api/propellers/build", json=candidate)
    assert validate_response.status_code == 422
    assert build_response.status_code == 422
    assert build_response.json()["issues"][0]["code"] == "blade_count_unsupported"
    assert "unsupported in this release" in build_response.json()["detail"]
    assert submitted == []


def test_nominal_hub_gap_is_rejected_before_job_submission(monkeypatch):
    candidate = {**EXAMPLE, "assembly": {**EXAMPLE["assembly"], "hub_diameter_mm": 60}}
    submitted = []
    monkeypatch.setattr(propellers.jobs, "submit", lambda *args, **kwargs: submitted.append(args))
    response = client.post("/api/propellers/build", json=candidate)
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "hub_root_nominal_overlap_required"
    assert submitted == []


def test_semantically_invalid_blade_is_rejected_by_validate_and_direct_build(monkeypatch):
    candidate = deepcopy(EXAMPLE)
    candidate["blade_spec"]["airfoil_sections"][1].pop("thickness_override_ratio", None)
    candidate["blade_spec"]["thickness_distribution"]["points"][1]["thickness_ratio"] = 0.20
    submitted = []
    monkeypatch.setattr(propellers.jobs, "submit", lambda *args, **kwargs: submitted.append(args))
    validate_response = client.post("/api/propellers/validate", json=candidate)
    build_response = client.post("/api/propellers/build", json=candidate)
    assert validate_response.status_code == 422
    assert build_response.status_code == 422
    assert build_response.json()["issues"][0]["code"] == "invalid_blade_spec"
    assert build_response.json()["issues"][0]["field"] == "blade_spec.thickness_distribution"
    assert submitted == []


def test_api_normalizes_omitted_azimuth_for_job_submission(monkeypatch):
    candidate = deepcopy(EXAMPLE)
    candidate["assembly"].pop("initial_azimuth_deg")
    submitted = []

    class AcceptedJob:
        job_id = "a" * 32
        build_type = "propeller"
        elapsed_seconds = 0.0
        runtime_build_id = "openvsp-3.54.0-bladegen-fixed-plane.1"
        runtime_contract = "bladegen.fixed-radial-sections.v1"
        runtime_fingerprint = "f" * 64

    def record(spec, build_type):
        submitted.append((spec, build_type))
        return AcceptedJob()

    monkeypatch.setattr(propellers.jobs, "submit", record)
    response = client.post("/api/propellers/build", json=candidate)
    assert response.status_code == 202
    assert submitted[0][0]["assembly"]["initial_azimuth_deg"] == 0.0


def test_propeller_job_uses_shared_queue_and_allowlisted_artifacts(monkeypatch):
    def successful_run(job, input_path):
        assert job.build_type == "propeller"
        assert input_path.name == "propeller_spec_input.json"
        job.status = "running"
        for name in (
            "propeller_solid.step",
            "propeller_preview.stl",
            "propeller_spec.json",
            "blade_solid.step",
            "blade_spec.json",
            "validation.json",
            "engine_manifest.json",
        ):
            (job.output_dir / name).write_text("artifact", encoding="utf-8")
        job.status = "succeeded"

    monkeypatch.setattr(propellers.jobs, "_run", successful_run)
    response = client.post("/api/propellers/build", json=EXAMPLE)
    assert response.status_code == 202
    accepted = response.json()
    assert accepted["build_type"] == "propeller"
    job_id = accepted["job_id"]
    for _ in range(50):
        status = client.get(f"/api/jobs/{job_id}").json()
        if status["status"] == "succeeded":
            break
        time.sleep(0.01)
    assert status["build_type"] == "propeller"
    artifacts = client.get(f"/api/jobs/{job_id}/artifacts").json()
    names = {row["name"] for row in artifacts}
    assert {
        "propeller_solid.step",
        "propeller_preview.stl",
        "blade_solid.step",
        "engine_manifest.json",
    } <= names
    assert client.get(f"/api/jobs/{job_id}/artifacts/propeller_solid.step").status_code == 200
    assert client.get(f"/api/jobs/{job_id}/artifacts/not-allowed.txt").status_code == 404


def test_propeller_generation_rejects_unavailable_runtime_before_queue(monkeypatch):
    jobs_before = set(propellers.jobs._jobs)

    def unavailable():
        raise RuntimeReadinessError("managed fixed-plane runtime unavailable")

    monkeypatch.setattr(propellers.jobs, "_readiness_checker", unavailable)
    response = client.post("/api/propellers/build", json=EXAMPLE)
    assert response.status_code == 503
    assert "fixed-plane runtime unavailable" in response.json()["detail"]
    assert set(propellers.jobs._jobs) == jobs_before
    assert client.post("/api/propellers/validate", json=EXAMPLE).status_code == 200
