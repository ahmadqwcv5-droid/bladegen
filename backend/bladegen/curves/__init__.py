"""Canonical, backend-independent curve evaluation and resolution."""

from .canonical import evaluate_curve
from .resolver import RESOLVER_VERSION, resolve_blade_spec, resolve_curve

__all__ = ["RESOLVER_VERSION", "evaluate_curve", "resolve_blade_spec", "resolve_curve"]
