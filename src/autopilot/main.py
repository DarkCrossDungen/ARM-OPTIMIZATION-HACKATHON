from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Literal
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, model_validator

from .pipeline import APPROVED_HF_MODELS, OptimizationMode, preview_recipe
from .fixtures import sample_evidence
from .orchestration import new_preview_evidence, preview_orchestration


APP_ROOT = Path(__file__).resolve().parent
app = FastAPI(title="ArmDX", version="0.2.0")
app.mount("/static", StaticFiles(directory=APP_ROOT / "static"), name="static")
templates = Jinja2Templates(directory=APP_ROOT / "templates")

MODEL_CATALOG = {
    model_id: {
        "id": model_id,
        "name": details["display_name"],
        "parameters": details["parameters"],
        "source_precision": details["source_precision"],
        "estimated_file_gb": details["estimated_source_gb"],
        "estimated_minimum_memory_gb": details["estimated_minimum_memory_gb"],
        "status": "source-download-planned",
    }
    for model_id, details in APPROVED_HF_MODELS.items()
}


class OptimizationRequest(BaseModel):
    model_name: str = Field(default="Qwen/Qwen2.5-1.5B-Instruct", min_length=1, max_length=160)
    objective: Literal["generation_speed", "prompt_speed", "low_memory"] = "generation_speed"
    mode: OptimizationMode = "speed"
    profile: str = "guided"
    answer_length: Literal["short", "standard", "long"] = "standard"
    quality_floor: Literal["basic", "good", "highest"] = "good"
    response_start_priority: Literal["relaxed", "balanced", "fastest"] = "balanced"
    vm_memory_gb: float = Field(default=8, ge=2, le=1024)
    memory_budget_gb: float = Field(default=6, ge=2, le=1024)
    context_size: int = Field(ge=512, le=32768)
    memory_guardrail_percent: int = Field(ge=1, le=100)
    generation_threads: int = Field(default=4, ge=1, le=128)
    prompt_threads: int = Field(default=4, ge=1, le=128)
    batch_size: int = Field(default=512, ge=32, le=4096)
    micro_batch_size: int = Field(default=128, ge=16, le=1024)
    prompt_tokens: int = Field(default=512, ge=32, le=8192)
    generation_tokens: int = Field(default=128, ge=16, le=4096)
    repetitions: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def validate_memory_budget(self) -> "OptimizationRequest":
        model = MODEL_CATALOG.get(self.model_name)
        minimum_gb = (
            float(model["estimated_minimum_memory_gb"]) if model else 2.0
        )
        if self.memory_budget_gb < minimum_gb:
            raise ValueError(
                f"This model needs an estimated minimum budget of {minimum_gb:g} GB."
            )
        if self.memory_budget_gb > self.vm_memory_gb:
            raise ValueError("Memory budget cannot exceed the RAM installed on the VM.")
        return self


jobs: dict[str, dict[str, object]] = {}
job_lock = Lock()
active_job_id: str | None = None


def run_preview_job(job_id: str) -> None:
    """Temporary local-preview job; replaced by the Arm VM benchmark runner."""
    global active_job_id
    try:
        job = jobs[job_id]
        job["status"] = "waiting_for_vm"
        job["message"] = "Optimization recipe is ready. No benchmark was run; connect an Arm64 VM to create candidates and measure results."
        job["result"] = None
        job["orchestration"] = preview_orchestration(job["request"]["mode"])
        job["finished_at"] = datetime.now(timezone.utc).isoformat()
    finally:
        with job_lock:
            if active_job_id == job_id:
                active_job_id = None


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "mode": "local-preview", "vm": "not-connected"}


@app.get("/api/console-state")
async def console_state() -> dict[str, object]:
    """Truthful operator-console state before a remote Arm VM is configured."""
    return {
        "mode": "local-preview",
        "connection": {
            "vm": "not-configured",
            "ssh_tunnel": "not-configured",
            "remote_service": "unreachable",
            "last_heartbeat": None,
        },
        "security": {
            "ssh_client": "installed",
            "key_only_login": "pending-vm",
            "password_login_disabled": "pending-vm",
            "port_8000_public": False,
            "source_ip_restricted": "pending-vm",
        },
        "runtime": {
            "runner": "llama.cpp",
            "runner_status": "not-installed-on-vm",
            "model_status": "not-installed-on-vm",
            "active_job_id": active_job_id,
        },
    }


@app.get("/api/models")
async def list_models() -> list[dict[str, object]]:
    return list(MODEL_CATALOG.values())


@app.get("/api/optimization-modes")
async def optimization_modes() -> list[dict[str, str]]:
    return [
        {"id": "speed", "label": "Speed Mode", "description": "Maximize generation tokens per second."},
        {"id": "quality", "label": "Quality Mode", "description": "Preserve the highest possible output quality."},
        {"id": "lightweight", "label": "Lightweight Mode", "description": "Minimize RAM and model size."},
        {"id": "serve_more", "label": "Serve More Users", "description": "Optimize the inference server for concurrent requests."},
        {"id": "custom", "label": "Custom", "description": "Set memory, response-start, and quality limits."},
    ]


@app.get("/api/sample-evidence/{mode}")
async def get_sample_evidence(mode: OptimizationMode) -> dict[str, object]:
    """Demo-only report shape; never persisted as a job result."""
    return sample_evidence(mode)

@app.get("/api/optimization-jobs")
async def list_optimization_jobs() -> list[dict[str, object]]:
    return list(reversed(list(jobs.values())))


@app.post("/api/optimization-jobs", status_code=202)
async def create_optimization_job(
    payload: OptimizationRequest, background_tasks: BackgroundTasks
) -> dict[str, object]:
    global active_job_id
    with job_lock:
        if active_job_id is not None:
            raise HTTPException(status_code=409, detail="An optimization job is already running.")
        job_id = str(uuid4())
        active_job_id = job_id
    jobs[job_id] = {
        "id": job_id,
        "status": "queued",
        "request": payload.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "message": "Preparing optimization job...",
        "result": None,
        "optimization_plan": preview_recipe(payload.mode),
        "orchestration": preview_orchestration(payload.mode),
        "evidence": new_preview_evidence(job_id, payload.model_dump()).to_dict(),
        "deployment": {"status": "not-started", "endpoint": None},
    }
    background_tasks.add_task(run_preview_job, job_id)
    return jobs[job_id]


@app.post("/api/optimization-jobs/{job_id}/serve", status_code=409)
async def serve_optimized_model(job_id: str) -> dict[str, str]:
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    evidence = jobs[job_id].get("evidence", {})
    if not evidence.get("measured_on_arm"):
        return {
            "detail": "No measured optimized model exists yet. Connect the Arm64 VM and complete a measured optimization run first."
        }
    return {"detail": "Measured serving is ready to be started by the Arm worker."}


@app.get("/api/optimization-jobs/{job_id}")
async def get_optimization_job(job_id: str) -> dict[str, object]:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
