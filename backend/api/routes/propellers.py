"""PropellerSpec validation and serialized assembly build endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from api.schemas import BuildAccepted
from api.services.jobs import jobs
from bladegen.models import PropellerSpec

router = APIRouter(prefix="/propellers", tags=["propellers"])


def _validate(payload: dict) -> PropellerSpec:
    try:
        return PropellerSpec.model_validate(payload)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/validate")
def validate_propeller(payload: dict) -> dict:
    spec = _validate(payload)
    nominal_root_radius = spec.blade_spec.diameter_mm / 2.0 * spec.blade_spec.root_radius_ratio
    return {
        "valid": True,
        "schema_version": spec.schema_version,
        "blade_count": spec.assembly.blade_count,
        "airfoil_sections_per_blade": len(spec.blade_spec.airfoil_sections),
        "rotation_axis": "X",
        "nominal_radial_overlap_mm": spec.assembly.hub_diameter_mm / 2.0 - nominal_root_radius,
        "geometric_qualification": "Final positive-volume overlap and collisions are measured during build",
    }


@router.post("/build", response_model=BuildAccepted, status_code=202)
def build_propeller(payload: dict) -> BuildAccepted:
    spec = _validate(payload)
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
