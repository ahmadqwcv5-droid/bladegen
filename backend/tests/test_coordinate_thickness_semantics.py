import json
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app
from bladegen.airfoils.importers import import_airfoil

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "custom_multi_airfoil_finite_te.json"
FIXTURE = Path(__file__).parent / "fixtures" / "airfoils" / "independent_analytic_finite_te.dat"
client = TestClient(app)


def coordinate_payload() -> tuple[dict, float]:
    imported = import_airfoil(FIXTURE.read_bytes(), FIXTURE.name)
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["airfoil_sections"][2]["airfoil"] = imported.airfoil.model_dump(mode="json")
    return payload, imported.metrics.max_thickness_ratio


def test_coordinate_profile_must_match_active_thickness_control() -> None:
    payload, natural_ratio = coordinate_payload()
    assert payload["thickness_distribution"]["points"][2]["thickness_ratio"] != natural_ratio
    response = client.post("/api/design-preview", json=payload)
    assert response.status_code == 422
    assert "inconsistent with imported coordinate profile geometric thickness" in response.text


def test_coordinate_profile_with_natural_thickness_has_canonical_preview() -> None:
    payload, natural_ratio = coordinate_payload()
    payload["thickness_distribution"]["points"][2]["thickness_ratio"] = natural_ratio
    response = client.post("/api/design-preview", json=payload)
    assert response.status_code == 200, response.text
    station = response.json()["stations"][2]
    assert station["kind"] == "coordinates"
    assert station["effective_thickness_ratio"] == natural_ratio
    assert station["source"]["metrics"]["max_thickness_ratio"] == natural_ratio
