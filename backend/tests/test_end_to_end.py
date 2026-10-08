from pathlib import Path

import pytest

from bladegen.models import BladeSpec
from bladegen.pipeline import build
from bladegen.solid.ocp_solidify import inspect_shape, read_step
from bladegen.validation.measure_sections import measure_sections

EXAMPLE = Path(__file__).resolve().parents[2] / "examples/x57_finite_te_multi_airfoil.json"


@pytest.mark.integration
def test_real_v02_build_step_reimport_and_independent_geometry(tmp_path):
    if not __import__("os").environ.get("OPENVSP_ROOT"):
        pytest.skip("OPENVSP_ROOT is not configured")
    result = build(EXAMPLE, tmp_path)
    step = tmp_path / "blade_solid.step"
    solid = inspect_shape(read_step(step))
    assert solid["solids"] == 1
    assert solid["shells"] == 1
    assert solid["closed_shell"]
    assert solid["brepcheck_valid"]
    assert solid["free_edges"] == 0
    assert solid["volume_method"].endswith("adaptive Gauss-Kronrod")
    assert result["solidification"]["roundtrip"]["volume_delta_mm3"] <= 1e-5

    measured = measure_sections(step, BladeSpec.from_json(EXAMPLE))
    representatives = [row for row in measured if row["requested_r_over_R"] in (0.20, 0.60, 1.00)]
    assert len(representatives) == 3
    assert max(row["chord_absolute_error_mm"] for row in representatives) <= 0.05
    assert max(row["twist_absolute_error_deg"] for row in representatives) <= 0.05
    assert max(row["te_absolute_error_mm"] for row in representatives) <= 0.02
    assert all(row["wire_valid"] and row["wire_closed"] for row in representatives)
