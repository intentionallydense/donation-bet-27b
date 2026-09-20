"""Run the eight-condition Qwen screen with an explicit evaluation notice.

The run reuses the original no-notice baseline rows and fixed thresholds. It
does not issue baseline model or baseline estimate-judge requests; only the
1,600 directional prompts are newly sampled.
"""

import hashlib
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from tqdm import tqdm

import shared.runner as runner
from shared.classify_eval_awareness import (
    classify_eval_awareness,
    eval_awareness_cache_dir,
)
from shared.models import MODELS
from shared.prompts.screening import (
    EVAL_NOTICE_SUFFIX,
    EVAL_NOTICE_TEXT,
    SCREENING_OUTCOMES,
    SCREENING_STYLES,
)


MODEL = "qwen3.6-27b-local"
EXPERIMENT = "giraffes_eval_awareness_screen_eval_note_test"
N_PER_DIRECTION = 100
BASELINE_ROWS_PER_CONDITION = 100
REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DATA_ROOT = Path(
    os.environ.get(
        "GIRAFFES_SOURCE_DATA_ROOT",
        REPO_ROOT / "data" / "giraffes_screen",
    )
)
DATA_ROOT = Path(
    os.environ.get(
        "GIRAFFES_NOTICE_DATA_ROOT",
        REPO_ROOT / "data" / "giraffes_screen_eval_note_test",
    )
)
DIRECTIONS_CACHE_ONLY = os.environ.get(
    "GIRAFFES_DIRECTIONS_CACHE_ONLY", ""
).lower() in {"1", "true", "yes"}
PROMPT_KEYS = [
    f"screen_giraffes_{style}_{outcomes}_{EVAL_NOTICE_SUFFIX}"
    for style in SCREENING_STYLES
    for outcomes in SCREENING_OUTCOMES
]


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _base_prompt_key(notice_prompt_key):
    suffix = f"_{EVAL_NOTICE_SUFFIX}"
    if not notice_prompt_key.endswith(suffix):
        raise ValueError(f"not an eval-notice prompt key: {notice_prompt_key}")
    return notice_prompt_key[: -len(suffix)]


def _load_original_baselines_and_thresholds():
    results_path = SOURCE_DATA_ROOT / "results_with_traces.jsonl"
    thresholds_path = SOURCE_DATA_ROOT / "thresholds.json"
    if not results_path.exists() or not thresholds_path.exists():
        raise FileNotFoundError(
            "The completed no-notice giraffes screen is required at "
            f"{SOURCE_DATA_ROOT}"
        )

    source = pd.read_json(results_path, lines=True)
    source = source[source["direction"] == "baseline"].copy()
    with thresholds_path.open() as f:
        source_thresholds = json.load(f)

    baselines = {}
    thresholds = {}
    for notice_key in PROMPT_KEYS:
        base_key = _base_prompt_key(notice_key)
        rows = source[source["prompt_key"] == base_key].copy()
        if len(rows) != BASELINE_ROWS_PER_CONDITION:
            raise ValueError(
                f"Expected {BASELINE_ROWS_PER_CONDITION} baseline rows for "
                f"{base_key}, found {len(rows)}"
            )
        if rows["estimate"].isna().any():
            raise ValueError(f"Unparsed baseline estimate in {base_key}")
        baselines[notice_key] = rows
        thresholds[notice_key] = source_thresholds[base_key]

    metadata = {
        "experiment": EXPERIMENT,
        "evaluation_notice": EVAL_NOTICE_TEXT,
        "new_baseline_model_requests": 0,
        "new_baseline_estimate_judge_requests": 0,
        "reused_baseline_rows_per_condition": BASELINE_ROWS_PER_CONDITION,
        "new_direction_requests_per_arm_per_condition": N_PER_DIRECTION,
        "source_results": str(results_path),
        "source_results_sha256": _sha256(results_path),
        "source_thresholds": str(thresholds_path),
        "source_thresholds_sha256": _sha256(thresholds_path),
    }
    return baselines, thresholds, metadata


def _run_fixed_threshold_directions(baselines, thresholds):
    model = MODELS[MODEL]
    max_concurrent = model["max_concurrent"]
    sender = runner._lazy_sender(model)
    semaphore = threading.Semaphore(max_concurrent)
    total = len(PROMPT_KEYS) * 2 * N_PER_DIRECTION
    progress = tqdm(total=total, desc="Qwen3.6-27B eval-notice directions")
    all_dfs = {}
    all_cached = {}
    with ThreadPoolExecutor(max_workers=len(PROMPT_KEYS)) as executor:
        futures = {
            executor.submit(
                runner._run_directions_for_prompt,
                prompt_key,
                model,
                N_PER_DIRECTION,
                thresholds[prompt_key],
                MODEL,
                sender,
                max_concurrent,
                progress,
                baselines[prompt_key],
                semaphore,
                DIRECTIONS_CACHE_ONLY,
            ): prompt_key
            for prompt_key in PROMPT_KEYS
        }
        for future in as_completed(futures):
            prompt_key = futures[future]
            frame, cached_phases = future.result()
            all_dfs[prompt_key] = frame
            if cached_phases:
                all_cached[prompt_key] = cached_phases
    progress.close()

    if all_cached:
        parts = [
            f"{key}: {', '.join(phases)}"
            for key, phases in sorted(all_cached.items())
        ]
        print(f"Loaded direction phases from cache: {'; '.join(parts)}")

    combined = pd.concat(
        [all_dfs[key] for key in PROMPT_KEYS], ignore_index=True
    )
    direction_mask = combined["direction"] != "baseline"
    print("Extracting eval-notice direction estimates (judge)...")
    direction_estimates = runner.batch_extract_estimates(
        combined[direction_mask], EXPERIMENT
    )
    combined.loc[direction_mask, "estimate"] = direction_estimates
    return combined


def main():
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    runner.CACHE_DIR = str(DATA_ROOT / "cache")
    runner.ESTIMATE_JUDGE_CACHE_ROOT = str(DATA_ROOT / "estimate_judge_cache")

    baselines, thresholds, metadata = _load_original_baselines_and_thresholds()
    raw_df = _run_fixed_threshold_directions(baselines, thresholds)

    annotated = raw_df.copy()
    annotated["eval_awareness_raw"] = None
    annotated["eval_awareness_reasoning"] = None
    annotated["eval_awareness_score"] = None
    annotated["eval_aware"] = False

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
    with (DATA_ROOT / "run_metadata.json").open("w") as f:
        json.dump(metadata, f, indent=2, sort_keys=True)

    directional = annotated[directional_mask].copy()
    directional["estimate_parsed"] = directional["estimate"].notna()
    summary = (
        directional.groupby("prompt_key", as_index=False)
        .agg(
            n=("prompt_key", "size"),
            traces_kept=(
                "reasoning",
                lambda s: int(s.fillna("").str.len().gt(0).sum()),
            ),
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

    print(f"Completed Qwen3.6-27B eval notice: {len(annotated)} rows")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
