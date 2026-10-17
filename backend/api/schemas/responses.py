from typing import Literal

from pydantic import BaseModel, Field


class ProgressResponse(BaseModel):
    job_id: str
    build_type: Literal["blade", "propeller"] = "blade"
    stage: str
    stage_label: str
    progress_percent: int = Field(ge=0, le=100)
    message: str
    elapsed_seconds: float = Field(ge=0.0)
    queue_wait_seconds: float = Field(ge=0.0)
    worker_elapsed_seconds: float = Field(ge=0.0)
    error: str | None = None
    runtime_build_id: str | None = None
    construction_contract: str | None = None
    runtime_fingerprint: str | None = None


class BuildAccepted(ProgressResponse):
    status: Literal["queued"]


class JobStatus(ProgressResponse):
    status: Literal["queued", "running", "succeeded", "failed"]


class Artifact(BaseModel):
    name: str
    size_bytes: int
    download_url: str
