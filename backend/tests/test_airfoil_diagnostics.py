from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app
from bladegen.airfoils.diagnostics import coordinate_profile_diagnostics
from bladegen.airfoils.importers import import_airfoil

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures" / "airfoils"
EXAMPLE = ROOT / "examples" / "custom_multi_airfoil_finite_te.json"
client = TestClient(app)


def _import(name: str):
    path = FIXTURES / name
    return import_airfoil(path.read_bytes(), path.name)


def test_sparse_coordinate_profile_warns_without_mutating_coordinates() -> None:
    imported = _import("independent_cambered_finite_te.dat")
    before = deepcopy(imported.airfoil.model_dump(mode="json"))
    diagnostics = coordinate_profile_diagnostics(imported.airfoil.upper, imported.airfoil.lower)
    assert diagnostics["has_warning"]
    assert diagnostics["upper_point_count"] == diagnostics["lower_point_count"] == 5
    assert diagnostics["maximum_chordwise_spacing"] == 0.25
    assert "low_coordinate_density" in diagnostics["warning_codes"]
    assert imported.airfoil.model_dump(mode="json") == before


def test_adequately_sampled_profile_has_no_misleading_density_warning() -> None:
    imported = _import("independent_analytic_finite_te.dat")
    diagnostics = coordinate_profile_diagnostics(imported.airfoil.upper, imported.airfoil.lower)
    assert diagnostics["upper_point_count"] == diagnostics["lower_point_count"] == 41
    assert diagnostics["maximum_chordwise_spacing"] <= 0.04
    assert diagnostics["warning_codes"] == []
    assert not diagnostics["has_warning"]


def test_standalone_bladespec_embedded_coordinates_receive_preview_warning() -> None:
    imported = _import("independent_cambered_finite_te.dat")
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["airfoil_sections"][2]["airfoil"] = imported.airfoil.model_dump(mode="json")
    payload["thickness_distribution"]["points"][2]["thickness_ratio"] = (
        imported.metrics.max_thickness_ratio
    )
    embedded_before = deepcopy(payload["airfoil_sections"][2]["airfoil"])
    response = client.post("/api/design-preview", json=payload)
    assert response.status_code == 200, response.text
    station = response.json()["stations"][2]
    assert station["diagnostics"]["has_warning"]
    assert "Final STEP fidelity" in station["diagnostics"]["advisory"]
    assert payload["airfoil_sections"][2]["airfoil"] == embedded_before
