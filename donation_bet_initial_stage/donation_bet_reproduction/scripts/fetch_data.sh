#!/usr/bin/env bash
set -euo pipefail

profile="${1:-main}"
case "$profile" in
  main|all) ;;
  *)
    echo "Usage: $0 [main|all]" >&2
    exit 2
    ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
data_dir="$repo_root/data"
data_repo="https://github.com/TruthfulAI-research/value_leakage_data.git"
data_commit="dfa085df38c48b98a66b4af2b095f50f600ba6e6"

main_paths=(
  final_data/cache
  final_data/estimate_judge_cache
  final_data/plot_cot_categories_v2_cache
  final_data/trajectories
)
all_paths=(
  "${main_paths[@]}"
  final_data/plot_cot_categories_cache
  final_data/plot_eval_awareness_cache
  final_data/run_monitorability_cache
)

if [[ -e "$data_dir/.git" ]]; then
  current="$(git -C "$data_dir" rev-parse HEAD)"
  if [[ "$current" != "$data_commit" ]]; then
    echo "Refusing to replace existing data checkout at $current" >&2
    echo "Expected pinned commit: $data_commit" >&2
    exit 1
  fi
else
  if [[ -d "$data_dir" ]]; then
    if find "$data_dir" -mindepth 1 -print -quit | grep -q .; then
      echo "Refusing to overwrite non-empty directory: $data_dir" >&2
      exit 1
    fi
    rmdir "$data_dir"
  elif [[ -e "$data_dir" ]]; then
    echo "Refusing to overwrite non-directory: $data_dir" >&2
    exit 1
  fi
  git clone --filter=blob:none --sparse "$data_repo" "$data_dir"
  git -C "$data_dir" fetch --depth 1 origin "$data_commit"
fi

git -C "$data_dir" sparse-checkout init --cone
if [[ "$profile" == "main" ]]; then
  git -C "$data_dir" sparse-checkout set "${main_paths[@]}"
else
  git -C "$data_dir" sparse-checkout set "${all_paths[@]}"
fi
git -C "$data_dir" checkout --detach "$data_commit"

echo "Fetched Donation Bet '$profile' artifacts at $data_commit"
du -sh "$data_dir/final_data"

