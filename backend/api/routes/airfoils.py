"""Airfoil catalog, safe import, and canonical design-preview API."""

from __future__ import annotations

import math

import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import ValidationError

from bladegen.airfoils.canonical import naca_4digit_coordinates
from bladegen.airfoils.geometry_metrics import measure_airfoil
from bladegen.airfoils.importers import import_airfoil
from bladegen.airfoils.library import AirfoilLibrary
from bladegen.curves.canonical import evaluate_curve
from bladegen.curves.resolver import resolve_blade_spec
from bladegen.models import BladeSpec

router = APIRouter()
library = AirfoilLibrary()


@router.get("/airfoils/catalog")
def catalog() -> list[dict]:
    return library.catalog()


@router.get("/airfoils/{profile_id}")
def profile(profile_id: str) -> dict:
    try:
        return library.get(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Airfoil profile not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/airfoils/import", status_code=201)
async def upload_airfoil(
    request: Request,
    filename: str = Query(min_length=1, max_length=255),
    display_name: str = Query(min_length=1, max_length=120),
    normalize: bool = Query(default=False),
    source: str | None = Query(default=None, max_length=500),
    license_info: str | None = Query(default=None, max_length=500),
    notes: str | None = Query(default=None, max_length=1000),
) -> dict:
    try:
        imported = import_airfoil(await request.body(), filename, normalize=normalize)
        return library.add_imported(
            imported,
            display_name=display_name,
            original_filename=filename,
            source=source,
            license_info=license_info,
            notes=notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _profile_payload(section, resolved_section, spec: BladeSpec) -> dict:
    if section.airfoil.type == "naca4":
        source_upper, source_lower = naca_4digit_coordinates(section.airfoil.code)
        name = f"NACA {section.airfoil.code}"
        nominal = int(section.airfoil.code[2:]) / 100.0
    else:
        source_upper, source_lower = section.airfoil.upper, section.airfoil.lower
        name = "Imported coordinate profile"
        nominal = measure_airfoil(source_upper, source_lower).max_thickness_ratio
    effective = evaluate_curve(
        spec.thickness_distribution, section.r_over_R, "thickness_ratio"
    )
    return {
        "r_over_R": section.r_over_R,
        "name": name,
        "kind": section.airfoil.type,
        "local_chord_mm": resolved_section.local_chord_mm,
        "nominal_thickness_ratio": nominal,
        "effective_thickness_ratio": effective,
        "requested_trailing_edge_thickness_mm": (
            resolved_section.requested_trailing_edge_thickness_mm
        ),
        "source": {
            "upper": source_upper,
            "lower": source_lower,
            "metrics": measure_airfoil(source_upper, source_lower).to_dict(),
        },
        "resolved": {
            "upper": resolved_section.airfoil.upper,
            "lower": resolved_section.airfoil.lower,
            "metrics": measure_airfoil(
                resolved_section.airfoil.upper, resolved_section.airfoil.lower
            ).to_dict(),
        },
        "preview_status": "canonical design definition; final CAD validation not yet performed",
    }


@router.post("/design-preview")
def design_preview(payload: dict) -> dict:
    try:
        spec = BladeSpec.model_validate(payload)
        resolved = resolve_blade_spec(spec)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    radius_mm = spec.diameter_mm / 2.0
    definitions = (
        ("chord", spec.chord_distribution, "chord_over_R", radius_mm, "mm"),
        ("twist", spec.twist_distribution, "twist_deg", 1.0, "deg"),
        ("rake", spec.rake_distribution, "rake_over_R", radius_mm, "mm"),
        ("skew", spec.skew_distribution, "skew_over_R", radius_mm, "mm"),
        ("thickness", spec.thickness_distribution, "thickness_ratio", 100.0, "% t/c"),
    )
    distributions = {}
    for name, curve, field, scale, unit in definitions:
        locations = np.linspace(curve.points[0].r_over_R, curve.points[-1].r_over_R, 251)
        samples = [
            [float(location), evaluate_curve(curve, float(location), field) * scale]
            for location in locations
        ]
        controls = [
            [point.r_over_R, float(getattr(point, field)) * scale] for point in curve.points
        ]
        if any(not math.isfinite(value) for row in samples for value in row):
            raise HTTPException(status_code=422, detail=f"{name} preview is non-finite")
        distributions[name] = {
            "interpolation": curve.interpolation.value,
            "unit": unit,
            "samples": samples,
            "controls": controls,
        }
    return {
        "schema_version": "1",
        "stations": [
            _profile_payload(section, resolved_section, spec)
            for section, resolved_section in zip(spec.airfoil_sections, resolved.airfoil_sections)
        ],
        "distributions": distributions,
    }
