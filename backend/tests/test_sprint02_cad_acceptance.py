from __future__ import annotations

import os
from pathlib import Path

import pytest

from bladegen.models import BladeSpec
from bladegen.pipeline import build


ROOT = Path(__file__).resolve().parents[2]
CASES = (
    ("sprint02_case_a_three_section.json", 3, 0.25),
    ("sprint02_case_c_eight_section.json", 8, 0.18),
    ("sprint02_naca0008_thickness_override.json", 3, 0.25),
)


@pytest.mark.integration
@pytest.mark.parametrize(("filename", "section_count", "root"), CASES)
def test_sprint02_real_cad_acceptance(
    filename: str, section_count: int, root: float, tmp_path: Path
) -> None:
    if not os.environ.get("OPENVSP_ROOT"):
        pytest.skip("OPENVSP_ROOT is not configured")

    spec_path = ROOT / "examples" / filename
    spec = BladeSpec.from_json(spec_path)
    result = build(spec_path, tmp_path)
    topology = result["solidification"]["solid_after_reimport"]
    geometry = result["geometry_validation"]

    assert len(spec.airfoil_sections) == section_count
    assert spec.root_radius_ratio == pytest.approx(root)
    assert topology["solids"] == topology["shells"] == 1
    assert topology["closed_shell"] and topology["brepcheck_valid"]
    assert topology["free_edges"] == 0
    assert result["solidification"]["roundtrip"]["one_solid"]
    assert geometry["passed"]
    assert geometry["airfoil_station_count"] == section_count
    assert geometry["max_chord_error_mm"] <= 0.05
    assert geometry["max_twist_error_deg"] <= 0.05
    assert geometry["max_reference_axis_error_mm"] <= 0.05
    assert geometry["max_te_error_mm"] <= 0.020

    if "thickness_override" in filename:
        control_rows = [
            row for row in geometry["stations"] if "airfoil_station" in row["station_roles"]
        ]
        assert control_rows
        assert max(
            abs(row["measured_max_thickness_over_chord"] - 0.10)
            for row in control_rows
        ) <= 0.002
