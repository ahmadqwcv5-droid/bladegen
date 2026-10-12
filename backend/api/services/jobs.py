"""Serialized, isolated build-job execution with backend-owned progress."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from bladegen.progress import PROGRESS_FILENAME, QUEUED_PROGRESS, read_progress

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
RUN_ROOT = WORKSPACE_ROOT / "output" / "runs"
ALLOWED_ARTIFACTS = {
    "blade_solid.step",
    "blade_preview.stl",
    "blade_spec.json",
    "validation.json",
    "validation.csv",
    "resolved_blade_spec.json",
    "blade_openvsp.vsp3",
    "blade_openvsp.step",
    "blade_validation.json",
    "blade_validation.csv",
    "propeller_solid.step",
    "propeller_preview.stl",
    "propeller_spec.json",
    "assembly_validation.csv",
}


@dataclass
class Job:
    job_id: str
    build_type: str = "blade"
    status: str = "queued"
    stage: str = QUEUED_PROGRESS.stage
    stage_label: str = QUEUED_PROGRESS.stage_label
    progress_percent: int = QUEUED_PROGRESS.progress_percent
    message: str = QUEUED_PROGRESS.message
    error: str | None = None
    output_dir: Path = field(default_factory=Path)
    submitted_at: float = field(default_factory=time.monotonic)
    completed_at: float | None = None

    @property
    def elapsed_seconds(self) -> float:
        end = self.completed_at if self.completed_at is not None else time.monotonic()
        return round(max(0.0, end - self.submitted_at), 1)


class JobManager:
    def __init__(
        self,
        timeout_seconds: int | None = None,
        run_root: Path | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds or int(os.getenv("BLADEGEN_BUILD_TIMEOUT", "300"))
        self.run_root = run_root or RUN_ROOT
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bladegen-build")
        self.run_root.mkdir(parents=True, exist_ok=True)

    def submit(self, spec: dict, build_type: str = "blade") -> Job:
        if build_type not in {"blade", "propeller"}:
            raise ValueError(f"Unsupported build type: {build_type}")
        job_id = uuid.uuid4().hex
        output_dir = self.run_root / job_id
        output_dir.mkdir(parents=False, exist_ok=False)
        input_path = output_dir / f"{build_type}_spec_input.json"
        input_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
        job = Job(job_id=job_id, build_type=build_type, output_dir=output_dir)
        with self._lock:
            self._jobs[job_id] = job
        self._executor.submit(self._run, job, input_path)
        return job

    @staticmethod
    def _write_log(path: Path, content: str | bytes | None) -> None:
        if isinstance(content, bytes):
            content = content.decode(errors="replace")
        path.write_text(content or "", encoding="utf-8")

    def _refresh_progress(self, job: Job) -> None:
        progress = read_progress(job.output_dir / PROGRESS_FILENAME)
        if progress is None or not 0 <= progress.progress_percent <= 100:
            return
        public_percent = min(progress.progress_percent, 95)
        if public_percent < job.progress_percent:
            return
        if progress.progress_percent > 95:
            job.stage = "confirmation"
            job.stage_label = "Awaiting build confirmation"
            job.message = "Pipeline work finished; waiting for the CAD worker to confirm success"
        else:
            job.stage = progress.stage
            job.stage_label = progress.stage_label
            job.message = progress.message
        job.progress_percent = public_percent

    def _fail(self, job: Job, error: str) -> None:
        self._refresh_progress(job)
        for private_path, label in ((job.output_dir, "<job>"), (WORKSPACE_ROOT, "<workspace>")):
            error = error.replace(str(private_path), label)
        job.status = "failed"
        job.error = error
        job.completed_at = time.monotonic()

    def _run(self, job: Job, input_path: Path) -> None:
        with self._lock:
            job.status = "running"
            job.stage = "validation"
            job.stage_label = (
                "Validating PropellerSpec" if job.build_type == "propeller" else "Validating BladeSpec"
            )
            job.message = "The CAD worker is checking the neutral input contract"
        command = [
            sys.executable,
            "-m",
            "bladegen.cli",
            "build-propeller" if job.build_type == "propeller" else "build",
            str(input_path),
            "--output",
            str(job.output_dir),
            "--progress-file",
            str(job.output_dir / PROGRESS_FILENAME),
        ]
        try:
            process = subprocess.run(
                command,
                cwd=WORKSPACE_ROOT,
                env=os.environ.copy(),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            self._write_log(job.output_dir / "build_stdout.log", process.stdout)
            self._write_log(job.output_dir / "build_stderr.log", process.stderr)
            if process.returncode:
                message = (process.stderr or process.stdout or "build failed").strip()
                raise RuntimeError(message[-4000:])
            required = (
                (
                    "propeller_solid.step",
                    "propeller_preview.stl",
                    "propeller_spec.json",
                    "blade_solid.step",
                    "blade_spec.json",
                    "validation.json",
                )
                if job.build_type == "propeller"
                else ("blade_solid.step", "blade_preview.stl", "validation.json")
            )
            missing = [name for name in required if not (job.output_dir / name).is_file()]
            if missing:
                raise RuntimeError(f"Build did not produce required artifacts: {missing}")
        except subprocess.TimeoutExpired as exc:
            self._write_log(job.output_dir / "build_stdout.log", exc.stdout)
            self._write_log(job.output_dir / "build_stderr.log", exc.stderr)
            with self._lock:
                self._fail(
                    job,
                    f"Build timed out after {self.timeout_seconds} seconds during "
                    f"{job.stage_label}",
                )
        except Exception as exc:
            with self._lock:
                self._fail(job, f"{type(exc).__name__}: {exc}")
        else:
            with self._lock:
                self._refresh_progress(job)
                job.status = "succeeded"
                job.stage = "complete"
                job.stage_label = "Build complete"
                job.progress_percent = 100
                job.message = (
                    "Validated propeller STEP, preview, and assembly artifacts are ready"
                    if job.build_type == "propeller"
                    else "Validated STEP, preview, and validation artifacts are ready"
                )
                job.completed_at = time.monotonic()

    def get(self, job_id: str) -> Job | None:
        if len(job_id) != 32 or any(ch not in "0123456789abcdef" for ch in job_id):
            return None
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None and job.status in {"queued", "running"}:
                self._refresh_progress(job)
            return job

    def artifacts(self, job: Job) -> list[Path]:
        return sorted(
            path
            for path in job.output_dir.iterdir()
            if path.is_file() and path.name in ALLOWED_ARTIFACTS
        )


jobs = JobManager()
