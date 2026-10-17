#!/usr/bin/env python3
"""Run the frozen FP02-C1 matrix through the serialized product job pipeline."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from api.services.jobs import JobManager
from bladegen.curves.resolver import resolve_blade_spec
from bladegen.models import BladeSpec
from bladegen.validation.propeller_preflight import validate_propeller_payload


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def topology(validation: dict, build_type: str) -> dict:
    if build_type == "propeller":
        return validation["assembly_validation"]["final_after_reimport"]
    return validation["solidification"]["solid_after_reimport"]


def case_result(case: dict, job, definition_path: Path) -> dict:
    validation_path = job.output_dir / "validation.json"
    result: dict[str, Any] = {
        "id": case["id"],
        "build_type": case["build_type"],
        "definition_path": case["definition_path"],
        "definition_sha256": sha256(definition_path),
        "job_id": job.job_id,
        "job_output": str(job.output_dir),
        "status": job.status,
        "stage": job.stage,
        "elapsed_seconds": job.elapsed_seconds,
        "queue_wait_seconds": job.queue_wait_seconds,
        "worker_elapsed_seconds": job.worker_elapsed_seconds,
        "worker_timeout_seconds": job.worker_timeout_seconds,
        "error": job.error,
    }
    if not validation_path.is_file():
        result["passed"] = False
        result["missing_validation_json"] = True
        return result
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    geometry = (
        validation["reference_blade_validation"]["geometry_validation"]
        if case["build_type"] == "propeller"
        else validation["geometry_validation"]
    )
    final = topology(validation, case["build_type"])
    completion = validation["completion_context"]
    station_count = geometry["station_count"]
    completed_count = len(geometry["stations"])
    checks = {
        "job_succeeded": job.status == "succeeded",
        "validation_pass": validation["status"] == "PASS",
        "geometry_pass": geometry["passed"] is True,
        "planned_station_count": station_count == case["planned_section_count"],
        "completed_station_count": completed_count == station_count,
        "completion_context_count": completion["planned_section_count"] == station_count
        and completion["completed_section_count"] == completed_count,
        "one_solid": final["solids"] == 1,
        "one_shell": final["shells"] == 1,
        "zero_free_edges": final["free_edges"] == 0,
        "closed_shell": final["closed_shell"] is True,
        "brepcheck_valid": final["brepcheck_valid"] is True,
    }
    result.update(
        {
            "passed": all(checks.values()),
            "checks": checks,
            "planned_station_count": station_count,
            "completed_station_count": completed_count,
            "topology": final,
            "geometry_summary": {
                key: geometry.get(key)
                for key in (
                    "max_chord_error_mm",
                    "max_twist_error_deg",
                    "max_reference_axis_error_mm",
                    "control_contour_rms_max_mm",
                    "control_contour_p95_max_mm",
                    "control_contour_max_mm",
                    "max_te_error_mm",
                )
            },
            "runtime": validation["engine"],
            "completion_context": completion,
            "artifacts": {
                path.name: {"size_bytes": path.stat().st_size, "sha256": sha256(path)}
                for path in job.output_dir.iterdir()
                if path.is_file()
                and path.name
                in {
                    "blade_solid.step",
                    "propeller_solid.step",
                    "blade_spec.json",
                    "propeller_spec.json",
                    "resolved_blade_spec.json",
                    "validation.json",
                    "engine_manifest.json",
                }
            },
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=900.0)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[2]
    manifest_path = args.manifest.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manager = JobManager(timeout_seconds=args.timeout_seconds, run_root=output / "jobs")
    summary: dict[str, Any] = {
        "schema": "bladegen.fp02-c1-matrix-result.v1",
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256(manifest_path),
        "timeout_seconds_per_design": args.timeout_seconds,
        "started_unix": time.time(),
        "cases": [],
    }
    write_json(output / "matrix_results.json", summary)

    for case in manifest["cases"]:
        definition_path = repository / case["definition_path"]
        if sha256(definition_path) != case["sha256"]:
            raise RuntimeError(f"Frozen definition hash mismatch for {case['id']}")
        payload = json.loads(definition_path.read_text(encoding="utf-8"))
        if case["build_type"] == "propeller":
            submitted = validate_propeller_payload(
                payload, require_runtime_support=True
            ).model_dump(mode="json")
        else:
            spec = BladeSpec.model_validate(payload)
            resolve_blade_spec(spec)
            submitted = spec.model_dump(mode="json")
        job = manager.submit(submitted, build_type=case["build_type"])
        print(f"{case['id']} submitted as {job.job_id}", flush=True)
        previous = None
        while job.status in {"queued", "running"}:
            current = manager.get(job.job_id)
            if current is None:
                raise RuntimeError(f"Job disappeared: {job.job_id}")
            job = current
            marker = (job.status, job.stage, job.progress_percent)
            if marker != previous:
                print(
                    f"{case['id']} {job.status} {job.stage} {job.progress_percent}%",
                    flush=True,
                )
                previous = marker
            time.sleep(1.0)
        result = case_result(case, job, definition_path)
        summary["cases"].append(result)
        write_json(output / "matrix_results.json", summary)
        print(f"{case['id']} {job.status} passed={result['passed']}", flush=True)

    summary["completed_unix"] = time.time()
    summary["elapsed_seconds"] = summary["completed_unix"] - summary["started_unix"]
    summary["passed_count"] = sum(case["passed"] for case in summary["cases"])
    summary["failed_count"] = len(summary["cases"]) - summary["passed_count"]
    summary["passed"] = summary["passed_count"] == len(summary["cases"])
    write_json(output / "matrix_results.json", summary)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
