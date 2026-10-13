from pathlib import Path

import numpy as np
import pytest
from scipy.interpolate import PchipInterpolator

from bladegen.curves import canonical
from bladegen.curves.canonical import evaluate_curve, prepare_curve
from bladegen.curves.resolver import resolve_blade_spec, tolerance_profile
from bladegen.models import BladeSpec

CUSTOM_SPEC = Path(__file__).resolve().parents[2] / "examples/custom_multi_airfoil_finite_te.json"


@pytest.fixture(scope="module")
def spec() -> BladeSpec:
    return BladeSpec.from_json(CUSTOM_SPEC)


def test_canonical_linear_is_piecewise_linear(spec):
    curve = spec.thickness_distribution
    assert curve.interpolation.value == "linear"
    assert evaluate_curve(curve, 0.6) == pytest.approx(0.12, abs=0.0)


def test_canonical_pchip_is_scipy_with_no_extrapolation(spec):
    curve = spec.chord_distribution
    x = [point.r_over_R for point in curve.points]
    y = [point.chord_over_R for point in curve.points]
    expected = float(PchipInterpolator(x, y, extrapolate=False)(0.275))
    assert evaluate_curve(curve, 0.275) == expected


def test_prepared_vector_evaluation_matches_scalar_reference_at_knots_and_dense_queries(spec):
    rng = np.random.default_rng(40402)
    definitions = (
        (spec.chord_distribution, "chord_over_R"),
        (spec.twist_distribution, "twist_deg"),
        (spec.rake_distribution, "rake_over_R"),
        (spec.skew_distribution, "skew_over_R"),
        (spec.thickness_distribution, "thickness_ratio"),
    )
    for curve, value_name in definitions:
        x = np.asarray([point.r_over_R for point in curve.points])
        y = np.asarray([getattr(point, value_name) for point in curve.points])
        queries = np.unique(
            np.concatenate(
                [
                    x,
                    np.nextafter(x, x[0] - 1.0),
                    np.nextafter(x, x[-1] + 1.0),
                    np.linspace(x[0], x[-1], 1001),
                    rng.uniform(x[0], x[-1], 250),
                ]
            )
        )
        queries = queries[(queries >= x[0]) & (queries <= x[-1])]
        if curve.interpolation.value == "linear":
            expected = np.interp(queries, x, y)
        else:
            expected = np.asarray(PchipInterpolator(x, y, extrapolate=False)(queries))
        for index, knot in enumerate(x):
            expected[queries == knot] = y[index]
        prepared = prepare_curve(curve, value_name)
        actual = prepared.evaluate_many(queries)
        for knot, value in zip(x, y):
            assert actual[np.flatnonzero(queries == knot)[0]] == value
        assert actual == pytest.approx(expected, rel=0.0, abs=1e-15)
        assert np.asarray([prepared.evaluate(float(query)) for query in queries]) == pytest.approx(
            actual,
            rel=0.0,
            abs=0.0,
        )


def test_resolver_constructs_each_pchip_once_per_request(spec, monkeypatch):
    constructions = 0
    original = canonical.PchipInterpolator

    def recording_constructor(*args, **kwargs):
        nonlocal constructions
        constructions += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(canonical, "PchipInterpolator", recording_constructor)
    resolve_blade_spec(spec)
    expected = sum(
        distribution.interpolation.value == "pchip"
        for distribution in (
            spec.chord_distribution,
            spec.twist_distribution,
            spec.rake_distribution,
            spec.skew_distribution,
            spec.thickness_distribution,
        )
    )
    assert constructions == expected


def test_no_extrapolation(spec):
    with pytest.raises(ValueError, match="outside"):
        evaluate_curve(spec.chord_distribution, 0.199999)
    with pytest.raises(ValueError, match="outside"):
        evaluate_curve(spec.chord_distribution, 1.000001)


def test_all_user_controls_are_preserved_exactly(spec):
    resolved = resolve_blade_spec(spec)
    fields = {
        "chord": (spec.chord_distribution, "chord_over_R"),
        "twist": (spec.twist_distribution, "twist_deg"),
        "rake": (spec.rake_distribution, "rake_over_R"),
        "skew": (spec.skew_distribution, "skew_over_R"),
        "thickness": (spec.thickness_distribution, "thickness_ratio"),
    }
    for name, curve in resolved.curve_items():
        source, value_name = fields[name]
        actual = dict(zip(curve.parameter_vector, curve.value_vector))
        for point in source.points:
            assert actual[point.r_over_R] == getattr(point, value_name)


def test_adaptive_resolution_satisfies_tolerances(spec):
    resolved = resolve_blade_spec(spec)
    for _, curve in resolved.curve_items():
        assert curve.verification_locations >= 5001
        assert curve.max_canonical_vs_resolved_error <= curve.tolerance


def test_resolved_output_is_deterministic(spec):
    assert resolve_blade_spec(spec).model_dump() == resolve_blade_spec(spec).model_dump()


def test_physical_unit_tolerance_conversion(spec):
    profile = tolerance_profile(spec)
    radius = spec.diameter_mm / 2.0
    assert profile["chord"].stored_value == 0.005 / radius
    assert profile["rake"].stored_value == 0.005 / radius
    assert profile["skew"].stored_value == 0.005 / radius
    assert profile["twist"].stored_value == 0.002
    assert profile["thickness"].stored_value == 1e-5
