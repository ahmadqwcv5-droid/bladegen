"""Internal, backend-neutral resolved blade representation."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .blade_spec import AirfoilCoordinates, BladeSpec, Interpolation, StrictModel


class ResolvedCurve(StrictModel):
    """Deterministic piecewise-linear realization of a product curve."""

    parameter_vector: tuple[float, ...] = Field(min_length=2)
    value_vector: tuple[float, ...] = Field(min_length=2)
    representation: Literal["linear"] = "linear"
    source_interpolation: Interpolation
    original_control_count: int = Field(ge=2)
    tolerance: float = Field(gt=0.0)
    tolerance_unit: str
    stored_value_tolerance: float = Field(gt=0.0)
    verification_locations: int = Field(ge=5001)
    max_canonical_vs_resolved_error: float = Field(ge=0.0)
    max_canonical_vs_resolved_error_stored: float = Field(ge=0.0)

    @model_validator(mode="after")
    def vectors_are_consistent(self) -> "ResolvedCurve":
        if len(self.parameter_vector) != len(self.value_vector):
            raise ValueError("Resolved parameter and value vector lengths differ")
        if any(
            right <= left for left, right in zip(self.parameter_vector, self.parameter_vector[1:])
        ):
            raise ValueError("Resolved parameters must be strictly increasing")
        return self


class ResolvedAirfoilSection(StrictModel):
    """Backend-neutral section coordinates after canonical TE processing."""

    r_over_R: float
    airfoil: AirfoilCoordinates
    trailing_edge_policy: Literal["unchanged", "smooth_chord_normal"]
    local_chord_mm: float = Field(gt=0.0)
    requested_trailing_edge_thickness_mm: float = Field(ge=0.0)
    generated_trailing_edge_thickness_mm: float = Field(ge=0.0)
    mathematical_error_mm: float = Field(ge=0.0)


class ResolvedBladeSpec(StrictModel):
    """BladeSpec geometry plus curves resolved before any backend is invoked."""

    resolver_version: str
    tolerance_profile: str
    source_bladespec: BladeSpec
    airfoil_sections: tuple[ResolvedAirfoilSection, ...]
    chord_curve: ResolvedCurve
    twist_curve: ResolvedCurve
    rake_curve: ResolvedCurve
    skew_curve: ResolvedCurve
    thickness_curve: ResolvedCurve

    @property
    def radius_mm(self) -> float:
        return self.source_bladespec.diameter_mm / 2.0

    def curve_items(self) -> tuple[tuple[str, ResolvedCurve], ...]:
        return (
            ("chord", self.chord_curve),
            ("twist", self.twist_curve),
            ("rake", self.rake_curve),
            ("skew", self.skew_curve),
            ("thickness", self.thickness_curve),
        )
