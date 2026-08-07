"""ArmDX candidate planning shared by the dashboard and future Arm VM worker."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

OptimizationMode = Literal["speed", "quality", "lightweight", "serve_more", "custom"]

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
            CandidateRecipe("Q4_0", "kleidiai", "Arm-friendly decode candidate"),
            CandidateRecipe("Q4_K_M", "kleidiai", "balanced speed candidate"),
            CandidateRecipe("Q5_K_M", common, "quality-safe speed candidate"),
        ],
        "quality": [
            CandidateRecipe("BF16", "kleidiai", "high-fidelity baseline"),
            CandidateRecipe("Q8_0", common, "high-quality candidate"),
            CandidateRecipe("Q6_K", common, "quality/memory comparison"),
        ],
        "lightweight": [
            CandidateRecipe("Q2_K", "kleidiai", "smallest footprint candidate"),
            CandidateRecipe("Q3_K_S", "kleidiai", "small footprint candidate"),
            CandidateRecipe("Q4_0", "kleidiai", "safe lightweight candidate"),
        ],
        "serve_more": [
            CandidateRecipe("Q4_0", common, "parallel-server throughput candidate"),
            CandidateRecipe("Q5_K_M", common, "parallel-server quality candidate"),
        ],
        "custom": [
            CandidateRecipe("Q4_0", "kleidiai", "custom baseline candidate"),
            CandidateRecipe("Q5_K_M", common, "custom balanced candidate"),
            CandidateRecipe("Q8_0", common, "custom quality candidate"),
        ],
    }
    return recipes[mode]


def preview_recipe(mode: OptimizationMode) -> dict[str, object]:
    """A truthful plan only; no benchmark measurements are present here."""
    mode_messages = {
        "speed": "Maximize generation tokens per second while retaining the selected quality floor.",
        "quality": "Retain the highest-quality candidate that fits the selected memory limit.",
        "lightweight": "Minimize GGUF size and peak RAM while retaining the selected quality floor.",
        "serve_more": "Tune the warmed llama-server for concurrent requests and response latency.",
        "custom": "Search only candidates that satisfy the custom memory, response-start, and quality limits.",
    }
    return {
        "intent": mode_messages[mode],
        "arm_builds": ["stock", "kleidiai", "kleidiai-openblas"],
        "candidates": [asdict(candidate) for candidate in planned_candidates(mode)],
        "measurements": ["prompt_tokens_per_second", "generation_tokens_per_second", "ttft_ms", "peak_rss_mb", "model_size_mb"],
        "status": "planned-only-until-arm-vm-connects",
    }
