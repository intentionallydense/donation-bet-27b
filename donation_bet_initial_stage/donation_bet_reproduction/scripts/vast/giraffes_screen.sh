#!/usr/bin/env bash
set -euo pipefail

source /venv/main/bin/activate
set -a
source /workspace/.env
set +a

export PYTHONUNBUFFERED=1
export OPENAI_TIMEOUT=600
export LOCAL_OPENAI_TIMEOUT=1800

cd /workspace/donation_bet_reproduction
exec python3 -m donation_bet.run_giraffes_screen
