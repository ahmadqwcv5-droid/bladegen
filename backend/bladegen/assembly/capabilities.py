"""Lightweight assembly release capabilities with no OCP shape dependencies."""

from __future__ import annotations

CONTRACT_BLADE_COUNT_MIN = 2
CONTRACT_BLADE_COUNT_MAX = 8
SUPPORTED_BLADE_COUNTS = (2, 3, 4)


def capabilities() -> dict:
    return {
        "contract_blade_count_min": CONTRACT_BLADE_COUNT_MIN,
        "contract_blade_count_max": CONTRACT_BLADE_COUNT_MAX,
        "supported_blade_counts": list(SUPPORTED_BLADE_COUNTS),
        "release_policy": (
            "Blade counts 2, 3, and 4 are qualified in this release; "
            "higher contract-valid counts are not yet qualified."
        ),
    }


def require_supported_blade_count(blade_count: int) -> None:
    if blade_count not in SUPPORTED_BLADE_COUNTS:
        supported = ", ".join(str(value) for value in SUPPORTED_BLADE_COUNTS)
        raise ValueError(
            f"Blade count {blade_count} is unsupported in this release; "
            f"qualified choices are {supported}"
        )


def nominal_hub_guidance(
    diameter_mm: float,
    root_radius_ratio: float,
    hub_diameter_mm: float,
) -> dict:
    root_radius_mm = diameter_mm / 2.0 * root_radius_ratio
    hub_radius_mm = hub_diameter_mm / 2.0
    overlap_mm = hub_radius_mm - root_radius_mm
    return {
        "root_radius_mm": root_radius_mm,
        "hub_radius_mm": hub_radius_mm,
        "nominal_radial_overlap_mm": max(overlap_mm, 0.0),
        "nominal_radial_gap_mm": max(-overlap_mm, 0.0),
        "required_hub_diameter_bound_mm": diameter_mm * root_radius_ratio,
        "bound_is_exclusive": True,
        "passes_nominal_policy": overlap_mm > 0.0,
    }
