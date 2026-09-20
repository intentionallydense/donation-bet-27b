#!/usr/bin/env bash
set -euo pipefail

readonly PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly CODE_ROOT="${PROJECT_ROOT}/donation_bet_reproduction"
readonly DATA_ROOT="${PROJECT_ROOT}/vast_snapshots/eval_notice_final_20.64.248.96_20047/data/giraffes_screen_eval_note_test"
readonly SECRETS_FILE="/home/iodide/nix-config/secrets/secrets.yaml"
readonly PYTHON="${PROJECT_ROOT}/../.judge-venv/bin/python"

export LD_LIBRARY_PATH="/run/current-system/sw/share/nix-ld/lib"
export PYTHONPATH="${CODE_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

OPENAI_API_KEY="$(
    sops decrypt --extract '["OPENAI_API_KEY"]' "${SECRETS_FILE}"
)"
if [[ -z "${OPENAI_API_KEY}" ]]; then
    echo "SOPS returned an empty OpenAI API key" >&2
    exit 1
fi
export OPENAI_API_KEY

cd "${CODE_ROOT}"
"${PYTHON}" scripts/repair_estimate_judge_cache.py \
    --data-root "${DATA_ROOT}" \
    --experiment giraffes_eval_awareness_screen_eval_note_test \
    --max-attempts 0
"${PYTHON}" scripts/repair_eval_awareness_cache.py \
    --data-root "${DATA_ROOT}" \
    --experiment giraffes_eval_awareness_screen_eval_note_test
unset OPENAI_API_KEY
