"""Canonical BladeSpec v0.1 curve mathematics.

``linear`` means ordinary piecewise-linear interpolation. ``pchip`` means
SciPy's :class:`PchipInterpolator` with extrapolation disabled. No backend
package is imported here: this module owns the product-level meaning of a
BladeSpec distribution.
"""

from __future__ import annotations

import math

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


def evaluate_curve(curve_spec, r_over_R: float, value_name: str | None = None) -> float:
    """Evaluate a BladeSpec distribution at one in-domain radial station.

    Control-point values are returned directly so the user values are
    preserved exactly rather than merely recovered by interpolation.
    """
    parameter = float(r_over_R)
    if not math.isfinite(parameter):
        raise ValueError("Curve evaluation parameter must be finite")
    parameters, values = curve_data(curve_spec, value_name)
    if parameter < parameters[0] or parameter > parameters[-1]:
        raise ValueError(f"r_over_R={parameter} is outside [{parameters[0]}, {parameters[-1]}]")
    exact = np.flatnonzero(parameters == parameter)
    if exact.size:
        return float(values[int(exact[0])])
    interpolation = Interpolation(curve_spec.interpolation)
    if interpolation is Interpolation.LINEAR:
        return float(np.interp(parameter, parameters, values))
    evaluator = PchipInterpolator(parameters, values, extrapolate=False)
    result = float(evaluator(parameter))
    if not math.isfinite(result):
        raise ValueError("Canonical PCHIP evaluation produced a non-finite value")
    return result
