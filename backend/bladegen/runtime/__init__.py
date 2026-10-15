"""Managed OpenVSP runtime selection and provenance."""

from .manager import (
    CONSTRUCTION_CONTRACT,
    EXPECTED_BUILD_ID,
    RuntimeIdentity,
    RuntimeReadinessError,
    inspect_runtime,
    load_openvsp_runtime,
    require_runtime_ready,
)

__all__ = [
    "CONSTRUCTION_CONTRACT",
    "EXPECTED_BUILD_ID",
    "RuntimeIdentity",
    "RuntimeReadinessError",
    "inspect_runtime",
    "load_openvsp_runtime",
    "require_runtime_ready",
]
