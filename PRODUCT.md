# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Developers and hackathon judges who need to evaluate and tune local LLM inference on Arm64 Linux hardware without manually guessing `llama.cpp` runtime flags.

## Product Purpose

ArmDX is a local operator console for safely controlling one remote Arm64 VM: it configures reproducible `llama.cpp` benchmark runs, observes their progress, and displays the measured evidence returned by that VM.

## Positioning

The product does not claim a speedup in advance: it runs a reproducible Arm64 benchmark on the connected Oracle VM and preserves the raw output that supports each result.

## Operating Context

The operator uses a localhost dashboard on a Windows laptop. Once an Oracle Arm64 VM is provisioned, the remote service runs only on the VM loopback interface and the laptop reaches it through a user-owned SSH local tunnel. At present the VM and SSH tunnel are not configured.

## Capabilities and Constraints

- MVP supports one `llama.cpp` GGUF model and one benchmark job at a time.
- Safe controls cover objective, context size, threads, batch sizing, and a memory guardrail.
- Preview mode must show no invented performance figures while no Arm VM is connected.
- The console must visibly distinguish local-preview, disconnected, connecting, ready, running, failed, and complete states.
- The remote service must accept only an allowed model directory and safe runtime configuration.
- Measured output must distinguish prompt processing, generation speed, and memory use.

## Brand Commitments

The product name is ArmDX. The interface uses #000807, #b80c09, #f1f7ed, and #7ca982, with cobalt blue added as the primary operational accent. It must feel modern and substantive, use typography and open structure rather than repetitive boxes, and avoid generic AI-dashboard styling.

## Evidence on Hand

- [docs/product-spec.md](docs/product-spec.md) defines benchmark and evidence rules.
- There is no connected Arm64 VM or measured benchmark result yet.

## Product Principles

1. Show what is measured and keep unknown values visibly unknown.
2. Make safe Arm64 tuning understandable without hiding constraints.
