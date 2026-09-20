# Vendored upstream: TruthfulAI-research/value_leakage (pristine subset)

Pristine, byte-for-byte copies of the **only** upstream files this project uses,
taken from the Donation Bet code release for *Value Leakage: An LLM's Answers
Are Silently Shaped by Its Own Values* (arXiv:2607.14345).

- Repository: <https://github.com/TruthfulAI-research/value_leakage>
- Commit: `f7e5480cfe8abeb64b7007ba24fb0164519c3b68`
- Verification: every file's git blob SHA-1 matches the upstream tree at that
  commit; `UPSTREAM_FILES.sha256` records SHA-256 for local integrity checks.
- **License: the upstream repository has no LICENSE file.** This copy is for
  private research use only. Do not redistribute it or make a repository
  containing it public without a license from the authors.

Nothing here is imported directly. The runnable copy lives in
`donation_bet_initial_stage/donation_bet_reproduction/` and equals this
directory plus `upstream.patch` plus our own files (see the README there).

## What we use, and for what

| File | Used for |
|---|---|
| `shared/runner.py` | `_create_sender` (API client factory) and `_parse_tagged_estimate` (reads `<final_estimate>` tags): used by the Luna estimate extractor; whole runner drove the stage-1 screen. **Patched.** |
| `shared/prompts/thresholds.py` | `_NUMBER_JUDGE_PROMPT` (estimate-extraction judge prompt) and `_QUESTIONS` (Fermi question bank, incl. giraffes). |
| `shared/judge_jsonl_cache.py` | `JsonlJudgeCache`, judge-result caching (transitive). |
| `shared/classify_eval_awareness.py` | Eval-awareness judge, stage-1 screen. **Patched** (judge model). |
| `shared/models.py` | Model registry, stage-1 screen. **Patched** (adds local Qwen3.6-27B). Reads `shared/system_prompts/*.txt` at import time. |
| `shared/get_main_dfs.py` | Loads the paper's released data frames, stage-1 screen. |
| `shared/experiments/thresholds.py` | Threshold-experiment registry. **Patched** (adds the giraffe eval-awareness screen). |
| `shared/prompts/__init__.py` | Prompt registry. **Patched** (registers our screening prompts). |
| `shared/__init__.py`, `shared/experiments/__init__.py`, `donation_bet/__init__.py` | Package markers. |
| `shared/system_prompts/*.txt` | Claude system prompts read by `models.py`. |
| `pyproject.toml`, `sitecustomize.py` | Upstream environment definition and startup shim, kept for reference. |

## upstream.patch

Our modifications to the five patched files, as a unified diff against these
pristine copies. Apply from the working bundle directory with `patch -p1`.
Summary of what it changes:

- `shared/runner.py`: estimate-extraction judge switched from Claude Sonnet to
  GPT-5.6 Luna; `threshold_style` parameter added to the direction hash;
  imports `format_threshold`/`normalize_threshold` from our
  `shared/prompts/prompts.py`.
- `shared/models.py`: adds the `qwen3.6-27b-local` entry (local OpenAI-style
  server, Qwen thinking-mode sampling settings).
- `shared/classify_eval_awareness.py`: judge model GPT-5.6 Luna at max effort.
- `shared/experiments/thresholds.py`: registers `giraffes_eval_awareness_screen`.
- `shared/prompts/__init__.py`: merges our `SCREENING_PROMPTS` into
  `THRESHOLD_PROMPTS`.

The other ~40 upstream files originally copied (plotting, monitorability,
trajectories, Tinker support, their tests) were never used and were removed on
2026-09-04. Refetch from the pinned commit if ever needed.
