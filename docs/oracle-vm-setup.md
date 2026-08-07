# Oracle Arm64 VM setup

## Provisioning

Create an Ubuntu Arm64 Ampere A1 VM in Oracle Cloud. Keep SSH (port 22) open
only to your own public IP. Do not expose the dashboard port publicly.

## Install the project

```bash
git clone YOUR_GITHUB_REPOSITORY arm-llm-autopilot
cd arm-llm-autopilot
chmod +x scripts/setup-oracle-arm64.sh
./scripts/setup-oracle-arm64.sh
```

The setup script creates `models/`, `evidence/`, and `quality/`. ArmDX's
measured worker downloads only its approved source model and creates its GGUF
candidates inside `models/`; do not copy untrusted model paths into the service.

## Install the private system service

On the VM:

```bash
sudo bash scripts/install-armdx-service.sh "$(pwd)" ubuntu
sudo systemctl status armdx
```

The service binds only to `127.0.0.1:8000` and restarts after a failure or VM reboot.

For troubleshooting only, stop the service and run it manually:

```bash
sudo systemctl stop armdx
.venv/bin/python -m uvicorn autopilot.main:app --app-dir src --host 127.0.0.1 --port 8000
```

On the laptop:

```bash
.\scripts\start-ssh-tunnel.ps1 -VmHost VM_PUBLIC_IP -KeyPath "$env:USERPROFILE\.ssh\armdx_ed25519"
```

Open `http://127.0.0.1:8000` on the laptop. The browser traffic travels
through SSH; port 8000 remains private to the VM.

## Benchmark integration

ArmDX creates its approved GGUF candidates on the VM, runs the same workload
for every candidate, retains raw JSON output, and will not treat sample data as
evidence. Use the Security runbook before starting the system service.
