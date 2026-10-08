import time

from fastapi.testclient import TestClient

from api.main import app
from api.routes import blades

client = TestClient(app)


def example():
    response = client.get("/api/examples/x57_finite_te_multi_airfoil")
    assert response.status_code == 200
    return response.json()


def test_health_and_example_loading():
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/examples").json()[0]["id"] == "x57_finite_te_multi_airfoil"
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
        for name in ("blade_solid.step", "blade_preview.stl", "validation.json"):
            (job.output_dir / name).write_text("artifact", encoding="utf-8")
        job.status = "succeeded"

    monkeypatch.setattr(blades.jobs, "_run", successful_run)
    response = client.post("/api/build", json=example())
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    for _ in range(50):
        status = client.get(f"/api/jobs/{job_id}").json()["status"]
        if status == "succeeded":
            break
        time.sleep(0.01)
    assert status == "succeeded"
    artifacts = client.get(f"/api/jobs/{job_id}/artifacts").json()
    assert {item["name"] for item in artifacts} >= {
        "blade_solid.step",
        "blade_preview.stl",
        "validation.json",
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
