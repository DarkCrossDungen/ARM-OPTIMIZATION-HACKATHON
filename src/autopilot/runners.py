"""Boundaries for benchmark execution on the future Arm64 VM."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class RuntimeConfiguration:
    generation_threads: int
    prompt_threads: int
    batch_size: int
    micro_batch_size: int
    context_size: int


@dataclass(frozen=True)
class BenchmarkRequest:
    model_path: Path
    prompt_tokens: int
    generation_tokens: int
    repetitions: int
    config: RuntimeConfiguration


@dataclass(frozen=True)
class BenchmarkResult:
    prompt_tokens_per_second: float | None
    generation_tokens_per_second: float | None
    raw_output: dict[str, object]
    ttft_ms: float | None = None
    peak_rss_mb: float | None = None
    model_size_mb: float | None = None


class BenchmarkRunner(Protocol):
    def run(self, request: BenchmarkRequest) -> BenchmarkResult:
        """Run one reproducible benchmark and return parsed measurements."""


@dataclass(frozen=True)
class ArmRuntimeBuild:
    name: str
    build_dir: Path
    description: str


ARM_RUNTIME_BUILDS = (
    ArmRuntimeBuild("stock", Path("llama.cpp/build-stock"), "Generic Arm CPU backend"),
    ArmRuntimeBuild("kleidiai", Path("llama.cpp/build-kleidiai"), "Arm KleidiAI CPU kernels"),
    ArmRuntimeBuild("kleidiai-openblas", Path("llama.cpp/build-kleidiai-openblas"), "KleidiAI plus BLAS prompt-processing candidate"),
)


def parse_llama_bench_output(raw: dict[str, Any] | list[dict[str, Any]]) -> BenchmarkResult:
    """Extract stable measurements from llama-bench JSON without guessing missing values."""
    entries = raw if isinstance(raw, list) else raw.get("results", raw.get("benchmarks", []))
    if not isinstance(entries, list):
        entries = []
    prompt_speed = generation_speed = ttft_ms = peak_rss_mb = model_size_mb = None
    for entry in entries:
        if not isinstance(entry, dict):
            continue

        # Current llama-bench JSON uses n_gen: 0 is prompt processing, >0 is generation.
        # Older output uses a test/name field instead, so never assume missing n_gen means prompt.
        n_gen = entry.get("n_gen")
        speed = entry.get("avg_ts", entry.get("tokens_per_second"))
        test = str(entry.get("test", entry.get("name", ""))).lower()

        if isinstance(speed, (int, float)):
            if isinstance(n_gen, int):
                if n_gen == 0:
                    prompt_speed = float(speed)
                else:
                    generation_speed = float(speed)
            elif test in {"pp", "prompt", "prompt_processing"}:
                prompt_speed = float(speed)
            elif test in {"tg", "generation", "token_generation"}:
                generation_speed = float(speed)

        # Extract other metrics
        for key, target in (("ttft_ms", "ttft"), ("peak_rss_mb", "rss"), ("model_size_mb", "size")):
            value = entry.get(key)
            if isinstance(value, (int, float)):
                if target == "ttft": ttft_ms = float(value)
                if target == "rss": peak_rss_mb = float(value)
                if target == "size": model_size_mb = float(value)

    payload: dict[str, object] = raw if isinstance(raw, dict) else {"results": raw}
    return BenchmarkResult(prompt_speed, generation_speed, payload, ttft_ms, peak_rss_mb, model_size_mb)


FIXED_QUALITY_PROMPTS = (
    "Explain why matching benchmark conditions matters in one sentence.",
    "Write a concise Python function that returns the larger of two integers.",
)


@dataclass(frozen=True)
class QualityGateResult:
    passed: bool
    completed_prompts: int
    total_prompts: int


class PromptQualityGate:
    """Minimal repeatable quality guard for future candidate output comparisons."""

    def evaluate(self, responses: list[str]) -> QualityGateResult:
        completed = sum(bool(response and response.strip()) for response in responses[: len(FIXED_QUALITY_PROMPTS)])
        return QualityGateResult(completed == len(FIXED_QUALITY_PROMPTS), completed, len(FIXED_QUALITY_PROMPTS))


class LlamaServerLauncher:
    """Build a safe private llama-server command after measured evidence exists."""

    def __init__(self, llama_server_path: Path, allowed_models_dir: Path) -> None:
        self.llama_server_path = llama_server_path.resolve()
        self.allowed_models_dir = allowed_models_dir.resolve()

    def command(self, model_path: Path, config: RuntimeConfiguration, port: int = 8080) -> list[str]:
        model_path = model_path.resolve()
        if self.allowed_models_dir not in model_path.parents:
            raise ValueError("Server model path must remain inside the configured models directory.")
        if not 1024 <= port <= 65535:
            raise ValueError("Server port must be between 1024 and 65535.")
        return [str(self.llama_server_path), "--model", str(model_path), "--host", "127.0.0.1", "--port", str(port), "--threads", str(config.generation_threads), "--ctx-size", str(config.context_size), "--batch-size", str(config.batch_size), "--ubatch-size", str(config.micro_batch_size)]


class ArmModelTransformer:
    """Safe command builder for the Arm VM conversion and quantization pipeline."""

    def __init__(self, llama_root: Path, allowed_models_dir: Path) -> None:
        self.llama_root = llama_root.resolve()
        self.allowed_models_dir = allowed_models_dir.resolve()

    def source_gguf_path(self, model_slug: str) -> Path:
        return self.allowed_models_dir / f"{model_slug}-BF16.gguf"

    def quantized_path(self, model_slug: str, quantization: str) -> Path:
        return self.allowed_models_dir / f"{model_slug}-{quantization}.gguf"

    def convert_command(self, model_id: str, output_path: Path) -> list[str]:
        self._validate_output(output_path)
        return [
            "python3", str(self.llama_root / "convert_hf_to_gguf.py"),
            "--remote", model_id, "--outfile", str(output_path), "--outtype", "bf16",
        ]

    def quantize_command(self, source_path: Path, output_path: Path, quantization: str) -> list[str]:
        self._validate_output(source_path)
        self._validate_output(output_path)
        if quantization not in {"Q2_K", "Q3_K_S", "Q4_0", "Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0"}:
            raise ValueError("Quantization is not in ArmDX's approved candidate set.")
        return [
            str(self.llama_root / "build-kleidiai" / "bin" / "llama-quantize"),
            str(source_path), str(output_path), quantization,
        ]

    def _validate_output(self, path: Path) -> None:
        resolved = path.resolve()
        if resolved != self.allowed_models_dir and self.allowed_models_dir not in resolved.parents:
            raise ValueError("Model artifact must remain inside the configured models directory.")


class Arm64LlamaBenchRunner:
    """Adapter for llama-bench on the Arm64 VM; never used in local preview."""

    def __init__(self, llama_bench_path: Path, allowed_models_dir: Path) -> None:
        self.llama_bench_path = llama_bench_path.resolve()
        self.allowed_models_dir = allowed_models_dir.resolve()

    def run(self, request: BenchmarkRequest) -> BenchmarkResult:
        model_path = request.model_path.resolve()
        if self.allowed_models_dir not in model_path.parents:
            raise ValueError("Model path must be inside the configured models directory.")
        if not model_path.is_file():
            raise FileNotFoundError(f"Model not found: {model_path}")
        if not self.llama_bench_path.is_file():
            raise FileNotFoundError(f"llama-bench not found: {self.llama_bench_path}")

        command = [
            str(self.llama_bench_path), "--output", "json", "--repetitions", str(request.repetitions),
            "--model", str(model_path), "--n-prompt", str(request.prompt_tokens),
            "--n-gen", str(request.generation_tokens), "--threads", str(request.config.generation_threads),
            "--batch-size", str(request.config.batch_size), "--ubatch-size", str(request.config.micro_batch_size),
        ]
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        return parse_llama_bench_output(json.loads(completed.stdout))
