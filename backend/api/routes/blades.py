from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import ValidationError

from api.schemas import Artifact, BuildAccepted, JobStatus
from api.services.jobs import ALLOWED_ARTIFACTS, WORKSPACE_ROOT, jobs
from bladegen.curves.resolver import resolve_blade_spec
from bladegen.models import BladeSpec

router = APIRouter()
EXAMPLES_ROOT = WORKSPACE_ROOT / "examples"


def _example_path(example_id: str) -> Path:
    if not example_id or any(
        ch not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for ch in example_id
    ):
        raise HTTPException(status_code=404, detail="Example not found")
    path = EXAMPLES_ROOT / f"{example_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Example not found")
    return path


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "bladegen", "schema_version": "0.2"}


@router.get("/examples")
def list_examples() -> list[dict]:
    return [
        {"id": path.stem, "name": BladeSpec.from_json(path).name}
        for path in sorted(EXAMPLES_ROOT.glob("*.json"))
    ]


@router.get("/examples/{example_id}")
def get_example(example_id: str) -> dict:
    return BladeSpec.from_json(_example_path(example_id)).model_dump(mode="json")


@router.post("/validate")
def validate_spec(payload: dict) -> dict:
    try:
        spec = BladeSpec.model_validate(payload)
        resolved = resolve_blade_spec(spec)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "valid": True,
        "schema_version": spec.schema_version,
        "airfoil_sections": len(spec.airfoil_sections),
        "resolved_curve_points": {
            name: len(curve.parameter_vector) for name, curve in resolved.curve_items()
        },
    }


@router.post("/build", response_model=BuildAccepted, status_code=202)
def build(payload: dict) -> BuildAccepted:
    validate_spec(payload)
    job = jobs.submit(payload)
    return BuildAccepted(job_id=job.job_id, status="queued")


@router.get("/jobs/{job_id}", response_model=JobStatus)
def job_status(job_id: str) -> JobStatus:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(job_id=job.job_id, status=job.status, error=job.error)


@router.get("/jobs/{job_id}/artifacts", response_model=list[Artifact])
def job_artifacts(job_id: str) -> list[Artifact]:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "succeeded":
        return []
    return [
        Artifact(
            name=path.name,
            size_bytes=path.stat().st_size,
            download_url=f"/api/jobs/{job_id}/artifacts/{path.name}",
        )
        for path in jobs.artifacts(job)
    ]


@router.get("/jobs/{job_id}/artifacts/{artifact_name}")
def download_artifact(job_id: str, artifact_name: str) -> FileResponse:
    job = jobs.get(job_id)
    if job is None or job.status != "succeeded" or artifact_name not in ALLOWED_ARTIFACTS:
        raise HTTPException(status_code=404, detail="Artifact not found")
    path = job.output_dir / artifact_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(path, filename=artifact_name)
