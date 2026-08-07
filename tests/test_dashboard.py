from fastapi.testclient import TestClient
from pathlib import Path

from autopilot.orchestration import EvidenceStore, new_preview_evidence
from autopilot.runners import (
    ArmModelTransformer,
    LlamaServerLauncher,
    PromptQualityGate,
    RuntimeConfiguration,
    parse_llama_bench_output,
)

from autopilot.main import app, jobs


client = TestClient(app)


def setup_function() -> None:
    jobs.clear()


def test_health_reports_preview_without_vm() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "mode": "local-preview",
        "vm": "not-connected",
    }


def test_console_state_is_truthful_before_vm_setup() -> None:
    response = client.get("/api/console-state")

    assert response.status_code == 200
    state = response.json()
    assert state["connection"]["vm"] == "not-configured"
    assert state["connection"]["ssh_tunnel"] == "not-configured"
    assert state["security"]["port_8000_public"] is False
    assert state["runtime"]["active_job_id"] is None


def test_preview_job_never_invents_benchmark_results() -> None:
    response = client.post(
        "/api/optimization-jobs",
        json={
            "model_name": "demo.gguf",
            "objective": "generation_speed",
            "context_size": 4096,
            "memory_guardrail_percent": 80,
        },
    )

    assert response.status_code == 202
    job = client.get(f"/api/optimization-jobs/{response.json()['id']}").json()
    assert job["status"] == "waiting_for_vm"
    assert job["result"] is None
    assert "No benchmark was run" in job["message"]
    assert job["optimization_plan"]["arm_builds"]
    assert job["optimization_plan"]["candidates"]
    assert job["evidence"]["measured_on_arm"] is False
    assert job["orchestration"]["phases"][0]["status"] == "complete"


def test_dashboard_loads() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Oracle Arm64 VM not connected" in response.text
    assert "Speed Mode" in response.text
    assert "Serve More Users" in response.text
    assert "Custom limits" in response.text
    assert "Apply and start optimized model" in response.text


def test_memory_budget_cannot_exceed_vm_ram() -> None:
    response = client.post(
        "/api/optimization-jobs",
        json={
            "model_name": "demo.gguf",
            "objective": "generation_speed",
            "context_size": 4096,
            "memory_guardrail_percent": 80,
            "vm_memory_gb": 4,
            "memory_budget_gb": 6,
        },
    )

    assert response.status_code == 422
    assert "cannot exceed" in response.text

def test_model_catalog_exposes_memory_floor() -> None:
    response = client.get("/api/models")

    assert response.status_code == 200
    model = response.json()[0]
    assert model["name"] == "Qwen 2.5 Instruct"
    assert model["estimated_minimum_memory_gb"] == 2.0


def test_optimization_modes_expose_five_plain_language_goals() -> None:
    response = client.get("/api/optimization-modes")

    assert response.status_code == 200
    assert [mode["id"] for mode in response.json()] == [
        "speed",
        "quality",
        "lightweight",
        "serve_more",
        "custom",
    ]


def test_cannot_start_optimized_server_without_arm_evidence() -> None:
    created = client.post(
        "/api/optimization-jobs",
        json={"context_size": 4096, "memory_guardrail_percent": 80},
    ).json()
    response = client.post(f"/api/optimization-jobs/{created['id']}/serve")

    assert response.status_code == 409
    assert "VM" in response.json()["detail"]


def test_sample_evidence_is_explicitly_not_measured() -> None:
    response = client.get("/api/sample-evidence/speed")

    assert response.status_code == 200
    sample = response.json()
    assert sample["kind"] == "sample_not_measured"
    assert "not measured" in sample["label"].lower()


def test_llama_bench_parser_only_reads_present_metrics() -> None:
    parsed = parse_llama_bench_output(
        {"results": [{"test": "pp", "avg_ts": 123.4}, {"test": "tg", "avg_ts": 45.6}]}
    )

    assert parsed.prompt_tokens_per_second == 123.4
    assert parsed.generation_tokens_per_second == 45.6
    assert parsed.ttft_ms is None
    assert parsed.peak_rss_mb is None


def test_transformer_and_server_launcher_reject_paths_outside_model_directory(tmp_path: Path) -> None:
    models = tmp_path / "models"
    models.mkdir()
    transformer = ArmModelTransformer(tmp_path / "llama", models)
    config = RuntimeConfiguration(4, 4, 512, 128, 4096)
    launcher = LlamaServerLauncher(tmp_path / "llama-server", models)

    try:
        transformer.quantize_command(tmp_path / "outside.gguf", models / "candidate.gguf", "Q4_0")
        assert False, "expected transformer path validation"
    except ValueError:
        pass
    try:
        launcher.command(tmp_path / "outside.gguf", config)
        assert False, "expected server path validation"
    except ValueError:
        pass


def test_quality_gate_and_evidence_store_are_repeatable(tmp_path: Path) -> None:
    gate = PromptQualityGate()
    assert gate.evaluate(["answer", "answer"]).passed is True
    assert gate.evaluate(["answer", ""]).passed is False

    evidence = new_preview_evidence("test-job", {"mode": "speed"})
    store = EvidenceStore(tmp_path / "evidence")
    path = store.save(evidence)
    loaded = store.load("test-job")

    assert path.exists()
    assert loaded.measured_on_arm is False
    assert loaded.status == "planned-not-measured"
