from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from bladegen.airfoils import (
    apply_smooth_chord_normal_te,
    naca_4digit_coordinates,
    trailing_edge_gap_normalized,
)
from bladegen.curves.resolver import resolve_blade_spec
from bladegen.models import BladeSpec

ROOT = Path(__file__).resolve().parents[2]
FINITE_SPEC = ROOT / "examples/custom_multi_airfoil_finite_te.json"


@pytest.mark.parametrize(
    ("code", "expected_thickness", "expected_camber"),
    [
        ("4415", 0.15, 0.04),
        ("4412", 0.12, 0.04),
        ("2412", 0.12, 0.02),
        ("0012", 0.12, 0.00),
        ("0010", 0.10, 0.00),
    ],
)
def test_canonical_naca_profiles(code, expected_thickness, expected_camber):
    upper, lower = naca_4digit_coordinates(code)
    assert len(upper) == len(lower) == 161
    assert upper[0] == lower[0] == (0.0, 0.0)
    assert upper[-1] == lower[-1] == (1.0, 0.0)
    grid = np.linspace(0.0, 1.0, 4001)
    ux, uy = np.asarray(upper).T
    lx, ly = np.asarray(lower).T
    top = np.interp(grid, np.sort(ux), uy[np.argsort(ux)])
    bottom = np.interp(grid, np.sort(lx), ly[np.argsort(lx)])
    assert float(np.max(top - bottom)) == pytest.approx(expected_thickness, abs=0.002)
    assert float(np.max(np.abs(0.5 * (top + bottom)))) == pytest.approx(expected_camber, abs=0.001)


def test_smooth_chord_normal_te_policy_is_exact_and_local():
    upper, lower = naca_4digit_coordinates("4415")
    modified_upper, modified_lower = apply_smooth_chord_normal_te(
        upper, lower, target_gap_mm=1.2, chord_mm=70.0
    )
    assert [point[0] for point in modified_upper] == [point[0] for point in upper]
    assert [point[0] for point in modified_lower] == [point[0] for point in lower]
    for original, modified in zip(upper, modified_upper):
        if original[0] <= 0.85:
            assert modified == original
    assert trailing_edge_gap_normalized(modified_upper, modified_lower) * 70.0 == pytest.approx(
        1.2, abs=1e-12
    )


def test_v02_resolves_all_requested_te_gaps_exactly():
    resolved = resolve_blade_spec(BladeSpec.from_json(FINITE_SPEC))
    assert len(resolved.airfoil_sections) == 5
    assert max(section.mathematical_error_mm for section in resolved.airfoil_sections) <= 1e-12


def test_v01_rejects_v02_airfoil_fields():
    data = json.loads(FINITE_SPEC.read_text())
    data["schema_version"] = "0.1"
    with pytest.raises(ValidationError):
        BladeSpec.model_validate(data)
