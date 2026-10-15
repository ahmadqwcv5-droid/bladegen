#!/usr/bin/env python3
"""Validate the AB02 candidate with the unchanged production geometry gate.

The worker delegates measurement and acceptance to the already-audited
``diagnose_x57_validation.run_worker`` implementation.  This wrapper only
binds that diagnostic to an explicitly supplied candidate STEP/spec identity,
keeps the worker in a separately supervised process, and compiles its durable
timing events after completion.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import diagnose_x57_validation as diagnostic  # noqa: E402


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def worker(args: argparse.Namespace) -> int:
    diagnostic.EXPECTED_STEP_SHA256 = args.expected_step_sha256
    return diagnostic.run_worker(
        args.output_dir.resolve(),
        args.job_dir.resolve(),
        args.evidence_root.resolve(),
    )


def launch(args: argparse.Namespace) -> int:
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    worker_command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "worker",
        "--job-dir",
        str(args.job_dir.resolve()),
        "--evidence-root",
        str(args.evidence_root.resolve()),
        "--output-dir",
        str(output_dir),
        "--expected-step-sha256",
        args.expected_step_sha256,
    ]
    timeout_command = [
        "timeout",
        "--signal=TERM",
        f"--kill-after={args.kill_after_seconds}s",
        f"{args.timeout_seconds}s",
        *worker_command,
    ]
    configuration = {
        "created_at_utc": diagnostic.utc_now(),
        "launcher_command": shlex.join([sys.executable, *sys.argv]),
        "supervised_worker_command": shlex.join(timeout_command),
        "cwd": str(REPOSITORY_ROOT),
        "external_timeout_seconds": args.timeout_seconds,
        "termination_signal": "TERM",
        "kill_after_seconds": args.kill_after_seconds,
        "production_default_timeout_changed": False,
        "production_measurement_function": "bladegen.validation.measure_sections.measure_sections",
        "production_acceptance_function": "bladegen.pipeline._geometry_summary",
        "step_path": str((args.job_dir / "blade_solid.step").resolve()),
        "spec_path": str((args.job_dir / "blade_spec.json").resolve()),
        "expected_step_sha256": args.expected_step_sha256,
        "openvsp_launch_permitted": False,
        "cad_regeneration_or_repair_permitted": False,
    }
    write_json(output_dir / "runtime_configuration.json", configuration)

    started_ns = time.monotonic_ns()
    log_path = output_dir / "full_validation.log"
    with log_path.open("w", encoding="utf-8", buffering=1) as log:
        process = subprocess.run(
            timeout_command,
            cwd=REPOSITORY_ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
            env={**os.environ, "BLADEGEN_DIAGNOSTIC_NO_OPENVSP": "1"},
        )
    elapsed = (time.monotonic_ns() - started_ns) / 1_000_000_000.0
    timed_out = process.returncode in {124, 137}
    events = diagnostic.read_json_lines(output_dir / "validation_events.jsonl")
    rows = diagnostic.compile_timings(output_dir, events, timed_out)
    measurements = diagnostic.read_json_lines(output_dir / "measurement_records.jsonl")
    result = {
        "completed_at_utc": diagnostic.utc_now(),
        "returncode": process.returncode,
        "timed_out": timed_out,
        "worker_wall_seconds": elapsed,
        "planned_station_count": next(
            (event.get("planned_station_count") for event in events if event.get("event") == "station_plan_ready"),
            None,
        ),
        "completed_station_count": len(measurements),
        "operation_statistics": diagnostic.operation_statistics(rows),
        "worker_result": diagnostic.read_json(output_dir / "worker_result.json", {}),
    }
    write_json(output_dir / "launcher_result.json", result)
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    return process.returncode


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)
    for name in ("launch", "worker"):
        command = subparsers.add_parser(name)
        command.add_argument("--job-dir", type=Path, required=True)
        command.add_argument("--evidence-root", type=Path, required=True)
        command.add_argument("--output-dir", type=Path, required=True)
        command.add_argument("--expected-step-sha256", required=True)
        if name == "launch":
            command.add_argument("--timeout-seconds", type=int, default=900)
            command.add_argument("--kill-after-seconds", type=int, default=30)
    return result


def main() -> int:
    args = parser().parse_args()
    if args.command == "worker":
        return worker(args)
    return launch(args)


if __name__ == "__main__":
    raise SystemExit(main())
