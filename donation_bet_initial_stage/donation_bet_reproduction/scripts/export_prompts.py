#!/usr/bin/env python3
"""Export the main Donation Bet prompts without importing third-party packages."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.experiments import THRESHOLD_EXPERIMENTS
from shared.prompts import THRESHOLD_PROMPTS


EXPERIMENT = "main_experiment_accurate"


def main() -> None:
    experiment = THRESHOLD_EXPERIMENTS[EXPERIMENT]
    exported = {
        "experiment": EXPERIMENT,
        "sampling": {
            "temperature": 1,
            "n_baseline_per_question": experiment["n_baseline"],
            "n_per_threshold_per_direction": experiment["n_per_threshold"],
            "threshold_spec": experiment["thresholds"],
            "threshold_note": (
                "Computed independently for each model/question from the "
                "baseline distribution; the main experiment uses the median."
            ),
        },
        "prompt_sets": {
            key: {
                field: value
                for field, value in THRESHOLD_PROMPTS[key].items()
                if field in {
                    "baseline",
                    "below_good_template",
                    "above_good_template",
                    "judge_prompt",
                    "baseline_key",
                }
            }
            for key in experiment["prompts"]
        },
    }
    out = ROOT / "prompts" / f"{EXPERIMENT}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(exported, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {out} ({len(exported['prompt_sets'])} question sets)")


if __name__ == "__main__":
    main()
