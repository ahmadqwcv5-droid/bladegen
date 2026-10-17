from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.services.jobs import jobs
from bladegen.models import BladeSpec, RotationDirection
from bladegen.validation.expected_geometry import (
    _arc_resample,
    diagnostic_profile,
    evaluate_distribution,
    evaluate_state,
    resolved_control_profile,
    section_transform,
)
from bladegen.validation.measure_sections import _twist_degrees, symmetric_distances
from bladegen.validation.policy import PRODUCTION_INTERMEDIATE_CONTOUR, contour_passes

ROOT = Path(__file__).resolve().parents[2]
Q02 = ROOT / "qualification" / "fp02" / "cases" / "Q02.json"
Q04 = ROOT / "qualification" / "fp02" / "cases" / "Q04.json"
Q04_R1 = ROOT / "qualification" / "fp02_c1" / "cases" / "Q04.R1.json"


def _legacy_blend(spec: BladeSpec, station: float, count: int = 2001):
    right_index = next(
        index for index, section in enumerate(spec.airfoil_sections) if section.r_over_R >= station
    )
    right = spec.airfoil_sections[right_index]
    if math.isclose(right.r_over_R, station, abs_tol=1e-12):
        left = right
    else:
        left = spec.airfoil_sections[right_index - 1]
    fraction = (
        0.0
        if left.r_over_R == right.r_over_R
        else (station - left.r_over_R) / (right.r_over_R - left.r_over_R)
    )
    grid = np.linspace(0.0, 1.0, count)
    blended = []
    for a, b in zip(resolved_control_profile(spec, left), resolved_control_profile(spec, right)):
        blended.append(
            (1.0 - fraction) * _arc_resample(a, grid) + fraction * _arc_resample(b, grid)
        )
    return blended[0], blended[1], left, right, fraction


def _te_gap(profile) -> float:
    upper, lower = profile[:2]
    return float(abs(upper[-1, 1] - lower[-1, 1]))


def test_pchip_intermediate_applies_independent_thickness_after_profile_blend() -> None:
    spec = BladeSpec.from_json(Q02)
    station = 0.30
    legacy_upper, legacy_lower, left, right, fraction = _legacy_blend(spec, station)
    base_ratio = (1.0 - fraction) * evaluate_distribution(
        spec.thickness_distribution, "thickness_ratio", left.r_over_R
    ) + fraction * evaluate_distribution(
        spec.thickness_distribution, "thickness_ratio", right.r_over_R
    )
    target_ratio = evaluate_distribution(spec.thickness_distribution, "thickness_ratio", station)
    corrected = diagnostic_profile(spec, station)

    assert base_ratio == 0.135
    assert target_ratio == 0.129375
    assert _te_gap(corrected) == pytest.approx(
        _te_gap((legacy_upper, legacy_lower)) * target_ratio / base_ratio,
        abs=1e-12,
    )


def test_constant_thickness_intermediate_and_explicit_station_are_identity() -> None:
    spec = BladeSpec.from_json(Q02)
    for station in (0.40, 0.50):
        legacy_upper, legacy_lower, *_ = _legacy_blend(spec, station)
        corrected_upper, corrected_lower, *_ = diagnostic_profile(spec, station)
        np.testing.assert_array_equal(corrected_upper, legacy_upper)
        np.testing.assert_array_equal(corrected_lower, legacy_lower)


def test_linear_distribution_intermediate_is_identity() -> None:
    payload = BladeSpec.from_json(Q02).model_dump(mode="json")
    payload["thickness_distribution"]["interpolation"] = "linear"
    spec = BladeSpec.model_validate(payload)
    legacy_upper, legacy_lower, *_ = _legacy_blend(spec, 0.30)
    corrected_upper, corrected_lower, *_ = diagnostic_profile(spec, 0.30)
    np.testing.assert_array_equal(corrected_upper, legacy_upper)
    np.testing.assert_array_equal(corrected_lower, legacy_lower)


def test_original_q04_is_rejected_before_cad_queueing() -> None:
    client = TestClient(app)
    payload = json.loads(Q04.read_text(encoding="utf-8"))
    before = set(jobs._jobs)

    response = client.post("/api/build", json=payload)

    assert response.status_code == 422
    assert "Thickness distribution at r/R=0.18 is 0.150000, inconsistent" in response.text
    assert "geometric thickness 0.130553" in response.text
    assert set(jobs._jobs) == before


def test_reverse_transform_reflects_only_the_tangential_coordinate() -> None:
    reverse_spec = BladeSpec.from_json(Q04_R1)
    normal_payload = reverse_spec.model_dump(mode="json")
    normal_payload["rotation_direction"] = "normal"
    normal_spec = BladeSpec.model_validate(normal_payload)
    reverse_state = evaluate_state(reverse_spec, 0.40)
    normal_state = evaluate_state(normal_spec, 0.40)
    reverse_reference, reverse_chord, reverse_normal = section_transform(reverse_state)
    normal_reference, normal_chord, normal_normal = section_transform(normal_state)

    np.testing.assert_allclose(reverse_reference, normal_reference * [1.0, -1.0])
    np.testing.assert_allclose(reverse_chord, normal_chord * [1.0, -1.0])
    np.testing.assert_allclose(reverse_normal, normal_normal * [1.0, -1.0])


def test_twist_measurement_preserves_bladespec_semantics_for_both_directions() -> None:
    angle = math.radians(31.0)
    normal_chord = np.array([math.sin(angle), math.cos(angle)])
    reverse_chord = normal_chord * [1.0, -1.0]

    assert _twist_degrees(normal_chord, RotationDirection.NORMAL) == pytest.approx(31.0)
    assert _twist_degrees(reverse_chord, RotationDirection.REVERSE) == pytest.approx(31.0)


def test_incorrect_unscaled_finite_te_contour_remains_rejected() -> None:
    spec = BladeSpec.from_json(Q02)
    station = 0.30
    legacy_upper, legacy_lower, *_ = _legacy_blend(spec, station)
    corrected_upper, corrected_lower, *_ = diagnostic_profile(spec, station)
    chord_mm = evaluate_distribution(spec.chord_distribution, "chord_over_R", station) * (
        spec.diameter_mm / 2.0
    )
    legacy = np.vstack((legacy_upper, legacy_lower)) * chord_mm
    corrected = np.vstack((corrected_upper, corrected_lower)) * chord_mm
    distances = symmetric_distances(legacy, corrected)
    rms = float(np.sqrt(np.mean(distances * distances)))
    p95 = float(np.percentile(distances, 95))
    maximum = float(np.max(distances))

    assert rms > PRODUCTION_INTERMEDIATE_CONTOUR.rms_mm
    assert p95 > PRODUCTION_INTERMEDIATE_CONTOUR.p95_mm
    assert contour_passes(rms, p95, maximum, PRODUCTION_INTERMEDIATE_CONTOUR)["passed"] is False
