#!/usr/bin/env python3
"""Run the production X-57 final-STEP gate against retained CAD, with timings.

This is a diagnostic supervisor/worker.  It does not generate or repair CAD,
does not load OpenVSP, and does not replace the production measurement logic.
The worker transparently times the callables used by ``measure_sections`` and
then calls the exact production ``_geometry_summary`` acceptance function.
"""

from __future__ import annotations

import argparse
import csv
import functools
import hashlib
import importlib.metadata
import json
import os
import platform
import shlex
import signal
import subprocess
import sys
import time
import traceback
from collections import defaultdict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

JOB_ID = "a93b281c29b640afaa6bad698d64a61b"
EXPECTED_STEP_SHA256 = "43c2cd72bebcd3949e0fe0b210aaac9ccbf6918952743fd109ecb0cac2e401d6"
DEFAULT_JOB_DIR = REPOSITORY_ROOT / "output" / "runs" / JOB_ID
DEFAULT_EVIDENCE_ROOT = REPOSITORY_ROOT / "docs" / "evidence" / "sprint04b" / "x57"
DEFAULT_OUTPUT_ROOT = DEFAULT_EVIDENCE_ROOT / "validation_diagnostics"
PRODUCTION_SOURCES = (
    "backend/bladegen/pipeline.py",
    "backend/bladegen/models/blade_spec.py",
    "backend/bladegen/curves/resolver.py",
    "backend/bladegen/solid/ocp_solidify.py",
    "backend/bladegen/validation/measure_sections.py",
    "backend/bladegen/validation/station_plan.py",
    "backend/bladegen/validation/expected_geometry.py",
    "backend/bladegen/validation/policy.py",
    "backend/bladegen/validation/geometry_validation.py",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return sha256_bytes(encoded)


def write_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def git_output(*arguments: str, binary: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=not binary,
    )
    return result.stdout


def file_record(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": sha256_file(path),
    }


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def collect_environment() -> dict[str, Any]:
    import numpy
    import OCP
    import scipy

    openvsp_root = REPOSITORY_ROOT / ".tooling" / "openvsp-3.54.0" / "opt" / "OpenVSP"
    openvsp_binary = openvsp_root / "vsp"
    return {
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "executable": sys.executable,
            "full_version": sys.version,
        },
        "platform": platform.platform(),
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "ocp_binding": getattr(OCP, "__version__", None),
        "cadquery_ocp_distribution": package_version("cadquery-ocp"),
        "opencascade": "7.9.3 (version carried by OCP 7.9.3.1)",
        "bladegen_distribution": package_version("bladegen"),
        "openvsp": {
            "version": "3.54.0",
            "verification": "static installed-distribution identity; executable was not launched",
            "root": str(openvsp_root.resolve()),
            "binary_exists": openvsp_binary.is_file(),
            "binary_sha256": sha256_file(openvsp_binary) if openvsp_binary.is_file() else None,
        },
    }


