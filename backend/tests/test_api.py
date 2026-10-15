import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routes import blades
from bladegen.runtime.manager import RuntimeReadinessError

client = TestClient(app)


@pytest.fixture(autouse=True)
def ready_runtime(monkeypatch):
    identity = SimpleNamespace(
        root=Path("/test/fixed-plane-runtime"),
        fingerprint="f" * 64,
        build_id="openvsp-3.54.0-bladegen-fixed-plane.1",
        construction_contract="bladegen.fixed-radial-sections.v1",
    )
    monkeypatch.setattr(blades.jobs, "_readiness_checker", lambda: identity)


def example():
    response = client.get("/api/examples/custom_multi_airfoil_finite_te")
    assert response.status_code == 200
    return response.json()


def test_health_and_example_loading():
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/examples").json()[0]["id"] == "custom_multi_airfoil_finite_te"
    assert example()["schema_version"] == "0.2"


def test_validate_accepts_real_example_and_rejects_invalid_input():
    response = client.post("/api/validate", json=example())
    assert response.status_code == 200
    invalid = example()
    invalid["diameter_mm"] = -1
    response = client.post("/api/validate", json=invalid)
    assert response.status_code == 422
    assert "diameter_mm" in response.json()["detail"]


def test_job_lifecycle_artifacts_and_failure(monkeypatch, tmp_path):
    def successful_run(job, input_path):
        job.status = "running"
        for name in (
            "blade_solid.step",
            "blade_preview.stl",
            "validation.json",
            "engine_manifest.json",
        ):
            (job.output_dir / name).write_text("artifact", encoding="utf-8")
        job.status = "succeeded"

    monkeypatch.setattr(blades.jobs, "_run", successful_run)
    response = client.post("/api/build", json=example())
    assert response.status_code == 202
    accepted = response.json()
    assert accepted["status"] == "queued"
    assert accepted["stage"] == "queued"
    assert accepted["progress_percent"] == 0
    assert accepted["elapsed_seconds"] >= 0
    job_id = accepted["job_id"]
    for _ in range(50):
        status = client.get(f"/api/jobs/{job_id}").json()["status"]
        if status == "succeeded":
            break
        time.sleep(0.01)
    assert status == "succeeded"
    payload = client.get(f"/api/jobs/{job_id}").json()
    assert {
        "stage",
        "stage_label",
        "progress_percent",
        "message",
        "elapsed_seconds",
    } <= payload.keys()
    artifacts = client.get(f"/api/jobs/{job_id}/artifacts").json()
    assert {item["name"] for item in artifacts} >= {
        "blade_solid.step",
        "blade_preview.stl",
        "validation.json",
        "engine_manifest.json",
    }
    assert client.get(f"/api/jobs/{job_id}/artifacts/blade_solid.step").status_code == 200

    def failed_run(job, input_path):
        job.status = "failed"
        job.error = "intentional failure"

    monkeypatch.setattr(blades.jobs, "_run", failed_run)
    job_id = client.post("/api/build", json=example()).json()["job_id"]
    for _ in range(50):
        payload = client.get(f"/api/jobs/{job_id}").json()
        if payload["status"] == "failed":
            break
        time.sleep(0.01)
    assert payload["error"] == "intentional failure"
    assert client.get(f"/api/jobs/{job_id}/artifacts").json() == []


def test_generation_rejects_unavailable_runtime_before_queue(monkeypatch):
    jobs_before = set(blades.jobs._jobs)

    def unavailable():
        raise RuntimeReadinessError("managed fixed-plane runtime unavailable")

    monkeypatch.setattr(blades.jobs, "_readiness_checker", unavailable)
    response = client.post("/api/build", json=example())
    assert response.status_code == 503
    assert "fixed-plane runtime unavailable" in response.json()["detail"]
    assert set(blades.jobs._jobs) == jobs_before
    assert client.post("/api/validate", json=example()).status_code == 200


def test_runtime_status_is_read_only_and_separate_from_input_validity(monkeypatch):
    class Ready:
        def safe_dict(self):
            return {
                "build_id": "openvsp-3.54.0-bladegen-fixed-plane.1",
                "construction_contract": "bladegen.fixed-radial-sections.v1",
                "fingerprint": "f" * 64,
            }

    monkeypatch.setattr(blades, "require_runtime_ready", lambda: Ready())
    response = client.get("/api/runtime")
    assert response.status_code == 200
    assert response.json()["ready"] is True
    assert response.json()["construction_contract"] == "bladegen.fixed-radial-sections.v1"

    def unavailable():
        raise RuntimeReadinessError("runtime missing")

    monkeypatch.setattr(blades, "require_runtime_ready", unavailable)
    assert client.get("/api/runtime").json()["ready"] is False
    assert client.post("/api/validate", json=example()).status_code == 200
