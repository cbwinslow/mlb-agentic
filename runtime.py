from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

import yaml

from .actions import ACTION_REGISTRY
from .models import AgentBootstrapRequest, BootstrapRunResult, JobResult, JobSpec, StepResult


_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _read_yaml(path: Path) -> Dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _expand_value(value: Any, variables: Dict[str, Any]) -> Any:
    if isinstance(value, str):
        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            return str(variables.get(key, match.group(0)))
        return _VAR_PATTERN.sub(repl, value)
    if isinstance(value, list):
        return [_expand_value(v, variables) for v in value]
    if isinstance(value, dict):
        return {k: _expand_value(v, variables) for k, v in value.items()}
    return value


def _load_manifest(root: Path) -> Dict[str, Any]:
    return _read_yaml(root / "config" / "manifest.yaml")


def _resolve_job_ids(request: AgentBootstrapRequest, manifest: Dict[str, Any]) -> List[str]:
    if request.mode == "job_ids":
        return request.job_ids
    if request.mode == "profile":
        profile = request.profile or ""
        profiles = manifest.get("profiles", {})
        if profile not in profiles:
            raise ValueError(f"Unknown profile: {profile}")
        return profiles[profile]["jobs"]
    raise ValueError(f"Unsupported mode: {request.mode}")


def _load_job(root: Path, manifest: Dict[str, Any], job_id: str, variables: Dict[str, Any]) -> JobSpec:
    rel = manifest["jobs"].get(job_id)
    if not rel:
        raise ValueError(f"Unknown job id: {job_id}")
    raw = _read_yaml(root / rel)
    expanded = _expand_value(raw, variables)
    return JobSpec(**expanded)


def run_bootstrap(root_dir: str, request_data: Dict[str, Any]) -> BootstrapRunResult:
    root = Path(root_dir)
    manifest = _load_manifest(root)
    request = AgentBootstrapRequest(**request_data)
    merged_variables = dict(os.environ)
    merged_variables.update(request.variables)
    job_ids = _resolve_job_ids(request, manifest)

    job_results: List[JobResult] = []
    overall_status = "success"

    for job_id in job_ids:
        job = _load_job(root, manifest, job_id, merged_variables)
        run_dir = root / ".runs" / job.id
        run_dir.mkdir(parents=True, exist_ok=True)
        context = {
            "run_dir": str(run_dir),
            "git_bin": merged_variables.get("GIT_BIN", "git"),
            "request_timeout_seconds": int(merged_variables.get("REQUEST_TIMEOUT_SECONDS", 120)),
        }
        step_results: List[StepResult] = []
        job_status = "success"

        for step in job.steps:
            action = ACTION_REGISTRY.get(step.action)
            if action is None:
                job_status = "failed"
                overall_status = "failed"
                step_results.append(StepResult(step_id=step.id, action=step.action, status="failed", detail="unmapped action"))
                break
            try:
                detail = action(step.args, context)
                step_results.append(StepResult(step_id=step.id, action=step.action, status="success", detail=detail))
            except Exception as exc:
                job_status = "failed"
                overall_status = "failed"
                step_results.append(StepResult(step_id=step.id, action=step.action, status="failed", detail=str(exc)))
                break

        job_results.append(JobResult(job_id=job.id, status=job_status, step_results=step_results))
        if job_status == "failed":
            break

    return BootstrapRunResult(
        requested_mode=request.mode,
        requested_jobs=job_ids,
        status=overall_status,
        jobs=job_results,
    )
