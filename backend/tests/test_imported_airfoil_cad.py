from __future__ import annotations

import json
from pathlib import Path

import pytest

from bladegen.airfoils.importers import import_airfoil
from bladegen.models import BladeSpec
from bladegen.pipeline import build
from bladegen.runtime.manager import RuntimeReadinessError, require_runtime_ready

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "custom_multi_airfoil_finite_te.json"
FIXTURE = Path(__file__).parent / "fixtures" / "airfoils" / "independent_analytic_finite_te.dat"


@pytest.mark.integration
def test_imported_non_naca_profile_generates_valid_faithful_step(tmp_path: Path) -> None:
    try:
        require_runtime_ready()
    except RuntimeReadinessError as exc:
        pytest.skip(str(exc))
    imported = import_airfoil(FIXTURE.read_bytes(), FIXTURE.name)
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["name"] = "sprint03a_imported_coordinate_acceptance"
    payload["airfoil_sections"][2]["airfoil"] = imported.airfoil.model_dump(mode="json")
    payload["thickness_distribution"]["points"][2]["thickness_ratio"] = (
        imported.metrics.max_thickness_ratio
    )
    spec_path = tmp_path / "imported_spec.json"
    spec_path.write_text(json.dumps(payload), encoding="utf-8")
    spec = BladeSpec.from_json(spec_path)
    result = build(spec_path, tmp_path / "result")

    topology = result["solidification"]["solid_after_reimport"]
    geometry = result["geometry_validation"]
    assert topology["solids"] == topology["shells"] == 1
    assert topology["free_edges"] == 0
    assert topology["closed_shell"] and topology["brepcheck_valid"]
    assert result["solidification"]["roundtrip"]["one_solid"]
    assert geometry["passed"]
    imported_row = next(row for row in geometry["stations"] if row["requested_r_over_R"] == 0.6)
    assert imported_row["contour_rms_pass"]
    assert imported_row["contour_p95_pass"]
    assert imported_row["contour_max_pass"]
    assert imported_row["production_contour_policy"]["name"] == "production_control_section_gate"
    assert (
        imported_row["imported_profile_acceptance"]["policy"]["name"]
        == "imported_profile_acceptance_target"
    )
    assert imported_row["imported_profile_acceptance"]["passed"]
    assert imported_row["measured_max_thickness_over_chord"] == pytest.approx(
        imported.metrics.max_thickness_ratio, abs=0.002
    )
    resolved_section = result["airfoil_resolution"]["sections"][2]
    assert spec.airfoil_sections[2].airfoil.type == "coordinates"
    assert resolved_section["policy"] == "smooth_chord_normal"
