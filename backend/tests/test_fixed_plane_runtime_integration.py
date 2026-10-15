from __future__ import annotations

import json
from pathlib import Path

import pytest

from bladegen.adapters.openvsp_adapter import build_and_export
from bladegen.curves.resolver import resolve_blade_spec
from bladegen.models import BladeSpec
from bladegen.pipeline import build
from bladegen.runtime.manager import RuntimeReadinessError, require_runtime_ready
from bladegen.validation.geometry_validation import compare_steps

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
NONZERO_RAKE_SPEC = WORKSPACE_ROOT / "examples/custom_multi_airfoil_finite_te.json"


def _require_native_runtime():
    try:
        return require_runtime_ready()
    except RuntimeReadinessError as exc:
        pytest.skip(str(exc))


@pytest.mark.integration
def test_zero_and_nonzero_rake_fixed_plane_geometry(tmp_path):
    identity = _require_native_runtime()
    nonzero = build(NONZERO_RAKE_SPEC, tmp_path / "nonzero-rake")
    assert nonzero["status"] == "PASS"
    assert nonzero["engine"]["fingerprint"] == identity.fingerprint
    assert nonzero["geometry_validation"]["passed"] is True
    assert nonzero["geometry_validation"]["max_chord_error_mm"] <= 0.05
    assert nonzero["geometry_validation"]["max_twist_error_deg"] <= 0.1
    assert nonzero["geometry_validation"]["max_reference_axis_error_mm"] <= 0.05

    zero_payload = json.loads(NONZERO_RAKE_SPEC.read_text(encoding="utf-8"))
    for point in zero_payload["rake_distribution"]["points"]:
        point["rake_over_R"] = 0.0
    zero_path = tmp_path / "zero-rake.json"
    zero_path.write_text(json.dumps(zero_payload, indent=2) + "\n", encoding="utf-8")
    zero = build(zero_path, tmp_path / "zero-rake")
    assert zero["status"] == "PASS"
    assert zero["geometry_validation"]["passed"] is True


@pytest.mark.integration
def test_diagnostic_rotation_environment_flag_cannot_change_geometry(monkeypatch, tmp_path):
    _require_native_runtime()
    resolved = resolve_blade_spec(BladeSpec.from_json(NONZERO_RAKE_SPEC))
    monkeypatch.setenv("BLADEGEN_BYPASS_AUTO_RIB_ROTATION", "0")
    left = build_and_export(resolved, tmp_path / "flag-off")
    monkeypatch.setenv("BLADEGEN_BYPASS_AUTO_RIB_ROTATION", "1")
    right = build_and_export(resolved, tmp_path / "flag-on")
    comparison = compare_steps(left.step_path, right.step_path, samples=9)
    assert comparison["rms_mm"] <= 1e-9
    assert comparison["p95_mm"] <= 1e-9
    assert comparison["max_mm"] <= 1e-9
    assert comparison["bbox_max_abs_error_mm"] <= 1e-9
    assert comparison["surface_area_difference_mm2"] <= 1e-8
