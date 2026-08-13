"""ArmDX candidate planning shared by the dashboard and future Arm VM worker."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

OptimizationMode = Literal["speed", "quality", "lightweight"]

APPROVED_HF_MODELS = {
    "Qwen/Qwen2.5-1.5B-Instruct": {
        "display_name": "Qwen 2.5 Instruct",
        "parameters": "1.54B",
        "source_precision": "BF16",
        "estimated_source_gb": 3.1,
        "estimated_minimum_memory_gb": 2.0,
    }
}


@dataclass(frozen=True)
class CandidateRecipe:
    quantization: str
    runtime_build: str
    purpose: str


def planned_candidates(mode: OptimizationMode) -> list[CandidateRecipe]:
    """Return the finite, reproducible candidates to run on an Arm VM."""
    common = "kleidiai-openblas"
    recipes = {
        "speed": [
            CandidateRecipe("Q8_0", "kleidiai", "Arm-optimized Q8 runtime candidate"),
            CandidateRecipe("Q8_0", common, "Arm kernels plus BLAS candidate"),
        ],
        "quality": [
            CandidateRecipe("Q8_0", "kleidiai", "high-fidelity Arm runtime candidate"),
            CandidateRecipe("Q8_0", common, "high-fidelity Arm kernels plus BLAS candidate"),
        ],
        "lightweight": [
            CandidateRecipe("Q4_0", "stock", "smaller GGUF baseline candidate"),
            CandidateRecipe("Q4_0", "kleidiai", "smaller Arm-optimized GGUF candidate"),
            CandidateRecipe("Q4_K_M", "stock", "balanced small GGUF candidate"),
        ],
    }
    return recipes[mode]


def preview_recipe(mode: OptimizationMode) -> dict[str, object]:
    """A truthful plan only; no benchmark measurements are present here."""
    mode_messages = {
        "speed": "Compare the same Q8_0 model with stock and Arm-optimized runtimes.",
        "quality": "Use the high-fidelity Q8_0 profile and measure the fastest Arm runtime for it.",
        "lightweight": "Compare available smaller GGUF files and select the smallest measured profile.",
    }
    return {
        "intent": mode_messages[mode],
        "arm_builds": ["stock", "kleidiai", "kleidiai-openblas"],
        "candidates": [asdict(candidate) for candidate in planned_candidates(mode)],
        "measurements": ["prompt_tokens_per_second", "generation_tokens_per_second", "model_size_mb"],
        "status": "planned-only-until-arm-vm-connects",
    }
