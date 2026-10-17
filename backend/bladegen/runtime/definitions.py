"""Canonical submitted-definition identities shared by queue and worker."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from bladegen.models import BladeSpec, PropellerSpec

DEFINITION_IDENTITY_SCHEMA = "bladegen.definition-identity.v1"


def canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def definition_identity(
    payload: dict[str, Any], build_type: Literal["blade", "propeller"]
) -> dict[str, Any]:
    """Validate and identify both submitted JSON semantics and normalized model."""
    if build_type == "blade":
        model = BladeSpec.model_validate(payload)
        reference_hash = None
    elif build_type == "propeller":
        model = PropellerSpec.model_validate(payload)
        reference_submitted_hash = canonical_json_sha256(payload["blade_spec"])
        reference_hash = canonical_json_sha256(model.blade_spec.model_dump(mode="json"))
    else:  # pragma: no cover - internal type boundary
        raise ValueError(f"Unsupported build type: {build_type}")
    result: dict[str, Any] = {
        "schema": DEFINITION_IDENTITY_SCHEMA,
        "build_type": build_type,
        "canonical_submitted_sha256": canonical_json_sha256(payload),
        "normalized_model_sha256": canonical_json_sha256(model.model_dump(mode="json")),
    }
    if reference_hash is not None:
        result["reference_blade_canonical_submitted_sha256"] = reference_submitted_hash
        result["reference_blade_normalized_sha256"] = reference_hash
    return result
