"""Per-run engine provenance for fixed-plane CAD attempts."""

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .definitions import canonical_json_sha256, definition_identity
from .execution import resolve_build_timeout_seconds
from .identity import implementation_source_identity
from .manager import CONSTRUCTION_CONTRACT, RuntimeIdentity, selected_runtime_root

ENGINE_MANIFEST_SCHEMA = "bladegen.engine-manifest.v2"
COMPLETION_CONTEXT_SCHEMA = "bladegen.completion-context.v1"
ADAPTER_REVISION = "bladegen.openvsp-adapter.fixed-plane.1"
VALIDATION_REVISION = "bladegen.final-step-validation.3"
SERIALIZATION = "RFC-8259 JSON; UTF-8; object keys sorted; separators ',' and ':'"


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def begin_engine_manifest(
    path: Path,
    *,
    submitted: dict[str, Any],
    resolved: dict[str, Any],
    identity: RuntimeIdentity | None,
    build_type: str = "blade",
    readiness_error: str | None = None,
) -> dict[str, Any]:
    try:
        requested_root, selection = selected_runtime_root()
        requested_root_value = str(requested_root)
    except Exception:
        selection = "OPENVSP_ROOT" if "OPENVSP_ROOT" in os.environ else "managed_default"
        requested_root_value = os.getenv("OPENVSP_ROOT")
    job_id = os.getenv("BLADEGEN_JOB_ID")
    external_timeout = os.getenv("BLADEGEN_EXTERNAL_TIMEOUT_SECONDS")
    worker_timeout = resolve_build_timeout_seconds() if job_id else None
    submitted_identity = definition_identity(submitted, build_type)
    payload: dict[str, Any] = {
        "schema": ENGINE_MANIFEST_SCHEMA,
        "state": "REQUESTED" if identity else "REJECTED",
        "fixed_plane_contract": CONSTRUCTION_CONTRACT,
        "requested_runtime": {
            "selection": selection,
            "root": requested_root_value,
            "expected_build_id": "openvsp-3.54.0-bladegen-fixed-plane.1",
            "expected_capability": "fixed_radial_sections_v1",
            "expected_fingerprint": os.getenv("BLADEGEN_EXPECTED_RUNTIME_FINGERPRINT"),
        },
        "actually_loaded_runtime": None,
        "runtime_readiness": identity.private_dict() if identity else None,
        "readiness_error": readiness_error,
        "construction_policy": (
            "fixed Y = R * r/R radial section; native derivative-driven m_ZRotate "
            "is calculated but identity is applied at that operation"
        ),
        "implementation": {
            "adapter_revision": ADAPTER_REVISION,
            "resolver_revision": resolved.get("resolver_version"),
            "validation_revision": VALIDATION_REVISION,
            "source_set": implementation_source_identity(),
        },
        "versions": {
            "python": platform.python_version(),
            "python_abi": f"{sys.version_info.major}.{sys.version_info.minor}",
            "openvsp": identity.openvsp_version if identity else None,
            "OCP": _package_version("cadquery-ocp") or _package_version("OCP"),
            "numpy": _package_version("numpy"),
            "scipy": _package_version("scipy"),
        },
        "definition_hashes": {
            "serialization": SERIALIZATION,
            "canonical_submitted_sha256": canonical_json_sha256(submitted),
            "canonical_resolved_sha256": canonical_json_sha256(resolved),
        },
        "definition_identity": submitted_identity,
        "execution": {
            "run_id": os.getenv("BLADEGEN_RUN_ID") or path.parent.name,
            "job_id": job_id,
            "execution_mode": "api_worker" if job_id else "direct_cli",
            "api_worker_timeout_seconds": worker_timeout,
            "external_timeout_seconds": (
                int(external_timeout) if external_timeout is not None else None
            ),
            "requested_at_utc": datetime.now(UTC).isoformat(),
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def completion_context(
    *,
    submitted: dict[str, Any],
    build_type: str,
    identity: RuntimeIdentity | dict[str, Any],
    planned_section_count: int,
    completed_section_count: int,
) -> dict[str, Any]:
    """Bind a current result to its job, definition, runtime, and full station set."""
    job_id = os.getenv("BLADEGEN_JOB_ID")
    runtime = identity.safe_dict() if isinstance(identity, RuntimeIdentity) else identity
    return {
        "schema": COMPLETION_CONTEXT_SCHEMA,
        "build_type": build_type,
        "run_id": os.getenv("BLADEGEN_RUN_ID") or None,
        "job_id": job_id,
        "definition_identity": definition_identity(submitted, build_type),
        "runtime": {
            "fingerprint": runtime["fingerprint"],
            "build_id": runtime["build_id"],
            "construction_contract": runtime["construction_contract"],
        },
        "planned_section_count": planned_section_count,
        "completed_section_count": completed_section_count,
        "worker_timeout_seconds": resolve_build_timeout_seconds() if job_id else None,
    }


def record_loaded_runtime(path: Path, identity: RuntimeIdentity) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["state"] = "ACTUALLY_LOADED"
    payload["actually_loaded_runtime"] = identity.private_dict()
    payload["versions"]["openvsp"] = identity.openvsp_version
    payload["execution"]["loaded_at_utc"] = datetime.now(UTC).isoformat()
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def record_completed_runtime(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["state"] = "COMPLETED"
    payload["execution"]["completed_at_utc"] = datetime.now(UTC).isoformat()
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
