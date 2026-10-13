"""Canonical BladeSpec v0.1 curve mathematics.

``linear`` means ordinary piecewise-linear interpolation. ``pchip`` means
SciPy's :class:`PchipInterpolator` with extrapolation disabled. No backend
package is imported here: this module owns the product-level meaning of a
BladeSpec distribution.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy.interpolate import PchipInterpolator

from bladegen.models.blade_spec import Interpolation

_VALUE_FIELDS = (
    "chord_over_R",
    "twist_deg",
    "rake_over_R",
    "skew_over_R",
    "thickness_ratio",
)


def curve_value_name(curve_spec) -> str:
    """Return the single engineering-value field used by a distribution."""
    matches = [
        name for name in _VALUE_FIELDS if curve_spec.points and hasattr(curve_spec.points[0], name)
    ]
    if len(matches) != 1:
        raise TypeError("Unable to identify the BladeSpec distribution value field")
    return matches[0]


def curve_data(curve_spec, value_name: str | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Extract validated finite, strictly increasing curve vectors."""
    field = value_name or curve_value_name(curve_spec)
    parameters = np.asarray([point.r_over_R for point in curve_spec.points], dtype=float)
    values = np.asarray([getattr(point, field) for point in curve_spec.points], dtype=float)
    if parameters.size < 2 or parameters.shape != values.shape:
        raise ValueError("A canonical curve requires at least two parameter/value pairs")
    if not np.all(np.isfinite(parameters)) or not np.all(np.isfinite(values)):
        raise ValueError("Canonical curve data must be finite")
    if np.any(np.diff(parameters) <= 0.0):
        raise ValueError("Canonical curve parameters must be strictly increasing")
    return parameters, values


class PreparedCurveEvaluator:
    """Request-local canonical evaluator with one interpolation construction.

    Scalar and array evaluation share the same validated immutable vectors.
    Exact user controls are restored explicitly after interpolation so bulk
    evaluation has the same knot semantics as the original scalar function.
    """

    def __init__(self, curve_spec, value_name: str | None = None):
        self.parameters, self.values = curve_data(curve_spec, value_name)
        self.interpolation = Interpolation(curve_spec.interpolation)
        self._evaluator: Any | None = None
        if self.interpolation is Interpolation.PCHIP:
            self._evaluator = PchipInterpolator(
                self.parameters,
                self.values,
                extrapolate=False,
            )

    def evaluate_many(self, r_over_R) -> np.ndarray:
        queries = np.asarray(r_over_R, dtype=float)
        flat = queries.reshape(-1)
        if not np.all(np.isfinite(flat)):
            raise ValueError("Curve evaluation parameters must be finite")
        if np.any(flat < self.parameters[0]) or np.any(flat > self.parameters[-1]):
            outside = flat[(flat < self.parameters[0]) | (flat > self.parameters[-1])][0]
            raise ValueError(
                f"r_over_R={float(outside)} is outside "
                f"[{self.parameters[0]}, {self.parameters[-1]}]"
            )
        if self.interpolation is Interpolation.LINEAR:
            evaluated = np.asarray(
                np.interp(flat, self.parameters, self.values),
                dtype=float,
            )
        else:
            evaluated = np.asarray(self._evaluator(flat), dtype=float)

        insertion = np.searchsorted(self.parameters, flat)
        candidates = np.clip(insertion, 0, len(self.parameters) - 1)
        exact = self.parameters[candidates] == flat
        evaluated[exact] = self.values[candidates[exact]]
        if not np.all(np.isfinite(evaluated)):
            raise ValueError("Canonical curve evaluation produced a non-finite value")
        return evaluated.reshape(queries.shape)

    def evaluate(self, r_over_R: float) -> float:
        return float(self.evaluate_many(float(r_over_R)))


def prepare_curve(curve_spec, value_name: str | None = None) -> PreparedCurveEvaluator:
    """Prepare one immutable distribution for repeated scalar/array queries."""
    return PreparedCurveEvaluator(curve_spec, value_name)


def evaluate_curve(curve_spec, r_over_R: float, value_name: str | None = None) -> float:
    """Evaluate a BladeSpec distribution at one in-domain radial station.

    Control-point values are returned directly so the user values are
    preserved exactly rather than merely recovered by interpolation.
    """
    parameter = float(r_over_R)
    if not math.isfinite(parameter):
        raise ValueError("Curve evaluation parameter must be finite")
    return prepare_curve(curve_spec, value_name).evaluate(parameter)
