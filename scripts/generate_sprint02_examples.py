#!/usr/bin/env python3
"""Generate deterministic Sprint 02 acceptance BladeSpec v0.2 examples."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from bladegen.models import BladeSpec


ROOT = Path(__file__).resolve().parents[1]


def distribution(interpolation: str, radii: list[float], field: str, values: list[float]):
    return {
        "interpolation": interpolation,
        "points": [
            {"r_over_R": radius, field: value}
            for radius, value in zip(radii, values, strict=True)
        ],
    }


def section(radius: float, code: str, te_mm: float, override: float | None = None):
    result = {
        "r_over_R": radius,
        "airfoil": {"type": "naca4", "code": code},
        "trailing_edge_thickness_mm": te_mm,
    }
    if override is not None:
        result["thickness_override_ratio"] = override
    return result


def write(name: str, data: dict) -> None:
    validated = BladeSpec.model_validate(data)
    (ROOT / "examples" / name).write_text(
        validated.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )


baseline = json.loads(
    (ROOT / "examples" / "custom_multi_airfoil_finite_te.json").read_text()
)

case_a = deepcopy(baseline)
case_a.update(
    name="sprint02_case_a_three_section",
    root_radius_ratio=0.25,
    airfoil_sections=[
        section(0.25, "0012", 0.60),
        section(0.625, "0012", 0.45),
        section(1.0, "0012", 0.30),
    ],
    chord_distribution=distribution(
        "pchip", [0.25, 0.45, 0.72, 1.0], "chord_over_R", [0.32, 0.30, 0.20, 0.10]
    ),
    twist_distribution=distribution(
        "pchip", [0.25, 0.50, 0.80, 1.0], "twist_deg", [34.0, 28.0, 18.0, 10.0]
    ),
    rake_distribution=distribution(
        "linear", [0.25, 0.70, 1.0], "rake_over_R", [0.0, 0.02, 0.03]
    ),
    skew_distribution=distribution(
        "linear", [0.25, 0.55, 0.85, 1.0], "skew_over_R", [0.0, -0.01, -0.03, -0.04]
    ),
    thickness_distribution=distribution(
        "linear", [0.25, 0.55, 1.0], "thickness_ratio", [0.12, 0.12, 0.12]
    ),
)
write("sprint02_case_a_three_section.json", case_a)

radii = [0.18, 0.28, 0.40, 0.51, 0.63, 0.76, 0.88, 1.00]
codes = ["4415", "4412", "2412", "0012", "0010", "0009", "0008", "0008"]
ratios = [0.15, 0.12, 0.12, 0.12, 0.10, 0.09, 0.08, 0.08]
tes = [1.00, 0.90, 0.75, 0.65, 0.50, 0.40, 0.30, 0.20]
case_c = deepcopy(baseline)
case_c.update(
    name="sprint02_case_c_eight_section",
    root_radius_ratio=0.18,
    airfoil_sections=[section(r, c, te) for r, c, te in zip(radii, codes, tes, strict=True)],
    chord_distribution=distribution(
        "pchip", [0.18, 0.34, 0.55, 0.72, 0.90, 1.0], "chord_over_R", [0.34, 0.335, 0.28, 0.21, 0.14, 0.09]
    ),
    twist_distribution=distribution(
        "pchip", [0.18, 0.30, 0.47, 0.68, 0.84, 1.0], "twist_deg", [43.0, 38.0, 31.0, 23.0, 16.0, 10.0]
    ),
    rake_distribution=distribution(
        "pchip", [0.18, 0.50, 0.75, 1.0], "rake_over_R", [0.0, 0.015, 0.03, 0.04]
    ),
    skew_distribution=distribution(
        "pchip", [0.18, 0.38, 0.62, 0.82, 1.0], "skew_over_R", [0.0, -0.008, -0.022, -0.04, -0.05]
    ),
    thickness_distribution=distribution("linear", radii, "thickness_ratio", ratios),
)
write("sprint02_case_c_eight_section.json", case_c)

override = deepcopy(case_a)
override["name"] = "sprint02_naca0008_thickness_override"
override["airfoil_sections"] = [section(r, "0008", te, 0.10) for r, te in zip([0.25, 0.625, 1.0], [0.60, 0.45, 0.30], strict=True)]
override["thickness_distribution"] = distribution(
    "linear", [0.25, 0.55, 1.0], "thickness_ratio", [0.10, 0.10, 0.10]
)
write("sprint02_naca0008_thickness_override.json", override)

print("Generated and model-validated Sprint 02 examples")
