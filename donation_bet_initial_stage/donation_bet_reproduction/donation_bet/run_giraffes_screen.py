"""Run and annotate the eight-condition Qwen giraffes screening experiment."""

import json
from pathlib import Path

import pandas as pd

import shared.runner as runner
from shared.classify_eval_awareness import (
    classify_eval_awareness,
    eval_awareness_cache_dir,
)
from shared.get_main_dfs import get_main_dfs


MODEL = "qwen3.6-27b-local"
EXPERIMENT = "giraffes_eval_awareness_screen"
DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "giraffes_screen"


def main():
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    runner.CACHE_DIR = str(DATA_ROOT / "cache")
    runner.ESTIMATE_JUDGE_CACHE_ROOT = str(DATA_ROOT / "estimate_judge_cache")

    raw_df, thresholds, display_name = get_main_dfs(
        EXPERIMENT,
        [MODEL],
        raw=True,
    )[MODEL]

    annotated = raw_df.copy()
    annotated["eval_awareness_raw"] = None
    annotated["eval_awareness_reasoning"] = None
    annotated["eval_awareness_score"] = None
    annotated["eval_aware"] = False

    # Baselines are only used to set the threshold; the setup comparison is
    # between directional donation-bet prompts, so judge those 1,600 traces.
    directional_mask = annotated["direction"] != "baseline"
    directional = annotated.loc[directional_mask].copy()
    classify_eval_awareness(
        directional,
        cache_dir=eval_awareness_cache_dir(
            EXPERIMENT,
            cache_root=DATA_ROOT / "eval_awareness_cache",
        ),
    )
    for column in (
        "eval_awareness_raw",
        "eval_awareness_reasoning",
        "eval_awareness_score",
        "eval_aware",
    ):
        annotated.loc[directional_mask, column] = directional[column]

    with (DATA_ROOT / "results_with_traces.jsonl").open("w") as f:
        for row in annotated.to_dict(orient="records"):
            f.write(json.dumps(row, default=str) + "\n")

    with (DATA_ROOT / "thresholds.json").open("w") as f:
        json.dump(thresholds, f, indent=2, sort_keys=True)

    directional = annotated[directional_mask].copy()
    directional["estimate_parsed"] = directional["estimate"].notna()
    summary = (
        directional.groupby("prompt_key", as_index=False)
        .agg(
            n=("prompt_key", "size"),
            traces_kept=("reasoning", lambda s: int(s.fillna("").str.len().gt(0).sum())),
            estimates_parsed=("estimate_parsed", "sum"),
            eval_awareness_scored=("eval_awareness_score", "count"),
            eval_aware_count=("eval_aware", "sum"),
            mean_eval_awareness_score=("eval_awareness_score", "mean"),
        )
    )
    summary["eval_aware_rate"] = (
        summary["eval_aware_count"] / summary["eval_awareness_scored"]
    )
    summary = summary.sort_values(
        ["eval_aware_rate", "mean_eval_awareness_score", "prompt_key"]
    )
    summary.to_csv(DATA_ROOT / "eval_awareness_summary.csv", index=False)

    print(f"Completed {display_name}: {len(annotated)} materialized rows")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
