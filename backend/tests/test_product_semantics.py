import json
from pathlib import Path

import pytest

from bladegen.curves.resolver import resolve_blade_spec
from bladegen.models import BladeSpec

EXAMPLE = Path(__file__).resolve().parents[2] / "examples/custom_multi_airfoil_finite_te.json"


def test_naca_change_cannot_silently_keep_contradictory_thickness_curve():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["airfoil_sections"][-1]["airfoil"]["code"] = "0008"
    with pytest.raises(ValueError, match="inconsistent with nominal NACA 0008"):
        resolve_blade_spec(BladeSpec.model_validate(data))


def test_explicit_naca_thickness_override_is_supported():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["airfoil_sections"][-1]["airfoil"]["code"] = "0008"
    data["airfoil_sections"][-1]["thickness_override_ratio"] = 0.10
    resolved = resolve_blade_spec(BladeSpec.model_validate(data))
    section = resolved.airfoil_sections[-1]
    assert section.r_over_R == 1.0
    ordinates = [point[1] for point in section.airfoil.upper] + [
        point[1] for point in section.airfoil.lower
    ]
    assert max(ordinates) - min(ordinates) == pytest.approx(0.10, abs=0.002)
    assert section.generated_trailing_edge_thickness_mm == pytest.approx(
        data["airfoil_sections"][-1]["trailing_edge_thickness_mm"], abs=1e-12
    )
