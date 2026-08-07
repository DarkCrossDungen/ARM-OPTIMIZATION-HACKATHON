"""Truthful job orchestration and evidence persistence for ArmDX."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .pipeline import OptimizationMode, preview_recipe


PHASE_NAMES = (
    "Validate request",
    "Download approved source",
    "Convert BF16 source to GGUF",
    "Create quantized candidates",
    "Measure baseline",
    "Benchmark candidates",
    "Run quality gate",
    "Select best profile",
    "Start optimized server",
)


@dataclass(frozen=True)
class JobPhase:
    name: str
    status: str
    detail: str


def planned_phases() -> list[dict[str, str]]:
    return [
        asdict(JobPhase(name, "blocked", "Waiting for a connected Arm64 VM."))
        for name in PHASE_NAMES
    ]


def preview_orchestration(mode: OptimizationMode) -> dict[str, Any]:
    """Return a complete plan without claiming that a benchmark occurred."""
    phases = planned_phases()
    phases[0] = asdict(JobPhase(PHASE_NAMES[0], "complete", "Request validated locally."))
    return {
        "mode": "local-preview",
        "phases": phases,
        "candidate_plan": preview_recipe(mode),
        "next_action": "Connect the Arm64 VM before model conversion or benchmarking.",
    }


@dataclass(frozen=True)
class EvidenceRecord:
    job_id: str
    status: str
    measured_on_arm: bool
    created_at: str
    request: dict[str, Any]
    commands: list[list[str]]
    raw_outputs: list[dict[str, Any]]
    selected_candidate: dict[str, Any] | None
    measurements: dict[str, float | None]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvidenceStore:
    """JSON evidence storage used only by the Arm worker after a real run."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def save(self, evidence: EvidenceRecord) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.directory / f"{evidence.job_id}.json"
        target.write_text(json.dumps(evidence.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return target

    def load(self, job_id: str) -> EvidenceRecord:
        payload = json.loads((self.directory / f"{job_id}.json").read_text(encoding="utf-8"))
        return EvidenceRecord(**payload)


def new_preview_evidence(job_id: str, request: dict[str, Any]) -> EvidenceRecord:
    return EvidenceRecord(
        job_id=job_id,
        status="planned-not-measured",
        measured_on_arm=False,
        created_at=datetime.now(timezone.utc).isoformat(),
        request=request,
        commands=[],
        raw_outputs=[],
        selected_candidate=None,
        measurements={
            "prompt_tokens_per_second": None,
            "generation_tokens_per_second": None,
            "ttft_ms": None,
            "peak_rss_mb": None,
            "model_size_mb": None,
        },
    )
