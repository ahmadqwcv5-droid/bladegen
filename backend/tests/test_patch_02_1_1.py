from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app
from api.services.jobs import Job, JobManager
from bladegen.models import BladeSpec
from bladegen.progress import ProgressReporter, ProgressState

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "custom_multi_airfoil_finite_te.json"
client = TestClient(app)


def _progress(stage: str, percent: int) -> ProgressState:
    return ProgressState(stage, stage.replace("_", " ").title(), percent, stage)


def _write_engine_manifest(job: Job) -> None:
    (job.output_dir / "engine_manifest.json").write_text(
        json.dumps(
            {
                "state": "COMPLETED",
                "actually_loaded_runtime": {
                    "fingerprint": job.runtime_fingerprint,
                    "build_id": job.runtime_build_id,
                    "construction_contract": job.runtime_contract,
                },
            }
        ),
        encoding="utf-8",
    )


def _job(tmp_path: Path, character: str) -> tuple[JobManager, Job, Path]:
    manager = JobManager(run_root=tmp_path)
    output = tmp_path / (character * 32)
    output.mkdir()
    input_path = output / "blade_spec_input.json"
    input_path.write_text("{}", encoding="utf-8")
    return manager, Job(character * 32, output_dir=output), input_path


def test_pydantic_and_fastapi_serialize_absent_override_as_null() -> None:
    model_payload = BladeSpec.from_json(EXAMPLE).model_dump(mode="json")
    assert all(
        "thickness_override_ratio" in section and section["thickness_override_ratio"] is None
        for section in model_payload["airfoil_sections"]
    )

    response = client.get("/api/examples/custom_multi_airfoil_finite_te")
    assert response.status_code == 200
    assert all(
        "thickness_override_ratio" in section and section["thickness_override_ratio"] is None
        for section in response.json()["airfoil_sections"]
    )


def test_null_override_naca_change_passes_real_validate_endpoint() -> None:
    payload = client.get("/api/examples/custom_multi_airfoil_finite_te").json()
    section = payload["airfoil_sections"][-1]
    assert section["airfoil"]["code"] == "0010"
    assert section["thickness_override_ratio"] is None
    section["airfoil"]["code"] = "0008"
    payload["thickness_distribution"]["points"][-1]["thickness_ratio"] = 0.08
    response = client.post("/api/validate", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["valid"] is True


def test_running_job_clamps_legacy_subprocess_100_to_95(tmp_path: Path) -> None:
    manager, job, _ = _job(tmp_path, "a")
    job.status = "running"
    ProgressReporter(job.output_dir / "progress.json").report(_progress("complete", 100))
    manager._refresh_progress(job)
    assert job.status == "running"
    assert job.progress_percent == 95
    assert job.stage == "confirmation"


def test_manager_confirms_success_at_100(monkeypatch, tmp_path: Path) -> None:
    manager, job, input_path = _job(tmp_path, "b")

    def run(command, **kwargs):
        ProgressReporter(job.output_dir / "progress.json").report(_progress("confirmation", 95))
        for name in ("blade_solid.step", "blade_preview.stl", "validation.json"):
            (job.output_dir / name).write_text("artifact", encoding="utf-8")
        _write_engine_manifest(job)
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr("api.services.jobs.verify_completed_result", lambda *args: None)
    manager._run(job, input_path)
    assert job.status == "succeeded"
    assert job.progress_percent == 100
    assert job.stage == "complete"


def test_nonzero_exit_after_final_milestone_stays_failed_below_100(
    monkeypatch, tmp_path: Path
) -> None:
    manager, job, input_path = _job(tmp_path, "c")

    def run(command, **kwargs):
        ProgressReporter(job.output_dir / "progress.json").report(_progress("confirmation", 95))
        for name in ("blade_solid.step", "blade_preview.stl", "validation.json"):
            (job.output_dir / name).write_text("artifact", encoding="utf-8")
        return subprocess.CompletedProcess(command, 7, "", "late subprocess failure")

    monkeypatch.setattr(subprocess, "run", run)
    manager._run(job, input_path)
    assert job.status == "failed"
    assert job.progress_percent == 95
    assert "late subprocess failure" in (job.error or "")


def test_missing_required_artifact_prevents_100(monkeypatch, tmp_path: Path) -> None:
    manager, job, input_path = _job(tmp_path, "d")

    def run(command, **kwargs):
        ProgressReporter(job.output_dir / "progress.json").report(_progress("confirmation", 95))
        (job.output_dir / "blade_solid.step").write_text("artifact", encoding="utf-8")
        (job.output_dir / "validation.json").write_text("artifact", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr(subprocess, "run", run)
    manager._run(job, input_path)
    assert job.status == "failed"
    assert job.progress_percent == 95
    assert "blade_preview.stl" in (job.error or "")
