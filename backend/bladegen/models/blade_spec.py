"""Backend-neutral BladeSpec v0.1 and v0.2 product schema."""

from __future__ import annotations

import math
from enum import Enum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Interpolation(str, Enum):
    """Product-level radial interpolation method."""

    LINEAR = "linear"
    PCHIP = "pchip"


class RotationDirection(str, Enum):
    """Direction relative to the product's standard propeller-axis convention."""

    NORMAL = "normal"
    REVERSE = "reverse"


UnitCoordinate = Annotated[
    float,
    Field(
        description="Coordinate normalized by local chord; normal-offset contours may extend slightly beyond 0..1."
    ),
]


class AirfoilCoordinates(StrictModel):
    """Unmodified normalized upper and lower airfoil coordinate lists."""

    type: Literal["coordinates"] = Field(
        description="Airfoil representation discriminator; v0.1 and v0.2 support coordinates."
    )
    upper: list[tuple[UnitCoordinate, float]] = Field(
        min_length=3,
        description="Ordered upper-surface [x/c, y/c] points in supplied contour order.",
    )
    lower: list[tuple[UnitCoordinate, float]] = Field(
        min_length=3,
        description="Ordered lower-surface [x/c, y/c] points in supplied contour order.",
    )

    @model_validator(mode="after")
    def finite_coordinates(self) -> "AirfoilCoordinates":
        for surface_name, points in (("upper", self.upper), ("lower", self.lower)):
            if any(not math.isfinite(value) for point in points for value in point):
                raise ValueError(f"{surface_name} contains a non-finite coordinate")
        return self


class Naca4Airfoil(StrictModel):
    """Canonical NACA 4-digit product input resolved before any backend."""

    type: Literal["naca4"]
    code: str = Field(pattern=r"^[0-9]{4}$")


AirfoilDefinition = Annotated[AirfoilCoordinates | Naca4Airfoil, Field(discriminator="type")]


class AirfoilSection(StrictModel):
    r_over_R: float = Field(
        gt=0.0, le=1.0, description="Section radial location divided by blade radius."
    )
    airfoil: AirfoilDefinition = Field(
        description="Normalized section contour; finite or sharp trailing edge is preserved."
    )
    trailing_edge_thickness_mm: float | None = Field(
        default=None,
        ge=0.0,
        description="v0.2 physical chord-normal trailing-edge thickness in millimeters.",
    )
    thickness_override_ratio: float | None = Field(
        default=None,
        gt=0.0,
        le=1.0,
        description=(
            "Explicit engineering override of nominal NACA thickness; omit to require "
            "the thickness distribution to match the selected NACA code."
        ),
    )


class ChordPoint(StrictModel):
    r_over_R: float = Field(gt=0.0, le=1.0, description="Radial station r/R.")
    chord_over_R: float = Field(gt=0.0, description="Local chord divided by blade radius.")


class TwistPoint(StrictModel):
    r_over_R: float = Field(gt=0.0, le=1.0, description="Radial station r/R.")
    twist_deg: float = Field(description="Local geometric blade twist in degrees.")


class RakePoint(StrictModel):
    r_over_R: float = Field(gt=0.0, le=1.0, description="Radial station r/R.")
    rake_over_R: float = Field(description="Local axial rake divided by blade radius.")


class SkewPoint(StrictModel):
    r_over_R: float = Field(gt=0.0, le=1.0, description="Radial station r/R.")
    skew_over_R: float = Field(description="Local tangential skew divided by blade radius.")


class ThicknessPoint(StrictModel):
    r_over_R: float = Field(gt=0.0, le=1.0, description="Radial station r/R.")
    thickness_ratio: float = Field(
        gt=0.0, description="Local maximum thickness divided by local chord."
    )


class DistributionBase(StrictModel):
    interpolation: Interpolation = Field(
        description="Backend-independent radial interpolation algorithm."
    )

    @staticmethod
    def ensure_ordered(points: list, label: str) -> None:
        if len(points) < 2:
            raise ValueError(f"{label} requires at least two points")
        radii = [point.r_over_R for point in points]
        if any(right <= left for left, right in zip(radii, radii[1:])):
            raise ValueError(f"{label} r_over_R values must be strictly increasing")


