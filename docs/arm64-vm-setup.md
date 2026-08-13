# Arm64 VM Setup Runbook

This runbook describes the private ArmDX benchmark host.
The hackathon demo uses an Azure Cobalt 100 Arm64 VM, but the steps work on any Ubuntu 22.04/24.04 Arm64 Linux VM.

---

## 1. Provision the VM

Tested configuration:

```text
Cloud provider : Microsoft Azure
VM SKU         : Standard_D4ps_v6
CPU            : Azure Cobalt 100 Arm64 (4 vCPUs)
OS             : Ubuntu 24.04 LTS Arm64
Login user     : azureuser   (or the name you choose at VM creation)
Disk           : >= 30 GB  (llama.cpp build artifacts + three GGUF files ~6-7 GB)
```

**Azure networking rules (required before you start):**

| Rule | Direction | Port | Source |
|------|-----------|------|--------|
| SSH  | Inbound   | 22   | Your laptop's public IP only |
| (none) | Inbound | 8000 | **Do not open.** Access via SSH tunnel only. |

---

## 2. Clone the repository

```bash
git clone https://github.com/DarkCrossDungen/ARM-OPTIMIZATION-HACKATHON.git armdx
cd armdx
```

All subsequent commands in this runbook assume you are inside the `armdx/` directory.

---

## 3. Install system packages and build llama.cpp

Run the bundled setup script. It installs all required system packages, clones `llama.cpp`,
builds all three candidate runtimes, creates the Python virtual environment, and creates
the `models/`, `evidence/`, and `quality/` directories.

```bash
chmod +x scripts/setup-arm64-vm.sh
./scripts/setup-arm64-vm.sh
```

What the script does (verbatim from `scripts/setup-arm64-vm.sh`):

```bash
# System packages
sudo apt-get update
sudo apt-get install --yes \
  build-essential cmake git libssl-dev libopenblas-dev \
  python3-venv python3-pip

# Clone llama.cpp (skipped if already present)
git clone https://github.com/ggml-org/llama.cpp.git

# Build 1: stock (no KleidiAI)
cmake -S llama.cpp -B llama.cpp/build-stock -DGGML_CPU_KLEIDIAI=OFF
cmake --build llama.cpp/build-stock --config Release --parallel

# Build 2: KleidiAI
cmake -S llama.cpp -B llama.cpp/build-kleidiai -DGGML_CPU_KLEIDIAI=ON
cmake --build llama.cpp/build-kleidiai --config Release --parallel

# Build 3: KleidiAI + OpenBLAS
cmake -S llama.cpp -B llama.cpp/build-kleidiai-openblas \
  -DGGML_CPU_KLEIDIAI=ON -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS
cmake --build llama.cpp/build-kleidiai-openblas --config Release --parallel

# Python virtual environment
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -r llama.cpp/requirements.txt

# Runtime directories
mkdir -p models evidence quality
```

Expected build artifacts after the script completes:

```text
llama.cpp/build-stock/bin/llama-bench
llama.cpp/build-stock/bin/llama-quantize
llama.cpp/build-kleidiai/bin/llama-bench
llama.cpp/build-kleidiai/bin/llama-quantize
llama.cpp/build-kleidiai-openblas/bin/llama-bench
llama.cpp/build-kleidiai-openblas/bin/llama-quantize
```

Allow 10-20 minutes on a 4-vCPU VM for all three parallel builds.

---

## 4. Download and prepare the Qwen2.5 GGUF model files

The backend (`src/autopilot/main.py`) looks for these three files under `~/models/`
(the home directory of the service user, e.g. `/home/azureuser/models/`):

```text
~/models/qwen2.5-1.5b-instruct-q8_0.gguf    (~1570 MB)
~/models/qwen2.5-1.5b-instruct-q4_0.gguf    (~ 892 MB)
~/models/qwen2.5-1.5b-instruct-q4_k_m.gguf  (~1066 MB)
```

Note: this is `$HOME/models/`, **not** the `models/` subdirectory inside the cloned repository.

### Option A — Convert from Hugging Face source (on-VM)

This uses the `convert_hf_to_gguf.py` script that ships with `llama.cpp` and the
`llama-quantize` binary built in Step 3. `huggingface_hub` is already installed by
`requirements.txt`.

```bash
MODELS_DIR="$HOME/models"
mkdir -p "$MODELS_DIR"

# Download and convert the BF16 source GGUF (~3.1 GB download)
python3 llama.cpp/convert_hf_to_gguf.py \
  --remote Qwen/Qwen2.5-1.5B-Instruct \
  --outfile "$MODELS_DIR/qwen2.5-1.5b-instruct-BF16.gguf" \
  --outtype bf16

# Quantize to Q8_0
llama.cpp/build-kleidiai/bin/llama-quantize \
  "$MODELS_DIR/qwen2.5-1.5b-instruct-BF16.gguf" \
  "$MODELS_DIR/qwen2.5-1.5b-instruct-q8_0.gguf" Q8_0

# Quantize to Q4_0
llama.cpp/build-kleidiai/bin/llama-quantize \
  "$MODELS_DIR/qwen2.5-1.5b-instruct-BF16.gguf" \
  "$MODELS_DIR/qwen2.5-1.5b-instruct-q4_0.gguf" Q4_0

# Quantize to Q4_K_M
llama.cpp/build-kleidiai/bin/llama-quantize \
  "$MODELS_DIR/qwen2.5-1.5b-instruct-BF16.gguf" \
  "$MODELS_DIR/qwen2.5-1.5b-instruct-q4_k_m.gguf" Q4_K_M

# Remove the large BF16 source to free disk space
rm "$MODELS_DIR/qwen2.5-1.5b-instruct-BF16.gguf"
```

