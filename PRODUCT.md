# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Developers and hackathon judges who need to evaluate and tune local LLM inference on Arm64 Linux hardware without manually guessing `llama.cpp` runtime flags.

## Product Purpose

ArmDX is a local operator console for safely controlling one remote Arm64 VM: it configures reproducible `llama.cpp` benchmark runs, observes their progress, stores evidence, and displays the measured result returned by that VM.

## Positioning

The product does not claim a speedup in advance. It runs matched benchmarks on the connected Azure Cobalt 100 Arm64 VM and preserves the raw output that supports each result.

## Operating Context

The operator uses a localhost dashboard on a Windows laptop. The remote service runs only on the Arm64 VM loopback interface, and the laptop reaches it through a user-owned SSH local tunnel. The dashboard remains private; port 8000 is not opened to the internet.

## Capabilities and Constraints

- MVP supports one approved `llama.cpp` GGUF model family and one benchmark job at a time.
- User-facing controls are intentionally simple: Make it faster, Keep quality, and Reduce disk size.
- Speed mode compares the same `Q8_0` model across stock, KleidiAI, and KleidiAI + OpenBLAS runtime builds.
- Lightweight mode compares smaller GGUF candidates and selects the smallest successfully measured profile.
- Keep Quality mode keeps the high-fidelity `Q8_0` profile and selects the fastest measured Arm runtime.
- Preview mode must show no invented performance figures while no Arm VM is connected.
- The remote service must accept only allowed model paths and safe runtime configuration.
- Measured output must distinguish prompt processing speed, generation speed, and model file size.
- Measured job history is persisted under `evidence/jobs/` and reloads after service restart.

## Brand Commitments

The product name is ArmDX. The interface uses #000807, #b80c09, #f1f7ed, and #7ca982, with cobalt blue added as the primary operational accent. It must feel modern and substantive, use typography and open structure rather than repetitive boxes, and avoid generic AI-dashboard styling.

## Evidence on Hand

- [docs/product-spec.md](docs/product-spec.md) defines benchmark and evidence rules.
- Live Azure Cobalt 100 Arm64 runs measured speed, quality-profile, and disk-size flows.
- [results/summary.md](results/summary.md) summarizes the current measured demo results.

## Product Principles

1. Show what is measured and keep unknown values visibly unknown.
2. Make safe Arm64 tuning understandable without hiding constraints.
3. Prefer truthful evidence over promotional claims.
