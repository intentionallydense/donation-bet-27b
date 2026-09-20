# Prompt inventory

Index of the upstream prompt text this bundle still carries (value_leakage @
f7e5480; pristine copies in `../../upstream_value_leakage/`). Rows for prompt
families we never used (CoT disclosure judge, monitor, trajectory extractor,
eval-notice suite, honesty/Conglomerate system prompts) were removed on
2026-09-04 along with their modules; they exist at the pinned upstream commit.
`prompts/main_experiment_accurate.json` is an export of upstream prompt text
produced by `scripts/export_prompts.py`, not something we wrote.

| Paper component | Exact prompt location |
|---|---|
| Nine Fermi questions; baseline, below-good, above-good, and framing variants | `shared/prompts/thresholds.py` |
| Main 9 x 3 prompt export plus estimate-extraction judges | `prompts/main_experiment_accurate.json` |
| Experiment sizes and threshold percentiles | `shared/experiments/thresholds.py` |
| Evaluation-awareness judge | `shared/classify_eval_awareness.py`, `EVAL_AWARENESS_PROMPT_UKAISI` |
| Claude.ai system-prompt snapshots | `shared/system_prompts/*.txt` |
| Model aliases, temperatures, token budgets, reasoning effort, and optional system prompts | `shared/models.py` |

Regenerate the JSON export after intentionally editing a prompt:

```bash
python scripts/export_prompts.py
```

The JSON preserves `{threshold}` as a placeholder because the actual threshold
is computed separately for every model/question from that model's baseline
median. This is part of the experiment, not a missing constant.

