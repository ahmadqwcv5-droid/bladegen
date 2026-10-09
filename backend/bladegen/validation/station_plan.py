"""Deterministic, BladeSpec-driven final-CAD validation station planning."""

from __future__ import annotations

from dataclasses import dataclass

from bladegen.models import BladeSpec


@dataclass(frozen=True)
class ValidationStation:
    requested_r_over_R: float
    sampled_r_over_R: float
    roles: tuple[str, ...]
    endpoint: str | None = None
    sample_offset_r_over_R: float = 0.0

    @property
    def station_kind(self) -> str:
        if "airfoil_station" in self.roles:
            return "control"
        if "airfoil_midpoint" in self.roles:
            return "intermediate"
        return "distribution"


@dataclass(frozen=True)
class ValidationStationPlan:
    root_r_over_R: float
    tip_r_over_R: float
    stations: tuple[ValidationStation, ...]
    endpoint_policy: str = "domain-relative inward cuts evaluated at sampled radius"


def _endpoint_samples(spec: BladeSpec) -> dict[float, tuple[float, str, float]]:
    radii = [section.r_over_R for section in spec.airfoil_sections]
    root, tip = spec.root_radius_ratio, 1.0
    domain = tip - root
    root_gap = radii[1] - root
    tip_gap = tip - radii[-2]
    root_offset = min(root_gap * 0.025, domain * 0.00625)
    tip_offset = min(tip_gap * 0.0025, domain * 0.000625)
    if root_offset <= 0.0 or tip_offset <= 0.0:
        raise ValueError("Unable to derive positive root/tip validation offsets")
    return {
        root: (root + root_offset, "root", root_offset),
        tip: (tip - tip_offset, "tip", -tip_offset),
    }


def plan_validation_stations(spec: BladeSpec) -> ValidationStationPlan:
    """Plan unique CAD checks from the exact submitted engineering definition."""
    roles: dict[float, set[str]] = {}

    def add(radius: float, role: str) -> None:
        key = round(float(radius), 12)
        roles.setdefault(key, set()).add(role)

    airfoil_radii = [section.r_over_R for section in spec.airfoil_sections]
    for radius in airfoil_radii:
        add(radius, "airfoil_station")
    for left, right in zip(airfoil_radii, airfoil_radii[1:]):
        add((left + right) / 2.0, "airfoil_midpoint")

    distributions = {
        "chord_control": spec.chord_distribution,
        "twist_control": spec.twist_distribution,
        "rake_control": spec.rake_distribution,
        "skew_control": spec.skew_distribution,
        "thickness_control": spec.thickness_distribution,
    }
    for role, distribution in distributions.items():
        for point in distribution.points:
            add(point.r_over_R, role)

    endpoints = _endpoint_samples(spec)
    planned = []
    for requested in sorted(roles):
        sampled, endpoint, offset = endpoints.get(requested, (requested, None, 0.0))
        planned.append(
            ValidationStation(
                requested_r_over_R=requested,
                sampled_r_over_R=sampled,
                roles=tuple(sorted(roles[requested])),
                endpoint=endpoint,
                sample_offset_r_over_R=offset,
            )
        )
    return ValidationStationPlan(
        root_r_over_R=spec.root_radius_ratio,
        tip_r_over_R=1.0,
        stations=tuple(planned),
    )
