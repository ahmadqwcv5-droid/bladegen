"""PropellerSpec capability, validation, and serialized build endpoints."""

from typing import Any

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from api.schemas import BuildAccepted
from api.services.jobs import jobs
from bladegen.assembly.capabilities import capabilities, nominal_hub_guidance
from bladegen.validation.propeller_preflight import (
    PropellerPreflightError,
    validate_propeller_payload,
)

router = APIRouter(prefix="/propellers", tags=["propellers"])


def _validate(payload: Any):
    try:
        return validate_propeller_payload(payload, require_runtime_support=True)
    except PropellerPreflightError as exc:
        return JSONResponse(
            status_code=422,
            content={"detail": exc.detail, "issues": exc.issue_dicts()},
        )


@router.get("/capabilities")
def propeller_capabilities() -> dict:
    return capabilities()


@router.post("/validate")
def validate_propeller(payload: Any = Body(...)) -> dict:
    spec = _validate(payload)
    if isinstance(spec, JSONResponse):
        return spec
    guidance = nominal_hub_guidance(
        spec.blade_spec.diameter_mm,
        spec.blade_spec.root_radius_ratio,
        spec.assembly.hub_diameter_mm,
    )
    return {
        "valid": True,
        "schema_version": spec.schema_version,
        "blade_count": spec.assembly.blade_count,
        "airfoil_sections_per_blade": len(spec.blade_spec.airfoil_sections),
        "rotation_axis": "X",
        "nominal_radial_overlap_mm": guidance["nominal_radial_overlap_mm"],
        "nominal_hub_guidance": guidance,
        "capabilities": capabilities(),
        "geometric_qualification": (
            "Nominal preflight passed; final positive-volume overlap, collisions, fusion, "
            "bore clearance, and STEP topology are measured only during build."
        ),
    }


@router.post("/build", response_model=BuildAccepted, status_code=202)
def build_propeller(payload: Any = Body(...)) -> BuildAccepted:
    spec = _validate(payload)
    if isinstance(spec, JSONResponse):
        return spec
    job = jobs.submit(spec.model_dump(mode="json"), build_type="propeller")
    return BuildAccepted(
        job_id=job.job_id,
        build_type=job.build_type,
        status="queued",
        stage="queued",
        stage_label="Queued",
        progress_percent=0,
        message="Waiting for the serialized CAD worker",
        elapsed_seconds=job.elapsed_seconds,
    )
