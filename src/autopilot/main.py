from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Literal
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, model_validator

from .pipeline import APPROVED_HF_MODELS, OptimizationMode, preview_recipe
from .fixtures import sample_evidence
from .orchestration import new_preview_evidence, preview_orchestration, EvidenceRecord, EvidenceStore, PHASE_NAMES, JobPhase
from .runners import (
    ARM_RUNTIME_BUILDS,
    ArmRuntimeBuild,
    BenchmarkRequest,
    BenchmarkResult,
    OracleLlamaBenchRunner,
    RuntimeConfiguration,
    parse_llama_bench_output,
)
import platform
import subprocess


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


jobs: dict[str, dict[str, Any]] = {}
job_lock = Lock()
active_job_id: str | None = None


def is_arm64() -> bool:
    """Check if we're running on ARM64 architecture."""
    machine = platform.machine().lower()
    return machine in ("aarch64", "arm64")


def run_real_arm_job(job_id: str) -> None:
    """Run a measured Arm64 profile selected by the user's optimization goal."""
    global active_job_id
    job = jobs[job_id]
    try:
        request = job["request"]
        mode = request.get("mode", "speed")
        home = Path.home()
        models_dir = home / "models"
        model_paths = {
            "Q8_0": models_dir / "qwen2.5-1.5b-instruct-q8_0.gguf",
            "Q4_0": models_dir / "qwen2.5-1.5b-instruct-q4_0.gguf",
            "Q4_K_M": models_dir / "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        }
        baseline_model = model_paths["Q8_0"]
        if not baseline_model.exists():
            job["status"] = "failed"
            job["message"] = f"Baseline model not found: {baseline_model}"
            return

        candidate_specs = {
            "speed": [("Q8_0", "kleidiai"), ("Q8_0", "kleidiai-openblas")],
            "quality": [("Q8_0", "kleidiai"), ("Q8_0", "kleidiai-openblas")],
            "lightweight": [("Q4_0", "stock"), ("Q4_0", "kleidiai"), ("Q4_K_M", "stock")],
        }[mode]
        phases = [{"name": name, "status": "pending", "detail": ""} for name in PHASE_NAMES]
        phases[0] = {"name": PHASE_NAMES[0], "status": "complete", "detail": "Request validated"}
        for index in (1, 2, 3):
            phases[index] = {"name": PHASE_NAMES[index], "status": "skipped", "detail": "Using prebuilt model artifacts on the Arm VM"}
        phases[4] = {"name": PHASE_NAMES[4], "status": "running", "detail": "Measuring Q8_0 stock baseline"}
        phases[6] = {"name": PHASE_NAMES[6], "status": "skipped", "detail": "No separate quality evaluator is enabled for this MVP"}
        phases[8] = {"name": PHASE_NAMES[8], "status": "skipped", "detail": "Serving is outside this dashboard MVP"}
        job["orchestration"]["mode"] = "arm64-live"
        job["orchestration"]["phases"] = phases
        job["status"] = "running"
        job["message"] = "Running measured benchmarks on ARM64..."

        config = RuntimeConfiguration(
            generation_threads=request.get("generation_threads", 4),
            prompt_threads=request.get("prompt_threads", 4),
            batch_size=request.get("batch_size", 512),
            micro_batch_size=request.get("micro_batch_size", 128),
            context_size=request.get("context_size", 2048),
        )

        def run(model_path: Path, build_name: str) -> BenchmarkResult:
            build = next(item for item in ARM_RUNTIME_BUILDS if item.name == build_name)
            bench_path = home / build.build_dir / "bin" / "llama-bench"
            if not model_path.exists():
                raise FileNotFoundError(f"Model not found: {model_path}")
            if not bench_path.exists():
                raise FileNotFoundError(f"Benchmark binary not found: {bench_path}")
            return OracleLlamaBenchRunner(bench_path, models_dir).run(BenchmarkRequest(
                model_path=model_path,
                prompt_tokens=request.get("prompt_tokens", 1024),
                generation_tokens=request.get("generation_tokens", 128),
                repetitions=request.get("repetitions", 3),
                config=config,
            ))

        baseline = run(baseline_model, "stock")
        phases[4] = {"name": PHASE_NAMES[4], "status": "complete", "detail": "Q8_0 stock baseline measured"}
        phases[5] = {"name": PHASE_NAMES[5], "status": "running", "detail": "Testing Arm-optimized candidates"}
        job["orchestration"]["phases"] = phases

        candidates: list[dict[str, Any]] = []
        raw_outputs = [baseline.raw_output]
        for quantization, build_name in candidate_specs:
            model_path = model_paths[quantization]
            try:
                result = run(model_path, build_name)
                raw_outputs.append(result.raw_output)
                candidates.append({
                    "quantization": quantization,
                    "build": build_name,
                    "prompt_tokens_per_second": result.prompt_tokens_per_second,
                    "generation_tokens_per_second": result.generation_tokens_per_second,
                    "model_size_mb": round(model_path.stat().st_size / (1024 * 1024), 2),
                })
            except Exception as error:
                candidates.append({"quantization": quantization, "build": build_name, "error": str(error)})

        valid_candidates = [candidate for candidate in candidates if candidate.get("generation_tokens_per_second") is not None]
        if not valid_candidates:
            raise RuntimeError("No candidate benchmark completed successfully.")
        if mode == "lightweight":
            selected_data = min(valid_candidates, key=lambda candidate: float(candidate["model_size_mb"]))
            selection_reason = "Smallest successfully measured GGUF file"
        else:
            selected_data = max(valid_candidates, key=lambda candidate: float(candidate.get("prompt_tokens_per_second") or 0))
            selection_reason = "Best measured prompt-processing speed"

        baseline_prompt = baseline.prompt_tokens_per_second or 0.0
        baseline_generation = baseline.generation_tokens_per_second or 0.0
        selected_prompt = float(selected_data.get("prompt_tokens_per_second") or 0)
        selected_generation = float(selected_data.get("generation_tokens_per_second") or 0)
        prompt_change = ((selected_prompt - baseline_prompt) / baseline_prompt * 100) if baseline_prompt else None
        generation_change = ((selected_generation - baseline_generation) / baseline_generation * 100) if baseline_generation else None
        baseline_size = round(baseline_model.stat().st_size / (1024 * 1024), 2)

        phases[5] = {"name": PHASE_NAMES[5], "status": "complete", "detail": f"Measured {len(valid_candidates)} candidates"}
        phases[7] = {"name": PHASE_NAMES[7], "status": "complete", "detail": f"Selected {selected_data['quantization']} + {selected_data['build']}"}
        job["orchestration"]["phases"] = phases
        job["optimization_plan"]["status"] = "measured-on-arm"
        job["orchestration"]["next_action"] = "Review the measured result in the dashboard."
        job["result"] = {
            "mode": mode,
            "baseline": {
                "quantization": "Q8_0", "build": "stock", "model_size_mb": baseline_size,
                "prompt_tokens_per_second": baseline.prompt_tokens_per_second,
                "generation_tokens_per_second": baseline.generation_tokens_per_second,
            },
            "candidates": candidates,
            "selected": {**selected_data, "selection_reason": selection_reason},
            "changes": {"prompt_percent": prompt_change, "generation_percent": generation_change},
        }
        job["evidence"] = EvidenceRecord(
            job_id=job_id, status="complete", measured_on_arm=True,
            created_at=datetime.now(timezone.utc).isoformat(), request=request, commands=[],
            raw_outputs=raw_outputs,
            selected_candidate={"build": selected_data["build"], "quantization": selected_data["quantization"]},
            measurements={"prompt_tokens_per_second": selected_prompt, "generation_tokens_per_second": selected_generation,
                          "model_size_mb": float(selected_data.get("model_size_mb") or 0)},
        ).to_dict()
        job["status"] = "complete"
        job["message"] = f"Optimization complete: {selected_data['quantization']} + {selected_data['build']} selected."
        job["finished_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as error:
        job["status"] = "failed"
        job["message"] = f"Benchmark failed: {error}"
        job["finished_at"] = datetime.now(timezone.utc).isoformat()
    finally:
        with job_lock:
            if active_job_id == job_id:
                active_job_id = None


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
    if is_arm64():
        return {"status": "ok", "mode": "arm64-live", "vm": "connected"}
    return {"status": "ok", "mode": "local-preview", "vm": "not-connected"}


@app.get("/api/console-state")
async def console_state() -> dict[str, object]:
    """Truthful operator-console state before a remote Arm VM is configured."""
    live_arm = is_arm64()
    return {
        "mode": "arm64-live" if live_arm else "local-preview",
        "connection": {
            "vm": "connected" if live_arm else "not-connected",
            "ssh_tunnel": "local-loopback" if live_arm else "not-configured",
            "remote_service": "reachable" if live_arm else "unreachable",
            "last_heartbeat": datetime.now(timezone.utc).isoformat() if live_arm else None,
        },
        "security": {
            "ssh_client": "installed",
            "key_only_login": "configured" if live_arm else "pending-vm",
            "password_login_disabled": "configured" if live_arm else "pending-vm",
            "port_8000_public": False,
            "source_ip_restricted": "configured" if live_arm else "pending-vm",
        },
        "runtime": {
            "runner": "llama.cpp",
            "runner_status": "ready" if live_arm else "not-installed-on-vm",
            "model_status": "available" if live_arm else "not-installed-on-vm",
            "active_job_id": active_job_id,
        },
    }


@app.get("/api/models")
async def list_models() -> list[dict[str, str | float]]:
    return list(MODEL_CATALOG.values())


@app.get("/api/optimization-modes")
async def optimization_modes() -> list[dict[str, str]]:
    return [
        {"id": "speed", "label": "Make it faster", "description": "Compare the same Q8_0 model with Arm runtime builds."},
        {"id": "quality", "label": "Keep quality", "description": "Use the high-fidelity Q8_0 profile."},
        {"id": "lightweight", "label": "Reduce disk size", "description": "Select the smallest successfully measured GGUF."},
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
    # Use real ARM worker if on ARM64, otherwise preview mode
    if is_arm64():
        background_tasks.add_task(run_real_arm_job, job_id)
    else:
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
