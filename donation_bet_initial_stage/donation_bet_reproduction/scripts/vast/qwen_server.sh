#!/usr/bin/env bash
set -euo pipefail

source /venv/main/bin/activate
if [[ -f /workspace/.env ]]; then
  set -a
  source /workspace/.env
  set +a
fi

export HF_HOME="${GIRAFFES_HF_HOME:-${HF_HOME:-/workspace/.hf_home}}"

exec vllm serve Qwen/Qwen3.6-27B \
  --served-model-name Qwen/Qwen3.6-27B \
  --host 127.0.0.1 \
  --port 8000 \
  --dtype bfloat16 \
  --max-model-len 20000 \
  --gpu-memory-utilization 0.94 \
  --max-num-seqs 16 \
  --enable-prefix-caching \
  --language-model-only \
  --reasoning-parser qwen3
