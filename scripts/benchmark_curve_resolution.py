#!/usr/bin/env python3
"""Reproducible Sprint 04B canonical-evaluator performance qualification."""

from __future__ import annotations

import json
import platform
import statistics
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from bladegen.curves.canonical import evaluate_curve, prepare_curve  # noqa: E402
from bladegen.curves.resolver import resolve_blade_spec  # noqa: E402
from bladegen.models import BladeSpec  # noqa: E402


def synthetic_spec(point_count: int) -> BladeSpec:
    source = BladeSpec.from_json(ROOT / "examples" / "custom_multi_airfoil_finite_te.json")
    root = source.root_radius_ratio
    radii = np.linspace(root, 1.0, point_count)
    payload = source.model_dump(mode="json")
    payload["airfoil_sections"] = [
        {
            "r_over_R": root,
            "airfoil": {"type": "naca4", "code": "0012"},
            "trailing_edge_thickness_mm": 0.0,
        },
        {
            "r_over_R": 1.0,
            "airfoil": {"type": "naca4", "code": "0012"},
            "trailing_edge_thickness_mm": 0.0,
        },
    ]
    definitions = {
        "chord_distribution": ("chord_over_R", lambda r: 0.42 - 0.26 * r + 0.025 * np.sin(5 * r)),
        "twist_distribution": ("twist_deg", lambda r: 34.0 - 27.0 * r + 1.2 * np.sin(4 * r)),
        "rake_distribution": ("rake_over_R", lambda r: -0.02 + 0.045 * (r - root)),
        "skew_distribution": ("skew_over_R", lambda r: -0.03 * np.sin(np.pi * (r - root) / (1 - root))),
        "thickness_distribution": ("thickness_ratio", lambda _r: 0.12),
    }
    for key, (field, function) in definitions.items():
        payload[key] = {
            "interpolation": "pchip",
            "points": [
                {"r_over_R": float(radius), field: float(function(float(radius)))}
                for radius in radii
            ],
        }
    return BladeSpec.model_validate(payload)


def percentile95(values: list[float]) -> float:
    return float(np.percentile(np.asarray(values), 95, method="linear"))


def timings(operation, repetitions: int = 20) -> dict:
    cold_started = time.perf_counter()
    operation()
    cold = time.perf_counter() - cold_started
    warm = []
    for _ in range(repetitions):
        started = time.perf_counter()
        operation()
        warm.append(time.perf_counter() - started)
    return {
        "cold_first_seconds": cold,
        "warm_repetitions": repetitions,
        "warm_median_seconds": statistics.median(warm),
        "warm_p95_seconds": percentile95(warm),
        "warm_max_seconds": max(warm),
    }


def dense_legacy(spec: BladeSpec) -> None:
    definitions = (
        (spec.chord_distribution, "chord_over_R"),
        (spec.twist_distribution, "twist_deg"),
        (spec.rake_distribution, "rake_over_R"),
        (spec.skew_distribution, "skew_over_R"),
        (spec.thickness_distribution, "thickness_ratio"),
    )
    for curve, field in definitions:
        locations = np.linspace(curve.points[0].r_over_R, curve.points[-1].r_over_R, 5001)
        np.asarray([evaluate_curve(curve, float(location), field) for location in locations])


def dense_prepared(spec: BladeSpec) -> None:
    definitions = (
        (spec.chord_distribution, "chord_over_R"),
        (spec.twist_distribution, "twist_deg"),
        (spec.rake_distribution, "rake_over_R"),
        (spec.skew_distribution, "skew_over_R"),
        (spec.thickness_distribution, "thickness_ratio"),
    )
    for curve, field in definitions:
        locations = np.linspace(curve.points[0].r_over_R, curve.points[-1].r_over_R, 5001)
        prepare_curve(curve, field).evaluate_many(locations)


def main() -> None:
    result = {
        "machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "numpy": np.__version__,
        },
        "verification_locations_per_curve": 5001,
        "pchip_constructors": {
            "legacy_dense_phase": 5 * 5001,
            "prepared_dense_phase": 5,
            "current_full_resolution": 5,
        },
        "cases": {},
    }
    for count in (40, 200):
        spec = synthetic_spec(count)
        result["cases"][str(count)] = {
            "points_per_curve": count,
            "legacy_dense_evaluation": timings(lambda: dense_legacy(spec)),
            "prepared_dense_evaluation": timings(lambda: dense_prepared(spec)),
            "current_full_resolution": timings(lambda: resolve_blade_spec(spec)),
        }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
