from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class StepArgs(BaseModel):
    model_config = {"extra": "allow"}


class StepSpec(BaseModel):
    id: str
    action: str
    args: Dict[str, Any] = Field(default_factory=dict)


class JobSpec(BaseModel):
    version: int
    kind: Literal["job"]
    id: str
    source: str
    summary: str
    variables: Dict[str, Any] = Field(default_factory=dict)
    steps: List[StepSpec]


class AgentBootstrapRequest(BaseModel):
    mode: Literal["job_ids", "profile"]
    job_ids: List[str] = Field(default_factory=list)
    profile: Optional[str] = None
    variables: Dict[str, str] = Field(default_factory=dict)


class StepResult(BaseModel):
    step_id: str
    action: str
    status: Literal["success", "failed", "skipped"]
    detail: str


class JobResult(BaseModel):
    job_id: str
    status: Literal["success", "failed"]
    step_results: List[StepResult]


class BootstrapRunResult(BaseModel):
    requested_mode: str
    requested_jobs: List[str]
    status: Literal["success", "failed"]
    jobs: List[JobResult]