def collect_preflight(job_dir: Path, evidence_root: Path) -> dict[str, Any]:
    from bladegen.models import BladeSpec

    paths = {
        "retained_step": job_dir / "blade_solid.step",
        "job_input_spec": job_dir / "blade_spec_input.json",
        "job_generated_spec": job_dir / "blade_spec.json",
        "resolved_spec": job_dir / "resolved_blade_spec.json",
        "progress": job_dir / "progress.json",
        "stdout": job_dir / "build_stdout.log",
        "stderr": job_dir / "build_stderr.log",
        "exported_candidate": evidence_root / "exported_candidate.json",
        "evidence_submitted_spec": evidence_root / "job" / "submitted_blade_spec.json",
        "evidence_generated_spec": evidence_root / "job" / "blade_spec.json",
        "evidence_step": evidence_root / "job" / "blade_solid.step",
        "evidence_summary": evidence_root / "evidence_summary.json",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing retained evidence: {missing}")

    spec_names = (
        "exported_candidate",
        "evidence_submitted_spec",
        "evidence_generated_spec",
        "job_input_spec",
        "job_generated_spec",
    )
    parsed = {name: read_json(paths[name]) for name in spec_names}
    model_payloads = {
        name: BladeSpec.model_validate(payload).model_dump(mode="json")
        for name, payload in parsed.items()
    }
    first_parsed = parsed[spec_names[0]]
    first_model = model_payloads[spec_names[0]]
    parsed_equal = all(parsed[name] == first_parsed for name in spec_names[1:])
    model_equal = all(model_payloads[name] == first_model for name in spec_names[1:])

    source_hashes = {
        relative: sha256_file(REPOSITORY_ROOT / relative) for relative in PRODUCTION_SOURCES
    }
    source_hashes[str(Path(__file__).resolve().relative_to(REPOSITORY_ROOT))] = sha256_file(
        Path(__file__).resolve()
    )
    tracked_diff = git_output("diff", "--binary", "--no-ext-diff", binary=True)
    staged_diff = git_output("diff", "--cached", "--binary", "--no-ext-diff", binary=True)
    status = str(git_output("status", "--porcelain=v1", "--untracked-files=all"))
    branch = str(git_output("branch", "--show-current")).strip()
    head = str(git_output("rev-parse", "HEAD")).strip()
    artifacts = {name: file_record(path) for name, path in paths.items()}

    jq_hashes: dict[str, str | None] = {}
    jq = subprocess.run(
        ["sh", "-c", "command -v jq"], capture_output=True, text=True, check=False
    )
    if jq.returncode == 0:
        for name in spec_names:
            result = subprocess.run(
                ["jq", "-S", ".", str(paths[name])],
                check=True,
                capture_output=True,
            )
            jq_hashes[name] = sha256_bytes(result.stdout)
    else:
        jq_hashes = {name: None for name in spec_names}

    return {
        "captured_at_utc": utc_now(),
        "job_id": JOB_ID,
        "git": {
            "head": head,
            "branch": branch,
            "worktree_clean": status == "",
            "status_porcelain": status,
            "unstaged_tracked_patch_sha256": sha256_bytes(tracked_diff),
            "staged_patch_sha256": sha256_bytes(staged_diff),
        },
        "environment": collect_environment(),
        "artifacts": artifacts,
        "specification_equivalence": {
            "paths": {name: str(paths[name].resolve()) for name in spec_names},
            "raw_sha256": {name: artifacts[name]["sha256"] for name in spec_names},
            "parsed_json_equal": parsed_equal,
            "production_bladespec_model_equal": model_equal,
            "canonical_sorted_minified_sha256": {
                name: canonical_json_sha256(parsed[name]) for name in spec_names
            },
            "canonical_production_model_sha256": {
                name: canonical_json_sha256(model_payloads[name]) for name in spec_names
            },
            "documented_jq_sorted_sha256": jq_hashes,
        },
        "step_sha256_expected": EXPECTED_STEP_SHA256,
        "step_sha256_verified": artifacts["retained_step"]["sha256"]
        == EXPECTED_STEP_SHA256,
        "retained_and_evidence_step_identical": artifacts["retained_step"]["sha256"]
        == artifacts["evidence_step"]["sha256"],
        "relevant_source_sha256": source_hashes,
    }


class EventLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.stream = path.open("w", encoding="utf-8", buffering=1)
        self.origin_ns = time.monotonic_ns()
        self.sequence = 0
        self.operation_sequence = 0
        self.active_operations: dict[str, dict[str, Any]] = {}
        self.active_station: dict[str, Any] | None = None
        self.active_station_operation: str | None = None

    def emit(self, event: str, **fields: Any) -> dict[str, Any]:
        self.sequence += 1
        now_ns = time.monotonic_ns()
        record = {
            "sequence": self.sequence,
            "event": event,
            "utc": utc_now(),
            "monotonic_ns": now_ns,
            "since_run_start_seconds": (now_ns - self.origin_ns) / 1_000_000_000.0,
            **fields,
        }
        line = json.dumps(record, sort_keys=True, allow_nan=False)
        self.stream.write(line + "\n")
        self.stream.flush()
        print(f"DIAGNOSTIC_EVENT {line}", flush=True)
        return record

    def start_operation(self, operation: str, phase: str, **fields: Any) -> str:
        self.operation_sequence += 1
        operation_id = f"op-{self.operation_sequence:05d}"
        started_ns = time.monotonic_ns()
        metadata = {
            "operation_id": operation_id,
            "operation": operation,
            "phase": phase,
            **fields,
        }
        self.active_operations[operation_id] = {"started_ns": started_ns, **metadata}
        self.emit("operation_start", **metadata)
        return operation_id

    def end_operation(
        self,
        operation_id: str,
        status: str = "COMPLETED",
        error: str | None = None,
        **fields: Any,
    ) -> None:
        metadata = self.active_operations.pop(operation_id, None)
        if metadata is None:
            return
        ended_ns = time.monotonic_ns()
        self.emit(
            "operation_end",
            operation_id=operation_id,
            operation=metadata["operation"],
            phase=metadata["phase"],
            status=status,
            elapsed_seconds=(ended_ns - metadata["started_ns"]) / 1_000_000_000.0,
            error=error,
            **{key: value for key, value in metadata.items() if key.startswith("station_")},
            **fields,
        )

    @contextmanager
    def operation(self, operation: str, phase: str, **fields: Any) -> Iterator[None]:
        operation_id = self.start_operation(operation, phase, **fields)
        try:
            yield
        except BaseException as exc:
            self.end_operation(
                operation_id,
                status="ERROR",
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        else:
            self.end_operation(operation_id)

    def station_fields(self) -> dict[str, Any]:
        return dict(self.active_station or {})

    def start_station(self, fields: dict[str, Any]) -> None:
        if self.active_station is not None:
            self.end_station("INSTRUMENTATION_ERROR", error="next station began before completion")
        self.active_station = fields
        self.active_station_operation = self.start_operation(
            "station_total", "geometry_validation", **fields
        )
        self.emit("station_start", **fields)

    def end_station(
        self,
        status: str,
        measurement: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        if self.active_station is None:
            return
        fields = dict(self.active_station)
        operation_id = self.active_station_operation
        self.active_station = None
        self.active_station_operation = None
        if operation_id:
            self.end_operation(operation_id, status=status, error=error)
        self.emit(
            "station_end",
            status=status,
            error=error,
            measurement=measurement,
            **fields,
        )

    def signal_exit(self, signum: int) -> None:
        self.emit(
            "termination_signal",
            signal=signum,
            active_station=self.active_station,
            active_operations=list(self.active_operations.values()),
        )
        if self.active_station is not None:
            self.end_station("INCOMPLETE_SIGNAL", error=f"received signal {signum}")
        self.stream.flush()
        os._exit(128 + signum)


def timed_wrapper(
    logger: EventLog,
    operation: str,
    phase: str,
    function: Callable[..., Any],
    station_scoped: bool = False,
) -> Callable[..., Any]:
    @functools.wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        fields = logger.station_fields() if station_scoped else {}
        with logger.operation(operation, phase, **fields):
            return function(*args, **kwargs)

    return wrapped


def station_payload(index: int, planned: Any) -> dict[str, Any]:
    return {
        "station_index": index,
        "station_requested_r_over_R": planned.requested_r_over_R,
        "station_sampled_r_over_R": planned.sampled_r_over_R,
        "station_kind": planned.station_kind,
        "station_roles": list(planned.roles),
        "station_endpoint": planned.endpoint,
    }


def run_worker(output_dir: Path, job_dir: Path, evidence_root: Path) -> int:
    from bladegen.models import BladeSpec
    from bladegen.pipeline import _geometry_summary
    from bladegen.solid import ocp_solidify as ocp
    from bladegen.validation import measure_sections as measurement_module
    from bladegen.validation.station_plan import plan_validation_stations

    logger = EventLog(output_dir / "validation_events.jsonl")
    signal.signal(signal.SIGTERM, lambda signum, _frame: logger.signal_exit(signum))
    signal.signal(signal.SIGINT, lambda signum, _frame: logger.signal_exit(signum))
    measurement_stream = (output_dir / "measurement_records.jsonl").open(
        "w", encoding="utf-8", buffering=1
    )
    worker_started_ns = time.monotonic_ns()
    step_path = job_dir / "blade_solid.step"
    spec_path = job_dir / "blade_spec.json"
    logger.emit(
        "worker_start",
        pid=os.getpid(),
        step_path=str(step_path.resolve()),
        spec_path=str(spec_path.resolve()),
        openvsp_allowed=False,
    )

    try:
        with logger.operation("artifact_identity_recheck", "preflight"):
            actual_step_hash = sha256_file(step_path)
            if actual_step_hash != EXPECTED_STEP_SHA256:
                raise RuntimeError(
                    f"Retained STEP SHA-256 mismatch: {actual_step_hash} != {EXPECTED_STEP_SHA256}"
                )

        with logger.operation("canonical_input_preparation", "preflight"):
            spec = BladeSpec.from_json(spec_path)
            candidate = BladeSpec.from_json(evidence_root / "exported_candidate.json")
            submitted = BladeSpec.from_json(evidence_root / "job" / "submitted_blade_spec.json")
            if not (spec.model_dump(mode="json") == candidate.model_dump(mode="json") == submitted.model_dump(mode="json")):
                raise RuntimeError("Retained candidate/submitted/generated BladeSpecs differ")

        with logger.operation("diagnostic_station_plan_preparation", "preflight"):
            plan = plan_validation_stations(spec)
            plan_payload = {
                "production_function": "bladegen.validation.station_plan.plan_validation_stations",
                "planned_station_count": len(plan.stations),
                "root_r_over_R": plan.root_r_over_R,
                "tip_r_over_R": plan.tip_r_over_R,
                "endpoint_policy": plan.endpoint_policy,
                "stations": [station_payload(index, item) for index, item in enumerate(plan.stations)],
            }
            write_json(output_dir / "station_plan.json", plan_payload)
        plan_lookup = {
            round(item.sampled_r_over_R, 12): (index, item)
            for index, item in enumerate(plan.stations)
        }
        logger.emit("station_plan_ready", planned_station_count=len(plan.stations))

        topology_originals: dict[str, Callable[..., Any]] = {}
        topology_wrappers = {
            "_edge_status": "topology_edge_adjacency",
            "_mass": "topology_surface_mass_properties",
            "_bbox": "topology_bounding_box",
            "_volume_properties": "topology_volume_mass_properties",
        }
        for attribute, operation in topology_wrappers.items():
            original = getattr(ocp, attribute)
            topology_originals[attribute] = original
            setattr(ocp, attribute, timed_wrapper(logger, operation, "retained_topology", original))
        try:
            with logger.operation("retained_topology_step_read", "retained_topology"):
                topology_shape = ocp.read_step(step_path)
            with logger.operation("retained_topology_and_mass_checks", "retained_topology"):
                topology = ocp.inspect_shape(topology_shape)
            write_json(output_dir / "retained_step_topology.json", topology)
        finally:
            for attribute, original in topology_originals.items():
                setattr(ocp, attribute, original)

        original_functions: dict[str, Callable[..., Any]] = {}
        function_wrappers = {
            "read_step": "validation_step_read_import",
            "plan_validation_stations": "validation_station_plan_construction",
            "_section_shape": "section_extraction",
            "_wire_diagnostics": "section_wire_topology_checks",
            "_sample_edges": "section_contour_sampling",
            "_vertices": "section_vertex_extraction",
            "_endpoints": "section_dimensional_endpoints",
            "symmetric_distances": "section_contour_distance_measurement",
            "_identity_metrics": "section_profile_identity_measurement",
        }
        for attribute, operation in function_wrappers.items():
            original = getattr(measurement_module, attribute)
            original_functions[attribute] = original
            setattr(
                measurement_module,
                attribute,
                timed_wrapper(
                    logger,
                    operation,
                    "geometry_validation",
                    original,
                    station_scoped=attribute not in {"read_step", "plan_validation_stations"},
                ),
            )

        original_placed_contour = measurement_module.placed_contour
        original_functions["placed_contour"] = original_placed_contour

        @functools.wraps(original_placed_contour)
        def placed_contour_wrapper(specification: Any, station: float) -> Any:
            match = plan_lookup.get(round(float(station), 12))
            if match is None:
                raise RuntimeError(f"Instrumentation could not identify sampled station {station}")
            index, planned = match
            logger.start_station(station_payload(index, planned))
            with logger.operation(
                "section_expected_contour_preparation",
                "geometry_validation",
                **logger.station_fields(),
            ):
                return original_placed_contour(specification, station)

        measurement_module.placed_contour = placed_contour_wrapper

        captured_count = 0
        target_code = measurement_module.measure_sections.__code__

        def capture_records(frame: Any) -> None:
            nonlocal captured_count
            records = frame.f_locals.get("records")
            if not isinstance(records, list):
                return
            while captured_count < len(records):
                record = records[captured_count]
                logger.end_station("COMPLETED", measurement=record)
                measurement_stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
                measurement_stream.flush()
                captured_count += 1

        def trace_measurements(frame: Any, event: str, _argument: Any) -> Any:
            if frame.f_code is target_code:
                try:
                    if event in {"line", "return", "exception"}:
                        capture_records(frame)
                except Exception as exc:  # noqa: BLE001 - observation must not alter validation
                    logger.emit(
                        "instrumentation_error",
                        error=f"{type(exc).__name__}: {exc}",
                    )
                return trace_measurements
            return None

        try:
            validation_operation = logger.start_operation(
                "production_measure_sections", "geometry_validation"
            )
            sys.settrace(trace_measurements)
            try:
                records = measurement_module.measure_sections(step_path, spec)
            except BaseException as exc:
                logger.end_operation(
                    validation_operation,
                    status="ERROR",
                    error=f"{type(exc).__name__}: {exc}",
                )
                raise
            else:
                logger.end_operation(validation_operation)
            finally:
                sys.settrace(None)
                measurement_stream.flush()
        finally:
            for attribute, original in original_functions.items():
                setattr(measurement_module, attribute, original)

        with logger.operation("production_geometry_summary", "geometry_validation"):
            geometry_summary = _geometry_summary(records, spec)

        with logger.operation("diagnostic_measurement_report_write", "reporting"):
            write_json(output_dir / "completed_measurements.json", records)
            write_json(output_dir / "geometry_validation_result.json", geometry_summary)

        internal_status = "PASS" if geometry_summary["passed"] else "FAIL"
        worker_result = {
            "completed_at_utc": utc_now(),
            "execution_status": "COMPLETED",
            "internal_geometry_validation": internal_status,
            "planned_station_count": len(plan.stations),
            "completed_station_count": len(records),
            "elapsed_seconds": (time.monotonic_ns() - worker_started_ns) / 1_000_000_000.0,
            "openvsp_launched": False,
            "cad_regenerated_or_repaired": False,
        }
        write_json(output_dir / "worker_result.json", worker_result)
        logger.emit("worker_end", **worker_result)
        return 0
    except Exception as exc:  # noqa: BLE001 - preserve any production-validator failure
        logger.end_station("ERROR", error=f"{type(exc).__name__}: {exc}")
        worker_result = {
            "completed_at_utc": utc_now(),
            "execution_status": "ERROR",
            "internal_geometry_validation": "INCOMPLETE",
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
            "elapsed_seconds": (time.monotonic_ns() - worker_started_ns) / 1_000_000_000.0,
            "openvsp_launched": False,
            "cad_regenerated_or_repaired": False,
        }
        write_json(output_dir / "worker_result.json", worker_result)
        logger.emit("worker_error", **worker_result)
        traceback.print_exc()
        return 1
    finally:
        measurement_stream.close()
        logger.stream.close()


def read_json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def compile_timings(
    output_dir: Path,
    events: list[dict[str, Any]],
    timed_out: bool,
) -> list[dict[str, Any]]:
    starts = {
        event["operation_id"]: event
        for event in events
        if event.get("event") == "operation_start"
    }
    ends = {
        event["operation_id"]: event
        for event in events
        if event.get("event") == "operation_end"
    }
    rows = []
    for operation_id, start in starts.items():
        end = ends.get(operation_id)
        status = end.get("status") if end else ("INCOMPLETE_TIMEOUT" if timed_out else "INCOMPLETE")
        rows.append(
            {
                "operation_id": operation_id,
                "phase": start.get("phase"),
                "operation": start.get("operation"),
                "station_index": start.get("station_index"),
                "requested_r_over_R": start.get("station_requested_r_over_R"),
                "sampled_r_over_R": start.get("station_sampled_r_over_R"),
                "station_kind": start.get("station_kind"),
                "station_roles": "|".join(start.get("station_roles", [])),
                "start_monotonic_ns": start.get("monotonic_ns"),
                "end_monotonic_ns": end.get("monotonic_ns") if end else None,
                "elapsed_seconds": end.get("elapsed_seconds") if end else None,
                "status": status,
                "error": end.get("error") if end else None,
            }
        )
    fields = (
        "operation_id",
        "phase",
        "operation",
        "station_index",
        "requested_r_over_R",
        "sampled_r_over_R",
        "station_kind",
        "station_roles",
        "start_monotonic_ns",
        "end_monotonic_ns",
        "elapsed_seconds",
        "status",
        "error",
    )
    with (output_dir / "validation_timings.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def operation_statistics(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    values: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row["status"] == "COMPLETED" and row["elapsed_seconds"] is not None:
            values[str(row["operation"])].append(float(row["elapsed_seconds"]))
    return {
        operation: {
            "count": len(durations),
            "total_seconds": sum(durations),
            "mean_seconds": sum(durations) / len(durations),
            "max_seconds": max(durations),
        }
        for operation, durations in sorted(values.items())
    }


def measurement_metrics(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not records:
        return None
    return {
        "max_chord_error_mm": max(row["chord_absolute_error_mm"] for row in records),
        "max_twist_error_deg": max(row["twist_absolute_error_deg"] for row in records),
        "max_reference_axis_error_mm": max(
            row["reference_axis_position_error_mm"] for row in records
        ),
        "max_trailing_edge_error_mm": max(row["te_absolute_error_mm"] for row in records),
        "max_contour_rms_mm_all_stations": max(row["contour_rms_mm"] for row in records),
        "max_contour_p95_mm_all_stations": max(row["contour_p95_mm"] for row in records),
        "max_contour_error_mm_all_stations": max(row["contour_max_mm"] for row in records),
        "failed_station_count": sum(
            not all(
                row[key]
                for key in (
                    "chord_pass",
                    "twist_pass",
                    "reference_axis_pass",
                    "contour_rms_pass",
                    "contour_p95_pass",
                    "contour_max_pass",
                    "te_pass",
                    "wire_count_pass",
                    "wire_valid_pass",
                    "wire_closed_pass",
                )
            )
            for row in records
        ),
    }


def render_report(summary: dict[str, Any]) -> str:
    internal = summary["complete_internal_geometry_validation"]
    topology = summary["retained_step_topology"]
    runtime = summary["runtime_cost"]
    identity = summary["evidence_identity"]
    metrics = internal.get("measured_errors") or {}
    slow = runtime.get("slowest_leaf_operations", [])
    slow_rows = "\n".join(
        f"| {item['operation']} | {item['station_index'] if item['station_index'] is not None else '—'} | {item['elapsed_seconds']:.6f} |"
        for item in slow[:10]
    ) or "| — | — | — |"
    metric_rows = "\n".join(
        f"| {name} | {value:.12g} |" for name, value in metrics.items() if isinstance(value, float)
    ) or "| No complete measurements | — |"
    git_status = identity["git"]["status_porcelain"] or "(clean)"
    topology_result = topology.get("result") or {}
    bbox = topology_result.get("bbox")
    recommendation = summary["smallest_justified_next_action"]
    return f"""# X-57 Retained STEP Validation Diagnosis

## Outcome

- Retained STEP topology: **{topology['status']}**.
- Complete internal geometry validation: **{internal['status']}**.
- Planned/completed stations: **{internal['planned_station_count']} / {internal['completed_station_count']}**.
- External NASA geometry fidelity: **UNVERIFIED**. No official reference STEP was supplied or compared in this diagnostic.
- The old product job `{JOB_ID}` remains failed; these are separately labelled diagnostic results.

## Evidence identity

- HEAD: `{identity['git']['head']}` on `{identity['git']['branch']}`.
- Diagnostic started with a dirty worktree and preserved the existing work.
- Retained STEP SHA-256: `{identity['artifacts']['retained_step']['sha256']}` (required hash verified: `{identity['step_sha256_verified']}`).
- Candidate/submitted/generated parsed JSON equal: `{identity['specification_equivalence']['parsed_json_equal']}`.
- Candidate/submitted/generated production BladeSpec models equal: `{identity['specification_equivalence']['production_bladespec_model_equal']}`.
- Documented `jq -S` canonical SHA-256: `{next(iter(identity['specification_equivalence']['documented_jq_sorted_sha256'].values()))}` for every compared specification.
- Production validation sources unchanged during the run: `{summary['diagnostic_integrity']['production_sources_unchanged']}`.
- Retained failed-job artifacts unchanged during the run: `{summary['diagnostic_integrity']['failed_job_artifacts_unchanged']}`.

Initial dirty-worktree status:

```text
{git_status.rstrip()}
```

## Exact entrypoint and configuration

The diagnostic called the production gate in its original order:

```python
_geometry_summary(measure_sections(retained_step, actual_submitted_bladespec), actual_submitted_bladespec)
```

Production source was not modified. Observational wrappers timed the functions referenced by `measure_sections`; a trace hook persisted each exact record after production appended it. OpenVSP was not launched, CAD was not regenerated or repaired, station planning/sampling/tolerances were unchanged, and no external reference comparison ran.

Worker command (external timeout):

```text
{summary['runtime_configuration']['worker_command']}
```

- Working directory: `{summary['runtime_configuration']['cwd']}`
- External limit: {summary['runtime_configuration']['external_timeout_seconds']} seconds; TERM then KILL after {summary['runtime_configuration']['kill_after_seconds']} seconds.
- Python: {identity['environment']['python']['version']} (`{identity['environment']['python']['executable']}`)
- OpenVSP: {identity['environment']['openvsp']['version']} (static identity only; not launched)
- OCP/OpenCascade: {identity['environment']['ocp_binding']} / {identity['environment']['opencascade']}
- NumPy: {identity['environment']['numpy']}; SciPy: {identity['environment']['scipy']}

## Retained STEP topology

- Shape type: `{topology_result.get('shape_type')}`
- Solids/shells/faces: `{topology_result.get('solids')}` / `{topology_result.get('shells')}` / `{topology_result.get('faces')}`
- Free edges: `{topology_result.get('free_edges')}`
- Closed shell: `{topology_result.get('closed_shell')}`
- BRepCheck valid: `{topology_result.get('brepcheck_valid')}`
- Surface area: `{topology_result.get('surface_area_mm2')}` mm²
- Volume: `{topology_result.get('volume_mm3')}` mm³
- Bounding box: `{json.dumps(bbox, sort_keys=True)}`

Topology is reported separately and is not treated as full geometry acceptance.

## Complete internal geometry validation

The unchanged plan contained 41 stations: the 40 unique distribution radii plus one airfoil midpoint. The endpoint policy made inward root/tip cuts at sampled `r/R` 0.207365125 and 0.9995014875.

| Measurement | Maximum |
| --- | ---: |
{metric_rows}

- Production summary completed: `{internal['production_summary_completed']}`.
- Production acceptance boolean: `{internal.get('passed')}`.
- Failed stations: `{metrics.get('failed_station_count') if metrics else 'unknown'}`.
- Exact measurements: `{internal.get('measurement_output')}`.

## Runtime and cost

- External worker wall time: `{runtime.get('worker_wall_seconds')}` seconds.
- Exact `measure_sections` elapsed: `{runtime.get('production_measure_sections_seconds')}` seconds.
- Final `_geometry_summary` elapsed: `{runtime.get('production_geometry_summary_seconds')}` seconds.
- STEP import within geometry validation: `{runtime.get('validation_step_read_seconds')}` seconds.
- Topology qualification elapsed (separately labelled): `{runtime.get('retained_topology_seconds')}` seconds.

Slowest completed leaf operations:

| Operation | Station index | Seconds |
| --- | ---: | ---: |
{slow_rows}

Confirmed cost finding: {runtime.get('confirmed_cost_finding')}.

The old job's 300.2 seconds was whole-job elapsed time. Its only surviving progress marker says geometry validation was active, but its logs contain no stage timestamps. Earlier-stage and old-validator durations therefore remain **unknown**; file mtimes are chronology only and were not promoted to measured runtimes.

## Qualification boundaries

1. Input fidelity and interactive Apply performance retain the previously accepted Sprint 04B results; manual entry was not repeated.
2. This run qualifies only the retained STEP against the existing internal geometry gate.
3. It does not change the failed job to success and does not create an official product `validation.json`.
4. External NASA surface fidelity remains **UNVERIFIED**, independent of topology or internal validation status.

## Smallest justified next action

{recommendation}
"""


def finalize(output_dir: Path, job_dir: Path) -> dict[str, Any]:
    preflight = read_json(output_dir / "preflight_evidence.json", {})
    runtime_configuration = read_json(output_dir / "runtime_configuration.json", {})
    launcher = read_json(output_dir / "launcher_result.json", {})
    worker = read_json(output_dir / "worker_result.json", {})
    topology_result = read_json(output_dir / "retained_step_topology.json")
    geometry_result = read_json(output_dir / "geometry_validation_result.json")
    plan = read_json(output_dir / "station_plan.json", {})
    events = read_json_lines(output_dir / "validation_events.jsonl")
    measurements = read_json_lines(output_dir / "measurement_records.jsonl")
    timed_out = launcher.get("returncode") in {124, 137}
    timing_rows = compile_timings(output_dir, events, timed_out)
    statistics = operation_statistics(timing_rows)
    if measurements:
        write_json(output_dir / "completed_measurements.json", measurements)

    topology_passed = bool(
        topology_result
        and topology_result.get("solids") == 1
        and topology_result.get("shells") == 1
        and topology_result.get("free_edges") == 0
        and topology_result.get("closed_shell")
        and topology_result.get("brepcheck_valid")
    )
    if geometry_result is not None:
        internal_status = "PASS" if geometry_result.get("passed") else "FAIL"
    else:
        internal_status = "INCOMPLETE"

    def completed_time(operation: str) -> float | None:
        candidates = [
            float(row["elapsed_seconds"])
            for row in timing_rows
            if row["operation"] == operation
            and row["status"] == "COMPLETED"
            and row["elapsed_seconds"] is not None
        ]
        return sum(candidates) if candidates else None

    parent_operations = {
        "production_measure_sections",
        "station_total",
        "retained_topology_and_mass_checks",
    }
    slowest_leaf = sorted(
        (
            {
                "operation": row["operation"],
                "station_index": row["station_index"],
                "requested_r_over_R": row["requested_r_over_R"],
                "sampled_r_over_R": row["sampled_r_over_R"],
                "elapsed_seconds": float(row["elapsed_seconds"]),
            }
            for row in timing_rows
            if row["status"] == "COMPLETED"
            and row["elapsed_seconds"] is not None
            and row["operation"] not in parent_operations
        ),
        key=lambda item: item["elapsed_seconds"],
        reverse=True,
    )
    leaf_aggregate = {
        name: values
        for name, values in statistics.items()
        if name not in parent_operations and name.startswith("section_")
    }
    confirmed_cost = "No complete per-operation timing evidence was available."
    bottleneck = None
    if leaf_aggregate:
        bottleneck, values = max(
            leaf_aggregate.items(), key=lambda item: item[1]["total_seconds"]
        )
        confirmed_cost = (
            f"{bottleneck} had the largest accumulated measured section-operation cost "
            f"({values['total_seconds']:.6f} s across {values['count']} completed calls)."
        )

    source_hashes_after = {
        relative: sha256_file(REPOSITORY_ROOT / relative) for relative in PRODUCTION_SOURCES
    }
    expected_sources = {
        key: value
        for key, value in preflight.get("relevant_source_sha256", {}).items()
        if key in PRODUCTION_SOURCES
    }
    retained_names = (
        "retained_step",
        "job_input_spec",
        "job_generated_spec",
        "resolved_spec",
        "progress",
        "stdout",
        "stderr",
    )
    artifacts_after = {
        "retained_step": file_record(job_dir / "blade_solid.step"),
        "job_input_spec": file_record(job_dir / "blade_spec_input.json"),
        "job_generated_spec": file_record(job_dir / "blade_spec.json"),
        "resolved_spec": file_record(job_dir / "resolved_blade_spec.json"),
        "progress": file_record(job_dir / "progress.json"),
        "stdout": file_record(job_dir / "build_stdout.log"),
        "stderr": file_record(job_dir / "build_stderr.log"),
    }
    failed_artifacts_unchanged = all(
        artifacts_after[name]["sha256"]
        == preflight.get("artifacts", {}).get(name, {}).get("sha256")
        for name in retained_names
    )
    status_after = str(git_output("status", "--porcelain=v1", "--untracked-files=all"))

    if internal_status == "PASS":
        measured = completed_time("production_measure_sections")
        if measured is not None and measured >= 240.0 and bottleneck:
            recommendation = (
                f"Keep all validation rules unchanged and investigate only the confirmed `{bottleneck}` "
                "cost path before the fresh end-to-end build. Do not increase the production timeout "
                "until that narrow cost is understood and requalified."
            )
        else:
            recommendation = (
                "Run the planned fresh end-to-end UI build on unchanged geometry and validation rules. "
                "The retained STEP passed standalone; do not relabel the old failed job."
            )
    elif internal_status == "FAIL":
        recommendation = (
            "Review the exact failed station records and their unchanged tolerance checks before any "
            "engine or CAD change. Do not optimize around or weaken the geometric failure."
        )
    else:
        last_started = next(
            (row for row in reversed(timing_rows) if row["status"].startswith("INCOMPLETE")),
            None,
        )
        last_label = last_started["operation"] if last_started else "unknown operation"
        recommendation = (
            f"Investigate the last active `{last_label}` call with a narrower native-level profiler. "
            "The complete geometry result remains unverified; do not raise production timeouts or "
            "weaken sampling/tolerances at this diagnosis gate."
        )

    summary = {
        "diagnostic_schema": "bladegen.x57-retained-validation-diagnosis.v1",
        "generated_at_utc": utc_now(),
        "diagnostic_directory": str(output_dir.resolve()),
        "failed_job_id": JOB_ID,
        "old_failed_job_status_unchanged": True,
        "evidence_identity": preflight,
        "runtime_configuration": runtime_configuration,
        "retained_step_topology": {
            "status": "PASS" if topology_passed else ("FAIL" if topology_result else "INCOMPLETE"),
            "result": topology_result,
        },
        "complete_internal_geometry_validation": {
            "status": internal_status,
            "production_summary_completed": geometry_result is not None,
            "passed": geometry_result.get("passed") if geometry_result else None,
            "planned_station_count": plan.get("planned_station_count"),
            "completed_station_count": len(measurements),
            "measured_errors": measurement_metrics(measurements),
            "production_summary": geometry_result,
            "measurement_output": (
                str((output_dir / "completed_measurements.json").resolve())
                if measurements
                else None
            ),
        },
        "runtime_cost": {
            "external_timeout_occurred": timed_out,
            "worker_returncode": launcher.get("returncode"),
            "worker_wall_seconds": launcher.get("worker_wall_seconds"),
            "production_measure_sections_seconds": completed_time("production_measure_sections"),
            "production_geometry_summary_seconds": completed_time("production_geometry_summary"),
            "validation_step_read_seconds": completed_time("validation_step_read_import"),
            "retained_topology_seconds": completed_time("retained_topology_and_mass_checks"),
            "operation_statistics": statistics,
            "slowest_leaf_operations": slowest_leaf[:25],
            "confirmed_cost_finding": confirmed_cost,
        },
        "old_job_timing_evidence": {
            "reported_whole_job_elapsed_seconds": 300.2,
            "exact_earlier_stage_durations": "UNKNOWN",
            "exact_old_geometry_validation_duration": "UNKNOWN",
            "reason": "progress and build logs contain no timestamps; artifact mtimes are chronology only",
        },
        "external_nasa_geometry_fidelity": {
            "status": "UNVERIFIED",
            "reason": "No official NASA reference geometry was compared in this diagnostic.",
        },
        "diagnostic_integrity": {
            "openvsp_launched": False,
            "cad_regenerated_or_repaired": False,
            "production_sources_unchanged": expected_sources == source_hashes_after,
            "production_source_sha256_after": source_hashes_after,
            "failed_job_artifacts_unchanged": failed_artifacts_unchanged,
            "failed_job_artifacts_after": artifacts_after,
            "git_status_after": status_after,
        },
        "worker_result": worker,
        "smallest_justified_next_action": recommendation,
    }
    write_json(output_dir / "diagnostic_summary.json", summary)
    (output_dir / "X57_VALIDATION_DIAGNOSIS.md").write_text(
        render_report(summary), encoding="utf-8"
    )
    return summary


def unique_output_directory(root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = root / f"{JOB_ID[:8]}_{stamp}"
    candidate = base
    suffix = 0
    while candidate.exists():
        suffix += 1
        candidate = root / f"{base.name}_{suffix:02d}"
    return candidate


def launch(args: argparse.Namespace) -> int:
    job_dir = args.job_dir.resolve()
    evidence_root = args.evidence_root.resolve()
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else unique_output_directory(args.output_root.resolve())
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    preflight = collect_preflight(job_dir, evidence_root)
    write_json(output_dir / "preflight_evidence.json", preflight)

    equivalence = preflight["specification_equivalence"]
    if not preflight["step_sha256_verified"]:
        raise RuntimeError("Retained STEP checksum mismatch; diagnostic stopped")
    if not preflight["retained_and_evidence_step_identical"]:
        raise RuntimeError("Retained/evidence STEP copies differ; diagnostic stopped")
    if not equivalence["parsed_json_equal"] or not equivalence["production_bladespec_model_equal"]:
        raise RuntimeError("Candidate/submitted/generated specifications differ; diagnostic stopped")

    worker_command = [
        "timeout",
        "--signal=TERM",
        "--kill-after=30s",
        f"{args.timeout_seconds}s",
        sys.executable,
        "-u",
        str(Path(__file__).resolve()),
        "worker",
        "--output-dir",
        str(output_dir),
        "--job-dir",
        str(job_dir),
        "--evidence-root",
        str(evidence_root),
    ]
    runtime_configuration = {
        "created_at_utc": utc_now(),
        "launcher_command": shlex.join([sys.executable, *sys.argv]),
        "worker_command": shlex.join(worker_command),
        "cwd": str(REPOSITORY_ROOT.resolve()),
        "external_timeout_seconds": args.timeout_seconds,
        "timeout_implementation": "GNU timeout external process supervisor",
        "termination_signal": "TERM",
        "kill_after_seconds": 30,
        "production_default_timeout_changed": False,
        "production_default_timeout_seconds": 300,
        "openvsp_launch_permitted": False,
        "step_regeneration_permitted": False,
        "actual_bladespec": str((job_dir / "blade_spec.json").resolve()),
        "retained_step": str((job_dir / "blade_solid.step").resolve()),
    }
    write_json(output_dir / "runtime_configuration.json", runtime_configuration)
    print(f"Diagnostic directory: {output_dir}", flush=True)
    print(f"Worker command: {runtime_configuration['worker_command']}", flush=True)

    started_ns = time.monotonic_ns()
    with (output_dir / "diagnostic.log").open("w", encoding="utf-8", buffering=1) as log:
        process = subprocess.run(
            worker_command,
            cwd=REPOSITORY_ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
            env={**os.environ, "BLADEGEN_DIAGNOSTIC_NO_OPENVSP": "1"},
        )
    worker_wall_seconds = (time.monotonic_ns() - started_ns) / 1_000_000_000.0
    launcher_result = {
        "completed_at_utc": utc_now(),
        "returncode": process.returncode,
        "worker_wall_seconds": worker_wall_seconds,
        "timed_out": process.returncode in {124, 137},
    }
    write_json(output_dir / "launcher_result.json", launcher_result)
    summary = finalize(output_dir, job_dir)
    print(
        json.dumps(
            {
                "diagnostic_directory": str(output_dir),
                "topology": summary["retained_step_topology"]["status"],
                "internal_geometry": summary["complete_internal_geometry_validation"]["status"],
                "planned": summary["complete_internal_geometry_validation"]["planned_station_count"],
                "completed": summary["complete_internal_geometry_validation"]["completed_station_count"],
                "worker_wall_seconds": worker_wall_seconds,
            },
            indent=2,
        ),
        flush=True,
    )
    return 0 if process.returncode == 0 else process.returncode


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)
    launch_parser = subparsers.add_parser("launch", help="create a run and supervise its worker")
    launch_parser.add_argument("--job-dir", type=Path, default=DEFAULT_JOB_DIR)
    launch_parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    launch_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    launch_parser.add_argument("--output-dir", type=Path)
    launch_parser.add_argument("--timeout-seconds", type=int, default=900)
    worker_parser = subparsers.add_parser("worker", help="internal retained-STEP validation worker")
    worker_parser.add_argument("--job-dir", type=Path, required=True)
    worker_parser.add_argument("--evidence-root", type=Path, required=True)
    worker_parser.add_argument("--output-dir", type=Path, required=True)
    finalize_parser = subparsers.add_parser("finalize", help="rebuild reports from durable logs")
    finalize_parser.add_argument("--job-dir", type=Path, default=DEFAULT_JOB_DIR)
    finalize_parser.add_argument("--output-dir", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    if args.command == "launch":
        return launch(args)
    if args.command == "worker":
        return run_worker(args.output_dir.resolve(), args.job_dir.resolve(), args.evidence_root.resolve())
    summary = finalize(args.output_dir.resolve(), args.job_dir.resolve())
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
