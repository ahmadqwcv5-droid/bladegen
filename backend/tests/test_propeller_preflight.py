from __future__ import annotations

import json
import math
from copy import deepcopy
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


def set_station(candidate_spec, index, *, code=None, override="unchanged", thickness=None):
    result = deepcopy(candidate_spec)
    section = result["blade_spec"]["airfoil_sections"][index]
    if code is not None:
        section["airfoil"] = {"type": "naca4", "code": code}
    if override != "unchanged":
        if override is None:
            section.pop("thickness_override_ratio", None)
        else:
            section["thickness_override_ratio"] = override
    if thickness is not None:
        station = section["r_over_R"]
        point = next(
            row
            for row in result["blade_spec"]["thickness_distribution"]["points"]
            if row["r_over_R"] == station
        )
        point["thickness_ratio"] = thickness
    return result


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


@pytest.mark.parametrize(
    "payload, expected_ratio",
    [
        (set_station(candidate(), 1, code="4412", override=None, thickness=0.20), 0.12),
        (set_station(candidate(), 1, code="0000", override=None, thickness=0.20), 0.0),
        (set_station(candidate(), 1, code="4412", override=0.18, thickness=0.20), 0.18),
    ],
)
def test_naca_thickness_semantics_reject_before_cad(payload, expected_ratio):
    with pytest.raises(PropellerPreflightError) as captured:
        validate_propeller_payload(payload)
    issue = captured.value.issues[0]
    assert issue.code == "invalid_blade_spec"
    assert issue.field == "blade_spec.thickness_distribution"
    assert issue.context["station_r_over_R"] == 0.4
    assert issue.context["evaluated_thickness_ratio"] == 0.20
    assert issue.context["expected_thickness_ratio"] == expected_ratio


def test_matching_explicit_naca_override_remains_supported():
    payload = set_station(candidate(), 1, code="4412", override=0.20, thickness=0.20)
    accepted = validate_propeller_payload(payload)
    assert accepted.blade_spec.airfoil_sections[1].thickness_override_ratio == 0.20


def coordinate_profile_payload(thickness):
    payload = deepcopy(candidate())
    section = payload["blade_spec"]["airfoil_sections"][1]
    section["airfoil"] = {
        "type": "coordinates",
        "upper": [[0, 0], [0.5, 0.1], [1, 0]],
        "lower": [[0, 0], [0.5, -0.1], [1, 0]],
    }
    section.pop("thickness_override_ratio", None)
    point = payload["blade_spec"]["thickness_distribution"]["points"][1]
    point["thickness_ratio"] = thickness
    return payload


def test_coordinate_profile_natural_thickness_mismatch_is_rejected():
    with pytest.raises(PropellerPreflightError) as captured:
        validate_propeller_payload(coordinate_profile_payload(0.18))
    issue = captured.value.issues[0]
    assert issue.code == "invalid_blade_spec"
    assert issue.context["selected_airfoil"] == "coordinate profile"
    assert issue.context["natural_thickness_ratio"] == pytest.approx(0.20)


def test_valid_coordinate_profile_is_accepted_without_modification():
    payload = coordinate_profile_payload(0.20)
    accepted = validate_propeller_payload(payload)
    assert accepted.blade_spec.airfoil_sections[1].airfoil.model_dump(mode="json") == payload[
        "blade_spec"
    ]["airfoil_sections"][1]["airfoil"]


def test_missing_and_explicit_zero_azimuth_normalize_equivalently():
    omitted = candidate()
    omitted["assembly"].pop("initial_azimuth_deg")
    explicit = candidate(initial_azimuth_deg=0)
    omitted_spec = validate_propeller_payload(omitted)
    explicit_spec = validate_propeller_payload(explicit)
    assert omitted_spec.assembly == explicit_spec.assembly
    assert omitted_spec.assembly.initial_azimuth_deg == 0.0
    retained = validate_propeller_payload(candidate(initial_azimuth_deg=17.5))
    assert retained.assembly.initial_azimuth_deg == 17.5


@pytest.mark.parametrize("invalid", [None, "zero"])
def test_explicit_invalid_azimuth_is_not_defaulted(invalid):
    with pytest.raises(PropellerPreflightError) as captured:
        validate_propeller_payload(candidate(initial_azimuth_deg=invalid))
    assert captured.value.issues[0].field == "assembly.initial_azimuth_deg"
