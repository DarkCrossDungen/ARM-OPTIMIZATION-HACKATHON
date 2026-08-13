# Architecture

```text
Browser dashboard -> private API/control service -> orchestration -> evidence JSON
                                           |
                                           v
                         llama-bench on Azure Cobalt 100 Arm64 VM
                                           |
                                           v
                    GGUF models + llama.cpp Arm CPU runtime builds
```

The API runs as a private `systemd` service on an Azure Cobalt 100 Arm64 Linux VM next to the model files and `llama.cpp` builds. The browser dashboard opens from a laptop through an SSH local tunnel, so the dashboard service remains bound to `127.0.0.1:8000` on the VM and is not exposed publicly.

Local preview mode may show the dashboard, a candidate plan, and sample report shape, but it never creates measured performance claims. Only the Arm64 worker running on the VM can produce `measured_on_arm=true` evidence.

## Runtime builds

ArmDX compares finite, reproducible `llama.cpp` runtime builds:

- `stock` — reference CPU build without KleidiAI.
- `kleidiai` — Arm KleidiAI CPU kernels enabled.
- `kleidiai-openblas` — KleidiAI plus OpenBLAS comparison build.

## Current MVP flows

- **Make it faster:** `Q8_0 + stock` baseline vs `Q8_0 + kleidiai` and `Q8_0 + kleidiai-openblas`.
- **Keep quality:** high-fidelity `Q8_0` profile across Arm runtime builds.
- **Reduce disk size:** `Q8_0` baseline vs smaller `Q4_0` / `Q4_K_M` candidates.

Completed measured jobs are persisted as JSON under `evidence/jobs/` and loaded into dashboard history after service restart.
