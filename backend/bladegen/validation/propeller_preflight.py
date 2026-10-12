"""Structured PropellerSpec parsing and inexpensive release preflight checks."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from pydantic import ValidationError

from bladegen.assembly.capabilities import (
    CONTRACT_BLADE_COUNT_MAX,
    CONTRACT_BLADE_COUNT_MIN,
    SUPPORTED_BLADE_COUNTS,
    nominal_hub_guidance,
)
from bladegen.models import PropellerSpec


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    field: str
    message: str
    context: dict[str, Any] | None = None
    operator: str | None = None
    bound: float | int | None = None

    def to_dict(self) -> dict:
        return {key: value for key, value in asdict(self).items() if value is not None}


class PropellerPreflightError(ValueError):
    def __init__(self, issues: list[ValidationIssue]):
        self.issues = issues
        super().__init__("; ".join(issue.message for issue in issues))

    @property
    def detail(self) -> str:
        return str(self)

    def issue_dicts(self) -> list[dict]:
        return [issue.to_dict() for issue in self.issues]


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _raw_issues(payload: Any, require_runtime_support: bool) -> list[ValidationIssue]:
    if not isinstance(payload, dict):
        return [ValidationIssue("invalid_document", "", "PropellerSpec must be a JSON object.")]
    assembly = payload.get("assembly")
    blade = payload.get("blade_spec")
    if not isinstance(assembly, dict):
        return [
            ValidationIssue(
                "assembly_required",
                "assembly",
                "A complete assembly object is required.",
            )
        ]

    issues: list[ValidationIssue] = []
    blade_count = assembly.get("blade_count")
    valid_integer_count = isinstance(blade_count, int) and not isinstance(blade_count, bool)
    if not valid_integer_count or not (
        CONTRACT_BLADE_COUNT_MIN <= blade_count <= CONTRACT_BLADE_COUNT_MAX
    ):
        issues.append(
            ValidationIssue(
                "blade_count_invalid",
                "assembly.blade_count",
                (
                    "Blade count must be an integer from "
                    f"{CONTRACT_BLADE_COUNT_MIN} through {CONTRACT_BLADE_COUNT_MAX}."
                ),
                {
                    "contract_min": CONTRACT_BLADE_COUNT_MIN,
                    "contract_max": CONTRACT_BLADE_COUNT_MAX,
                },
            )
        )
    elif require_runtime_support and blade_count not in SUPPORTED_BLADE_COUNTS:
        issues.append(
            ValidationIssue(
                "blade_count_unsupported",
                "assembly.blade_count",
                (
                    f"Blade count {blade_count} is unsupported in this release. "
                    "Choose 2, 3, or 4 blades."
                ),
                {
                    "requested_blade_count": blade_count,
                    "supported_blade_counts": list(SUPPORTED_BLADE_COUNTS),
                },
            )
        )

    numeric: dict[str, float] = {}
    for field in (
        "hub_diameter_mm",
        "hub_length_mm",
        "shaft_bore_diameter_mm",
        "initial_azimuth_deg",
    ):
        value = _number(assembly.get(field))
        path = f"assembly.{field}"
        if value is None or not math.isfinite(value):
            issues.append(
                ValidationIssue(
                    "finite_number_required",
                    path,
                    f"{field} must be a finite number.",
                )
            )
        else:
            numeric[field] = value
            if field != "initial_azimuth_deg" and value <= 0.0:
                issues.append(
                    ValidationIssue(
                        "positive_dimension_required",
                        path,
                        f"{field} must be greater than zero.",
                        {field: value},
                        operator=">",
                        bound=0.0,
                    )
                )

    hub_diameter = numeric.get("hub_diameter_mm")
    bore_diameter = numeric.get("shaft_bore_diameter_mm")
    if (
        hub_diameter is not None
        and bore_diameter is not None
        and hub_diameter > 0.0
        and bore_diameter >= hub_diameter
    ):
        issues.append(
            ValidationIssue(
                "bore_smaller_than_hub_required",
                "assembly.shaft_bore_diameter_mm",
                "Shaft bore diameter must be smaller than hub diameter.",
                {
                    "shaft_bore_diameter_mm": bore_diameter,
                    "hub_diameter_mm": hub_diameter,
                },
                operator="<",
                bound=hub_diameter,
            )
        )

    if isinstance(blade, dict):
        diameter = _number(blade.get("diameter_mm"))
        root_ratio = _number(blade.get("root_radius_ratio"))
        if (
            diameter is not None
            and root_ratio is not None
            and math.isfinite(diameter)
            and math.isfinite(root_ratio)
            and diameter > 0.0
            and 0.0 < root_ratio < 1.0
            and hub_diameter is not None
            and hub_diameter > 0.0
        ):
            if hub_diameter >= diameter:
                issues.append(
                    ValidationIssue(
                        "hub_smaller_than_propeller_required",
                        "assembly.hub_diameter_mm",
                        "Hub diameter must be smaller than the propeller diameter.",
                        {
                            "hub_diameter_mm": hub_diameter,
                            "propeller_diameter_mm": diameter,
                        },
                        operator="<",
                        bound=diameter,
                    )
                )
            guidance = nominal_hub_guidance(diameter, root_ratio, hub_diameter)
            if not guidance["passes_nominal_policy"]:
                issues.append(
                    ValidationIssue(
                        "hub_root_nominal_overlap_required",
                        "assembly.hub_diameter_mm",
                        (
                            "Hub diameter is too small for the current blade root. "
                            f"Blade root radius: {guidance['root_radius_mm']:g} mm. "
                            f"Hub radius: {guidance['hub_radius_mm']:g} mm. "
                            f"Nominal radial gap: {guidance['nominal_radial_gap_mm']:g} mm. "
                            "The current assembly policy requires a hub diameter greater than "
                            f"{guidance['required_hub_diameter_bound_mm']:g} mm."
                        ),
                        {
                            "hub_diameter_mm": hub_diameter,
                            "root_radius_mm": guidance["root_radius_mm"],
                            "hub_radius_mm": guidance["hub_radius_mm"],
                            "nominal_gap_mm": guidance["nominal_radial_gap_mm"],
                            "required_diameter_bound_mm": guidance[
                                "required_hub_diameter_bound_mm"
                            ],
                            "bound_is_exclusive": True,
                        },
                        operator=">",
                        bound=guidance["required_hub_diameter_bound_mm"],
                    )
                )
    return issues


def _pydantic_issues(error: ValidationError) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for item in error.errors(include_url=False, include_input=False):
        location = ".".join(str(part) for part in item.get("loc", ()))
        message = str(item.get("msg", "Invalid value"))
        code = "invalid_propeller_spec"
        if location.startswith("blade_spec") or not location:
            code = "invalid_blade_spec" if location.startswith("blade_spec") else code
        elif location.startswith("assembly.blade_count"):
            code = "blade_count_invalid"
        elif location.startswith("assembly"):
            code = "invalid_assembly_value"
        issues.append(
            ValidationIssue(
                code,
                location,
                f"{location or 'PropellerSpec'}: {message}.",
            )
        )
    return issues


def validate_propeller_payload(
    payload: Any,
    *,
    require_runtime_support: bool = True,
) -> PropellerSpec:
    issues = _raw_issues(payload, require_runtime_support)
    if issues:
        raise PropellerPreflightError(issues)
    try:
        return PropellerSpec.model_validate(payload)
    except ValidationError as exc:
        raise PropellerPreflightError(_pydantic_issues(exc)) from exc
