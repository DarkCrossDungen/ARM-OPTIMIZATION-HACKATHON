"""Explicitly non-measured sample evidence for the ArmDX demo surface."""

from __future__ import annotations

from typing import Any

from .pipeline import OptimizationMode


def sample_evidence(mode: OptimizationMode) -> dict[str, Any]:
    """Return display-only fixture data; never attach it to a real job."""
    focus = {
        "speed": "Generation speed",
        "quality": "Quality retention",
        "lightweight": "Memory and model size",
        "serve_more": "Concurrent throughput",
        "custom": "Your selected limits",
    }[mode]
    return {
        "kind": "sample_not_measured",
        "label": "Sample evidence — not measured on your VM",
        "mode": mode,
        "focus": focus,
        "metrics": {
            "generation_tokens_per_second": "Example only",
            "ttft_ms": "Example only",
            "peak_rss_mb": "Example only",
            "model_size_mb": "Example only",
            "quality_gate": "Example only",
        },
        "note": "This fixture demonstrates the report format. It is not a benchmark result and cannot be applied or exported as evidence.",
    }
