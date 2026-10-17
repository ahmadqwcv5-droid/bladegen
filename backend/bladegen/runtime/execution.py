"""Single-source worker execution timeout selection."""

from __future__ import annotations

import math
import os

DEFAULT_BUILD_TIMEOUT_SECONDS = 300.0


def resolve_build_timeout_seconds(explicit: float | int | None = None) -> float:
    """Resolve one positive finite worker timeout with constructor precedence."""
    value: object = explicit
    if value is None:
        value = os.getenv("BLADEGEN_BUILD_TIMEOUT", str(DEFAULT_BUILD_TIMEOUT_SECONDS))
    if isinstance(value, bool):
        raise ValueError("BLADEGEN_BUILD_TIMEOUT must be a positive finite number")
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("BLADEGEN_BUILD_TIMEOUT must be a positive finite number") from exc
    if not math.isfinite(timeout) or timeout <= 0.0:
        raise ValueError("BLADEGEN_BUILD_TIMEOUT must be a positive finite number")
    return timeout


def format_timeout_seconds(timeout: float) -> str:
    """Return a stable environment/manifest representation."""
    return str(int(timeout)) if timeout.is_integer() else format(timeout, ".15g")
