#!/usr/bin/env python3
"""Controlled, disposable X-57 OpenVSP root-end-cap A/B experiment.

The supervisor records immutable inputs, writes the experiment plan before any
arm is generated, and launches each OpenVSP arm in a fresh timeout-bounded
process.  The production adapter is not edited: a diagnostic wrapper changes
only the value passed by its existing EndCap.CapUMinOption setter.  Raw STEP is
the authoritative experimental output; no OCP solidification is performed.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import time
import traceback
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
SCRIPT_ROOT = Path(__file__).resolve().parent
for entry in (BACKEND_ROOT, SCRIPT_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import diagnose_x57_contours as isolation

JOB_ID = "a93b281c29b640afaa6bad698d64a61b"
EXPECTED_FINAL_STEP_SHA256 = "43c2cd72bebcd3949e0fe0b210aaac9ccbf6918952743fd109ecb0cac2e401d6"
EXPECTED_RAW_STEP_SHA256 = "85f798f74f672e4c78f3560e3413fcbdbba0ff7410424a840a5fc4e746d8b07f"
RECORDED_HEAD = "1cdb564a2eb92b0171acbab705b41ca63b57416c"

IMMEDIATE_SETTER_ABS_TOLERANCE = 1.0e-12
PERSISTED_NUMERIC_READBACK_ABS_TOLERANCE = 1.0e-12
ENUM_READBACK_ABS_TOLERANCE = 1.0e-12
AUTHORITATIVE_ROOT_ABS_TOLERANCE = 1.0e-12
KNOWN_OPENVSP_AFLIMIT_CLAMP = 0.20
PRIOR_INSTRUMENTATION_ATTEMPT = (
    "docs/evidence/sprint04b/x57/root_cap_ab/a93b281c_20261014T130337Z"
)
SECOND_INSTRUMENTATION_ATTEMPT = (
    "docs/evidence/sprint04b/x57/root_cap_ab/a93b281c_20261014T131157Z"
)
GENERATED_MESH_METRIC_SEMANTICS = frozenset(
    ("PropGeom.SmallPanelW", "PropGeom.MaxGrowth")
)
OPENVSP_PROPGEOM_SOURCE_PATH = (
    "/tmp/openvsp-src-354-rootcap/src/geom_core/PropGeom.cpp"
)
OPENVSP_PROPGEOM_SOURCE_SHA256 = (
    "1c4aac94d329f120fc78e6139882c6e23102270c05a1df4bbfb888a7965f7b4c"
)
OPENVSP_PROPSCREEN_SOURCE_PATH = (
    "/tmp/openvsp-src-354-rootcap/src/gui_and_draw/PropScreen.cpp"
)
OPENVSP_PROPSCREEN_SOURCE_SHA256 = (
    "2e35b242765757c1bf364ef83024804641c1ad5c8c12f0898001e7a7fe21d6bd"
)

PRIMARY_STATIONS = (0.22302, 0.29061, 0.50345)
EXPANDED_SAMPLED_STATIONS = (
    0.207365125,
    0.20949,
    0.22302,
    0.24183,
    0.26472,
    0.29061,
    0.31863,
    0.34811,
    0.50345,
    0.80632,
    0.9995014875,
)
RECORDED_PRODUCTION = {
    0.22302: (0.25375722740826995, 0.5031017053270439, 0.5237420974076966),
    0.29061: (0.019304832105279175, 0.0323074200908484, 0.03629183077790371),
    0.50345: (0.007424959867116377, 0.012598481083922258, 0.014482362418194583),
}

DEFAULT_JOB_DIR = REPOSITORY_ROOT / "output" / "runs" / JOB_ID
DEFAULT_EVIDENCE_ROOT = REPOSITORY_ROOT / "docs" / "evidence" / "sprint04b" / "x57"
DEFAULT_PRIOR_ISOLATION = (
    DEFAULT_EVIDENCE_ROOT
    / "contour_isolation"
    / "a93b281c_20261014T105834Z"
)
DEFAULT_OUTPUT_ROOT = DEFAULT_EVIDENCE_ROOT / "root_cap_ab"

PRODUCTION_SOURCES = (
    "backend/bladegen/adapters/openvsp_adapter.py",
    "backend/bladegen/airfoils/canonical.py",
    "backend/bladegen/airfoils/geometry_metrics.py",
    "backend/bladegen/curves/resolver.py",
    "backend/bladegen/solid/ocp_solidify.py",
    "backend/bladegen/validation/expected_geometry.py",
    "backend/bladegen/validation/geometry_validation.py",
    "backend/bladegen/validation/measure_sections.py",
    "backend/bladegen/validation/station_plan.py",
    "scripts/diagnose_x57_contours.py",
    "scripts/diagnose_x57_validation.py",
)
HARNESS_SOURCES = (
    "scripts/run_x57_root_cap_ab.py",
    "scripts/x57_root_cap_ab_reporting.py",
)
FIXTURE_DIRECTORY = REPOSITORY_ROOT / "fixtures" / "x57_manual_reference"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(jsonable(value), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def command_output(argv: list[str]) -> str:
    return subprocess.run(
        argv,
        cwd=REPOSITORY_ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def station_slug(station: float) -> str:
    return f"rR_{station:.10f}".rstrip("0").rstrip(".").replace(".", "p")


def same_station(left: float, right: float) -> bool:
    return abs(float(left) - float(right)) <= 5.0e-13


class EventLog:
    def __init__(self, path: Path, prefix: str = "ROOT_CAP_AB_EVENT") -> None:
        self.stream = path.open("w", encoding="utf-8", buffering=1)
        self.origin_ns = time.monotonic_ns()
        self.sequence = 0
        self.prefix = prefix
        self.last_operation: dict[str, Any] | None = None

    def emit(self, event: str, **fields: Any) -> None:
        self.sequence += 1
        now = time.monotonic_ns()
        record = {
            "sequence": self.sequence,
            "event": event,
            "utc": utc_now(),
            "monotonic_ns": now,
            "since_process_start_seconds": (now - self.origin_ns) / 1e9,
            **jsonable(fields),
        }
        line = json.dumps(record, sort_keys=True, allow_nan=False)
        self.stream.write(line + "\n")
        self.stream.flush()
        print(f"{self.prefix} {line}", flush=True)

    @contextmanager
    def operation(self, name: str, **fields: Any) -> Iterator[None]:
        started = time.monotonic_ns()
        self.last_operation = {"operation": name, "status": "ACTIVE", **fields}
        self.emit("operation_start", operation=name, **fields)
        try:
            yield
        except BaseException as exc:
            self.emit(
                "operation_end",
                operation=name,
                status="ERROR",
                elapsed_seconds=(time.monotonic_ns() - started) / 1e9,
                error=f"{type(exc).__name__}: {exc}",
                **fields,
            )
            self.last_operation = {"operation": name, "status": "ERROR", **fields}
            raise
        else:
            self.emit(
                "operation_end",
                operation=name,
                status="COMPLETED",
                elapsed_seconds=(time.monotonic_ns() - started) / 1e9,
                **fields,
            )
            self.last_operation = {
                "operation": name,
                "status": "COMPLETED",
                **fields,
            }

    def close(self) -> None:
        if not self.stream.closed:
            self.stream.close()



def source_snapshot() -> dict[str, str]:
    return {
        relative: sha256_file(REPOSITORY_ROOT / relative)
        for relative in PRODUCTION_SOURCES
    }


def harness_source_snapshot() -> dict[str, str]:
    return {
        relative: sha256_file(REPOSITORY_ROOT / relative)
        for relative in HARNESS_SOURCES
    }


def require_harness_identity(expected: dict[str, str], operation: str) -> None:
    actual = harness_source_snapshot()
    if actual != expected:
        raise RuntimeError(
            f"Diagnostic harness source changed before {operation}: "
            f"expected={expected}, actual={actual}"
        )


def fixture_checksum_snapshot() -> dict[str, Any]:
    checksum_path = FIXTURE_DIRECTORY / "SHA256SUMS.txt"
    records = []
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        relative = relative.lstrip("* ")
        path = (FIXTURE_DIRECTORY / relative).resolve()
        path.relative_to(FIXTURE_DIRECTORY.resolve())
        actual = sha256_file(path) if path.is_file() else None
        records.append(
            {
                "relative_path": relative,
                "expected_sha256": expected,
                "actual_sha256": actual,
                "matched": actual == expected,
            }
        )
    return {
        "checksum_file": file_identity(checksum_path),
        "records": records,
        "all_verified": bool(records) and all(item["matched"] for item in records),
    }


def fixture_stable_identity(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return only content identities, excluding filesystem timestamps."""
    return {
        "checksum_file_sha256": snapshot["checksum_file"]["sha256"],
        "records": [
            {
                "relative_path": record["relative_path"],
                "expected_sha256": record["expected_sha256"],
                "actual_sha256": record["actual_sha256"],
                "matched": record["matched"],
            }
            for record in snapshot["records"]
        ],
    }


def readback_acceptance_policy() -> dict[str, Any]:
    """Describe diagnostic-only acceptance of OpenVSP parameter readbacks."""
    return {
        "scope": (
            "diagnostic harness instrumentation only; production validation, geometry, "
            "station plans, metrics, and engineering gates are unchanged"
        ),
        "immediate_setter_numeric": {
            "evidence_path": "parameter_acceptance.call_results[].accepted_immediate_value",
            "comparison": "absolute difference from applied setter value",
            "absolute_tolerance": IMMEDIATE_SETTER_ABS_TOLERANCE,
        },
        "persisted_generic_numeric": {
            "evidence_path": (
                "parameter_acceptance.call_results[].accepted_final_value, sourced from "
                "parameter_readback.after_export or accepted_step_settings"
            ),
            "comparison": "absolute difference from applied setter value",
            "absolute_tolerance": PERSISTED_NUMERIC_READBACK_ABS_TOLERANCE,
            "reason": (
                "true authored inputs remain exact at the diagnostic absolute tolerance; "
                "calculated mesh outputs are classified separately and are not covered by "
                "this persistence rule"
            ),
        },
        "enum_and_root_cap": {
            "evidence_path": (
                "parameter_acceptance.call_results for enum parameters and "
                "checks.root_cap_exact_after_update/after_export"
            ),
            "absolute_tolerance": ENUM_READBACK_ABS_TOLERANCE,
        },
        "Design.AFLimit": {
            "accepted_values": (
                "applied value under the immediate/persisted tolerance, or the documented "
                f"OpenVSP clamp {KNOWN_OPENVSP_AFLIMIT_CLAMP:.2f} if observed"
            ),
            "authoritative_geometry_path": "after_export.sections[0].r_over_R",
            "authoritative_root_absolute_tolerance": AUTHORITATIVE_ROOT_ABS_TOLERANCE,
        },
        "generated_mesh_metrics": {
            "semantic_parameters": sorted(GENERATED_MESH_METRIC_SEMANTICS),
            "adapter_attempt": (
                "the unchanged production adapter attempts its recorded value and the "
                "immediate accepted value must match at 1e-12"
            ),
            "generated_outcome": (
                "OpenVSP CalculateMeshMetrics subsequently recalculates these output "
                "parameters; final persistence is not required and the applied, immediate, "
                "final, and downstream delta values remain evidence"
            ),
            "final_persistence_required": False,
            "source_evidence": {
                "calculation": {
                    "path": OPENVSP_PROPGEOM_SOURCE_PATH,
                    "sha256": OPENVSP_PROPGEOM_SOURCE_SHA256,
                    "function_lines": "2053-2130",
                    "SmallPanelW_assignment_line": 2100,
                    "MaxGrowth_assignment_line": 2129,
                },
                "gui_output": {
                    "path": OPENVSP_PROPSCREEN_SOURCE_PATH,
                    "sha256": OPENVSP_PROPSCREEN_SOURCE_SHA256,
                    "AddOutput_lines": "562-563",
                    "Update_lines": "720-722",
                },
            },
        },
    }


def prior_instrumentation_attempt_metadata() -> dict[str, Any]:
    return {
        "relative_path": PRIOR_INSTRUMENTATION_ATTEMPT,
        "outcome": "CONFOUNDED_OR_INEFFECTIVE_INTERVENTION",
        "failure": "A_original cap or authored-parameter readback was not accepted",
        "interpretation": (
            "preserved stopped instrumentation attempt; the outcome was caused by the "
            "diagnostic harness's pre-taxonomy readback policy, not a production geometry "
            "or acceptance result"
        ),
        "preserved_unchanged": True,
    }


def second_instrumentation_attempt_metadata() -> dict[str, Any]:
    return {
        "relative_path": SECOND_INSTRUMENTATION_ATTEMPT,
        "outcome": "CONFOUNDED_OR_INEFFECTIVE_INTERVENTION",
        "interpretation": (
            "preserved stopped taxonomy attempt; B completed, but the diagnostic harness "
            "incorrectly required the generated PropGeom.SmallPanelW output to persist the "
            "adapter's attempted value"
        ),
        "preserved_unchanged": True,
    }


def file_identity(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": sha256_file(path),
    }


def recheck_openvsp_runtime_files(probe: dict[str, Any] | None) -> dict[str, Any]:
    """Re-hash every OpenVSP runtime file recorded by the isolated probe."""
    if probe is None:
        return {
            "before": {},
            "after": {},
            "unchanged": False,
            "errors": ["OpenVSP probe did not complete"],
        }

    before = probe.get("runtime_files", {})
    after: dict[str, Any] = {}
    errors: list[str] = []
    for name, expected in before.items():
        path = Path(expected["path"])
        try:
            actual = file_identity(path)
        except OSError as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
            actual = {
                "path": str(path),
                "size_bytes": None,
                "mtime_ns": None,
                "sha256": None,
            }
        actual["matched_probe"] = (
            actual["sha256"] == expected.get("sha256")
            and actual["size_bytes"] == expected.get("size_bytes")
        )
        after[name] = actual
    unchanged = bool(before) and not errors and all(
        record["matched_probe"] for record in after.values()
    )
    return {
        "before": before,
        "after": after,
        "unchanged": unchanged,
        "errors": errors,
    }


