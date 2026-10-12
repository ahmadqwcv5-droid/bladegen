from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from bladegen.models import PropellerSpec

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
BLADE = json.loads(
    (WORKSPACE_ROOT / "examples/custom_multi_airfoil_finite_te.json").read_text(encoding="utf-8")
)


def payload(**assembly_changes):
    assembly = {
        "blade_count": 3,
        "hub_diameter_mm": 90.0,
        "hub_length_mm": 45.0,
        "shaft_bore_diameter_mm": 12.0,
        "initial_azimuth_deg": 0.0,
        **assembly_changes,
    }
    return {
        "schema_version": "0.1",
        "name": "three_blade_propeller",
        "units": "mm",
        "blade_spec": BLADE,
        "assembly": assembly,
    }


def test_propeller_spec_preserves_complete_bladespec_contract():
    spec = PropellerSpec.model_validate(payload())
    assert spec.blade_spec.schema_version == "0.2"
    assert len(spec.blade_spec.airfoil_sections) == 5
    assert spec.assembly.blade_count == 3


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"blade_count": 1}, "blade_count"),
        ({"blade_count": 9}, "blade_count"),
        ({"hub_diameter_mm": 0}, "hub_diameter_mm"),
        ({"hub_length_mm": -1}, "hub_length_mm"),
        ({"shaft_bore_diameter_mm": 90}, "smaller than hub"),
        ({"hub_diameter_mm": 80}, "positive-volume connection"),
        ({"initial_azimuth_deg": math.inf}, "finite"),
        ({"hub_diameter_mm": 400}, "smaller than the propeller"),
    ],
)
def test_propeller_spec_rejects_invalid_dimensions(changes, message):
    with pytest.raises(ValidationError, match=message):
        PropellerSpec.model_validate(payload(**changes))


def test_propeller_spec_rejects_legacy_nested_bladespec():
    candidate = payload()
    candidate["blade_spec"] = {**BLADE, "schema_version": "0.1"}
    with pytest.raises(ValidationError, match="BladeSpec v0.2"):
        PropellerSpec.model_validate(candidate)
