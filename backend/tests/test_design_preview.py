from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from bladegen.airfoils.canonical import naca_4digit_coordinates
from bladegen.curves.canonical import evaluate_curve
from bladegen.curves.resolver import resolve_blade_spec
from bladegen.models import BladeSpec

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "custom_multi_airfoil_finite_te.json"
client = TestClient(app)


def test_preview_naca_source_and_resolved_te_match_canonical_definitions() -> None:
    spec = BladeSpec.from_json(EXAMPLE)
    response = client.post("/api/design-preview", json=spec.model_dump(mode="json"))
    assert response.status_code == 200, response.text
    payload = response.json()
    resolved = resolve_blade_spec(spec)

    for code in ("4412", "0012"):
        index = next(
            i
            for i, section in enumerate(spec.airfoil_sections)
            if section.airfoil.type == "naca4" and section.airfoil.code == code
        )
        expected_upper, expected_lower = naca_4digit_coordinates(code)
        assert payload["stations"][index]["source"]["upper"] == [list(row) for row in expected_upper]
        assert payload["stations"][index]["source"]["lower"] == [list(row) for row in expected_lower]
        assert payload["stations"][index]["resolved"]["upper"] == [
            list(row) for row in resolved.airfoil_sections[index].airfoil.upper
        ]
        assert payload["stations"][index]["resolved"]["lower"] == [
            list(row) for row in resolved.airfoil_sections[index].airfoil.lower
        ]
        assert payload["stations"][index]["preview_status"].startswith("canonical design")


@pytest.mark.parametrize(
    ("distribution_name", "field", "scale"),
    (
        ("chord", "chord_over_R", 200.0),
        ("twist", "twist_deg", 1.0),
        ("rake", "rake_over_R", 200.0),
        ("skew", "skew_over_R", 200.0),
        ("thickness", "thickness_ratio", 100.0),
    ),
)
def test_linear_and_pchip_chart_samples_match_canonical_evaluation(
    distribution_name: str, field: str, scale: float
) -> None:
    spec = BladeSpec.from_json(EXAMPLE)
    response = client.post("/api/design-preview", json=spec.model_dump(mode="json"))
    chart = response.json()["distributions"][distribution_name]
    curve = getattr(spec, f"{distribution_name}_distribution")
    assert len(chart["samples"]) == 251
    for index in (17, 73, 129, 207):
        radius, value = chart["samples"][index]
        assert value == pytest.approx(evaluate_curve(curve, radius, field) * scale, abs=1e-12)


def test_physical_chord_chart_updates_with_diameter_without_changing_twist() -> None:
    payload = BladeSpec.from_json(EXAMPLE).model_dump(mode="json")
    first = client.post("/api/design-preview", json=payload).json()
    doubled = deepcopy(payload)
    doubled["diameter_mm"] *= 2
    second = client.post("/api/design-preview", json=doubled).json()
    for (_, chord_a), (_, chord_b) in zip(
        first["distributions"]["chord"]["samples"],
        second["distributions"]["chord"]["samples"],
    ):
        assert chord_b == pytest.approx(2 * chord_a)
    assert first["distributions"]["twist"]["samples"] == second["distributions"]["twist"]["samples"]


def test_invalid_draft_is_rejected_without_running_cad() -> None:
    payload = BladeSpec.from_json(EXAMPLE).model_dump(mode="json")
    payload["airfoil_sections"][0]["airfoil"]["code"] = "44"
    response = client.post("/api/design-preview", json=payload)
    assert response.status_code == 422
    assert "string_pattern_mismatch" in response.text
