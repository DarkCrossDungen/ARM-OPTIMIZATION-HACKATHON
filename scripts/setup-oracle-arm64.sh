#!/usr/bin/env bash
set -euo pipefail

# Run on an Ubuntu Arm64 Oracle Ampere A1 VM after cloning this repository.
sudo apt-get update
sudo apt-get install --yes build-essential cmake git libssl-dev libopenblas-dev python3-venv python3-pip

if [ ! -d llama.cpp ]; then
  git clone https://github.com/ggml-org/llama.cpp.git
fi

# Build all candidate runtimes once. ArmDX benchmarks them on the same VM and
# retains only the build that wins for the selected user goal.
cmake -S llama.cpp -B llama.cpp/build-stock -DGGML_CPU_KLEIDIAI=OFF
cmake --build llama.cpp/build-stock --config Release --parallel

cmake -S llama.cpp -B llama.cpp/build-kleidiai -DGGML_CPU_KLEIDIAI=ON
cmake --build llama.cpp/build-kleidiai --config Release --parallel

cmake -S llama.cpp -B llama.cpp/build-kleidiai-openblas \
  -DGGML_CPU_KLEIDIAI=ON -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS
cmake --build llama.cpp/build-kleidiai-openblas --config Release --parallel

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -r llama.cpp/requirements.txt

mkdir -p models evidence quality
echo "Setup complete. ArmDX downloads Qwen source and creates GGUF candidates on this VM."
