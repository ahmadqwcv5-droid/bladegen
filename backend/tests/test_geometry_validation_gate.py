import json
from pathlib import Path

import pytest

from bladegen.models import BladeSpec
from bladegen.pipeline import _geometry_summary

ROOT = Path(__file__).resolve().parents[2]


def _record(endpoint: str, radius: float) -> dict:
    return {
        "endpoint": endpoint,
        "station_roles": ["airfoil_station"],
        "requested_r_over_R": radius,
        "sampled_r_over_R": radius,
        "chord_absolute_error_mm": 0.0,
        "twist_absolute_error_deg": 0.0,
        "reference_axis_position_error_mm": 0.0,
        "contour_rms_mm": 0.0,
        "contour_p95_mm": 0.0,
        "contour_max_mm": 0.0,
        "te_absolute_error_mm": 0.0,
        "chord_pass": True,
        "twist_pass": True,
        "reference_axis_pass": True,
        "contour_rms_pass": True,
        "contour_p95_pass": True,
        "contour_max_pass": True,
        "te_pass": True,
        "wire_count_pass": True,
        "wire_valid_pass": True,
        "wire_closed_pass": True,
    }


@pytest.mark.parametrize(
    "failed_check", ["wire_count_pass", "wire_valid_pass", "wire_closed_pass"]
)
def test_required_geometry_gate_rejects_invalid_section_wires(failed_check: str):
    payload = json.loads(
        (ROOT / "examples" / "custom_multi_airfoil_finite_te.json").read_text()
    )
    spec = BladeSpec.model_validate(payload)
    records = [
        _record("root", spec.root_radius_ratio),
        _record("tip", 1.0),
    ]

    assert _geometry_summary(records, spec)["passed"] is True
    records[0][failed_check] = False
    assert _geometry_summary(records, spec)["passed"] is False