def artifact_snapshot(job_dir: Path) -> dict[str, Any]:
    paths = {
        "retained_final_step": job_dir / "blade_solid.step",
        "retained_raw_step": job_dir / "blade_openvsp.step",
        "retained_vsp3": job_dir / "blade_openvsp.vsp3",
        "generated_spec": job_dir / "blade_spec.json",
        "input_spec": job_dir / "blade_spec_input.json",
        "resolved_spec": job_dir / "resolved_blade_spec.json",
        "progress": job_dir / "progress.json",
        "stdout": job_dir / "build_stdout.log",
        "stderr": job_dir / "build_stderr.log",
        "exported_candidate": DEFAULT_EVIDENCE_ROOT / "exported_candidate.json",
        "submitted_spec": DEFAULT_EVIDENCE_ROOT / "job" / "submitted_blade_spec.json",
        "fixture_checksums": FIXTURE_DIRECTORY / "SHA256SUMS.txt",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Required retained evidence is missing: {missing}")
    return {name: file_identity(path) for name, path in paths.items()}


def environment_identity(openvsp_probe: dict[str, Any]) -> dict[str, Any]:
    import numpy
    import OCP
    import scipy

    binding_version = getattr(OCP, "__version__", "unknown")
    occt_version = ".".join(str(binding_version).split(".")[:3])
    return {
        "captured_at_utc": utc_now(),
        "platform": platform.platform(),
        "python": {
            "executable": sys.executable,
            "version": platform.python_version(),
            "full_version": sys.version,
        },
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "ocp_binding": binding_version,
        "cadquery_ocp_distribution": importlib.metadata.version("cadquery-ocp"),
        "opencascade_occt": {
            "version": occt_version,
            "identity_method": (
                "derived from OCP.__version__; no independent native Standard_Version API was available"
            ),
            "independently_queried": False,
        },
        "bladegen_distribution": importlib.metadata.version("bladegen"),
        "openvsp": openvsp_probe,
    }


def run_probe(output_path: Path) -> int:
    from bladegen.adapters.openvsp_adapter import _load_openvsp

    openvsp_root = Path(os.environ["OPENVSP_ROOT"]).resolve()
    runtime_paths = {
        "vsp_executable": openvsp_root / "vsp",
        "python_extension": openvsp_root / "python" / "openvsp" / "openvsp" / "_vsp.so",
        "python_api": openvsp_root / "python" / "openvsp" / "openvsp" / "vsp.py",
        "python_config": openvsp_root / "python" / "openvsp_config" / "openvsp_config" / "__init__.py",
    }
    vsp = _load_openvsp()
    constants = {
        name: int(getattr(vsp, name))
        for name in (
            "NO_END_CAP",
            "FLAT_END_CAP",
            "ROUND_END_CAP",
            "EDGE_END_CAP",
            "SHARP_END_CAP",
            "POINT_END_CAP",
            "ROUND_EXT_END_CAP_NONE",
            "ROUND_EXT_END_CAP_LE",
            "ROUND_EXT_END_CAP_TE",
            "ROUND_EXT_END_CAP_BOTH",
            "NUM_END_CAP_OPTIONS",
        )
    }
    write_json(
        output_path,
        {
            "captured_at_utc": utc_now(),
            "openvsp_version": str(vsp.GetVSPVersion()),
            "openvsp_version_parts": [
                int(vsp.GetVSPVersionMajor()),
                int(vsp.GetVSPVersionMinor()),
                int(vsp.GetVSPVersionChange()),
            ],
            "runtime_files": {
                name: file_identity(path)
                for name, path in runtime_paths.items()
            },
            "cap_type_constants": constants,
            "load_graphics": False,
            "model_created": False,
        },
    )
    return 0


def run_bounded(
    argv: list[str], log_path: Path, timeout_seconds: int, cwd: Path = REPOSITORY_ROOT
) -> dict[str, Any]:
    command = [
        "timeout",
        "--signal=TERM",
        "--kill-after=30s",
        f"{timeout_seconds}s",
        *argv,
    ]
    started = time.monotonic_ns()
    with log_path.open("w", encoding="utf-8", buffering=1) as log:
        completed = subprocess.run(
            command,
            cwd=cwd,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return {
        "argv": command,
        "command": " ".join(subprocess.list2cmdline([part]) for part in command),
        "returncode": completed.returncode,
        "timed_out": completed.returncode in {124, 137},
        "elapsed_seconds": (time.monotonic_ns() - started) / 1e9,
        "completed_at_utc": utc_now(),
        "log_path": str(log_path.resolve()),
    }


def collect_preflight(job_dir: Path, prior_isolation: Path, probe: dict[str, Any]) -> dict[str, Any]:
    from bladegen.curves.resolver import resolve_blade_spec
    from bladegen.models import BladeSpec, ResolvedBladeSpec

    prior_preflight = read_json(prior_isolation / "preflight_evidence.json")
    prior_summary = read_json(prior_isolation / "contour_isolation_summary.json")
    artifacts = artifact_snapshot(job_dir)
    fixtures = fixture_checksum_snapshot()
    sources = source_snapshot()
    recorded_sources = prior_preflight["relevant_source_sha256"]
    source_identity = {
        relative: {
            "current_sha256": sources.get(relative),
            "recorded_sha256": recorded_sources[relative],
            "matched": sources.get(relative) == recorded_sources[relative],
        }
        for relative in sorted(recorded_sources)
    }
    additional_source_identity = {}
    for relative in sorted(set(sources) - set(recorded_sources)):
        head_result = subprocess.run(
            ["git", "show", f"HEAD:{relative}"],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
        )
        head_sha256 = (
            hashlib.sha256(head_result.stdout).hexdigest()
            if head_result.returncode == 0
            else None
        )
        additional_source_identity[relative] = {
            "current_sha256": sources[relative],
            "HEAD_sha256": head_sha256,
            "matched_HEAD": sources[relative] == head_sha256,
        }

    spec_paths = {
        "generated": job_dir / "blade_spec.json",
        "input": job_dir / "blade_spec_input.json",
        "candidate": DEFAULT_EVIDENCE_ROOT / "exported_candidate.json",
        "submitted": DEFAULT_EVIDENCE_ROOT / "job" / "submitted_blade_spec.json",
    }
    models = {name: BladeSpec.from_json(path) for name, path in spec_paths.items()}
    model_payloads = {name: model.model_dump(mode="json") for name, model in models.items()}
    first = model_payloads["generated"]
    spec_equal = all(payload == first for payload in model_payloads.values())

    resolved = resolve_blade_spec(models["generated"])
    resolved_payload = jsonable(resolved.model_dump(mode="json"))
    retained_resolved_raw = read_json(job_dir / "resolved_blade_spec.json")
    retained_resolved_model = ResolvedBladeSpec.model_validate(retained_resolved_raw)
    retained_resolved_normalized = jsonable(retained_resolved_model.model_dump(mode="json"))
    resolved_equal = resolved_payload == retained_resolved_normalized
    raw_representation_equal = resolved_payload == retained_resolved_raw
    engineering_vectors = {
        name: {
            "parameter_vector": list(curve.parameter_vector),
            "value_vector": list(curve.value_vector),
            "interpolation": "linear",
        }
        for name, curve in resolved.curve_items()
    }

    head = command_output(["git", "rev-parse", "HEAD"])
    branch = command_output(["git", "branch", "--show-current"])
    git_status = subprocess.run(
        ["git", "status", "--short"], cwd=REPOSITORY_ROOT, check=True, text=True,
        stdout=subprocess.PIPE,
    ).stdout
    checks = {
        "retained_final_step_hash": artifacts["retained_final_step"]["sha256"] == EXPECTED_FINAL_STEP_SHA256,
        "retained_raw_step_hash": artifacts["retained_raw_step"]["sha256"] == EXPECTED_RAW_STEP_SHA256,
        "production_source_identity": all(item["matched"] for item in source_identity.values()),
        "additional_geometry_sources_match_HEAD": all(
            item["matched_HEAD"] for item in additional_source_identity.values()
        ),
        "candidate_submitted_generated_equivalent": spec_equal,
        "fresh_resolution_equals_retained": resolved_equal,
        "prior_diagnostic_completed": prior_summary.get("diagnostic_status") == "COMPLETED",
        "metric_self_tests": bool(isolation.metric_self_tests()["passed"]),
        "all_fixture_sha256_verified": fixtures["all_verified"],
        "openvsp_version": probe["openvsp_version_parts"] == [3, 54, 0],
    }
    return {
        "captured_at_utc": utc_now(),
        "job_id": JOB_ID,
        "git": {
            "head": head,
            "recorded_isolation_head": RECORDED_HEAD,
            "head_matches_recorded": head == RECORDED_HEAD,
            "branch": branch,
            "worktree_clean": not bool(git_status),
            "status_porcelain": git_status,
        },
        "artifacts": artifacts,
        "fixture_checksum_verification": fixtures,
        "sources": source_identity,
        "additional_sources": additional_source_identity,
        "source_snapshot_sha256": canonical_sha256(sources),
        "specification": {
            "paths": {name: str(path.resolve()) for name, path in spec_paths.items()},
            "canonical_model_sha256": {
                name: canonical_sha256(payload) for name, payload in model_payloads.items()
            },
            "models_equal": spec_equal,
            "fresh_resolved_sha256": canonical_sha256(resolved_payload),
            "retained_resolved_raw_sha256": canonical_sha256(retained_resolved_raw),
            "retained_resolved_normalized_sha256": canonical_sha256(
                retained_resolved_normalized
            ),
            "fresh_resolution_equals_retained": resolved_equal,
            "fresh_json_representation_equals_retained_raw": raw_representation_equal,
            "raw_representation_difference_is_not_semantic": (
                resolved_equal and not raw_representation_equal
            ),
            "engineering_vectors": engineering_vectors,
            "airfoil_sections": resolved_payload["airfoil_sections"],
        },
        "prior_isolation": {
            "path": str(prior_isolation.resolve()),
            "report_sha256": sha256_file(prior_isolation / "X57_CONTOUR_ISOLATION_REPORT.md"),
            "summary_sha256": sha256_file(prior_isolation / "contour_isolation_summary.json"),
            "stage_matrix_sha256": sha256_file(prior_isolation / "source_stage_matrix.csv"),
            "runner_sha256": sha256_file(prior_isolation / "diagnose_x57_contours.py"),
        },
        "checks": checks,
        "passed": all(checks.values()),
    }


def build_experiment_plan(
    output_dir: Path,
    preflight: dict[str, Any],
    probe: dict[str, Any],
    timeout_seconds_per_arm: int,
) -> dict[str, Any]:
    constants = probe["cap_type_constants"]
    adapter_path = REPOSITORY_ROOT / "backend" / "bladegen" / "adapters" / "openvsp_adapter.py"
    propgeom_path = Path("/tmp/openvsp-src-354-rootcap/src/geom_core/PropGeom.cpp")
    enum_doc = (
        Path(os.environ["OPENVSP_ROOT"])
        / "python"
        / "openvsp"
        / "doc"
        / "groups"
        / "Enumerations.html"
    )
    api_path = (
        Path(os.environ["OPENVSP_ROOT"])
        / "python"
        / "openvsp"
        / "openvsp"
        / "vsp.py"
    )
    plan = {
        "experiment_id": "X57-AB-01",
        "written_at_utc": utc_now(),
        "written_before_arm_a": True,
        "question": "Does changing only the active OpenVSP physical-root end-cap treatment materially change the confirmed inboard contour discrepancy?",
        "production_source_identity_verified": preflight["passed"],
        "intervention": {
            "semantic_parameter": "EndCap.CapUMinOption",
            "production_setter": "bladegen.adapters.openvsp_adapter._configure_geometry via _set",
            "legal_end_cap_values": [
                {
                    "enum_name": name,
                    "value": constants[name],
                    "legal_option": name != "NUM_END_CAP_OPTIONS",
                }
                for name in (
                    "NO_END_CAP",
                    "FLAT_END_CAP",
                    "ROUND_END_CAP",
                    "EDGE_END_CAP",
                    "SHARP_END_CAP",
                    "POINT_END_CAP",
                    "ROUND_EXT_END_CAP_NONE",
                    "ROUND_EXT_END_CAP_LE",
                    "ROUND_EXT_END_CAP_TE",
                    "ROUND_EXT_END_CAP_BOTH",
                    "NUM_END_CAP_OPTIONS",
                )
            ],
            "parameter_units_and_types": {
                "CapUMinOption": "enumerated integer",
                "CapUMinLength": "dimensionless",
                "CapUMinOffset": "dimensionless",
                "CapUMinStrength": "dimensionless",
                "CapUMinSweepFlag": "boolean",
                "CapUMinTess": "integer count",
            },
            "hook": "arm-local wrapper of openvsp_adapter._set; all non-target calls pass through unchanged",
            "A_original": {"enum_name": "FLAT_END_CAP", "value": constants["FLAT_END_CAP"]},
            "B_root_cap_intervention": {"enum_name": "NO_END_CAP", "value": constants["NO_END_CAP"]},
            "A2_original_repeat": {"enum_name": "FLAT_END_CAP", "value": constants["FLAT_END_CAP"]},
            "dependent_root_values_held": {
                "CapUMinLength": 1.0,
                "CapUMinOffset": 0.0,
                "CapUMinSweepFlag": 0.0,
                "CapUMinTess": 3.0,
                "CapUMinStrength": 0.5,
            },
            "tip_treatment_held": {
                "CapUMaxOption": constants["FLAT_END_CAP"],
                "CapUMaxLength": 1.0,
                "CapUMaxOffset": 0.0,
                "CapUMaxStrength": 0.5,
                "CapUMaxSweepFlag": 0.0,
            },
            "active_status_observation": {
                "public_api_available": False,
                "FLAT_END_CAP": "source behavior does not consume round/edge dependent shaping controls",
                "NO_END_CAP": "source returns without constructing an end cap; dependent shaping controls are inactive",
                "policy": (
                    "record accepted mode and dependent values; active-state statements are "
                    "source-derived because OpenVSP 3.54.0 exposes no IsParmActive API"
                ),
            },
        },
        "physical_root_identification": {
            "result": "CapUMin is the physical root control",
            "adapter_section_order": "XSec index 0 is resolved r/R 0.20238; last XSec is r/R 1.0",
            "openvsp_source_finding": "OpenVSP 3.54.0 PropGeom labels UMin as Propeller Root and UMax as Propeller Tip",
            "openvsp_source_tag": "OpenVSP_3.54.0",
            "openvsp_source_commit": "db6c6fe8f4eca27d7517f4ae0b2078abdd3fd927",
            "propgeom_source": {
                "path": str(propgeom_path.resolve()),
                "sha256": sha256_file(propgeom_path),
                "relevant_lines": "375-380",
            },
            "adapter_source": {"path": str(adapter_path.resolve()), "sha256": sha256_file(adapter_path)},
            "enum_document": {"path": str(enum_doc.resolve()), "sha256": sha256_file(enum_doc)},
            "api_document": {"path": str(api_path.resolve()), "sha256": sha256_file(api_path)},
        },
        "invariants": [
            "complete canonical BladeSpec and freshly resolved engineering data",
            "airfoil coordinates and both station radii",
            "chord, twist, rake, skew, thickness and zero auxiliary PCurves",
            "diameter, root radius, reference axis, rotation and placement",
            "tip end-cap treatment and all non-mode root cap values",
            "tessellation, clustering and STEP export settings",
            "runtime versions and production source hashes",
        ],
        "process_policy": {
            "fresh_process_per_arm": True,
            "fresh_model_via_production_build_and_export": True,
            "sequential_arms": True,
            "external_timeout_seconds_per_arm": timeout_seconds_per_arm,
            "kill_after_seconds": 30,
            "ocp_solidification": False,
            "retained_vsp3_loaded": False,
        },
        "readback_acceptance_policy": readback_acceptance_policy(),
        "preserved_prior_instrumentation_attempt": (
            prior_instrumentation_attempt_metadata()
        ),
        "preserved_second_instrumentation_attempt": (
            second_instrumentation_attempt_metadata()
        ),
        "primary_sampled_stations": list(PRIMARY_STATIONS),
        "recorded_production_baseline": {
            str(station): {"rms_mm": values[0], "p95_mm": values[1], "sampled_max_mm": values[2]}
            for station, values in RECORDED_PRODUCTION.items()
        },
        "baseline_reproduction_criteria": {
            "A_vs_retained_raw_independent_4x_sampled_max_each_mm": 0.0001,
            "production_metric_absolute_delta_each_mm": 0.0001,
            "production_metrics": ["rms_mm", "p95_mm", "sampled_max_mm"],
            "miss_outcome": "BASELINE_NOT_REPRODUCED; B is not launched",
        },
        "material_effect_criterion_predeclared": {
            "direct_A_vs_B_independent_4x_sampled_max_strictly_greater_mm": 0.001,
            "and_same_station_absolute_change_in_at_least_one_contour_metric_strictly_greater_mm": 0.001,
            "metrics": ["production RMS/P95/sampled max", "independent 4x RMS/P95/sampled max"],
            "rationale": "ten times the maximum permitted baseline-reproduction difference",
            "effect_triggers_A2": True,
        },
        "A2_reproduction_criteria": {
            "A2_vs_A_independent_4x_sampled_max_each_mm": 0.0001,
            "production_metric_absolute_delta_each_mm": 0.0001,
        },
        "conditional_expanded_sampled_stations": list(EXPANDED_SAMPLED_STATIONS),
        "outboard_control_choice": {
            "sampled_r_over_R": 0.80632,
            "prior_production_sampled_max_mm": 0.008687748615422649,
            "reason": "retained passing outboard distribution-control station",
        },
        "metrics": {
            "production": "unchanged bladegen.validation.measure_sections.measure_sections with observational station subset",
            "independent": "self-tested component-preserving bidirectional point-to-segment metric imported from diagnose_x57_contours.py",
            "densities": {
                "actual_points_per_edge": {"1x": 2500, "2x": 4999, "4x": 9997},
                "expected_points_per_surface": {"1x": 2001, "2x": 4001, "4x": 8001},
            },
            "sampled_max_is_continuous_hausdorff": False,
            "registration_or_scaling": False,
        },
        "allowed_outcomes": [
            "ROOT_CAP_EFFECT_REPRODUCED",
            "NO_MATERIAL_EFFECT_FOR_TESTED_INTERVENTION",
            "BASELINE_NOT_REPRODUCED",
            "CONFOUNDED_OR_INEFFECTIVE_INTERVENTION",
            "INCOMPLETE",
        ],
    }
    write_json(output_dir / "experiment_plan.json", plan)
    return plan

def _parm_record(vsp: Any, parm_id: str) -> dict[str, Any]:
    return {
        "group": str(vsp.GetParmGroupName(parm_id)),
        "display_group": str(vsp.GetParmDisplayGroupName(parm_id)),
        "name": str(vsp.GetParmName(parm_id)),
        "value": float(vsp.GetParmVal(parm_id)),
        "lower_limit": float(vsp.GetParmLowerLimit(parm_id)),
        "upper_limit": float(vsp.GetParmUpperLimit(parm_id)),
    }


def _pcuvre_snapshot(vsp: Any, prop_id: str) -> dict[str, Any]:
    indices = (
        ("thickness", vsp.PROP_THICK),
        ("chord", vsp.PROP_CHORD),
        ("twist", vsp.PROP_TWIST),
        ("rake", vsp.PROP_RAKE),
        ("skew", vsp.PROP_SKEW),
        ("sweep", vsp.PROP_SWEEP),
        ("induced_lift_coefficient", vsp.PROP_CLI),
        ("axial", vsp.PROP_AXIAL),
        ("tangential", vsp.PROP_TANGENTIAL),
    )
    return {
        name: {
            "index": int(index),
            "interpolation_enum": int(vsp.PCurveGetType(prop_id, index)),
            "parameter_vector": [float(value) for value in vsp.PCurveGetTVec(prop_id, index)],
            "value_vector": [float(value) for value in vsp.PCurveGetValVec(prop_id, index)],
        }
        for name, index in indices
    }


def _configuration_snapshot(vsp: Any, prop_id: str) -> dict[str, Any]:
    all_parameters = sorted(
        (_parm_record(vsp, parm_id) for parm_id in vsp.GetGeomParmIDs(prop_id)),
        key=lambda item: (item["group"], item["name"]),
    )
    surface_id = vsp.GetXSecSurf(prop_id, 0)
    sections = []
    for index in range(vsp.GetNumXSec(surface_id)):
        xsec_id = vsp.GetXSec(surface_id, index)
        parameters = sorted(
            (_parm_record(vsp, parm_id) for parm_id in vsp.GetXSecParmIDs(xsec_id)),
            key=lambda item: (item["group"], item["name"]),
        )
        radius = next(
            item["value"]
            for item in parameters
            if item["group"] == "XSec" and item["name"] == "RadiusFrac"
        )
        upper = [[float(point.x()), float(point.y())] for point in vsp.GetAirfoilUpperPnts(xsec_id)]
        lower = [[float(point.x()), float(point.y())] for point in vsp.GetAirfoilLowerPnts(xsec_id)]
        sections.append(
            {
                "index": index,
                "r_over_R": radius,
                "parameters": parameters,
                "upper": upper,
                "lower": lower,
                "upper_sha256": canonical_sha256(upper),
                "lower_sha256": canonical_sha256(lower),
            }
        )
    cap_names = (
        "CapUMinOption",
        "CapUMinLength",
        "CapUMinOffset",
        "CapUMinStrength",
        "CapUMinSweepFlag",
        "CapUMinTess",
        "CapUMaxOption",
        "CapUMaxLength",
        "CapUMaxOffset",
        "CapUMaxStrength",
        "CapUMaxSweepFlag",
    )
    caps = {}
    for name in cap_names:
        parm_id = vsp.FindParm(prop_id, name, "EndCap")
        if parm_id:
            caps[name] = _parm_record(vsp, parm_id)
    return {
        "all_prop_parameters": all_parameters,
        "cap_parameters": caps,
        "cap_parameter_active_state": {
            "observable_in_public_python_api": False,
            "meaning": (
                "OpenVSP source makes length/offset/strength/sweep inactive for FLAT and "
                "NO_END_CAP; accepted values are recorded without inventing an API-active flag"
            ),
        },
        "pcurves": _pcuvre_snapshot(vsp, prop_id),
        "sections": sections,
        "generated_outcomes": {
            "main_surface_count": int(vsp.GetNumMainSurfs(prop_id)),
            "xsec_count": int(vsp.GetNumXSec(surface_id)),
        },
    }


def _step_settings_snapshot(vsp: Any) -> dict[str, Any]:
    vehicle = vsp.GetVehicleID()
    names = (
        "LenUnit",
        "Tolerance",
        "SplitSurfs",
        "SplitSubSurfs",
        "MergePoints",
        "ToCubic",
        "ToCubicTol",
        "TrimTE",
        "MergeLETE",
        "ExportPropMainSurf",
    )
    return {
        name: _parm_record(vsp, vsp.FindParm(vehicle, name, "STEPSettings"))
        for name in names
    }


def _evaluate_arm_parameter_acceptance(
    context: dict[str, Any],
    requested_enum: int,
    expected_root_r_over_R: float,
) -> dict[str, Any]:
    after_geometry = context["after_geometry_update"]
    after_export = context["after_export"]
    final_geom = _semantic_parameter_map(after_export)
    final_step = {
        f"STEPSettings.{name}": float(record["value"])
        for name, record in context["accepted_step_settings"].items()
    }
    first_radius = float(after_export["sections"][0]["r_over_R"])
    call_results = []
    for call in context["set_calls"]:
        semantic = f"{call['group']}.{call['name']}"
        expected = float(call["applied_value"])
        immediate = float(call["accepted_immediate_value"])
        enum_readback = semantic.endswith("Option") or semantic == "STEPSettings.LenUnit"
        final_tolerance = (
            ENUM_READBACK_ABS_TOLERANCE
            if enum_readback
            else PERSISTED_NUMERIC_READBACK_ABS_TOLERANCE
        )
        final_value = (
            final_step.get(semantic)
            if call["group"] == "STEPSettings"
            else final_geom.get(semantic)
        )
        final_readback_present = final_value is not None
        generated_metric = semantic in GENERATED_MESH_METRIC_SEMANTICS
        if generated_metric:
            policy = (
                "generated OpenVSP mesh metric: unchanged adapter attempt and immediate "
                "setter acceptance are recorded at 1e-12; CalculateMeshMetrics owns the "
                "final output, so final persistence is not required"
            )
            immediate_matches_applied = (
                abs(immediate - expected) <= IMMEDIATE_SETTER_ABS_TOLERANCE
            )
            immediate_matches_clamp = False
            immediate_passed = immediate_matches_applied
            final_matches_applied = (
                final_value is not None
                and abs(float(final_value) - expected) <= final_tolerance
            )
            final_matches_clamp = False
            final_passed = final_readback_present
        elif semantic == "Design.AFLimit":
            policy = (
                "accept the applied AFLimit or documented OpenVSP 3.54.0 clamp 0.20 "
                "under the respective immediate/persisted tolerance; first XSec "
                "RadiusFrac remains the authoritative geometric root at 1e-12"
            )
            immediate_matches_applied = (
                abs(immediate - expected) <= IMMEDIATE_SETTER_ABS_TOLERANCE
            )
            immediate_matches_clamp = (
                abs(immediate - KNOWN_OPENVSP_AFLIMIT_CLAMP)
                <= IMMEDIATE_SETTER_ABS_TOLERANCE
            )
            immediate_passed = immediate_matches_applied or immediate_matches_clamp
            final_matches_applied = (
                final_value is not None
                and abs(float(final_value) - expected) <= final_tolerance
            )
            final_matches_clamp = (
                final_value is not None
                and abs(float(final_value) - KNOWN_OPENVSP_AFLIMIT_CLAMP)
                <= final_tolerance
            )
            final_passed = (
                (final_matches_applied or final_matches_clamp)
                and abs(first_radius - expected_root_r_over_R)
                <= AUTHORITATIVE_ROOT_ABS_TOLERANCE
            )
        else:
            policy = (
                "immediate setter readback must match applied value at 1e-12; persisted "
                f"{'enum' if enum_readback else 'numeric'} readback must match at "
                f"{final_tolerance:.0e}"
            )
            immediate_matches_applied = (
                abs(immediate - expected) <= IMMEDIATE_SETTER_ABS_TOLERANCE
            )
            immediate_matches_clamp = False
            immediate_passed = immediate_matches_applied
            final_matches_applied = (
                final_value is not None
                and abs(float(final_value) - expected) <= final_tolerance
            )
            final_matches_clamp = False
            final_passed = (
                final_matches_applied
            )
        call_results.append(
            {
                "semantic_parameter": semantic,
                "applied_value": expected,
                "accepted_immediate_value": immediate,
                "accepted_final_value": final_value,
                "immediate_evidence_path": (
                    f"set_calls[{call['sequence'] - 1}].accepted_immediate_value"
                ),
                "final_evidence_path": (
                    f"{'accepted_step_settings' if call['group'] == 'STEPSettings' else 'after_export.all_prop_parameters'}"
                    f"[{semantic}]"
                ),
                "immediate_absolute_tolerance": IMMEDIATE_SETTER_ABS_TOLERANCE,
                "final_absolute_tolerance": final_tolerance,
                "enum_readback": enum_readback,
                "parameter_role": (
                    "generated_mesh_metric" if generated_metric else "authored_input"
                ),
                "final_persistence_required": not generated_metric,
                "final_persistence_status": (
                    "NOT_APPLICABLE_GENERATED_OUTPUT"
                    if generated_metric
                    else "REQUIRED"
                ),
                "final_readback_present": final_readback_present,
                "adapter_attempted_value": expected,
                "generated_final_value": final_value if generated_metric else None,
                "downstream_change_from_immediate": (
                    None
                    if final_value is None
                    else float(final_value) - immediate
                ),
                "immediate_matches_applied": immediate_matches_applied,
                "immediate_matches_known_AFLimit_clamp": immediate_matches_clamp,
                "final_matches_applied": final_matches_applied,
                "final_matches_known_AFLimit_clamp": final_matches_clamp,
                "immediate_passed": immediate_passed,
                "final_passed": final_passed,
                "policy": policy,
            }
        )

    cap_after_update = float(
        after_geometry["cap_parameters"]["CapUMinOption"]["value"]
    )
    cap_after_export = float(
        after_export["cap_parameters"]["CapUMinOption"]["value"]
    )
    errors = [
        message
        for drain in context["drain_calls"]
        for message in drain["messages"]
    ]
    checks = {
        "all_setters_accepted_immediately": all(
            row["immediate_passed"] for row in call_results
        ),
        "all_authored_values_persisted": all(
            row["final_passed"]
            for row in call_results
            if row["final_persistence_required"]
        ),
        "all_generated_metric_readbacks_present": all(
            row["final_readback_present"]
            for row in call_results
            if not row["final_persistence_required"]
        ),
        "root_cap_exact_after_update": (
            abs(cap_after_update - requested_enum) <= ENUM_READBACK_ABS_TOLERANCE
        ),
        "root_cap_exact_after_export": (
            abs(cap_after_export - requested_enum) <= ENUM_READBACK_ABS_TOLERANCE
        ),
        "authoritative_first_xsec_root_preserved": (
            abs(first_radius - expected_root_r_over_R)
            <= AUTHORITATIVE_ROOT_ABS_TOLERANCE
        ),
        "production_engineering_readback_passed": True,
        "no_api_errors_including_post_snapshot": not errors,
    }
    return {
        "readback_acceptance_policy": readback_acceptance_policy(),
        "immediate_setter_absolute_tolerance": IMMEDIATE_SETTER_ABS_TOLERANCE,
        "persisted_numeric_absolute_tolerance": (
            PERSISTED_NUMERIC_READBACK_ABS_TOLERANCE
        ),
        "enum_and_root_cap_absolute_tolerance": ENUM_READBACK_ABS_TOLERANCE,
        "enum_acceptance_policy": "exact enum value within absolute tolerance",
        "generated_mesh_metrics": {
            "semantics": sorted(GENERATED_MESH_METRIC_SEMANTICS),
            "all_immediate_setter_attempts_accepted": all(
                row["immediate_passed"]
                for row in call_results
                if row["parameter_role"] == "generated_mesh_metric"
            ),
            "final_persistence_required": False,
            "records": [
                row
                for row in call_results
                if row["parameter_role"] == "generated_mesh_metric"
            ],
        },
        "aflimit_exception": {
            "requested_root_r_over_R": expected_root_r_over_R,
            "known_clamp": KNOWN_OPENVSP_AFLIMIT_CLAMP,
            "accepted_AFLimit": final_geom.get("Design.AFLimit"),
            "authoritative_first_xsec_RadiusFrac": first_radius,
            "authoritative_root_absolute_tolerance": (
                AUTHORITATIVE_ROOT_ABS_TOLERANCE
            ),
        },
        "call_results": call_results,
        "api_errors": errors,
        "checks": checks,
        "passed": all(checks.values()),
    }


def _selected_plan(spec: Any, sampled_stations: tuple[float, ...]) -> Any:
    from bladegen.validation.station_plan import (
        ValidationStationPlan,
        plan_validation_stations,
    )

    full = plan_validation_stations(spec)
    selected = tuple(
        item
        for item in full.stations
        if any(same_station(item.sampled_r_over_R, station) for station in sampled_stations)
    )
    if len(selected) != len(sampled_stations):
        found = [item.sampled_r_over_R for item in selected]
        raise RuntimeError(f"Requested diagnostic stations are not the exact production plan: {found}")
    return full, ValidationStationPlan(
        root_r_over_R=full.root_r_over_R,
        tip_r_over_R=full.tip_r_over_R,
        stations=selected,
        endpoint_policy=full.endpoint_policy,
    )


def _plot_overlay(
    path: Path,
    station: float,
    actual: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    *,
    second_actual: list[dict[str, Any]] | None = None,
    second_label: str = "",
) -> None:
    figure, axis = plt.subplots(figsize=(10, 7))
    for index, component in enumerate(expected):
        points = np.asarray(component["points"])
        axis.plot(
            points[:, 0],
            points[:, 1],
            color="#d62728",
            linewidth=1.0,
            label="unchanged expected" if index == 0 else None,
        )
    for index, component in enumerate(actual):
        points = np.asarray(component["points"])
        axis.plot(
            points[:, 0],
            points[:, 1],
            color="#1f77b4",
            linewidth=0.8,
            label="arm raw STEP" if index == 0 else None,
        )
    if second_actual is not None:
        for index, component in enumerate(second_actual):
            points = np.asarray(component["points"])
            axis.plot(
                points[:, 0],
                points[:, 1],
                color="#2ca02c",
                linestyle="--",
                linewidth=0.8,
                label=second_label if index == 0 else None,
            )
    axis.set_aspect("equal", adjustable="datalim")
    axis.set_xlabel("X (mm)")
    axis.set_ylabel("Z (mm)")
    axis.set_title(f"True-scale same-plane contour, r/R={station:.10g}")
    axis.legend()
    axis.grid(alpha=0.2)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_residuals(path: Path, station: float, metric: dict[str, Any]) -> None:
    figure, axis = plt.subplots(figsize=(10, 6))
    for label, detail_key, query_key, color in (
        ("actual to expected", "left_detail", "left_query", "#1f77b4"),
        ("expected to actual", "right_detail", "right_query", "#d62728"),
    ):
        detail = metric[detail_key]
        query = metric[query_key]
        for component in np.unique(query["component"]):
            mask = query["component"] == component
            axis.plot(
                query["s_fraction"][mask],
                detail["distance"][mask],
                color=color,
                linewidth=0.8,
                alpha=0.8,
                label=label if component == np.unique(query["component"])[0] else None,
            )
    axis.set_xlabel("Component arc fraction")
    axis.set_ylabel("Point-to-segment residual (mm)")
    axis.set_title(f"Directional sampled residuals, r/R={station:.10g}")
    axis.grid(alpha=0.2)
    axis.legend()
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _worst_upper_band(metric: dict[str, Any], expected: dict[str, Any], reference_axis: float) -> dict[str, Any]:
    query = metric["right_query"]
    detail = metric["right_detail"]
    local = isolation.local_coordinates(query["points"], expected, reference_axis)
    mask = (
        (query["component"] == "expected_upper")
        & (local[:, 0] >= 0.13)
        & (local[:, 0] <= 0.18)
    )
    if not np.any(mask):
        raise RuntimeError("No expected-upper samples in predeclared x/c band 0.13..0.18")
    distance = detail["distance"][mask]
    weights = query["weights"][mask]
    delta = detail["closest"][mask] - query["points"][mask]
    signed_normal = delta @ np.asarray(expected["normal_direction"])
    local_band = local[mask]
    maximum_index = int(np.argmax(distance))
    return {
        "band_x_over_c": [0.13, 0.18],
        "sample_count": int(np.sum(mask)),
        "arc_weighted": isolation.distance_stats(distance, weights),
        "maximum_query_x_over_c_y_over_c": local_band[maximum_index].tolist(),
        "maximum_distance_mm": float(distance[maximum_index]),
        "signed_normal_actual_projection_minus_expected_mm_at_max": float(
            signed_normal[maximum_index]
        ),
        "signed_normal_min_mm": float(np.min(signed_normal)),
        "signed_normal_max_mm": float(np.max(signed_normal)),
        "interpretation": "negative is below the expected upper surface in the shared requested normal direction",
    }


def _measure_step(
    step_path: Path,
    spec: Any,
    output_dir: Path,
    sampled_stations: tuple[float, ...],
    logger: EventLog,
    *,
    retained_raw_path: Path | None = None,
    density_convergence: bool = True,
) -> dict[str, Any]:
    from bladegen.solid import ocp_solidify as ocp
    from bladegen.validation import measure_sections as measurement

    output_dir.mkdir(parents=True, exist_ok=True)
    full_plan, selected_plan = _selected_plan(spec, sampled_stations)
    write_json(
        output_dir / "station_plan.json",
        {
            "full_production_station_count": len(full_plan.stations),
            "selected_count": len(selected_plan.stations),
            "selection_replaces_acceptance": False,
            "stations": [
                {
                    "requested_r_over_R": item.requested_r_over_R,
                    "sampled_r_over_R": item.sampled_r_over_R,
                    "roles": list(item.roles),
                    "endpoint": item.endpoint,
                    "sample_offset_r_over_R": item.sample_offset_r_over_R,
                }
                for item in selected_plan.stations
            ],
        },
    )

    with logger.operation("raw_step_read", path=str(step_path)):
        raw_shape = ocp.read_step(step_path)
    topology = ocp.inspect_shape(raw_shape)
    write_json(output_dir / "raw_step_topology.json", topology)

    sections: dict[float, Any] = {}
    production_samples: dict[float, list[np.ndarray]] = {}
    current_station: list[float | None] = [None]
    originals = {
        "read_step": measurement.read_step,
        "plan_validation_stations": measurement.plan_validation_stations,
        "_section_shape": measurement._section_shape,
        "_sample_edges": measurement._sample_edges,
    }

    def section_wrapper(shape: Any, radius_mm: float, station: float) -> Any:
        current_station[0] = float(station)
        with logger.operation("production_section_extraction", sampled_r_over_R=station):
            section = originals["_section_shape"](shape, radius_mm, station)
        sections[float(station)] = section
        return section

    def sample_wrapper(shape: Any, points_per_edge: int = 2500) -> list[np.ndarray]:
        station = current_station[0]
        with logger.operation(
            "production_section_sampling",
            sampled_r_over_R=station,
            points_per_edge=points_per_edge,
        ):
            result = originals["_sample_edges"](shape, points_per_edge)
        if station is not None and points_per_edge == 2500:
            production_samples[float(station)] = [points.copy() for points in result]
        return result

    measurement.read_step = lambda _path: raw_shape
    measurement.plan_validation_stations = lambda _spec: selected_plan
    measurement._section_shape = section_wrapper
    measurement._sample_edges = sample_wrapper
    try:
        with logger.operation("unchanged_production_measure_sections"):
            production_records = measurement.measure_sections(step_path, spec)
    finally:
        for name, original in originals.items():
            setattr(measurement, name, original)

    write_json(output_dir / "production_measurements.json", production_records)
    retained_shape = None
    if retained_raw_path is not None:
        with logger.operation("retained_raw_step_read", path=str(retained_raw_path)):
            retained_shape = ocp.read_step(retained_raw_path)

    radius = spec.diameter_mm / 2.0
    spec_payload = spec.model_dump(mode="json")
    records_by_station = {
        round(float(record["sampled_r_over_R"]), 12): record for record in production_records
    }
    station_results = []
    for planned in selected_plan.stations:
        station = float(planned.sampled_r_over_R)
        station_dir = output_dir / "stations" / station_slug(station)
        station_dir.mkdir(parents=True, exist_ok=False)
        section = sections[station]
        with logger.operation("persist_section_brep", sampled_r_over_R=station):
            brep_info = isolation.persist_section_brep(section, station_dir / "raw_section.brep")

        factors = (1, 2, 4) if density_convergence and same_station(station, 0.22302) else (4,)
        factor_results: dict[str, Any] = {}
        factor4_actual = None
        factor4_expected = None
        factor4_metric = None
        for factor in factors:
            points_per_edge = factor * (2500 - 1) + 1
            expected = isolation.independent_expected(spec_payload, station, factor)
            actual = isolation.sample_section_components(section, points_per_edge)
            with logger.operation(
                "independent_point_to_segment_metric",
                sampled_r_over_R=station,
                density_factor=factor,
                actual_points_per_edge=points_per_edge,
                expected_points_per_surface=factor * (2001 - 1) + 1,
            ):
                metric = isolation.compare_components(actual, expected["metric_components"])
            factor_results[f"{factor}x"] = {
                "actual_points_per_edge": points_per_edge,
                "expected_points_per_surface": factor * (2001 - 1) + 1,
                "metrics": isolation.public_metric(metric),
            }
            if factor == 4:
                factor4_actual = actual
                factor4_expected = expected
                factor4_metric = metric

        assert factor4_actual is not None and factor4_expected is not None and factor4_metric is not None
        isolation.save_components_csv(station_dir / "actual_raw_4x.csv", factor4_actual)
        isolation.save_components_csv(
            station_dir / "expected_unchanged_4x.csv", factor4_expected["metric_components"]
        )
        isolation.save_residual_csv(station_dir / "expected_residuals_4x.csv", factor4_metric)
        write_json(station_dir / "metric_density_results.json", factor_results)
        _plot_overlay(
            station_dir / "overlay_true_scale.png",
            station,
            factor4_actual,
            factor4_expected["metric_components"],
        )
        _plot_residuals(station_dir / "directional_residuals.png", station, factor4_metric)

        retained_metric_public = None
        if retained_shape is not None:
            with logger.operation("retained_raw_section_extraction", sampled_r_over_R=station):
                retained_section = originals["_section_shape"](retained_shape, radius, station)
            retained_brep = isolation.persist_section_brep(
                retained_section, station_dir / "retained_raw_section.brep"
            )
            retained_components = isolation.sample_section_components(
                retained_section, 4 * (2500 - 1) + 1
            )
            isolation.save_components_csv(
                station_dir / "retained_raw_actual_4x.csv", retained_components
            )
            with logger.operation("arm_vs_retained_raw_metric", sampled_r_over_R=station):
                retained_metric = isolation.compare_components(
                    factor4_actual, retained_components
                )
            retained_metric_public = isolation.public_metric(retained_metric)
            write_json(station_dir / "arm_vs_retained_raw_metric.json", retained_metric_public)
            _plot_overlay(
                station_dir / "arm_vs_retained_raw_true_scale.png",
                station,
                factor4_actual,
                factor4_expected["metric_components"],
                second_actual=retained_components,
                second_label="retained raw STEP",
            )
            brep_info["retained_raw"] = retained_brep

        production = records_by_station[round(station, 12)]
        headline = factor4_metric["bidirectional_equal_direction_arc_weighted"]
        upper_band = (
            _worst_upper_band(
                factor4_metric,
                factor4_expected,
                float(spec.reference_axis_x_over_c),
            )
            if same_station(station, 0.22302)
            else None
        )
        if upper_band is not None:
            write_json(station_dir / "upper_deficit_xc_0p13_0p18.json", upper_band)
        station_result = {
            "requested_r_over_R": planned.requested_r_over_R,
            "sampled_r_over_R": station,
            "roles": list(planned.roles),
            "endpoint": planned.endpoint,
            "production": production,
            "independent_4x": headline,
            "arm_vs_retained_raw_4x": (
                retained_metric_public["bidirectional_equal_direction_arc_weighted"]
                if retained_metric_public is not None
                else None
            ),
            "upper_deficit_band": upper_band,
            "section_brep": brep_info,
            "directory": str(station_dir.resolve()),
        }
        write_json(station_dir / "station_result.json", station_result)
        station_results.append(station_result)

    result = {
        "step": file_identity(step_path),
        "topology": topology,
        "station_plan_count": len(full_plan.stations),
        "measured_station_count": len(station_results),
        "stations": station_results,
    }
    write_json(output_dir / "measurement_result.json", result)
    return result


def run_arm(
    output_dir: Path,
    job_dir: Path,
    cap_enum_name: str,
    arm_label: str,
    retained_raw_path: Path | None,
) -> int:
    from bladegen.adapters import openvsp_adapter as adapter
    from bladegen.curves.resolver import resolve_blade_spec
    from bladegen.models import BladeSpec, ResolvedBladeSpec
    from bladegen.validation.geometry_validation import validate_openvsp_readback

    logger = EventLog(output_dir / "arm_events.jsonl")
    started_ns = time.monotonic_ns()

    def terminate(signum: int, _frame: Any) -> None:
        logger.emit("termination_signal", signal=signum)
        logger.close()
        os._exit(128 + signum)

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    logger.emit(
        "arm_start",
        arm_label=arm_label,
        cap_enum_name=cap_enum_name,
        pid=os.getpid(),
        fresh_process=True,
    )

    context: dict[str, Any] = {
        "phase": "unconfigured",
        "set_calls": [],
        "drain_calls": [],
        "target_calls": [],
    }
    originals: dict[str, Any] = {}
    try:
        with logger.operation("canonical_input_preparation"):
            spec = BladeSpec.from_json(job_dir / "blade_spec.json")
            resolved = resolve_blade_spec(spec)
            retained_raw_resolved = read_json(job_dir / "resolved_blade_spec.json")
            retained_model = ResolvedBladeSpec.model_validate(retained_raw_resolved)
            resolved_payload = jsonable(resolved.model_dump(mode="json"))
            retained_normalized = jsonable(retained_model.model_dump(mode="json"))
            if resolved_payload != retained_normalized:
                raise RuntimeError("Fresh production resolver output differs semantically from retained input")
            shutil.copy2(job_dir / "blade_spec.json", output_dir / "input_blade_spec.json")
            write_json(output_dir / "resolved_blade_spec.json", resolved_payload)
            write_json(
                output_dir / "resolved_identity.json",
                {
                    "fresh_semantic_sha256": canonical_sha256(resolved_payload),
                    "retained_normalized_semantic_sha256": canonical_sha256(retained_normalized),
                    "retained_raw_representation_sha256": canonical_sha256(retained_raw_resolved),
                    "semantic_equal": True,
                    "raw_representation_equal": resolved_payload == retained_raw_resolved,
                },
            )

        originals = {
            "_set": adapter._set,
            "_configure_geometry": adapter._configure_geometry,
            "_configure_step_export": adapter._configure_step_export,
            "_drain_errors": adapter._drain_errors,
        }

        def set_wrapper(
            vsp: Any, container: str, name: str, group: str, value: float
        ) -> None:
            parm_id = adapter._parm(vsp, container, name, group)
            before = float(vsp.GetParmVal(parm_id))
            target = group == "EndCap" and name == "CapUMinOption"
            applied = float(value)
            setter_return = None
            if target:
                production_expected = int(vsp.FLAT_END_CAP)
                if round(float(value)) != production_expected:
                    raise RuntimeError(
                        f"Production adapter no longer requests FLAT_END_CAP: {value}"
                    )
                if not hasattr(vsp, cap_enum_name):
                    raise RuntimeError(f"OpenVSP enum unavailable: {cap_enum_name}")
                applied = float(int(getattr(vsp, cap_enum_name)))
                setter_return = float(vsp.SetParmVal(parm_id, applied))
            else:
                originals["_set"](vsp, container, name, group, applied)
            after = float(vsp.GetParmVal(parm_id))
            call = {
                "sequence": len(context["set_calls"]) + 1,
                "phase": context["phase"],
                "group": group,
                "name": name,
                "production_intended_value": float(value),
                "applied_value": applied,
                "before_value": before,
                "setter_return_value": setter_return,
                "accepted_immediate_value": after,
                "target_intervention": target,
            }
            context["set_calls"].append(call)
            if target:
                context["target_calls"].append(call)

        def geometry_wrapper(vsp: Any, prop_id: str, resolved_input: Any) -> None:
            context["phase"] = "geometry"
            originals["_configure_geometry"](vsp, prop_id, resolved_input)
            context["vsp"] = vsp
            context["prop_id"] = prop_id
            context["after_geometry_update"] = _configuration_snapshot(vsp, prop_id)
            context["phase"] = "post_geometry"

        def step_wrapper(vsp: Any) -> None:
            context["phase"] = "step_export"
            originals["_configure_step_export"](vsp)
            context["accepted_step_settings"] = _step_settings_snapshot(vsp)
            context["phase"] = "post_step_settings"

        def drain_wrapper(vsp: Any) -> list[str]:
            messages = originals["_drain_errors"](vsp)
            context["drain_calls"].append(
                {
                    "sequence": len(context["drain_calls"]) + 1,
                    "phase": context["phase"],
                    "messages": list(messages),
                }
            )
            return messages

        adapter._set = set_wrapper
        adapter._configure_geometry = geometry_wrapper
        adapter._configure_step_export = step_wrapper
        adapter._drain_errors = drain_wrapper
        with logger.operation("production_build_and_raw_export", cap_enum_name=cap_enum_name):
            adapter_result = adapter.build_and_export(resolved, output_dir)
        if len(context["target_calls"]) != 1:
            raise RuntimeError(
                f"Expected exactly one root-cap setter interception; got {len(context['target_calls'])}"
            )
        vsp = context["vsp"]
        prop_id = context["prop_id"]
        context["after_export"] = _configuration_snapshot(vsp, prop_id)
        context["phase"] = "post_export_snapshot"
        adapter._drain_errors(vsp)
        requested_enum = int(getattr(vsp, cap_enum_name))
        parameter_acceptance = _evaluate_arm_parameter_acceptance(
            context,
            requested_enum,
            float(spec.root_radius_ratio),
        )
        readback_validation = validate_openvsp_readback(resolved, adapter_result.readback)
        if not readback_validation["passed"]:
            raise RuntimeError(f"Production OpenVSP readback failed: {readback_validation}")
        write_json(output_dir / "adapter_readback.json", adapter_result.readback)
        write_json(output_dir / "adapter_readback_validation.json", readback_validation)
        write_json(
            output_dir / "parameter_readback.json",
            {
                "arm_label": arm_label,
                "cap_enum_name": cap_enum_name,
                "set_calls": context["set_calls"],
                "target_calls": context["target_calls"],
                "api_error_drains": context["drain_calls"],
                "after_geometry_update": context["after_geometry_update"],
                "accepted_step_settings": context["accepted_step_settings"],
                "after_export": context["after_export"],
            },
        )

        write_json(output_dir / "parameter_acceptance.json", parameter_acceptance)

        measurement = _measure_step(
            adapter_result.step_path,
            spec,
            output_dir / "primary_measurements",
            PRIMARY_STATIONS,
            logger,
            retained_raw_path=retained_raw_path,
            density_convergence=True,
        )
        cap_after = context["after_export"]["cap_parameters"]["CapUMinOption"]["value"]
        result = {
            "status": "COMPLETED",
            "arm_label": arm_label,
            "cap_enum_name": cap_enum_name,
            "cap_enum_value": requested_enum,
            "intervention_accepted": (
                abs(cap_after - requested_enum) <= 1.0e-12
                and abs(
                    context["target_calls"][0]["accepted_immediate_value"]
                    - requested_enum
                )
                <= 1.0e-12
            ),
            "parameter_acceptance_passed": parameter_acceptance["passed"],
            "parameter_acceptance": parameter_acceptance,
            "input_blade_spec": file_identity(output_dir / "input_blade_spec.json"),
            "resolved_blade_spec": file_identity(
                output_dir / "resolved_blade_spec.json"
            ),
            "target_setter_call_count": len(context["target_calls"]),
            "fresh_process": True,
            "production_build_entrypoint": "bladegen.adapters.openvsp_adapter.build_and_export",
            "production_readback_passed": True,
            "raw_step": file_identity(adapter_result.step_path),
            "vsp3": file_identity(adapter_result.vsp3_path),
            "measurement": measurement,
            "elapsed_seconds": (time.monotonic_ns() - started_ns) / 1e9,
            "completed_at_utc": utc_now(),
        }
        write_json(output_dir / "arm_result.json", result)
        logger.emit("arm_complete", status="COMPLETED", elapsed_seconds=result["elapsed_seconds"])
        return 0
    except Exception as exc:  # noqa: BLE001 - worker boundary must persist diagnostics
        result = {
            "status": "INCOMPLETE",
            "arm_label": arm_label,
            "cap_enum_name": cap_enum_name,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
            "elapsed_seconds": (time.monotonic_ns() - started_ns) / 1e9,
            "partial_files": [
                str(path.relative_to(output_dir))
                for path in sorted(output_dir.rglob("*"))
                if path.is_file()
            ],
        }
        write_json(output_dir / "arm_result.json", result)
        logger.emit("arm_complete", status="INCOMPLETE", error=result["error"])
        return 1
    finally:
        for name, original in originals.items():
            setattr(adapter, name, original)
        logger.close()


def load_components_csv(path: Path) -> list[dict[str, Any]]:
    grouped: dict[str, list[tuple[int, float, float]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            grouped[row["component"]].append(
                (int(row["point_index"]), float(row["x_mm"]), float(row["z_mm"]))
            )
    return [
        {
            "name": name,
            "points": np.asarray(
                [(x, z) for _index, x, z in sorted(rows)], dtype=float
            ),
        }
        for name, rows in grouped.items()
    ]

def _station_map(arm_result: dict[str, Any]) -> dict[float, dict[str, Any]]:
    measurement = arm_result.get("measurement", arm_result)
    return {
        round(float(row["sampled_r_over_R"]), 12): row
        for row in measurement["stations"]
    }


def evaluate_baseline(
    arm_result: dict[str, Any], prior_isolation: Path
) -> dict[str, Any]:
    prior_rows = read_json(prior_isolation / "production_baseline_measurements.json")
    prior = {
        round(float(row["sampled_r_over_R"]), 12): row for row in prior_rows
    }
    rows = []
    all_passed = True
    for station, targets in RECORDED_PRODUCTION.items():
        row = _station_map(arm_result)[round(station, 12)]
        production = row["production"]
        production_deltas = {
            "rms_mm": float(production["contour_rms_mm"] - targets[0]),
            "p95_mm": float(production["contour_p95_mm"] - targets[1]),
            "sampled_max_mm": float(production["contour_max_mm"] - targets[2]),
        }
        retained = row["arm_vs_retained_raw_4x"]
        retained_max = (
            math.inf if retained is None else float(retained["sampled_max_mm"])
        )
        prior_row = prior[round(station, 12)]
        additional = {
            key: float(production[key] - prior_row[key])
            for key in (
                "actual_chord_mm",
                "actual_twist_deg",
                "reference_axis_position_error_mm",
                "measured_te_mm",
            )
        }
        passed = (
            retained_max <= 0.0001
            and all(abs(value) <= 0.0001 for value in production_deltas.values())
        )
        all_passed = all_passed and passed
        rows.append(
            {
                "sampled_r_over_R": station,
                "A_vs_retained_raw_4x_sampled_max_mm": retained_max,
                "production_deltas": production_deltas,
                "additional_chord_twist_axis_te_deltas": additional,
                "passed": passed,
            }
        )
    return {
        "criterion_declared_before_A": True,
        "threshold_mm": 0.0001,
        "station_results": rows,
        "passed": all_passed,
        "outcome_if_failed": "BASELINE_NOT_REPRODUCED",
    }


def _semantic_parameter_map(snapshot: dict[str, Any]) -> dict[str, float]:
    return {
        f"{item['group']}.{item['name']}": float(item["value"])
        for item in snapshot["all_prop_parameters"]
    }


def _value_differences(left: dict[str, Any], right: dict[str, Any]) -> list[dict[str, Any]]:
    left_flat = _semantic_parameter_map(left)
    right_flat = _semantic_parameter_map(right)
    keys = sorted(set(left_flat) | set(right_flat))
    return [
        {
            "semantic_parameter": key,
            "A_value": left_flat.get(key),
            "B_value": right_flat.get(key),
            "delta": (
                None
                if key not in left_flat or key not in right_flat
                else right_flat[key] - left_flat[key]
            ),
        }
        for key in keys
        if left_flat.get(key) != right_flat.get(key)
    ]


def compare_readbacks(a_dir: Path, b_dir: Path) -> dict[str, Any]:
    a = read_json(a_dir / "parameter_readback.json")
    b = read_json(b_dir / "parameter_readback.json")
    a_adapter = read_json(a_dir / "adapter_readback.json")
    b_adapter = read_json(b_dir / "adapter_readback.json")
    a_resolved = read_json(a_dir / "resolved_identity.json")
    b_resolved = read_json(b_dir / "resolved_identity.json")

    authored_differences = []
    sequence_compatible = len(a["set_calls"]) == len(b["set_calls"])
    if sequence_compatible:
        for left, right in zip(a["set_calls"], b["set_calls"]):
            identity = (left["phase"], left["group"], left["name"])
            if identity != (right["phase"], right["group"], right["name"]):
                sequence_compatible = False
                authored_differences.append(
                    {"kind": "setter_sequence", "A": identity, "B": (
                        right["phase"], right["group"], right["name"]
                    )}
                )
                continue
            for field in ("production_intended_value", "applied_value"):
                if left[field] != right[field]:
                    authored_differences.append(
                        {
                            "kind": field,
                            "phase": identity[0],
                            "semantic_parameter": f"{identity[1]}.{identity[2]}",
                            "A_value": left[field],
                            "B_value": right[field],
                        }
                    )
    else:
        authored_differences.append(
            {
                "kind": "setter_count",
                "A_count": len(a["set_calls"]),
                "B_count": len(b["set_calls"]),
            }
        )

    allowed = [
        item
        for item in authored_differences
        if item.get("kind") == "applied_value"
        and item.get("semantic_parameter") == "EndCap.CapUMinOption"
    ]
    unexpected_authored = [
        item for item in authored_differences if item not in allowed
    ]
    full_parameter_differences = _value_differences(
        a["after_export"], b["after_export"]
    )
    expected_full_difference = [
        item
        for item in full_parameter_differences
        if item["semantic_parameter"] == "EndCap.CapUMinOption"
    ]
    generated_metric_comparison = [
        {
            "semantic_parameter": semantic,
            "A_generated_value": _semantic_parameter_map(a["after_export"]).get(
                semantic
            ),
            "B_generated_value": _semantic_parameter_map(b["after_export"]).get(
                semantic
            ),
            "B_minus_A": (
                _semantic_parameter_map(b["after_export"]).get(semantic)
                - _semantic_parameter_map(a["after_export"]).get(semantic)
            ),
            "changed": (
                _semantic_parameter_map(a["after_export"]).get(semantic)
                != _semantic_parameter_map(b["after_export"]).get(semantic)
            ),
            "classification": "generated_mesh_metric_warning_not_authored_confound",
        }
        for semantic in sorted(GENERATED_MESH_METRIC_SEMANTICS)
    ]
    generated_full_differences = [
        item
        for item in full_parameter_differences
        if item["semantic_parameter"] in GENERATED_MESH_METRIC_SEMANTICS
    ]
    unexpected_full = [
        item
        for item in full_parameter_differences
        if item not in expected_full_difference
        and item not in generated_full_differences
    ]

    a_errors = [message for call in a["api_error_drains"] for message in call["messages"]]
    b_errors = [message for call in b["api_error_drains"] for message in call["messages"]]
    checks = {
        "setter_sequence_same": sequence_compatible,
        "exactly_one_allowed_authored_difference": (
            len(allowed) == 1 and not unexpected_authored
        ),
        "only_expected_full_prop_parameter_difference": (
            len(expected_full_difference) == 1 and not unexpected_full
        ),
        "adapter_readback_same": a_adapter == b_adapter,
        "resolved_semantic_hash_same": (
            a_resolved["fresh_semantic_sha256"] == b_resolved["fresh_semantic_sha256"]
        ),
        "pcurves_same": (
            a["after_export"]["pcurves"] == b["after_export"]["pcurves"]
        ),
        "xsections_and_airfoils_same": (
            a["after_export"]["sections"] == b["after_export"]["sections"]
        ),
        "step_settings_same": (
            a["accepted_step_settings"] == b["accepted_step_settings"]
        ),
        "tip_cap_same": all(
            a["after_export"]["cap_parameters"][name]
            == b["after_export"]["cap_parameters"][name]
            for name in (
                "CapUMaxOption",
                "CapUMaxLength",
                "CapUMaxOffset",
                "CapUMaxStrength",
                "CapUMaxSweepFlag",
            )
        ),
        "root_dependent_values_same": all(
            a["after_export"]["cap_parameters"][name]
            == b["after_export"]["cap_parameters"][name]
            for name in (
                "CapUMinLength",
                "CapUMinOffset",
                "CapUMinStrength",
                "CapUMinSweepFlag",
                "CapUMinTess",
            )
        ),
        "no_api_errors": not a_errors and not b_errors,
    }
    decisive_failed_checks = [
        name
        for name, passed in checks.items()
        if name != "only_expected_full_prop_parameter_difference" and not passed
    ]
    confounds = list(unexpected_authored)
    confounds.extend(
        {
            "kind": "failed_readback_invariant",
            "check": name,
            "api_errors": (
                {"A": a_errors, "B": b_errors}
                if name == "no_api_errors"
                else None
            ),
        }
        for name in decisive_failed_checks
    )
    result = {
        "semantic_id_policy": "group.name and ordered setter call; transient OpenVSP IDs excluded",
        "authored_differences": authored_differences,
        "allowed_authored_difference": allowed,
        "unexpected_authored_differences": unexpected_authored,
        "all_prop_parameter_differences": full_parameter_differences,
        "unexpected_all_prop_parameter_differences": unexpected_full,
        "generated_mesh_metric_comparison": generated_metric_comparison,
        "generated_mesh_metric_differences": generated_full_differences,
        "A_api_errors": a_errors,
        "B_api_errors": b_errors,
        "confounds": confounds,
        "generated_full_parameter_difference_warning": generated_full_differences,
        "checks": checks,
        # Full PropGeom snapshots include generated/derived outcomes. Keep those
        # differences visible, but only authored/readback invariants decide whether
        # this single-input intervention is confounded.
        "unconfounded": all(
            value
            for name, value in checks.items()
            if name != "only_expected_full_prop_parameter_difference"
        ),
        "active_state_limit": (
            "OpenVSP 3.54.0 public Python API has no IsParmActive or cap-success "
            "readback; accepted enum and dependent values are authoritative readbacks"
        ),
    }
    write_json(a_dir.parent / "readback_diff.json", result)
    return result


def _diagnostic_station_role(station: float) -> str:
    if same_station(station, 0.207365125):
        return "sampled root (requested root 0.20238); previously failed"
    if same_station(station, 0.22302):
        return "worst recorded failure"
    if any(
        same_station(station, value)
        for value in (0.20949, 0.24183, 0.26472, 0.31863, 0.34811)
    ):
        return "remaining previously failed plane"
    if same_station(station, 0.29061):
        return "passing inboard control"
    if same_station(station, 0.50345):
        return "passing outboard control"
    if same_station(station, 0.80632):
        return "additional previously passing outboard station"
    if same_station(station, 0.9995014875):
        return "sampled tip (requested tip 1.0)"
    return "diagnostic station"


def compare_arm_geometry(
    a_dir: Path,
    b_dir: Path,
    output_dir: Path,
    *,
    evaluate_material_effect: bool,
    sampled_stations: tuple[float, ...] = PRIMARY_STATIONS,
    measurement_subdir: str = "primary_measurements",
    result_filename: str = "arm_result.json",
    left_label: str = "A",
    right_label: str = "B",
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    a_result_path = (
        a_dir / result_filename
        if result_filename == "arm_result.json"
        else a_dir / measurement_subdir / result_filename
    )
    b_result_path = (
        b_dir / result_filename
        if result_filename == "arm_result.json"
        else b_dir / measurement_subdir / result_filename
    )
    a_result = read_json(a_result_path)
    b_result = read_json(b_result_path)
    a_rows = _station_map(a_result)
    b_rows = _station_map(b_result)
    result_rows = []
    csv_rows = []
    any_material = False
    section_fields = (
        "actual_chord_mm",
        "actual_twist_deg",
        "reference_axis_position_error_mm",
        "measured_te_mm",
        "section_edges",
        "resulting_wires",
        "wire_valid",
        "wire_closed",
        "wire_count_pass",
        "wire_valid_pass",
        "wire_closed_pass",
    )
    numeric_section_fields = section_fields[:6]
    for station in sampled_stations:
        key = round(station, 12)
        a_row, b_row = a_rows[key], b_rows[key]
        if (
            a_row["requested_r_over_R"] != b_row["requested_r_over_R"]
            or a_row["roles"] != b_row["roles"]
            or a_row["endpoint"] != b_row["endpoint"]
        ):
            raise RuntimeError(f"Station-plan mismatch between arms at sampled r/R={station}")
        station_dir = output_dir / station_slug(station)
        station_dir.mkdir(parents=True, exist_ok=False)
        a_station_dir = a_dir / measurement_subdir / "stations" / station_slug(station)
        b_station_dir = b_dir / measurement_subdir / "stations" / station_slug(station)
        a_components = load_components_csv(a_station_dir / "actual_raw_4x.csv")
        b_components = load_components_csv(b_station_dir / "actual_raw_4x.csv")
        a_expected_path = a_station_dir / "expected_unchanged_4x.csv"
        b_expected_path = b_station_dir / "expected_unchanged_4x.csv"
        a_expected_sha = sha256_file(a_expected_path)
        b_expected_sha = sha256_file(b_expected_path)
        if a_expected_sha != b_expected_sha:
            raise RuntimeError(
                f"Expected contour differs between arms at sampled r/R={station}"
            )
        metric = isolation.compare_components(a_components, b_components)
        public = isolation.public_metric(metric)
        isolation.save_components_csv(
            station_dir / f"{left_label}_actual_raw_4x.csv", a_components
        )
        isolation.save_components_csv(
            station_dir / f"{right_label}_actual_raw_4x.csv", b_components
        )
        isolation.save_residual_csv(
            station_dir / f"{left_label}_vs_{right_label}_residuals_4x.csv",
            metric,
        )
        write_json(
            station_dir / f"{left_label}_vs_{right_label}_metric.json",
            public,
        )
        expected = load_components_csv(a_expected_path)
        _plot_overlay(
            station_dir / f"{left_label}_{right_label}_expected_true_scale.png",
            station,
            a_components,
            expected,
            second_actual=b_components,
            second_label=f"{right_label} raw STEP",
        )
        _plot_residuals(
            station_dir
            / f"{left_label}_vs_{right_label}_directional_residuals.png",
            station,
            metric,
        )

        a_prod, b_prod = a_row["production"], b_row["production"]
        a_ind, b_ind = a_row["independent_4x"], b_row["independent_4x"]
        production_deltas = {
            "rms_mm": b_prod["contour_rms_mm"] - a_prod["contour_rms_mm"],
            "p95_mm": b_prod["contour_p95_mm"] - a_prod["contour_p95_mm"],
            "sampled_max_mm": b_prod["contour_max_mm"] - a_prod["contour_max_mm"],
        }
        independent_deltas = {
            name: b_ind[name] - a_ind[name]
            for name in ("rms_mm", "p95_mm", "sampled_max_mm")
        }
        a_section = {name: a_prod.get(name) for name in section_fields}
        b_section = {name: b_prod.get(name) for name in section_fields}
        section_deltas = {
            name: b_section[name] - a_section[name]
            for name in numeric_section_fields
            if a_section[name] is not None and b_section[name] is not None
        }
        direct = public["bidirectional_equal_direction_arc_weighted"]
        largest_error_change = max(
            abs(value)
            for value in (*production_deltas.values(), *independent_deltas.values())
        )
        material = (
            evaluate_material_effect
            and direct["sampled_max_mm"] > 0.001
            and largest_error_change > 0.001
        )
        any_material = any_material or material
        row = {
            "requested_r_over_R": a_row["requested_r_over_R"],
            "sampled_r_over_R": station,
            "station_roles": a_row["roles"],
            "endpoint": a_row["endpoint"],
            "diagnostic_role": _diagnostic_station_role(station),
            "same_expected_contour": True,
            "expected_contour_sha256": a_expected_sha,
            f"{left_label}_production": {
                "rms_mm": a_prod["contour_rms_mm"],
                "p95_mm": a_prod["contour_p95_mm"],
                "sampled_max_mm": a_prod["contour_max_mm"],
            },
            f"{right_label}_production": {
                "rms_mm": b_prod["contour_rms_mm"],
                "p95_mm": b_prod["contour_p95_mm"],
                "sampled_max_mm": b_prod["contour_max_mm"],
            },
            f"production_{right_label}_minus_{left_label}": production_deltas,
            f"{left_label}_independent_4x": a_ind,
            f"{right_label}_independent_4x": b_ind,
            f"independent_{right_label}_minus_{left_label}": independent_deltas,
            f"{left_label}_vs_{right_label}_direct_4x": direct,
            f"{left_label}_section_checks": a_section,
            f"{right_label}_section_checks": b_section,
            f"section_{right_label}_minus_{left_label}": section_deltas,
            "section_wire_integrity_same": all(
                a_section[name] == b_section[name] for name in section_fields[6:]
            ),
            "largest_absolute_error_metric_change_mm": largest_error_change,
            "material_effect_at_station": (
                material if evaluate_material_effect else None
            ),
            f"{left_label}_upper_deficit_band": a_row.get("upper_deficit_band"),
            f"{right_label}_upper_deficit_band": b_row.get("upper_deficit_band"),
            "directory": str(station_dir.resolve()),
        }
        write_json(station_dir / "comparison.json", row)
        result_rows.append(row)
        csv_row = {
            "requested_r_over_R": a_row["requested_r_over_R"],
            "sampled_r_over_R": station,
            "diagnostic_role": row["diagnostic_role"],
            "station_roles": json.dumps(a_row["roles"], separators=(",", ":")),
            "same_expected_contour": True,
            "expected_contour_sha256": a_expected_sha,
            f"{left_label}_production_rms_mm": a_prod["contour_rms_mm"],
            f"{right_label}_production_rms_mm": b_prod["contour_rms_mm"],
            f"production_rms_{right_label}_minus_{left_label}_mm": production_deltas["rms_mm"],
            f"{left_label}_production_p95_mm": a_prod["contour_p95_mm"],
            f"{right_label}_production_p95_mm": b_prod["contour_p95_mm"],
            f"production_p95_{right_label}_minus_{left_label}_mm": production_deltas["p95_mm"],
            f"{left_label}_production_sampled_max_mm": a_prod["contour_max_mm"],
            f"{right_label}_production_sampled_max_mm": b_prod["contour_max_mm"],
            f"production_sampled_max_{right_label}_minus_{left_label}_mm": production_deltas["sampled_max_mm"],
            f"{left_label}_independent_rms_mm": a_ind["rms_mm"],
            f"{right_label}_independent_rms_mm": b_ind["rms_mm"],
            f"{left_label}_independent_p95_mm": a_ind["p95_mm"],
            f"{right_label}_independent_p95_mm": b_ind["p95_mm"],
            f"{left_label}_independent_sampled_max_mm": a_ind["sampled_max_mm"],
            f"{right_label}_independent_sampled_max_mm": b_ind["sampled_max_mm"],
            f"{left_label}_vs_{right_label}_direct_4x_rms_mm": direct["rms_mm"],
            f"{left_label}_vs_{right_label}_direct_4x_p95_mm": direct["p95_mm"],
            f"{left_label}_vs_{right_label}_direct_4x_sampled_max_mm": direct["sampled_max_mm"],
            "material_effect_at_station": row["material_effect_at_station"],
            "section_wire_integrity_same": row["section_wire_integrity_same"],
        }
        for name in section_fields:
            csv_row[f"{left_label}_{name}"] = a_section[name]
            csv_row[f"{right_label}_{name}"] = b_section[name]
        for name, value in section_deltas.items():
            csv_row[f"{name}_{right_label}_minus_{left_label}"] = value
        csv_rows.append(csv_row)
    result = {
        "left_arm": left_label,
        "right_arm": right_label,
        "metric": "independent component-preserving bidirectional point-to-segment, 4x",
        "sampled_max_is_continuous_hausdorff": False,
        "same_expected_contour_required": True,
        "material_effect_threshold_mm": 0.001 if evaluate_material_effect else None,
        "material_effect_observed": any_material if evaluate_material_effect else None,
        "stations": result_rows,
    }
    write_json(output_dir / "comparison_summary.json", result)
    write_csv(output_dir / "station_comparison.csv", csv_rows)
    return result


def evaluate_a2_repeat(comparison: dict[str, Any]) -> dict[str, Any]:
    rows = []
    passed = True
    for row in comparison["stations"]:
        metric_deltas = list(row["production_A2_minus_A"].values())
        station_passed = (
            row["A_vs_A2_direct_4x"]["sampled_max_mm"] <= 0.0001
            and all(abs(value) <= 0.0001 for value in metric_deltas)
        )
        passed = passed and station_passed
        rows.append(
            {
                "sampled_r_over_R": row["sampled_r_over_R"],
                "A": {
                    "production": row["A_production"],
                    "independent_4x": row["A_independent_4x"],
                    "section_checks": row["A_section_checks"],
                },
                "A2": {
                    "production": row["A2_production"],
                    "independent_4x": row["A2_independent_4x"],
                    "section_checks": row["A2_section_checks"],
                },
                "A2_vs_A_direct_4x": row["A_vs_A2_direct_4x"],
                "production_metric_deltas": row["production_A2_minus_A"],
                "section_metric_deltas": row["section_A2_minus_A"],
                "passed": station_passed,
            }
        )
    return {
        "threshold_mm": 0.0001,
        "station_results": rows,
        "passed": passed,
    }



def run_measure_mode(
    output_dir: Path,
    job_dir: Path,
    step_path: Path,
    sampled_stations: tuple[float, ...],
) -> int:
    from bladegen.models import BladeSpec

    logger = EventLog(output_dir / "analysis_events.jsonl", prefix="ROOT_CAP_AB_ANALYSIS")
    try:
        spec = BladeSpec.from_json(job_dir / "blade_spec.json")
        result = _measure_step(
            step_path,
            spec,
            output_dir,
            sampled_stations,
            logger,
            density_convergence=False,
        )
        write_json(output_dir / "analysis_result.json", {"status": "COMPLETED", **result})
        return 0
    except Exception as exc:  # noqa: BLE001 - worker boundary must persist diagnostics
        write_json(
            output_dir / "analysis_result.json",
            {
                "status": "INCOMPLETE",
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            },
        )
        return 1
    finally:
        logger.close()


def _ancestor_pids(pid: int) -> set[int]:
    ancestors = {pid}
    current = pid
    while current > 1:
        try:
            fields = Path(f"/proc/{current}/stat").read_text(encoding="utf-8").split()
            parent = int(fields[3])
        except (FileNotFoundError, IndexError, ValueError):
            break
        if parent <= 1 or parent in ancestors:
            break
        ancestors.add(parent)
        current = parent
    return ancestors


def _active_cad_workers() -> list[str]:
    excluded = _ancestor_pids(os.getpid())
    result = subprocess.run(
        ["ps", "-eo", "pid=,comm=,args="],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    matches = []
    for line in result.stdout.splitlines():
        parts = line.strip().split(maxsplit=2)
        if len(parts) < 3:
            continue
        pid_text, comm, command = parts
        try:
            pid = int(pid_text)
            argv = shlex.split(command)
        except (ValueError, IndexError):
            continue
        if pid in excluded:
            continue
        module_cli = any(
            argv[index : index + 2] == ["-m", "bladegen.cli"]
            for index in range(max(0, len(argv) - 1))
        )
        script_cli = any(
            token.replace("\\", "/").endswith("/bladegen/cli.py")
            for token in argv
        )
        real_vsp = comm in {"vsp", "vsp.exe"} or any(
            Path(token).name in {"vsp", "vsp.exe"}
            and "OpenVSP" in token
            for token in argv
        )
        if module_cli or script_cli or real_vsp:
            matches.append(line.strip())
    return matches



def _ensure_openvsp_environment() -> None:
    if not os.environ.get("OPENVSP_ROOT"):
        candidate = REPOSITORY_ROOT / ".tooling" / "openvsp-3.54.0" / "opt" / "OpenVSP"
        if not (candidate / "python" / "openvsp_config").is_dir():
            raise RuntimeError("OPENVSP_ROOT is unset and the repository OpenVSP runtime is absent")
        os.environ["OPENVSP_ROOT"] = str(candidate)
    library = REPOSITORY_ROOT / ".tooling" / "openvsp-3.54.0" / "usr" / "lib" / "x86_64-linux-gnu"
    if library.is_dir():
        current = os.environ.get("LD_LIBRARY_PATH", "")
        entries = current.split(":") if current else []
        if str(library) not in entries:
            os.environ["LD_LIBRARY_PATH"] = str(library) + (f":{current}" if current else "")


def _launch_arm(
    root: Path,
    name: str,
    enum_name: str,
    job_dir: Path,
    timeout_seconds: int,
    *,
    retained_raw_path: Path | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    workers = _active_cad_workers()
    if workers:
        raise RuntimeError(f"Concurrent CAD worker detected before {name}: {workers}")
    arm_dir = root / name
    arm_dir.mkdir(parents=True, exist_ok=False)
    argv = [
        sys.executable,
        "-u",
        str(Path(__file__).resolve()),
        "arm",
        "--output-dir",
        str(arm_dir.resolve()),
        "--job-dir",
        str(job_dir.resolve()),
        "--cap-enum-name",
        enum_name,
        "--arm-label",
        name,
    ]
    if retained_raw_path is not None:
        argv.extend(["--retained-raw-path", str(retained_raw_path.resolve())])
    launcher = run_bounded(argv, arm_dir / "arm.log", timeout_seconds)
    write_json(arm_dir / "launcher_result.json", launcher)
    result_path = arm_dir / "arm_result.json"
    result = (
        read_json(result_path)
        if result_path.is_file()
        else {
            "status": "INCOMPLETE",
            "error": "arm_result.json absent",
            "launcher": launcher,
        }
    )
    return launcher, result


def _launch_expanded_analysis(
    root: Path,
    arm_name: str,
    job_dir: Path,
    timeout_seconds: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    arm_dir = root / arm_name
    output_dir = arm_dir / "expanded_measurements"
    output_dir.mkdir(parents=True, exist_ok=False)
    argv = [
        sys.executable,
        "-u",
        str(Path(__file__).resolve()),
        "measure",
        "--output-dir",
        str(output_dir.resolve()),
        "--job-dir",
        str(job_dir.resolve()),
        "--step-path",
        str((arm_dir / "blade_openvsp.step").resolve()),
        "--stations",
        "expanded",
    ]
    launcher = run_bounded(argv, output_dir / "analysis.log", timeout_seconds)
    write_json(output_dir / "launcher_result.json", launcher)
    result_path = output_dir / "analysis_result.json"
    result = read_json(result_path) if result_path.is_file() else {
        "status": "INCOMPLETE",
        "launcher": launcher,
    }
    return launcher, result

def _artifact_hashes(snapshot: dict[str, Any]) -> dict[str, str]:
    return {name: record["sha256"] for name, record in snapshot.items()}


def _report_station_rows(comparison: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not comparison:
        return []
    rows = []
    for row in comparison["stations"]:
        rows.append(
            {
                "requested_r_over_R": row["requested_r_over_R"],
                "sampled_r_over_R": row["sampled_r_over_R"],
                "role": row["diagnostic_role"],
                "station_roles": row["station_roles"],
                "same_expected_contour": row["same_expected_contour"],
                "A": {
                    "production": row["A_production"],
                    "independent": row["A_independent_4x"],
                    "section_checks": row["A_section_checks"],
                },
                "B": {
                    "production": row["B_production"],
                    "independent": row["B_independent_4x"],
                    "section_checks": row["B_section_checks"],
                },
                "direct_a_vs_b_4x": row["A_vs_B_direct_4x"],
                "section_B_minus_A": row["section_B_minus_A"],
                "section_wire_integrity_same": row[
                    "section_wire_integrity_same"
                ],
                "result": (
                    "MATERIAL_EFFECT"
                    if row["material_effect_at_station"]
                    else "NO_MATERIAL_EFFECT"
                ),
            }
        )
    return rows



def run_supervisor(
    output_root: Path,
    job_dir: Path,
    prior_isolation: Path,
    timeout_seconds_per_arm: int,
) -> int:
    import x57_root_cap_ab_reporting as reporting

    _ensure_openvsp_environment()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = output_root / f"a93b281c_{stamp}"
    if output_dir.exists():
        output_dir = output_root / f"a93b281c_{stamp}_{os.getpid()}"
    output_dir.mkdir(parents=True, exist_ok=False)
    lock_path = Path("/tmp/bladegen_x57_root_cap_ab.lock")
    lock_stream = lock_path.open("w", encoding="utf-8")
    try:
        fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise RuntimeError("Another X-57 root-cap diagnostic holds the process lock") from exc

    supervisor_events = EventLog(output_dir / "supervisor_events.jsonl")
    commands: list[str] = [
        shlex.join([sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]])
    ]
    initial_harness_sources = harness_source_snapshot()
    arm_launchers: dict[str, Any] = {}
    arms: dict[str, Any] = {}
    baseline: dict[str, Any] | None = None
    readback_diff: dict[str, Any] | None = None
    comparison: dict[str, Any] | None = None
    a2_repeat: dict[str, Any] | None = None
    expanded_comparison: dict[str, Any] | None = None
    expanded: dict[str, Any] = {}
    outcome = "INCOMPLETE"
    failure: str | None = None
    plan: dict[str, Any] | None = None
    preflight: dict[str, Any] | None = None
    initial_sources: dict[str, str] | None = None
    initial_fixtures: dict[str, Any] | None = None
    initial_artifacts: dict[str, Any] | None = None
    probe: dict[str, Any] | None = None

    try:
        require_harness_identity(initial_harness_sources, "OpenVSP probe")
        probe_launcher = run_bounded(
            [
                sys.executable,
                "-u",
                str(Path(__file__).resolve()),
                "probe",
                "--output",
                str((output_dir / "openvsp_probe.json").resolve()),
            ],
            output_dir / "openvsp_probe.log",
            60,
        )
        commands.append(probe_launcher["command"])
        write_json(output_dir / "openvsp_probe_launcher.json", probe_launcher)
        if probe_launcher["returncode"] != 0:
            raise RuntimeError(f"OpenVSP enum/version probe failed: {probe_launcher}")
        probe = read_json(output_dir / "openvsp_probe.json")
        write_json(output_dir / "environment_identity.json", environment_identity(probe))

        with supervisor_events.operation("preflight_identity"):
            preflight = collect_preflight(job_dir, prior_isolation, probe)
        write_json(output_dir / "preflight_evidence.json", preflight)
        initial_sources = source_snapshot()
        initial_artifacts = artifact_snapshot(job_dir)
        initial_fixtures = fixture_checksum_snapshot()
        write_json(
            output_dir / "harness_source_identity.json",
            {"before_A": initial_harness_sources},
        )

        plan = build_experiment_plan(
            output_dir, preflight, probe, timeout_seconds_per_arm
        )
        if not preflight["passed"]:
            raise RuntimeError(
                f"Preflight identity failed before A: "
                f"{[key for key, value in preflight['checks'].items() if not value]}"
            )

        retained_raw_path = job_dir / "blade_openvsp.step"
        require_harness_identity(initial_harness_sources, "A_original launch")
        with supervisor_events.operation("launch_A_original"):
            launcher, a_result = _launch_arm(
                output_dir,
                "A_original",
                "FLAT_END_CAP",
                job_dir,
                timeout_seconds_per_arm,
                retained_raw_path=retained_raw_path,
            )
        arm_launchers["A_original"] = launcher
        arms["A_original"] = a_result
        commands.append(launcher["command"])
        if launcher["returncode"] != 0 or a_result.get("status") != "COMPLETED":
            raise RuntimeError(f"A_original did not complete: {a_result}")
        if not (
            a_result.get("intervention_accepted")
            and a_result.get("parameter_acceptance_passed")
        ):
            outcome = "CONFOUNDED_OR_INEFFECTIVE_INTERVENTION"
            raise RuntimeError("A_original cap or authored-parameter readback was not accepted")

        baseline = evaluate_baseline(a_result, prior_isolation)
        baseline["status"] = "PASS" if baseline["passed"] else "FAIL"
        baseline["detail"] = (
            "All three stations met both predeclared 0.0001 mm criteria."
            if baseline["passed"]
            else "At least one station missed a predeclared 0.0001 mm criterion."
        )
        write_json(output_dir / "baseline_reproduction.json", baseline)
        if not baseline["passed"]:
            outcome = "BASELINE_NOT_REPRODUCED"
        else:
            require_harness_identity(
                initial_harness_sources,
                "B_root_cap_intervention launch",
            )
            with supervisor_events.operation("launch_B_root_cap_intervention"):
                launcher, b_result = _launch_arm(
                    output_dir,
                    "B_root_cap_intervention",
                    "NO_END_CAP",
                    job_dir,
                    timeout_seconds_per_arm,
                    retained_raw_path=None,
                )
            arm_launchers["B_root_cap_intervention"] = launcher
            arms["B_root_cap_intervention"] = b_result
            commands.append(launcher["command"])
            if launcher["returncode"] != 0 or b_result.get("status") != "COMPLETED":
                raise RuntimeError(
                    f"B_root_cap_intervention did not complete: {b_result}"
                )

            readback_diff = compare_readbacks(
                output_dir / "A_original",
                output_dir / "B_root_cap_intervention",
            )
            b_accepted = bool(
                b_result.get("intervention_accepted")
                and b_result.get("parameter_acceptance_passed")
            )
            if not b_accepted:
                readback_diff["confounds"].append(
                    {
                        "kind": "B_arm_acceptance_failed",
                        "parameter_acceptance": b_result.get(
                            "parameter_acceptance"
                        ),
                    }
                )
            readback_diff["status"] = (
                "ACCEPTED_UNCONFOUNDED"
                if readback_diff["unconfounded"] and b_accepted
                else "CONFOUNDED_OR_INEFFECTIVE"
            )
            write_json(output_dir / "readback_diff.json", readback_diff)

            comparison = compare_arm_geometry(
                output_dir / "A_original",
                output_dir / "B_root_cap_intervention",
                output_dir / "comparisons" / "A_vs_B",
                evaluate_material_effect=True,
            )
            shutil.copy2(
                output_dir
                / "comparisons"
                / "A_vs_B"
                / "station_comparison.csv",
                output_dir / "station_comparison.csv",
            )

            accepted = readback_diff["unconfounded"] and b_accepted
            if not accepted:
                outcome = "CONFOUNDED_OR_INEFFECTIVE_INTERVENTION"
            elif not comparison["material_effect_observed"]:
                outcome = "NO_MATERIAL_EFFECT_FOR_TESTED_INTERVENTION"
            else:
                require_harness_identity(
                    initial_harness_sources,
                    "A2_original_repeat launch",
                )
                with supervisor_events.operation("launch_A2_original_repeat"):
                    launcher, a2_result = _launch_arm(
                        output_dir,
                        "A2_original_repeat",
                        "FLAT_END_CAP",
                        job_dir,
                        timeout_seconds_per_arm,
                        retained_raw_path=retained_raw_path,
                    )
                arm_launchers["A2_original_repeat"] = launcher
                arms["A2_original_repeat"] = a2_result
                commands.append(launcher["command"])
                if launcher["returncode"] != 0 or a2_result.get("status") != "COMPLETED":
                    raise RuntimeError(f"A2_original_repeat did not complete: {a2_result}")
                if not (
                    a2_result.get("intervention_accepted")
                    and a2_result.get("parameter_acceptance_passed")
                ):
                    outcome = "CONFOUNDED_OR_INEFFECTIVE_INTERVENTION"
                    raise RuntimeError(
                        "A2_original_repeat cap or authored-parameter readback was not accepted"
                    )
                a_a2_comparison = compare_arm_geometry(
                    output_dir / "A_original",
                    output_dir / "A2_original_repeat",
                    output_dir / "comparisons" / "A_vs_A2",
                    evaluate_material_effect=False,
                    left_label="A",
                    right_label="A2",
                )
                shutil.copy2(
                    output_dir
                    / "comparisons"
                    / "A_vs_A2"
                    / "station_comparison.csv",
                    output_dir / "A2_station_comparison.csv",
                )
                a2_repeat = evaluate_a2_repeat(a_a2_comparison)
                write_json(output_dir / "A2_reproduction.json", a2_repeat)
                if not a2_repeat["passed"]:
                    outcome = "CONFOUNDED_OR_INEFFECTIVE_INTERVENTION"
                else:
                    require_harness_identity(
                        initial_harness_sources,
                        "expanded A analysis launch",
                    )
                    with supervisor_events.operation("expanded_existing_A_analysis"):
                        launcher, expanded["A_original"] = _launch_expanded_analysis(
                            output_dir,
                            "A_original",
                            job_dir,
                            timeout_seconds_per_arm,
                        )
                    arm_launchers["A_original_expanded_analysis"] = launcher
                    commands.append(launcher["command"])

                    require_harness_identity(
                        initial_harness_sources,
                        "expanded B analysis launch",
                    )
                    with supervisor_events.operation("expanded_existing_B_analysis"):
                        (
                            launcher,
                            expanded["B_root_cap_intervention"],
                        ) = _launch_expanded_analysis(
                            output_dir,
                            "B_root_cap_intervention",
                            job_dir,
                            timeout_seconds_per_arm,
                        )
                    arm_launchers[
                        "B_root_cap_intervention_expanded_analysis"
                    ] = launcher
                    commands.append(launcher["command"])
                    if all(
                        result.get("status") == "COMPLETED"
                        for result in expanded.values()
                    ):
                        expanded_comparison = compare_arm_geometry(
                            output_dir / "A_original",
                            output_dir / "B_root_cap_intervention",
                            output_dir / "comparisons" / "expanded_A_vs_B",
                            evaluate_material_effect=True,
                            sampled_stations=EXPANDED_SAMPLED_STATIONS,
                            measurement_subdir="expanded_measurements",
                            result_filename="analysis_result.json",
                        )
                        shutil.copy2(
                            output_dir
                            / "comparisons"
                            / "expanded_A_vs_B"
                            / "station_comparison.csv",
                            output_dir / "expanded_station_comparison.csv",
                        )
                        outcome = "ROOT_CAP_EFFECT_REPRODUCED"
                    else:
                        raise RuntimeError(
                            f"Conditional expanded existing-file analysis incomplete: {expanded}"
                        )
        if outcome == "INCOMPLETE":
            raise RuntimeError("Supervisor reached no supported diagnostic outcome")
    except Exception as exc:  # noqa: BLE001 - supervisor must finalize partial evidence
        if outcome not in {
            "BASELINE_NOT_REPRODUCED",
            "CONFOUNDED_OR_INEFFECTIVE_INTERVENTION",
            "NO_MATERIAL_EFFECT_FOR_TESTED_INTERVENTION",
            "ROOT_CAP_EFFECT_REPRODUCED",
        }:
            outcome = "INCOMPLETE"
        failure = f"{type(exc).__name__}: {exc}"
        write_json(
            output_dir / "supervisor_failure.json",
            {"error": failure, "traceback": traceback.format_exc()},
        )
    finally:
        post_sources = source_snapshot()
        post_artifacts = artifact_snapshot(job_dir)
        post_fixtures = fixture_checksum_snapshot()
        post_harness_sources = harness_source_snapshot()
        git_after = subprocess.run(
            ["git", "status", "--short"],
            cwd=REPOSITORY_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout
        production_unchanged = (
            initial_sources is not None and initial_sources == post_sources
        )
        artifacts_unchanged = (
            initial_artifacts is not None
            and _artifact_hashes(initial_artifacts)
            == _artifact_hashes(post_artifacts)
        )
        fixtures_unchanged = initial_fixtures is not None and (
            fixture_stable_identity(initial_fixtures)
            == fixture_stable_identity(post_fixtures)
        )
        harness_unchanged = initial_harness_sources == post_harness_sources
        runtime_file_recheck = recheck_openvsp_runtime_files(probe)
        integrity = {
            "production_sources_unchanged": production_unchanged,
            "harness_sources_unchanged": harness_unchanged,
            "original_artifacts_unchanged": artifacts_unchanged,
            "fixtures_unchanged": fixtures_unchanged,
            "all_fixture_sha256_verified_after": post_fixtures["all_verified"],
            "openvsp_runtime_files_unchanged": runtime_file_recheck["unchanged"],
            "openvsp_runtime_file_recheck": runtime_file_recheck,
            "source_hashes_after": post_sources,
            "harness_source_hashes_before": initial_harness_sources,
            "harness_source_hashes_after": post_harness_sources,
            "fixture_verification_after": post_fixtures,
            "original_artifact_hashes_after": _artifact_hashes(post_artifacts),
            "git_status_after": git_after,
            "production_files_edited_by_harness": not production_unchanged,
            "retained_vsp3_loaded": False,
            "ocp_solidification_performed": False,
        }
        integrity["passed"] = all(
            (
                production_unchanged,
                harness_unchanged,
                artifacts_unchanged,
                fixtures_unchanged,
                post_fixtures["all_verified"],
                runtime_file_recheck["unchanged"],
            )
        )
        if not integrity["passed"]:
            prior_outcome = outcome
            outcome = "INCOMPLETE"
            integrity_failure = (
                "IntegrityError: final source/artifact/fixture/harness/runtime identity "
                f"failed; provisional outcome was {prior_outcome}"
            )
            failure = f"{failure}; {integrity_failure}" if failure else integrity_failure
            write_json(
                output_dir / "supervisor_failure.json",
                {"error": failure, "integrity": integrity},
            )
        write_json(
            output_dir / "harness_source_identity.json",
            {
                "before_A": initial_harness_sources,
                "after_all_launches": post_harness_sources,
                "unchanged": harness_unchanged,
            },
        )
        write_json(output_dir / "integrity_recheck.json", integrity)
        supervisor_events.emit(
            "supervisor_complete", diagnostic_outcome=outcome, failure=failure
        )
        supervisor_events.close()
        if readback_diff is None:
            readback_diff = {
                "status": "NOT_RUN",
                "unconfounded": None,
                "confounds": failure or "B was not reached",
            }
            write_json(output_dir / "readback_diff.json", readback_diff)
        if not (output_dir / "station_comparison.csv").exists():
            baseline_rows = (
                [
                    {
                        "sampled_r_over_R": row["sampled_r_over_R"],
                        "A_vs_retained_raw_4x_sampled_max_mm": row[
                            "A_vs_retained_raw_4x_sampled_max_mm"
                        ],
                        "A_production_rms_delta_mm": row["production_deltas"][
                            "rms_mm"
                        ],
                        "A_production_p95_delta_mm": row["production_deltas"][
                            "p95_mm"
                        ],
                        "A_production_sampled_max_delta_mm": row[
                            "production_deltas"
                        ]["sampled_max_mm"],
                        "status": "BASELINE_ONLY",
                        "passed": row["passed"],
                    }
                    for row in baseline["station_results"]
                ]
                if baseline is not None
                else []
            )
            write_csv(
                output_dir / "station_comparison.csv",
                baseline_rows,
                fieldnames=(
                    None
                    if baseline_rows
                    else [
                        "sampled_r_over_R",
                        "A_vs_retained_raw_4x_sampled_max_mm",
                        "A_production_rms_delta_mm",
                        "A_production_p95_delta_mm",
                        "A_production_sampled_max_delta_mm",
                        "status",
                        "passed",
                    ]
                ),
            )

        topologies = {
            name: result["measurement"]["topology"]
            for name, result in arms.items()
            if result.get("status") == "COMPLETED" and "measurement" in result
        }
        next_action = {
            "ROOT_CAP_EFFECT_REPRODUCED": (
                "Review a separate implementation task that preserves the demonstrated section "
                "shape while restoring and qualifying physical root closure; do not adopt the "
                "cap-free experimental surface as a product solid."
            ),
            "NO_MATERIAL_EFFECT_FOR_TESTED_INTERVENTION": (
                "Run one bounded next experiment that captures the live pre-export OpenVSP "
                "main surface and same-plane raw STEP cuts to separate loft construction from "
                "STEP translation; keep the same BladeSpec and export settings."
            ),
            "BASELINE_NOT_REPRODUCED": (
                "Resolve the A-versus-retained repeatability discrepancy before interpreting any "
                "root-cap intervention."
            ),
            "CONFOUNDED_OR_INEFFECTIVE_INTERVENTION": (
                "Resolve the recorded intervention/readback confound before repeating this "
                "single-factor experiment."
            ),
            "INCOMPLETE": (
                "Inspect the last flushed operation and preserved partial arm outputs, then rerun "
                "the same bounded experiment without changing inputs or criteria."
            ),
        }[outcome]
        summary = {
            "experiment_id": "X57-AB-01",
            "diagnostic_outcome": outcome,
            "failure": failure,
            "last_active_operation": supervisor_events.last_operation,
            "commands": commands,
            "created_at_utc": utc_now(),
            "git": (
                preflight["git"]
                if preflight is not None
                else {"head": command_output(["git", "rev-parse", "HEAD"])}
            ),
            "experiment_plan": plan,
            "diagnostic_readback_acceptance_policy": readback_acceptance_policy(),
            "preserved_prior_instrumentation_attempt": (
                prior_instrumentation_attempt_metadata()
            ),
            "preserved_second_instrumentation_attempt": (
                second_instrumentation_attempt_metadata()
            ),
            "baseline_reproduction": baseline
            or {
                "status": "NOT_COMPLETED",
                "detail": failure or "A did not reach the baseline gate",
            },
            "intervention": plan["intervention"] if plan else {},
            "readback_diff": readback_diff,
            "station_comparison": _report_station_rows(comparison),
            "comparison": comparison,
            "A2_reproduction": a2_repeat,
            "conditional_expanded_analysis": expanded,
            "expanded_station_comparison": (
                expanded_comparison["stations"]
                if expanded_comparison is not None
                else []
            ),
            "expanded_comparison": expanded_comparison,
            "arms": {
                name: {
                    "status": result.get("status"),
                    "cap_enum_name": result.get("cap_enum_name"),
                    "intervention_accepted": result.get("intervention_accepted"),
                    "parameter_acceptance_passed": result.get(
                        "parameter_acceptance_passed"
                    ),
                    "input_blade_spec": result.get("input_blade_spec"),
                    "resolved_blade_spec": result.get("resolved_blade_spec"),
                    "raw_step": result.get("raw_step"),
                    "vsp3": result.get("vsp3"),
                    "topology": result.get("measurement", {}).get("topology"),
                }
                for name, result in arms.items()
            },
            "topology": topologies,
            "arm_launchers": arm_launchers,
            "integrity": integrity,
            "original_statuses": {
                "original_job": "FAILED",
                "retained_complete_internal_validation": "FAIL",
                "external_nasa_fidelity": "UNVERIFIED",
                "experimental_B": "diagnostic only; no automatic CAD acceptance",
            },
            "smallest_next_action": next_action,
            "experimental_scope": {
                "observed_path": "combined OpenVSP generation and raw STEP export",
                "live_pre_export_surface_capture_performed": False,
                "internal_mechanism_localized": False,
                "limitation": (
                    "optional live pre-export surface capture was not performed"
                ),
            },
            "qualification": {
                "full_41_station_validation_rerun": False,
                "production_acceptance_changed": False,
                "production_geometry_fix_implemented": False,
                "experimental_B_closed_solid_required": False,
                "live_pre_export_surface_capture_performed": False,
                "conclusion_scope": "combined generation/export path only",
            },
        }
        write_json(output_dir / "experiment_summary.json", summary)
        (output_dir / "commands.txt").write_text(
            "\n".join(commands) + ("\n" if commands else ""),
            encoding="utf-8",
        )
        shutil.copy2(Path(__file__).resolve(), output_dir / Path(__file__).name)
        helper_source = SCRIPT_ROOT / "x57_root_cap_ab_reporting.py"
        if helper_source.is_file():
            shutil.copy2(helper_source, output_dir / helper_source.name)
        reporting.collect_operation_timings(output_dir)
        reporting.write_report(output_dir, summary)
        write_json(
            output_dir / "bundle_intent.json",
            {
                "evidence_directory": str(output_dir.resolve()),
                "zip_path": str(output_dir.with_suffix(".zip").resolve()),
                "full_raw_steps_retained_locally": True,
                "full_raw_steps_omitted_from_zip": True,
            },
        )
        bundle = reporting.finalize_evidence_bundle(output_dir)
        write_json(output_dir.with_suffix(".bundle.json"), bundle)
        print(
            json.dumps(
                {
                    "diagnostic_outcome": outcome,
                    "evidence_directory": str(output_dir.resolve()),
                    "zip_path": bundle["zip_path"],
                    "zip_sha256": bundle["zip_sha256"],
                    "manifest_all_verified": bundle["all_sha256_verified"],
                    "failure": failure,
                },
                indent=2,
            ),
            flush=True,
        )
        fcntl.flock(lock_stream.fileno(), fcntl.LOCK_UN)
        lock_stream.close()
    return 0 if outcome in {
        "ROOT_CAP_EFFECT_REPRODUCED",
        "NO_MATERIAL_EFFECT_FOR_TESTED_INTERVENTION",
    } else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode")

    run = subparsers.add_parser("run", help="execute the bounded sequential A/B experiment")
    run.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    run.add_argument("--job-dir", type=Path, default=DEFAULT_JOB_DIR)
    run.add_argument("--prior-isolation", type=Path, default=DEFAULT_PRIOR_ISOLATION)
    run.add_argument("--timeout-seconds-per-arm", type=int, default=900)

    probe = subparsers.add_parser("probe", help=argparse.SUPPRESS)
    probe.add_argument("--output", type=Path, required=True)

    arm = subparsers.add_parser("arm", help=argparse.SUPPRESS)
    arm.add_argument("--output-dir", type=Path, required=True)
    arm.add_argument("--job-dir", type=Path, required=True)
    arm.add_argument(
        "--cap-enum-name",
        choices=("FLAT_END_CAP", "NO_END_CAP"),
        required=True,
    )
    arm.add_argument("--arm-label", required=True)
    arm.add_argument("--retained-raw-path", type=Path)

    measure = subparsers.add_parser("measure", help=argparse.SUPPRESS)
    measure.add_argument("--output-dir", type=Path, required=True)
    measure.add_argument("--job-dir", type=Path, required=True)
    measure.add_argument("--step-path", type=Path, required=True)
    measure.add_argument("--stations", choices=("primary", "expanded"), required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    mode = arguments.mode or "run"
    if mode == "probe":
        return run_probe(arguments.output.resolve())
    if mode == "arm":
        return run_arm(
            arguments.output_dir.resolve(),
            arguments.job_dir.resolve(),
            arguments.cap_enum_name,
            arguments.arm_label,
            arguments.retained_raw_path.resolve()
            if arguments.retained_raw_path
            else None,
        )
    if mode == "measure":
        stations = (
            PRIMARY_STATIONS
            if arguments.stations == "primary"
            else EXPANDED_SAMPLED_STATIONS
        )
        return run_measure_mode(
            arguments.output_dir.resolve(),
            arguments.job_dir.resolve(),
            arguments.step_path.resolve(),
            stations,
        )
    if mode == "run":
        return run_supervisor(
            arguments.output_root.resolve(),
            arguments.job_dir.resolve(),
            arguments.prior_isolation.resolve(),
            int(arguments.timeout_seconds_per_arm),
        )
    raise AssertionError(mode)


if __name__ == "__main__":
    raise SystemExit(main())
