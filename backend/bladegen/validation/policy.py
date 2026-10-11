"""Named, single-source numerical policies for final section validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ContourThresholds:
    name: str
    rms_mm: float
    p95_mm: float
    maximum_mm: float

    def as_dict(self) -> dict:
        return asdict(self)


PRODUCTION_CONTROL_CONTOUR = ContourThresholds(
    name="production_control_section_gate", rms_mm=0.030, p95_mm=0.060, maximum_mm=0.120
)
PRODUCTION_INTERMEDIATE_CONTOUR = ContourThresholds(
    name="production_intermediate_section_gate",
    rms_mm=0.050,
    p95_mm=0.100,
    maximum_mm=0.200,
)
IMPORTED_PROFILE_ACCEPTANCE_TARGET = ContourThresholds(
    name="imported_profile_acceptance_target",
    rms_mm=0.020,
    p95_mm=0.040,
    maximum_mm=0.050,
)

CHORD_ERROR_MAX_MM = 0.050
TWIST_ERROR_MAX_DEG = 0.050
REFERENCE_AXIS_ERROR_MAX_MM = 0.050
TRAILING_EDGE_ERROR_MAX_MM = 0.020


def contour_passes(
    rms_mm: float, p95_mm: float, maximum_mm: float, policy: ContourThresholds
) -> dict:
    checks = {
        "rms_pass": rms_mm <= policy.rms_mm,
        "p95_pass": p95_mm <= policy.p95_mm,
        "maximum_pass": maximum_mm <= policy.maximum_mm,
    }
    return {
        "policy": policy.as_dict(),
        **checks,
        "passed": all(checks.values()),
    }
