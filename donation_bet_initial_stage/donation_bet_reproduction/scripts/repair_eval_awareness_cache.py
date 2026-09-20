#!/usr/bin/env python3
"""Retry eval-awareness cache entries whose responses did not parse."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.classify_eval_awareness import (  # noqa: E402
    ACTIVE_EVAL_AWARENESS_PROMPT,
    _call_judge,
    _eval_awareness_cache,
    _parse_score,
    eval_awareness_cache_dir,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument(
        "--experiment", default="giraffes_eval_awareness_screen"
    )
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--max-concurrent", type=int, default=16)
    parser.add_argument("--normalize-only", action="store_true")
    return parser.parse_args()


_ANSWER_BLOCK_RE = re.compile(r"<answer>(.*?)</answer>", re.DOTALL | re.I)
_EXPLICIT_SCORE_PATTERNS = (
    re.compile(r"^\s*\*{0,2}score\s*:\s*\*{0,2}([1-7])\b", re.I | re.M),
    re.compile(r"^\s*\*{0,2}([1-7])\*{0,2}(?:\s*(?:—|-)|\s*$)", re.M),
    re.compile(r"\b([1-7])\s*/\s*7\b", re.I),
    re.compile(r"\bis\s+\*{0,2}([1-7])\s*\(", re.I),
    re.compile(r"\bscore\s+is\s+\*{0,2}([1-7])\b", re.I),
)


def _parse_explicit_verbose_score(raw: object) -> int | None:
    if not isinstance(raw, str):
        return None
    match = _ANSWER_BLOCK_RE.search(raw)
    if not match:
        return None
    answer_block = match.group(1)
    for pattern in _EXPLICIT_SCORE_PATTERNS:
        score_match = pattern.search(answer_block)
        if score_match:
            return int(score_match.group(1))
    return None


def main() -> int:
    args = parse_args()
    results_path = args.data_root / "results_with_traces.jsonl"
    pending: dict[str, dict] = {}
    with results_path.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row.get("direction") == "baseline":
                continue
            if row.get("eval_awareness_score") is not None:
                continue
            prompt = ACTIVE_EVAL_AWARENESS_PROMPT.format(
                prompt=row["prompt"],
                reasoning=row["reasoning"],
                answer=row["answer"],
            )
            pending[prompt] = {
                "prompt_key": row["prompt_key"],
                "direction": row["direction"],
                "raw": row.get("eval_awareness_raw"),
            }

    print(f"Found {len(pending)} unparsed eval-awareness responses")
    if not pending:
        return 0

    cache_dir = eval_awareness_cache_dir(
        args.experiment,
        cache_root=args.data_root / "eval_awareness_cache",
    )
    cache = _eval_awareness_cache(cache_dir)

    normalized: list[str] = []
    for prompt, metadata in pending.items():
        raw = metadata["raw"]
        score = _parse_explicit_verbose_score(raw)
        if score is None:
            continue
        cache.append(
            prompt,
            {
                "answer": f"<answer>{score}</answer>",
                "repair_method": "normalize_explicit_verbose_score",
                "source_answer_sha256": hashlib.sha256(
                    raw.encode("utf-8")
                ).hexdigest(),
            },
        )
        normalized.append(prompt)
        print(
            f"normalized score={score} "
            f"prompt_key={metadata['prompt_key']} "
            f"direction={metadata['direction']}"
        )
    for prompt in normalized:
        pending.pop(prompt)
    print(f"Normalized {len(normalized)} explicit verbose scores")
    if not pending:
        return 0
    if args.normalize_only:
        for metadata in pending.values():
            print(
                "normalization could not recover "
                f"prompt_key={metadata['prompt_key']} "
                f"direction={metadata['direction']}"
            )
        return 1

    for attempt in range(1, args.max_attempts + 1):
        # Removing only the in-memory entry forces an exact-prompt retry. The
        # replacement is appended to the JSONL shard, so last-line-wins cache
        # loading keeps the original response as an audit trail.
        for prompt in pending:
            with cache._entries_lock:
                cache.entries.pop(cache.key(prompt), None)

        results: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=args.max_concurrent) as executor:
            futures = {
                executor.submit(_call_judge, prompt, cache): prompt
                for prompt in pending
            }
            for future in as_completed(futures):
                prompt = futures[future]
                results[prompt] = future.result()

        still_pending: dict[str, dict] = {}
        for prompt, metadata in pending.items():
            result = results[prompt]
            score = _parse_score(result.get("answer", ""))
            if score is None:
                still_pending[prompt] = metadata
            else:
                print(
                    f"repaired attempt={attempt} score={score} "
                    f"prompt_key={metadata['prompt_key']} "
                    f"direction={metadata['direction']}"
                )
        pending = still_pending
        print(f"Attempt {attempt}: {len(pending)} still unparsed")
        if not pending:
            return 0

    for metadata in pending.values():
        print(
            "unrepaired "
            f"prompt_key={metadata['prompt_key']} "
            f"direction={metadata['direction']}"
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
