from __future__ import annotations

import json

import pytest

from bladegen.propeller_pipeline import _require_valid_roundtrip, build_propeller
from bladegen.validation.propeller_preflight import PropellerPreflightError


def valid_topology():
    return {
        "solids": 1,
        "shells": 1,
        "free_edges": 0,
        "closed_shell": True,
        "brepcheck_valid": True,
    }


def test_roundtrip_topology_accepts_one_closed_valid_solid():
    _require_valid_roundtrip(valid_topology())


@pytest.mark.parametrize(
    "field, value, diagnostic",
    [
        ("solids", 2, "solids=2"),
        ("shells", 0, "shells=0"),
        ("free_edges", 4, "free_edges=4"),
        ("closed_shell", False, "closed_shell=False"),
        ("brepcheck_valid", False, "brepcheck_valid=False"),
    ],
)
def test_roundtrip_topology_fails_with_specific_diagnostic(field, value, diagnostic):
    topology = valid_topology()
    topology[field] = value
    with pytest.raises(RuntimeError, match=diagnostic):
        _require_valid_roundtrip(topology)


@pytest.mark.parametrize(
    "assembly_change, diagnostic",
    [
        ({"blade_count": 5}, "unsupported in this release"),
        ({"hub_diameter_mm": 60}, "greater than 80 mm"),
        ({"hub_diameter_mm": 80}, "greater than 80 mm"),
    ],
)
def test_pipeline_rejects_preflight_before_reference_blade(
    monkeypatch,
    tmp_path,
    assembly_change,
    diagnostic,
):
    from bladegen import propeller_pipeline

    source = tmp_path / "propeller.json"
    payload = json.loads(
        (
            propeller_pipeline.Path(__file__).resolve().parents[2]
            / "examples/propeller_two_blade.json"
        ).read_text(encoding="utf-8")
    )
    payload["assembly"].update(assembly_change)
    source.write_text(json.dumps(payload), encoding="utf-8")
    blade_calls = []
    monkeypatch.setattr(propeller_pipeline, "build_blade", lambda *args: blade_calls.append(args))
    output = tmp_path / "output"
    with pytest.raises(PropellerPreflightError, match=diagnostic):
        build_propeller(source, output)
    assert blade_calls == []
    assert not output.exists()
