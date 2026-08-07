# ArmDX

ArmDX is an evidence-first control console for optimizing one `llama.cpp` LLM workload on an Arm64 Linux VM. It creates a constrained candidate plan, runs matched benchmarks on Arm hardware, keeps the raw evidence, and only enables serving after a measured winning candidate exists.

## What works locally now

- Five understandable goals: Speed, Quality, Lightweight, Serve More Users, and Custom.
- A truthful job plan with conversion, quantization, benchmark, quality, selection, and serving phases.
- Sample report data that is explicitly labelled **not measured on your VM**.
- SSH key, tunnel, hardening, verification, and future systemd deployment materials.

Local preview never claims Arm performance numbers.

## Run locally

```cmd
.venv\Scripts\python.exe -m uvicorn autopilot.main:app --app-dir src --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000.

## When the Arm64 VM is available

1. Follow [the Oracle VM runbook](docs/oracle-vm-setup.md).
2. Create an Ed25519 key, restrict port 22 to your public IP, and run the SSH hardening script.
3. Install the private `armdx` systemd service on the VM.
4. Open the local SSH tunnel from the laptop and use the same localhost URL.
5. Run a real job. ArmDX will retain matched raw evidence before allowing the optimized model to serve.

## Core technology

- Arm64 Ubuntu VM
- `llama.cpp` built as stock, KleidiAI, and KleidiAI + OpenBLAS candidates
- Qwen 2.5 1.5B Instruct as the first approved source model
- GGUF conversion and finite Q2–Q8 candidate set
- Private SSH local forwarding; the API binds only to VM loopback

See [architecture](docs/architecture.md), [security](docs/security.md), and [product specification](docs/product-spec.md).
