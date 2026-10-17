from __future__ import annotations

from pathlib import Path

import pytest

from bladegen.validation.policy import (
    IMPORTED_PROFILE_ACCEPTANCE_TARGET,
    PRODUCTION_CONTROL_CONTOUR,
    PRODUCTION_INTERMEDIATE_CONTOUR,
    contour_passes,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("policy", "expected"),
    (
        (PRODUCTION_CONTROL_CONTOUR, (0.030, 0.060, 0.120)),
        (PRODUCTION_INTERMEDIATE_CONTOUR, (0.050, 0.100, 0.200)),
        (IMPORTED_PROFILE_ACCEPTANCE_TARGET, (0.020, 0.040, 0.050)),
    ),
)
def test_named_contour_policy_thresholds(policy, expected: tuple[float, float, float]) -> None:
    assert (policy.rms_mm, policy.p95_mm, policy.maximum_mm) == expected
    assert contour_passes(*expected, policy)["passed"]


@pytest.mark.parametrize(
    "policy",
    (PRODUCTION_CONTROL_CONTOUR, PRODUCTION_INTERMEDIATE_CONTOUR, IMPORTED_PROFILE_ACCEPTANCE_TARGET),
)
@pytest.mark.parametrize("metric", ("rms_mm", "p95_mm", "maximum_mm"))
def test_value_just_above_each_named_threshold_fails(policy, metric: str) -> None:
    values = {
        "rms_mm": policy.rms_mm,
        "p95_mm": policy.p95_mm,
        "maximum_mm": policy.maximum_mm,
    }
    values[metric] += 1e-12
    result = contour_passes(**values, policy=policy)
    assert not result[metric.removesuffix("_mm").replace("maximum", "maximum") + "_pass"]
    assert not result["passed"]


def test_validation_document_names_both_distinct_policies() -> None:
    policy_document = (ROOT / "docs" / "developer" / "VALIDATION_POLICY.md").read_text(encoding="utf-8")
    assert "Production control-section gate" in policy_document
    assert "Imported-profile acceptance target" in policy_document
    for value in ("0.030 mm", "0.060 mm", "0.120 mm", "0.020 mm", "0.040 mm", "0.050 mm"):
        assert value in policy_document
