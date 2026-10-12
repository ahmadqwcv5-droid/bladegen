from __future__ import annotations

import pytest

from bladegen.propeller_pipeline import _require_valid_roundtrip


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
