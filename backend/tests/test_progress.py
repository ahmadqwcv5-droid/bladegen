from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from api.services.jobs import Job, JobManager
from bladegen.progress import ProgressReporter, ProgressState, read_progress


def state(stage: str, percent: int) -> ProgressState:
    return ProgressState(stage, stage.replace("_", " ").title(), percent, f"{stage} message")


def test_atomic_progress_is_monotonic_and_bounded(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    reporter = ProgressReporter(path)
    reporter.report(state("resolution", 5))
    reporter.report(state("queued", 0))
    assert read_progress(path) == state("resolution", 5)
    reporter.report(state("openvsp", 18))
    assert read_progress(path) == state("openvsp", 18)
    assert not list(tmp_path.glob("*.tmp"))
    with pytest.raises(ValueError, match="between 0 and 100"):
        reporter.report(state("invalid", 101))


def test_reader_ignores_partial_or_invalid_progress(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    path.write_text('{"stage": "openvsp"', encoding="utf-8")
    assert read_progress(path) is None


def test_jobs_never_share_progress(tmp_path: Path) -> None:
    manager = JobManager(run_root=tmp_path)
    left = Job("a" * 32, output_dir=tmp_path / ("a" * 32))
    right = Job("b" * 32, output_dir=tmp_path / ("b" * 32))
    left.output_dir.mkdir()
    right.output_dir.mkdir()
    ProgressReporter(left.output_dir / "progress.json").report(state("openvsp", 18))
    ProgressReporter(right.output_dir / "progress.json").report(state("preview", 72))
    manager._refresh_progress(left)
    manager._refresh_progress(right)
    assert (left.stage, left.progress_percent) == ("openvsp", 18)
    assert (right.stage, right.progress_percent) == ("preview", 72)


def test_success_reaches_100_and_uses_isolated_cli(monkeypatch, tmp_path: Path) -> None:
    manager = JobManager(run_root=tmp_path)
    output = tmp_path / ("c" * 32)
    output.mkdir()
    input_path = output / "blade_spec_input.json"
    input_path.write_text("{}", encoding="utf-8")
    job = Job("c" * 32, output_dir=output)
    captured: list[str] = []

    def run(command, **kwargs):
        captured.extend(command)
        ProgressReporter(output / "progress.json").report(state("complete", 100))
        for name in ("blade_solid.step", "blade_preview.stl", "validation.json"):
            (output / name).write_text("artifact", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr(subprocess, "run", run)
    manager._run(job, input_path)
    assert job.status == "succeeded"
    assert job.progress_percent == 100
    assert captured[:3] == [captured[0], "-m", "bladegen.cli"]
    assert "--progress-file" in captured


def test_failure_preserves_last_confirmed_stage(monkeypatch, tmp_path: Path) -> None:
    manager = JobManager(run_root=tmp_path)
    output = tmp_path / ("d" * 32)
    output.mkdir()
    input_path = output / "blade_spec_input.json"
    input_path.write_text("{}", encoding="utf-8")
    job = Job("d" * 32, output_dir=output)

    def run(command, **kwargs):
        ProgressReporter(output / "progress.json").report(state("solidification", 52))
        return subprocess.CompletedProcess(command, 1, "", f"OCP could not close shell in {output}")

    monkeypatch.setattr(subprocess, "run", run)
    manager._run(job, input_path)
    assert job.status == "failed"
    assert (job.stage, job.progress_percent) == ("solidification", 52)
    assert "OCP could not close shell" in (job.error or "")
    assert str(output) not in (job.error or "")
    assert "<job>" in (job.error or "")


def test_timeout_reports_failure_at_current_stage(monkeypatch, tmp_path: Path) -> None:
    manager = JobManager(timeout_seconds=1, run_root=tmp_path)
    output = tmp_path / ("e" * 32)
    output.mkdir()
    input_path = output / "blade_spec_input.json"
    input_path.write_text("{}", encoding="utf-8")
    ProgressReporter(output / "progress.json").report(state("openvsp", 18))
    job = Job("e" * 32, output_dir=output)

    def run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 1, output="partial", stderr="timeout")

    monkeypatch.setattr(subprocess, "run", run)
    manager._run(job, input_path)
    assert job.status == "failed"
    assert (job.stage, job.progress_percent) == ("openvsp", 18)
    assert "timed out after 1 seconds" in (job.error or "")


def test_new_job_starts_queued_at_zero(tmp_path: Path) -> None:
    job = Job("f" * 32, output_dir=tmp_path)
    assert job.status == "queued"
    assert job.stage == "queued"
    assert job.progress_percent == 0
