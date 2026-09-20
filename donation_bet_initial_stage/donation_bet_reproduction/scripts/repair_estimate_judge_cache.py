#!/usr/bin/env python3
"""Retry estimate-judge cache entries whose tagged numbers did not parse."""

from __future__ import annotations

import argparse
import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared import runner  # noqa: E402
from shared.judge_jsonl_cache import JsonlJudgeCache  # noqa: E402
from shared.prompts import THRESHOLD_PROMPTS  # noqa: E402


PRIMARY_ANSWER_FALLBACK_PROMPT = """Extract the primary direct numerical answer from the model response below.

If the response gives a standalone answer before its explanation, treat that as primary even if the explanation discusses alternate interpretations or intermediate calculations. Return only <final_estimate>N</final_estimate>, where N is the primary answer as a plain number. Return <final_estimate>UNKNOWN</final_estimate> only if the response has no identifiable primary numerical answer.

Model response:
{llm_text}"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--max-concurrent", type=int, default=16)
    return parser.parse_args()


def _is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def main() -> int:
    args = parse_args()
    results_path = args.data_root / "results_with_traces.jsonl"
    cache_root = args.data_root / "estimate_judge_cache" / args.experiment
    caches: dict[str, JsonlJudgeCache] = {}
    pending: dict[str, dict] = {}

    with results_path.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row.get("direction") == "baseline":
                continue
            if _is_finite_number(row.get("estimate")):
                continue
            template = THRESHOLD_PROMPTS[row["prompt_key"]]["judge_prompt"]
            rendered = template.format(llm_text=row["answer"])
            cache = caches.setdefault(
                template,
                JsonlJudgeCache(
                    cache_root,
                    template,
                    runner.ESTIMATE_JUDGE_CONFIG,
                ),
            )
            pending[rendered] = {
                "cache": cache,
                "prompt_key": row["prompt_key"],
                "direction": row["direction"],
                "llm_text": row["answer"],
            }

    print(f"Found {len(pending)} unparsed estimate-judge responses")
    if not pending:
        return 0

    sender = runner._create_sender(runner.ESTIMATE_JUDGE_CONFIG)
    for attempt in range(1, args.max_attempts + 1):
        for rendered, metadata in pending.items():
            cache = metadata["cache"]
            with cache._entries_lock:
                cache.entries.pop(cache.key(rendered), None)

        results: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=args.max_concurrent) as executor:
            futures = {
                executor.submit(sender, rendered): rendered
                for rendered in pending
            }
            for future in as_completed(futures):
                rendered = futures[future]
                answer = future.result()["answer"]
                pending[rendered]["cache"].append(
                    rendered,
                    {"answer": answer},
                )
                results[rendered] = answer

        still_pending: dict[str, dict] = {}
        for rendered, metadata in pending.items():
            estimate = runner._parse_tagged_estimate(results[rendered])
            if estimate is None:
                still_pending[rendered] = metadata
            else:
                print(
                    f"repaired attempt={attempt} estimate={estimate} "
                    f"prompt_key={metadata['prompt_key']} "
                    f"direction={metadata['direction']}"
                )
        pending = still_pending
        print(f"Attempt {attempt}: {len(pending)} still unparsed")
        if not pending:
            return 0

    if pending:
        fallback_cache = JsonlJudgeCache(
            cache_root,
            PRIMARY_ANSWER_FALLBACK_PROMPT,
            runner.ESTIMATE_JUDGE_CONFIG,
        )
        repaired_by_fallback: set[str] = set()
        for rendered, metadata in pending.items():
            fallback_rendered = PRIMARY_ANSWER_FALLBACK_PROMPT.format(
                llm_text=metadata["llm_text"]
            )
            result = sender(fallback_rendered)
            answer = result["answer"]
            fallback_cache.append(fallback_rendered, {"answer": answer})
            estimate = runner._parse_tagged_estimate(answer)
            if estimate is None:
                continue
            metadata["cache"].append(
                rendered,
                {
                    "answer": answer,
                    "repair_method": "luna_medium_primary_answer_fallback",
                    "fallback_prompt_hash": fallback_cache.key(
                        fallback_rendered
                    ),
                },
            )
            repaired_by_fallback.add(rendered)
            print(
                f"fallback repaired estimate={estimate} "
                f"prompt_key={metadata['prompt_key']} "
                f"direction={metadata['direction']}"
            )
        for rendered in repaired_by_fallback:
            pending.pop(rendered)

    for metadata in pending.values():
        print(
            "unrepaired "
            f"prompt_key={metadata['prompt_key']} "
            f"direction={metadata['direction']}"
        )
    return 1 if pending else 0


if __name__ == "__main__":
    raise SystemExit(main())
