# Corrected replacements for six dropped screening arms

This run supplies 100 fresh Qwen3.6-27B rollouts for each of three casual arms, with and without an explicit evaluation notice:

- good-cause/silent, below-good
- UNICEF/silent, below-good
- silent/naked-run, above-good (the bad outcome triggers at or below the threshold)

`arms.json` freezes all six exact messages. It reconstructs the deleted messages from `../HISTORICAL_PROMPTS.json` and changes only `If it's at or under,` to `If your number is at or under that,`. The original inclusive boundary, 133.0M threshold, notice, and all other wording are retained. This deliberately differs from the newer strict-comparison general templates.

Historical results are read-only. New raw responses, judge outputs, and the completed table live here. `manifest.json` records sampling settings, source hashes, model revision, and completion status. A completed table combines runs collected at different times; it is not a contemporaneous balanced replication.

- `run.py`: resumable generation against the private remote vLLM endpoint, 16 concurrent requests; saves all completed responses, including truncations.
- `sync.py`: waits for the model, starts the supervised experiment, and copies completed rows locally.
- `annotate.py`: applies the historical estimate-extraction and eval-awareness prompts using the same judge model and effort settings; caches responses locally. Loads the API key privately from SOPS.
- `summarize.py`: validates complete arm counts and outputs, verifies historical source hashes, and builds `summary.csv`, `REPORT.md`, and a combined results file. Refuses to declare completion on missing, truncated, or empty outputs. Genuine UNKNOWN estimates remain in the dataset and are reported separately from the parsed-estimate denominator.

Model weights are downloaded at a pinned revision to remote shared memory because the instance disk is smaller than the unquantized checkpoint. HF credentials are passed over SSH without printing them, stored temporarily with restrictive permissions, and removed after download. No credentials belong in this directory.