### Option B — Download pre-quantized files from Hugging Face

```bash
MODELS_DIR="$HOME/models"
mkdir -p "$MODELS_DIR"

.venv/bin/huggingface-cli download \
  Qwen/Qwen2.5-1.5B-Instruct-GGUF \
  qwen2.5-1.5b-instruct-q8_0.gguf \
  --local-dir "$MODELS_DIR"

.venv/bin/huggingface-cli download \
  Qwen/Qwen2.5-1.5B-Instruct-GGUF \
  qwen2.5-1.5b-instruct-q4_0.gguf \
  --local-dir "$MODELS_DIR"

.venv/bin/huggingface-cli download \
  Qwen/Qwen2.5-1.5B-Instruct-GGUF \
  qwen2.5-1.5b-instruct-q4_k_m.gguf \
  --local-dir "$MODELS_DIR"
```

Verify the files are present and correctly named:

```bash
ls -lh "$HOME/models/"
# Expected:
# qwen2.5-1.5b-instruct-q4_0.gguf    892M
# qwen2.5-1.5b-instruct-q4_k_m.gguf  1.1G
# qwen2.5-1.5b-instruct-q8_0.gguf    1.6G
```

---

## 5. Install and enable the systemd service

The `install-armdx-service.sh` script patches `deploy/armdx.service` with the correct
project directory and service user, installs it to `/etc/systemd/system/armdx.service`,
and enables it.

```bash
# Run from inside the armdx/ project directory
sudo bash scripts/install-armdx-service.sh "$(pwd)" azureuser
```

Replace `azureuser` with the actual login user if different (e.g. `ubuntu`).

### Verify the service is running

```bash
sudo systemctl status armdx
```

Expected: `Active: active (running)` and a log line:

```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Follow live logs:

```bash
sudo journalctl -u armdx -f
```

The service binds only to `127.0.0.1:8000`. Port 8000 is never exposed publicly.

For manual troubleshooting only:

```bash
sudo systemctl stop armdx
.venv/bin/python -m uvicorn autopilot.main:app --app-dir src --host 127.0.0.1 --port 8000
```

---

## 6. (Optional) Harden SSH access

```bash
# Replace 203.0.113.10 with your actual laptop public IP
sudo bash scripts/harden-ubuntu-ssh.sh 203.0.113.10 azureuser
```

This script disables password authentication, restricts `AllowUsers`, sets
`AllowTcpForwarding local` (required for the SSH tunnel), and enables `ufw`.

Keep your existing SSH session open and verify key-only login in a second terminal
before disconnecting.

### Verify security posture on the VM

```bash
bash scripts/verify-remote-security.sh
```

Confirm that `Dashboard listeners` shows `127.0.0.1:8000` only, not `0.0.0.0:8000`.

---

## 7. Open the dashboard from your laptop

### Linux / macOS

```bash
ssh -i ~/.ssh/armdx_azure \
    -N \
    -L 127.0.0.1:8000:127.0.0.1:8000 \
    azureuser@<VM_PUBLIC_IP>
```

### Windows (PowerShell)

```powershell
.\scripts\start-ssh-tunnel.ps1 -VmHost <VM_PUBLIC_IP> -KeyPath C:\Users\you\.ssh\armdx_azure -VmUser azureuser
```

Keep the tunnel terminal open. Navigate to:

```text
http://127.0.0.1:8000
```

Confirm live ARM64 mode:

```bash
curl http://127.0.0.1:8000/api/health
# {"status":"ok","mode":"arm64-live","vm":"connected"}
```

---

## 8. Run the first measured benchmark

1. Open `http://127.0.0.1:8000` in your browser.
2. Select an optimization goal:
   - **Make it faster** — Q8_0 model across stock / KleidiAI / KleidiAI+OpenBLAS builds
   - **Keep quality** — high-fidelity Q8_0 profile, selects fastest Arm runtime
   - **Reduce disk size** — compares Q8_0, Q4_0, Q4_K_M file sizes and speeds
3. Click **Run Optimization**.
4. The backend runs `llama-bench` three times per candidate, collects JSON, selects the winner,
   and stores evidence in `evidence/jobs/<job-id>.json`.

---

## Benchmark integration

ArmDX runs the same workload for baseline and candidates, retains raw `llama-bench` JSON, and marks evidence as measured only when the worker runs on Arm64 hardware.

Completed measured jobs are stored under:

```text
evidence/jobs/<job-id>.json
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `llama-bench not found` | Build did not complete | Re-run `./scripts/setup-arm64-vm.sh`; check `llama.cpp/build-*/bin/llama-bench` |
| `Baseline model not found` | Wrong path or filename | Confirm files in `$HOME/models/` with exact names from Step 4 |
| `mode: local-preview` in `/api/health` | Service not on Arm64 host | Deploy on Arm64 VM; verify `uname -m` returns `aarch64` |
| `active (failed)` in systemctl | Python import error | Run `sudo journalctl -u armdx -n 50` and fix reported error |
| Port 8000 connection refused | Service not running or tunnel closed | Check `sudo systemctl status armdx` and keep the SSH tunnel open |
| HTTP 409 on new job | Previous job still running | Wait for completion or restart the service |
