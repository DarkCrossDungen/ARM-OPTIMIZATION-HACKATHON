# Product specification

## Problem

Tuning local LLM inference on Arm64 servers requires knowledge of runtime flags,
model quantization, and fair benchmarking. A developer should not have to guess
which configuration will improve their workload.

## MVP promise

For one GGUF model running through `llama.cpp` on one Arm64 Linux VM, the tool
finds the best configuration from a limited, safe search space.

## Controls

- model file and quantization
- generation and prompt threads
- batch and micro-batch size
- context size
- memory guardrail
- fixed, reproducible benchmark workload

## Evidence rules

1. Compare the same model, VM, build, prompt size, generation length, and repetitions.
2. Keep raw command output and system metadata.
3. Reject failures and profiles that exceed memory limits.
4. Report prompt processing and token generation separately.
