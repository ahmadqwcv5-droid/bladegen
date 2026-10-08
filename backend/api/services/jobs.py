"""Serialized, isolated build-job execution."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

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
}


@dataclass
class Job:
    job_id: str
    status: str = "queued"
    error: str | None = None
    output_dir: Path = field(default_factory=Path)


class JobManager:
    def __init__(self, timeout_seconds: int | None = None) -> None:
        self.timeout_seconds = timeout_seconds or int(os.getenv("BLADEGEN_BUILD_TIMEOUT", "300"))
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bladegen-build")
        RUN_ROOT.mkdir(parents=True, exist_ok=True)

    def submit(self, spec: dict) -> Job:
        job_id = uuid.uuid4().hex
        output_dir = RUN_ROOT / job_id
        output_dir.mkdir(parents=False, exist_ok=False)
        input_path = output_dir / "blade_spec_input.json"
        input_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
        job = Job(job_id=job_id, output_dir=output_dir)
        with self._lock:
            self._jobs[job_id] = job
        self._executor.submit(self._run, job, input_path)
        return job

    def _run(self, job: Job, input_path: Path) -> None:
        with self._lock:
            job.status = "running"
        command = [
            sys.executable,
            "-m",
            "bladegen.cli",
            "build",
            str(input_path),
            "--output",
            str(job.output_dir),
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
            if process.returncode:
                message = (process.stderr or process.stdout or "build failed").strip()
                raise RuntimeError(message[-4000:])
            required = ("blade_solid.step", "blade_preview.stl", "validation.json")
            missing = [name for name in required if not (job.output_dir / name).is_file()]
            if missing:
                raise RuntimeError(f"Build did not produce required artifacts: {missing}")
        except Exception as exc:
            with self._lock:
                job.status = "failed"
                job.error = f"{type(exc).__name__}: {exc}"
        else:
            with self._lock:
                job.status = "succeeded"

    def get(self, job_id: str) -> Job | None:
        if len(job_id) != 32 or any(ch not in "0123456789abcdef" for ch in job_id):
            return None
        with self._lock:
            return self._jobs.get(job_id)

    def artifacts(self, job: Job) -> list[Path]:
        return sorted(
            path
            for path in job.output_dir.iterdir()
            if path.is_file() and path.name in ALLOWED_ARTIFACTS
        )


jobs = JobManager()
