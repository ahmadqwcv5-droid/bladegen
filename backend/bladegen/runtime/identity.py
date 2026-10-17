"""Deterministic identity of BladeGen's small production qualification core."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

IMPLEMENTATION_IDENTITY_SCHEMA = "bladegen.production-core-source-set.v1"

PRODUCTION_CORE_FILES = (
    "backend/api/services/jobs.py",
    "backend/api/services/result_verification.py",
    "backend/bladegen/adapters/openvsp_adapter.py",
    "backend/bladegen/airfoils/canonical.py",
    "backend/bladegen/airfoils/geometry_metrics.py",
    "backend/bladegen/assembly/builder.py",
    "backend/bladegen/assembly/capabilities.py",
    "backend/bladegen/assembly/hub.py",
    "backend/bladegen/assembly/transforms.py",
    "backend/bladegen/assembly/validation.py",
    "backend/bladegen/curves/canonical.py",
    "backend/bladegen/curves/resolver.py",
    "backend/bladegen/models/blade_spec.py",
    "backend/bladegen/models/propeller_spec.py",
    "backend/bladegen/models/resolved_blade_spec.py",
    "backend/bladegen/pipeline.py",
    "backend/bladegen/propeller_pipeline.py",
    "backend/bladegen/runtime/definitions.py",
    "backend/bladegen/runtime/execution.py",
    "backend/bladegen/runtime/identity.py",
    "backend/bladegen/runtime/manager.py",
    "backend/bladegen/runtime/provenance.py",
    "backend/bladegen/solid/ocp_solidify.py",
    "backend/bladegen/validation/expected_geometry.py",
    "backend/bladegen/validation/geometry_validation.py",
    "backend/bladegen/validation/measure_sections.py",
    "backend/bladegen/validation/policy.py",
    "backend/bladegen/validation/propeller_preflight.py",
    "backend/bladegen/validation/station_plan.py",
)


class ImplementationIdentityError(RuntimeError):
    """A required production source file is absent or unreadable."""


def _default_repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def implementation_source_identity(repository_root: Path | None = None) -> dict[str, Any]:
    root = (repository_root or _default_repository_root()).resolve()
    files = []
    missing = []
    for relative_path in sorted(PRODUCTION_CORE_FILES):
        path = root / relative_path
        if not path.is_file():
            missing.append(relative_path)
            continue
        files.append(
            {
                "path": relative_path,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    if missing:
        raise ImplementationIdentityError(
            "Required production source files are missing: " + ", ".join(missing)
        )
    body = {"schema": IMPLEMENTATION_IDENTITY_SCHEMA, "files": files}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return {**body, "aggregate_sha256": hashlib.sha256(encoded.encode()).hexdigest()}