class ChordDistribution(DistributionBase):
    points: list[ChordPoint] = Field(description="Chord control points.")

    @model_validator(mode="after")
    def ordered(self) -> "ChordDistribution":
        self.ensure_ordered(self.points, "chord_distribution")
        return self


class TwistDistribution(DistributionBase):
    points: list[TwistPoint] = Field(description="Twist control points.")

    @model_validator(mode="after")
    def ordered(self) -> "TwistDistribution":
        self.ensure_ordered(self.points, "twist_distribution")
        return self


class RakeDistribution(DistributionBase):
    points: list[RakePoint] = Field(description="Rake control points.")

    @model_validator(mode="after")
    def ordered(self) -> "RakeDistribution":
        self.ensure_ordered(self.points, "rake_distribution")
        return self


class SkewDistribution(DistributionBase):
    points: list[SkewPoint] = Field(description="Skew control points.")

    @model_validator(mode="after")
    def ordered(self) -> "SkewDistribution":
        self.ensure_ordered(self.points, "skew_distribution")
        return self


class ThicknessDistribution(DistributionBase):
    points: list[ThicknessPoint] = Field(description="Thickness-ratio control points.")

    @model_validator(mode="after")
    def ordered(self) -> "ThicknessDistribution":
        self.ensure_ordered(self.points, "thickness_distribution")
        return self


class BladeSpec(StrictModel):
    """Neutral engineering definition for one aerodynamic blade."""

    schema_version: Literal["0.1", "0.2"] = Field(
        default="0.1", description="BladeSpec schema version."
    )
    name: str = Field(min_length=1, description="User-facing blade design name.")
    units: Literal["mm"] = Field(description="Explicit length system; BladeSpec uses millimeters.")
    diameter_mm: float = Field(gt=0.0, description="Full propeller diameter in millimeters.")
    root_radius_ratio: float = Field(
        gt=0.0, lt=1.0, description="Blade aerodynamic root radius divided by radius."
    )
    reference_axis_x_over_c: float = Field(
        ge=0.0,
        le=1.0,
        description="Chordwise construction and pitch reference axis x/c.",
    )
    rotation_direction: RotationDirection = Field(
        description="Normal or reverse blade rotation convention."
    )
    airfoil_sections: list[AirfoilSection] = Field(
        min_length=2, description="Radially ordered normalized airfoil sections."
    )
    chord_distribution: ChordDistribution
    twist_distribution: TwistDistribution
    rake_distribution: RakeDistribution
    skew_distribution: SkewDistribution
    thickness_distribution: ThicknessDistribution

    @model_validator(mode="after")
    def radial_domains(self) -> "BladeSpec":
        if self.schema_version == "0.1" and any(
            section.airfoil.type != "coordinates" for section in self.airfoil_sections
        ):
            raise ValueError("NACA product inputs are available only in BladeSpec v0.2")
        te_values = [section.trailing_edge_thickness_mm for section in self.airfoil_sections]
        if self.schema_version == "0.1" and any(value is not None for value in te_values):
            raise ValueError("trailing_edge_thickness_mm is available only in BladeSpec v0.2")
        if self.schema_version == "0.2" and any(value is None for value in te_values):
            raise ValueError("BladeSpec v0.2 requires trailing_edge_thickness_mm per section")
        sections = [section.r_over_R for section in self.airfoil_sections]
        if any(right <= left for left, right in zip(sections, sections[1:])):
            raise ValueError("airfoil_sections r_over_R values must be strictly increasing")
        sequences = {
            "airfoil_sections": sections,
            "chord_distribution": [p.r_over_R for p in self.chord_distribution.points],
            "twist_distribution": [p.r_over_R for p in self.twist_distribution.points],
            "rake_distribution": [p.r_over_R for p in self.rake_distribution.points],
            "skew_distribution": [p.r_over_R for p in self.skew_distribution.points],
            "thickness_distribution": [p.r_over_R for p in self.thickness_distribution.points],
        }
        for name, radii in sequences.items():
            if not math.isclose(radii[0], self.root_radius_ratio, abs_tol=1e-12):
                raise ValueError(f"{name} must start at root_radius_ratio")
            if not math.isclose(radii[-1], 1.0, abs_tol=1e-12):
                raise ValueError(f"{name} must end at r_over_R=1.0")
        return self

    @classmethod
    def from_json(cls, path: str | Path) -> "BladeSpec":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))
