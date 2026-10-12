from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from bladegen.validation.propeller_preflight import (
    PropellerPreflightError,
    validate_propeller_payload,
)

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = json.loads(
    (WORKSPACE_ROOT / "examples/propeller_two_blade.json").read_text(encoding="utf-8")
)


def candidate(**assembly_changes):
    return {
        **EXAMPLE,
        "assembly": {
            **EXAMPLE["assembly"],
            "hub_length_mm": 30,
            **assembly_changes,
        },
    }


@pytest.mark.parametrize("diameter", [60, 80])
def test_strict_nominal_hub_policy_rejects_gap_and_tangential_contact(diameter):
    with pytest.raises(PropellerPreflightError) as captured:
        validate_propeller_payload(candidate(hub_diameter_mm=diameter))
    issue = next(
        row for row in captured.value.issues if row.code == "hub_root_nominal_overlap_required"
    )
    assert issue.field == "assembly.hub_diameter_mm"
    assert issue.context["root_radius_mm"] == 40
    assert issue.context["required_diameter_bound_mm"] == 80
    assert issue.context["bound_is_exclusive"] is True
    assert issue.context["nominal_gap_mm"] == (40 - diameter / 2)


def test_81_mm_passes_only_nominal_preflight_and_90_by_30_is_supported():
    close = validate_propeller_payload(candidate(hub_diameter_mm=81))
    accepted = validate_propeller_payload(candidate(hub_diameter_mm=90))
    assert close.assembly.hub_diameter_mm == 81
    assert accepted.assembly.hub_length_mm == 30


def test_dynamic_bound_tracks_diameter_and_root_ratio():
    resized = candidate(hub_diameter_mm=90)
    resized["blade_spec"] = {**resized["blade_spec"], "diameter_mm": 600}
    with pytest.raises(PropellerPreflightError) as captured:
        validate_propeller_payload(resized)
    issue = next(
        row for row in captured.value.issues if row.code == "hub_root_nominal_overlap_required"
    )
    assert issue.context["root_radius_mm"] == 60
    assert issue.context["required_diameter_bound_mm"] == 120


@pytest.mark.parametrize(
    "changes, code",
    [
        ({"shaft_bore_diameter_mm": 90}, "bore_smaller_than_hub_required"),
        ({"shaft_bore_diameter_mm": 91}, "bore_smaller_than_hub_required"),
        ({"hub_length_mm": 0}, "positive_dimension_required"),
        ({"hub_diameter_mm": -1}, "positive_dimension_required"),
        ({"initial_azimuth_deg": math.inf}, "finite_number_required"),
        ({"blade_count": 3.5}, "blade_count_invalid"),
        ({"blade_count": 5}, "blade_count_unsupported"),
        ({"blade_count": 8}, "blade_count_unsupported"),
    ],
)
def test_preflight_returns_stable_codes(changes, code):
    with pytest.raises(PropellerPreflightError) as captured:
        validate_propeller_payload(candidate(**changes))
    assert code in {issue.code for issue in captured.value.issues}


def test_invalid_nested_bladespec_is_sanitized():
    invalid = candidate()
    invalid["blade_spec"] = {**invalid["blade_spec"], "airfoil_sections": []}
    with pytest.raises(PropellerPreflightError) as captured:
        validate_propeller_payload(invalid)
    assert captured.value.issues[0].code == "invalid_blade_spec"
    assert "input_value" not in captured.value.detail
    assert "errors.pydantic.dev" not in captured.value.detail
