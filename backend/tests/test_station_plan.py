import json
from pathlib import Path

import pytest

from bladegen.models import BladeSpec
from bladegen.validation.station_plan import plan_validation_stations

EXAMPLE = Path(__file__).resolve().parents[2] / "examples/custom_multi_airfoil_finite_te.json"


def load() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_plan_uses_submitted_airfoils_midpoints_and_distribution_grids():
    data = load()
    data["root_radius_ratio"] = 0.25
    for name in (
        "chord_distribution",
        "twist_distribution",
        "rake_distribution",
        "skew_distribution",
        "thickness_distribution",
    ):
        data[name]["points"][0]["r_over_R"] = 0.25
    data["airfoil_sections"] = [
        {
            **data["airfoil_sections"][0],
            "r_over_R": 0.25,
            "airfoil": {"type": "naca4", "code": "0012"},
            "trailing_edge_thickness_mm": 0.4,
        },
        {
            **data["airfoil_sections"][2],
            "r_over_R": 0.625,
            "airfoil": {"type": "naca4", "code": "0012"},
            "trailing_edge_thickness_mm": 0.4,
        },
        {
            **data["airfoil_sections"][-1],
            "r_over_R": 1.0,
            "airfoil": {"type": "naca4", "code": "0012"},
            "trailing_edge_thickness_mm": 0.4,
        },
    ]
    data["thickness_distribution"] = {
        "interpolation": "linear",
        "points": [
            {"r_over_R": 0.25, "thickness_ratio": 0.12},
            {"r_over_R": 1.0, "thickness_ratio": 0.12},
        ],
    }
    spec = BladeSpec.model_validate(data)
    plan = plan_validation_stations(spec)
    by_requested = {station.requested_r_over_R: station for station in plan.stations}
    assert {0.25, 0.4375, 0.625, 0.8125, 1.0} <= set(by_requested)
    assert by_requested[0.25].endpoint == "root"
    assert by_requested[0.25].sampled_r_over_R > 0.25
    assert by_requested[1.0].endpoint == "tip"
    assert by_requested[1.0].sampled_r_over_R < 1.0
    assert "chord_control" in by_requested[0.35].roles


def test_plan_has_no_duplicate_stations_and_is_deterministic():
    spec = BladeSpec.model_validate(load())
    left = plan_validation_stations(spec)
    right = plan_validation_stations(spec)
    assert left == right
    requested = [station.requested_r_over_R for station in left.stations]
    assert len(requested) == len(set(requested))
    assert left.root_r_over_R == pytest.approx(0.2)
