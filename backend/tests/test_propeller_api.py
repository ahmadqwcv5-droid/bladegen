from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app
from api.routes import propellers

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = json.loads(
    (WORKSPACE_ROOT / "examples/propeller_three_blade.json").read_text(encoding="utf-8")
)
client = TestClient(app)


def test_propeller_validation_reports_contract_and_nominal_overlap():
    response = client.post("/api/propellers/validate", json=EXAMPLE)
    assert response.status_code == 200
    payload = response.json()
    assert payload["blade_count"] == 3
    assert payload["airfoil_sections_per_blade"] == 5
    assert payload["rotation_axis"] == "X"
    assert payload["nominal_radial_overlap_mm"] == 5.0


def test_propeller_validation_rejects_bore_and_tangential_hub_contact():
    bore = {**EXAMPLE, "assembly": {**EXAMPLE["assembly"], "shaft_bore_diameter_mm": 90}}
    response = client.post("/api/propellers/validate", json=bore)
    assert response.status_code == 422
    assert "smaller than hub" in response.json()["detail"]
    contact = {**EXAMPLE, "assembly": {**EXAMPLE["assembly"], "hub_diameter_mm": 80}}
    response = client.post("/api/propellers/validate", json=contact)
    assert response.status_code == 422
    assert "positive-volume connection" in response.json()["detail"]


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
    assert {"propeller_solid.step", "propeller_preview.stl", "blade_solid.step"} <= names
    assert client.get(
        f"/api/jobs/{job_id}/artifacts/propeller_solid.step"
    ).status_code == 200
    assert client.get(f"/api/jobs/{job_id}/artifacts/not-allowed.txt").status_code == 404
