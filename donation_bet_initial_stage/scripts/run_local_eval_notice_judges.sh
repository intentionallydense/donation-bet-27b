#!/usr/bin/env bash
set -euo pipefail

readonly PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly CODE_ROOT="${PROJECT_ROOT}/donation_bet_reproduction"
readonly SOURCE_ROOT="${PROJECT_ROOT}/vast_snapshots/rerun_20.64.248.96_20047/data/giraffes_screen"
readonly NOTICE_ROOT="${PROJECT_ROOT}/vast_snapshots/eval_notice_final_20.64.248.96_20047/data/giraffes_screen_eval_note_test"
readonly SECRETS_FILE="/home/iodide/nix-config/secrets/secrets.yaml"
readonly NIX_LD_LIBRARY_PATH="/run/current-system/sw/share/nix-ld/lib"
readonly PYTHON="${PROJECT_ROOT}/../.judge-venv/bin/python"

for required in \
    "${SOURCE_ROOT}/results_with_traces.jsonl" \
    "${SOURCE_ROOT}/thresholds.json" \
    "${NOTICE_ROOT}/cache" \
    "${SECRETS_FILE}" \
    "${PYTHON}"
do
    if [[ ! -e "${required}" ]]; then
        echo "Missing required local artifact: ${required}" >&2
        exit 1
    fi
done

export GIRAFFES_SOURCE_DATA_ROOT="${SOURCE_ROOT}"
export GIRAFFES_NOTICE_DATA_ROOT="${NOTICE_ROOT}"
export GIRAFFES_DIRECTIONS_CACHE_ONLY="1"
export LD_LIBRARY_PATH="${NIX_LD_LIBRARY_PATH}"
export LOCAL_JUDGE_PYTHON="${PYTHON}"
export LOCAL_JUDGE_SCRIPT="${CODE_ROOT}/donation_bet/run_giraffes_screen_eval_notice.py"
export PYTHONPATH="${CODE_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

# Decrypt only the one required key into this process. Direction cache-only mode
# guarantees the stopped local Qwen endpoint cannot be contacted.
OPENAI_API_KEY="$(
    sops decrypt --extract '["OPENAI_API_KEY"]' "${SECRETS_FILE}"
)"
if [[ -z "${OPENAI_API_KEY}" ]]; then
    echo "SOPS returned an empty OpenAI API key" >&2
    exit 1
fi
export OPENAI_API_KEY
cd "${CODE_ROOT}"
"${LOCAL_JUDGE_PYTHON}" "${LOCAL_JUDGE_SCRIPT}"
unset OPENAI_API_KEY
