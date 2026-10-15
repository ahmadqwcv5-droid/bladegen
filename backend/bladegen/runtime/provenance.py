"""Per-run engine provenance for fixed-plane CAD attempts."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .manager import CONSTRUCTION_CONTRACT, RuntimeIdentity, selected_runtime_root

ENGINE_MANIFEST_SCHEMA = "bladegen.engine-manifest.v1"
ADAPTER_REVISION = "bladegen.openvsp-adapter.fixed-plane.1"
VALIDATION_REVISION = "bladegen.final-step-validation.1"
SERIALIZATION = "RFC-8259 JSON; UTF-8; object keys sorted; separators ',' and ':'"


def _canonical_sha256(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def implementation_hashes() -> dict[str, str]:
    files = {
        "adapter": Path(__file__).resolve().parents[1] / "adapters" / "openvsp_adapter.py",
        "resolver": Path(__file__).resolve().parents[1] / "curves" / "resolver.py",
        "validation": (
            Path(__file__).resolve().parents[1] / "validation" / "geometry_validation.py"
        ),
    }
    return {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()}


def begin_engine_manifest(
    path: Path,
    *,
    submitted: dict[str, Any],
    resolved: dict[str, Any],
    identity: RuntimeIdentity | None,
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
            "source_sha256": implementation_hashes(),
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
            "canonical_submitted_sha256": _canonical_sha256(submitted),
            "canonical_resolved_sha256": _canonical_sha256(resolved),
        },
        "execution": {
            "run_id": os.getenv("BLADEGEN_RUN_ID") or path.parent.name,
            "job_id": job_id,
            "execution_mode": "api_worker" if job_id else "direct_cli",
            "api_worker_timeout_seconds": (
                int(os.getenv("BLADEGEN_BUILD_TIMEOUT", "300")) if job_id else None
            ),
            "external_timeout_seconds": (
                int(external_timeout) if external_timeout is not None else None
            ),
            "requested_at_utc": datetime.now(UTC).isoformat(),
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


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
