from typing import Literal

from pydantic import BaseModel


class BuildAccepted(BaseModel):
    job_id: str
    status: Literal["queued"]


class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    error: str | None = None


class Artifact(BaseModel):
    name: str
    size_bytes: int
    download_url: str
