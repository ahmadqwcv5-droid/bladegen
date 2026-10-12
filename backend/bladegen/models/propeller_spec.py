"""Backend-neutral PropellerSpec v0.1 product contract."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .blade_spec import BladeSpec, StrictModel


class AssemblySpec(StrictModel):
    """Simple Sprint 04A hub, bore, and cyclic blade placement definition."""

    blade_count: int = Field(ge=2, le=8)
    hub_diameter_mm: float = Field(gt=0.0)
    hub_length_mm: float = Field(gt=0.0)
    shaft_bore_diameter_mm: float = Field(gt=0.0)
    initial_azimuth_deg: float = 0.0

    @model_validator(mode="after")
    def dimensions_are_compatible(self) -> "AssemblySpec":
        values = (
            self.hub_diameter_mm,
            self.hub_length_mm,
            self.shaft_bore_diameter_mm,
            self.initial_azimuth_deg,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("assembly dimensions and azimuth must be finite")
        if self.shaft_bore_diameter_mm >= self.hub_diameter_mm:
            raise ValueError("shaft_bore_diameter_mm must be smaller than hub_diameter_mm")
        return self


class PropellerSpec(StrictModel):
    """Neutral reusable definition of one blade assembled around a simple hub."""

    schema_version: Literal["0.1"] = "0.1"
    name: str = Field(min_length=1)
    units: Literal["mm"] = "mm"
    blade_spec: BladeSpec
    assembly: AssemblySpec

    @model_validator(mode="after")
    def compatible_contracts(self) -> "PropellerSpec":
        if self.blade_spec.schema_version != "0.2":
            raise ValueError("PropellerSpec v0.1 requires a complete BladeSpec v0.2")
        if self.blade_spec.units != self.units:
            raise ValueError("PropellerSpec and nested BladeSpec units must match")
        if self.assembly.hub_diameter_mm >= self.blade_spec.diameter_mm:
            raise ValueError("hub_diameter_mm must be smaller than the propeller diameter")
        nominal_root_radius = self.blade_spec.diameter_mm / 2.0 * self.blade_spec.root_radius_ratio
        if self.assembly.hub_diameter_mm / 2.0 <= nominal_root_radius:
            raise ValueError(
                "hub radius must extend beyond the nominal blade root radius to permit "
                "positive-volume connection"
            )
        return self

    @classmethod
    def from_json(cls, path: str | Path) -> "PropellerSpec":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))
