# ArmDX Benchmark Summary

These results were measured on the live ArmDX Azure Arm64 benchmark host. ArmDX reports measured values only; no sample or preview data is included in this summary.

## Environment

| Item | Value |
| --- | --- |
| Cloud provider | Microsoft Azure |
| VM | Standard_D4ps_v6 |
| CPU | Azure Cobalt 100 Arm64 |
| OS | Ubuntu Arm64 |
| Runtime | llama.cpp |
| Runtime builds | stock, KleidiAI, KleidiAI + OpenBLAS |
| Model | Qwen2.5 1.5B Instruct |
| Workload | 1024 prompt tokens, 128 generated tokens |
| Threads | 4 |
| Repetitions | 3 |

## Make it faster

Speed mode compares the same `Q8_0` model and workload across runtime builds, so the runtime optimization is isolated from quantization changes.

| Profile | Prompt tok/s | Generation tok/s |
| --- | ---: | ---: |
| `Q8_0 + stock` | 73.95 | 37.51 |
| `Q8_0 + KleidiAI` | 97.28 | 42.68 |
| `Q8_0 + KleidiAI + OpenBLAS` | 96.87 | 40.61 |

Selected profile:

```text
Q8_0 + KleidiAI
```

Measured improvement:

| Metric | Baseline | Selected | Change |
| --- | ---: | ---: | ---: |
| Prompt processing | 73.95 tok/s | 97.28 tok/s | +31.5% |
| Generation | 37.51 tok/s | 42.68 tok/s | +13.8% |

## Reduce disk size

Lightweight mode compares the `Q8_0` baseline against smaller GGUF candidates and selects the smallest successfully measured profile.

| Profile | Size | Prompt tok/s | Generation tok/s |
| --- | ---: | ---: | ---: |
| `Q8_0 + stock` | 1570 MB | 74.36 | 36.87 |
| `Q4_0 + stock` | 892 MB | 80.55 | 35.17 |
| `Q4_0 + KleidiAI` | 892 MB | 80.81 | 34.39 |
| `Q4_K_M + stock` | 1066 MB | 62.82 | 32.39 |

Selected profile:

```text
Q4_0 + stock
```

Measured change:

| Metric | Baseline | Selected | Change |
| --- | ---: | ---: | ---: |
| GGUF file size | 1570 MB | 892 MB | about 43% smaller |
| Prompt processing | 74.36 tok/s | 80.55 tok/s | +8.3% |
| Generation | 36.87 tok/s | 35.17 tok/s | -4.6% |

## Keep quality

Keep Quality mode keeps the high-fidelity `Q8_0` profile and selects the fastest measured Arm runtime. This is not a separate semantic quality evaluation; it is a high-fidelity quantization profile.

| Profile | Prompt tok/s | Generation tok/s |
| --- | ---: | ---: |
| `Q8_0 + stock` | 74.33 | 36.63 |
| `Q8_0 + KleidiAI` | 97.19 | 42.86 |
| `Q8_0 + KleidiAI + OpenBLAS` | 97.41 | 42.47 |

Selected profile:

```text
Q8_0 + KleidiAI + OpenBLAS
```

Measured improvement:

| Metric | Baseline | Selected | Change |
| --- | ---: | ---: | ---: |
| Prompt processing | 74.33 tok/s | 97.41 tok/s | +31.1% |
| Generation | 36.63 tok/s | 42.47 tok/s | +16.0% |

## Evidence storage

Completed measured jobs are stored by the running VM service under:

```text
evidence/jobs/<job-id>.json
```

Those JSON files include the selected candidate, parsed measurements, and raw `llama-bench` output.
