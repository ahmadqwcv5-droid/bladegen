from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from bladegen.models import BladeSpec

SPEC = Path(__file__).resolve().parents[2] / "examples/x57_finite_te_multi_airfoil.json"


def raw_spec() -> dict:
    return json.loads(SPEC.read_text(encoding="utf-8"))


def test_bladespec_validation_accepts_neutral_example():
    spec = BladeSpec.model_validate(raw_spec())
    assert spec.units == "mm"
    assert spec.root_radius_ratio == spec.chord_distribution.points[0].r_over_R
    assert spec.airfoil_sections[-1].r_over_R == 1.0


def test_distribution_ordering_is_strict():
    data = raw_spec()
    data["chord_distribution"]["points"][1]["r_over_R"] = data["chord_distribution"]["points"][0][
        "r_over_R"
    ]
    with pytest.raises(ValidationError, match="strictly increasing"):
        BladeSpec.model_validate(data)


def test_required_distribution_cannot_be_omitted():
    data = raw_spec()
    del data["rake_distribution"]
    with pytest.raises(ValidationError):
        BladeSpec.model_validate(data)


def test_interpolation_name_validation():
    data = raw_spec()
    data["twist_distribution"]["interpolation"] = "openvsp_pcurve_1"
    with pytest.raises(ValidationError):
        BladeSpec.model_validate(data)


def test_airfoil_validation_requires_enough_points():
    data = deepcopy(raw_spec())
    data["airfoil_sections"][0]["airfoil"]["code"] = "44X5"
    with pytest.raises(ValidationError):
        BladeSpec.model_validate(data)


def test_user_schema_contains_no_backend_fields():
    text = SPEC.read_text(encoding="utf-8").lower()
    banned = ("openvsp", "xsec", "geom_id", "parm", "tess", "mesh", "export", "cluster", "cap_")
    assert not any(token in text for token in banned)
