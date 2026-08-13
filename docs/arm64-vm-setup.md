# Arm64 VM setup

This runbook describes the private ArmDX benchmark host. The hackathon demo uses an Azure Cobalt 100 Arm64 VM, but the setup is intentionally written for an Ubuntu-compatible Arm64 Linux VM.

## Provisioning

Create an Ubuntu Arm64 VM with enough disk for `llama.cpp`, build artifacts, and GGUF model files. For the measured demo we used:

```text
Provider: Microsoft Azure
VM: Standard_D4ps_v6
CPU: Azure Cobalt 100 Arm64
User: azureuser
Service port: 127.0.0.1:8000 only
```

Security rules:

1. Allow SSH port 22 only from your current public IP.
2. Do not expose port 8000 publicly.
3. Use SSH local forwarding to open the dashboard from your laptop.

## Install the project

On the VM:

```bash
git clone YOUR_GITHUB_REPOSITORY armdx
cd armdx
chmod +x scripts/setup-arm64-vm.sh
./scripts/setup-arm64-vm.sh
```

The setup script builds the runtime candidates and creates:

```text
models/
evidence/
quality/
```

The current deployed Azure VM stores prepared model files under `~/models/`. Keep model paths trusted and do not point the service at arbitrary user-controlled locations.

## Install the private system service

On the VM:

```bash
sudo bash scripts/install-armdx-service.sh "$(pwd)" azureuser
sudo systemctl status armdx
```

The service binds only to:

```text
127.0.0.1:8000
```

For troubleshooting only:

```bash
sudo systemctl stop armdx
.venv/bin/python -m uvicorn autopilot.main:app --app-dir src --host 127.0.0.1 --port 8000
```

## Open the dashboard from the laptop

```bash
ssh -i ~/.ssh/armdx_azure -N -L 127.0.0.1:8000:127.0.0.1:8000 azureuser@VM_PUBLIC_IP
```

Then open:

```text
http://127.0.0.1:8000
```

## Benchmark integration

ArmDX runs the same workload for baseline and candidates, retains raw `llama-bench` JSON, and marks evidence as measured only when the worker runs on Arm64 hardware.

Completed measured jobs are stored under:

```text
evidence/jobs/<job-id>.json
```
