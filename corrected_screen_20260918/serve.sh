#!/bin/bash
set -euo pipefail
export HF_HOME=/dev/shm/donation-hf
export HF_HUB_OFFLINE=1
exec /venv/main/bin/vllm serve /dev/shm/donation-hf/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9 --served-model-name Qwen/Qwen3.6-27B --host 127.0.0.1 --port 8000 --dtype bfloat16 --max-model-len 20000 --gpu-memory-utilization 0.94 --max-num-seqs 16 --enable-prefix-caching --language-model-only --reasoning-parser qwen3
