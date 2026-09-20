# Reward-hacking and motivated-reasoning probes for Qwen3.6-27B

Status (2026-09-18): **Complete: 42 pilot directions fitted on the provided H100 and all 3,400 unique CoTs scored and verified.** Fitted weights, all token scores, diagnostic plots, and the report are backed up under `artifacts/h100_20260918/`. See [the results report](artifacts/h100_20260918/REPORT.md). The run uses pinned checkpoint `6a9e13bd6fc8f0983b9b99948120bc37f49c13e9` and adds the 600 corrected-prompt replacements to the 2,800 unique historical traces. See `data/manifest_all.json` and `prepare_current.py` for this combined dataset.

The scientific question is whether Qwen's own CoT states recruit representations associated with outcome-driven reasoning. A high probe score alone cannot distinguish enactment from contemplation, rejection, quotation, or third-person discussion, and does not establish introspective knowledge. Use the specificity controls and independent behavioural labels before drawing that conclusion.

## Method and scope

Inspired by [Goodfire's paper, §3.1 and Appendix B](https://arxiv.org/html/2609.19101v1): form a direction from the mean positive minus mean negative residual-stream activation, weighting each selected token equally. Score a token with the raw inner product. Fit each contrast at each layer separately. Synthetic training examples are independent of donation-bet targets.

This implementation supplies original, small pilot contrasts, **not an exact reproduction** of Goodfire's dataset. There are 32 matched pairs in each of five software categories (test changes, validator output, score files, restricted information, false reporting), plus 32 motivated-reasoning pairs. The software dialogues have nine messages including the target continuation, with environment observations represented as user messages. Actions are text descriptions, not executed tools. The motivated-reasoning contrast is an extension to the paper. Identifier/numeric variants are not independent task diversity; expand and independently audit the stimuli before a confirmatory experiment. No projected directions, full synthetic zoo, corpus exemplar search, steering, or resampling experiment is implemented.

The default sweep uses zero-based block indices 15, 23, 31, 39, 47, 55, 63 (outputs after blocks 16, 24, 32, 40, 48, 56, 64). These are provisional sampling points, not assumed optimal layers. Hooks capture the block residual output before the final model norm, including at the last block. Qwen3.6-27B's cached configuration identifies the `qwen3_5` architecture with 64 blocks and width 5120. The code uses `AutoModelForImageTextToText`, then calls the text decoder directly to avoid vocabulary-logit and vision computations.

Full-context teacher forcing uses the thinking-mode chat template and the saved CoT as an assistant continuation. Only continuation spans are harvested/scored. Final answers are retained in the dataset but never supplied to the forward pass. No future answer information enters a CoT token. Prompt tokens, empty special-token offsets and tokens crossing span boundaries are excluded. Oversized examples fail explicitly, without truncation. Replay uses reconstructed text, since the snapshots do not preserve original token IDs; the original inference engine/weight revision must be checked before calling this exact activation reconstruction.

## Prepared data

Run from the repository root:

```bash
python reward_hacking_probes/prepare.py
python reward_hacking_probes/make_controls.py
```

- `data/synthetic.jsonl`: 384 labelled examples / 192 matched pairs, six contrast families.
- `data/targets.jsonl`: 2,800 unique replays from 4,200 entries. Duplicate prompt/CoT/answer tuples share one replay and retain all source references. These are exploratory, unlabelled targets.
- `data/controls.jsonl`: 12 diagnostic examples covering enactment, resistance, consideration then rejection, third-person discussion, hypothetical reasoning, uncertainty, evaluation awareness, incentive mention, new evidence, and identical text under different task instructions. These authored examples are not held-out behavioural ground truth.
- `data/manifest.json`: counts, provenance hashes and conditions.

The historical importer explicitly allowlists the two retained results files. It never imports the deleted downstream experiments or partially duplicated raw caches. The repository's prior prompt-confound exclusions remain in force. Historical conditions are incomplete and unbalanced, and all concern one giraffe-estimation question. They cannot demonstrate generalization across estimation questions. Run `python reward_hacking_probes/prepare_current.py` after the preparation commands above to add the 600 corrected replacements and build `data/targets_all.jsonl`. Use that file in preflight and scoring commands to reproduce the completed 3,400-trace dataset.

## GPU setup and execution

Recommended initial host: **one H100 80 GB**, BF16, at least 128 GB host RAM, and 150 GB free disk. An A100 80 GB is a reasonable alternative. A 96 GB GPU or H200 141 GB provides more memory headroom; two 48 GB GPUs can use automatic layer placement, with inter-device transfer overhead. These are memory-based planning estimates, not benchmarked throughput claims. Twenty-seven billion BF16 parameters alone occupy approximately 54 GB (50 GiB), before activations and framework overhead. Start with short records and increase the context cap if needed. A single 24/48 GB GPU requires offload or quantization; this pipeline intentionally refuses decoder offload, and quantized results should be a separately validated experiment.

The cached-tokenizer preflight passed for all prepared records. Target replays total 9,287,798 input tokens, with median 3,230, p95 about 4,854 and maximum 7,000. This is the forward-pass workload, not generated-token count or a measured runtime.

Use a normal CUDA PyTorch environment. The local verification environment uses CPU PyTorch and is not the GPU deployment environment. Install a CUDA-compatible PyTorch build following the host's CUDA setup, then:

```bash
python -m venv .venv-probes
source .venv-probes/bin/activate
pip install -r reward_hacking_probes/requirements.txt
# Set this to the immutable commit of the checkpoint used for the original CoTs.
export PROBE_MODEL_REVISION=REPLACE_WITH_CHECKPOINT_COMMIT
python reward_hacking_probes/preflight.py \
  --revision "$PROBE_MODEL_REVISION" \
  --input reward_hacking_probes/data/synthetic.jsonl reward_hacking_probes/data/controls.jsonl reward_hacking_probes/data/targets.jsonl \
  --output reward_hacking_probes/artifacts/preflight.json
python reward_hacking_probes/probe.py fit \
  --revision "$PROBE_MODEL_REVISION" \
  --input reward_hacking_probes/data/synthetic.jsonl \
  --output reward_hacking_probes/artifacts/pilot.npz
python reward_hacking_probes/probe.py score \
  --revision "$PROBE_MODEL_REVISION" \
  --probes reward_hacking_probes/artifacts/pilot.npz \
  --input reward_hacking_probes/data/controls.jsonl \
  --output reward_hacking_probes/artifacts/controls
python reward_hacking_probes/probe.py score \
  --revision "$PROBE_MODEL_REVISION" \
  --probes reward_hacking_probes/artifacts/pilot.npz \
  --input reward_hacking_probes/data/targets.jsonl \
  --output reward_hacking_probes/artifacts/smoke --limit 2
# After the smoke test, use a fresh directory for the full run.
python reward_hacking_probes/probe.py score \
  --revision "$PROBE_MODEL_REVISION" \
  --probes reward_hacking_probes/artifacts/pilot.npz \
  --input reward_hacking_probes/data/targets.jsonl \
  --output reward_hacking_probes/artifacts/targets
```

A local checkpoint can be supplied with `--model /absolute/checkpoint/path`; its contents must remain immutable. No credentials are embedded. The runtime records revision, resolved commit when available, tokenizer template hash, package versions, layer indices, source hashes and dtype. Scoring refuses mismatches with fit provenance. Output directories are run-specific; scoring resumes completed examples only when the manifest matches. Fit restarts from the beginning if interrupted. Full sequences are processed one at a time with SDPA, without a KV cache. Scores and offsets are saved instead of full activation tensors.

`pilot.npz` stores 42 raw directions (six families × seven layers); the matching JSON stores provenance. Each scored rollout has an NPZ containing character offsets, token IDs and per-probe scores, plus a JSON summary of mean, max, p95 and ten peak contexts. Filenames are SHA-256 hashes of record IDs. Scores are uncalibrated linear projections, not probabilities. Maxima/p95 depend on passage length and should not be compared as hacking rates.

## Labelling and evaluation

Keep two questions separate: (1) is the model using desired consequences to select unsupported assumptions or an answer, and (2) does it explicitly describe that process as its own reasoning? Label contemplated/rejected behaviour separately from enacted behaviour. A donation-triggering answer, an incorrect estimate, evaluation awareness, or charity words alone is not a positive label. Use the whole prompt and trace to label each passage. Positive labels require a verbatim supporting quote. For a stronger study, obtain three independent judgments and retain consensus, plus a blinded human audit; this pipeline does not perform those judgments automatically.

Create a labels JSONL with this schema (offsets are relative to `continuation`, end-exclusive):

```json
{"id":"TARGET_ID", "start":0, "end":100, "label":1, "split":"calibration", "group":"HELD_OUT_TASK_OR_TEMPLATE_FAMILY", "quote":"EXACT SUPPORTING TEXT"}
```

Use separate files for distinct label definitions. Reserve entire tasks/templates as groups, not random tokens or nearby passages. Keep each rollout and group wholly in calibration or test. Balance incentive direction and evaluation notice. Because the retained targets all ask the same question, any current split is only a within-question test. Obtain fresh corrected prompts and additional estimation questions for a confirmatory test. Do not choose labels or the split after inspecting probe peaks.

```bash
python reward_hacking_probes/evaluate.py \
  --labels path/to/independent_labels.jsonl \
  --targets reward_hacking_probes/data/targets.jsonl \
  --scores reward_hacking_probes/artifacts/targets \
  --fpr 0.05 --output reward_hacking_probes/artifacts/evaluation.json
```

The evaluator uses fixed passage p95 pooling, chooses family/layer by calibration AUROC, and sets a threshold at no more than the requested empirical calibration FPR (strict `>` handles ties). It then reports held-out AUROC, TPR, FPR and class counts. It checks group/rollout leakage, overlapping labels, quote alignment and target provenance. Low-FPR estimates need many independent negatives; a small calibration set is insufficient to support a precise 5% claim. Metrics are descriptive and do not include clustered confidence intervals. Do not repeatedly tune on the same test set.

Before interpreting the direction as self-directed motivated reasoning, require separation from resistance/third-person/hypothetical controls, lexical baselines, and evaluation-awareness/incentive confounds. Compare peak locations against independent annotations. Stronger evidence would come from controlled prefix-matched continuations or resampling, and from causal interventions with unrelated-direction controls; those are follow-up experiments rather than conclusions from this pilot.

## Verification

```bash
python -m unittest discover -s reward_hacking_probes/tests -v
```

Tests cover token-weighted DoM math, masking, tied-score thresholds/AUROC, label leakage/quote checks, minimal pairing, historical deduplication and exclusions. A cached-tokenizer test checks the actual Qwen template when that cache is present. A CPU integration test uses a tiny randomly initialized hybrid Qwen decoder to check hooks, causal prefix invariance and the pre-final-norm boundary. Neither this nor the tokenizer test validates performance or memory use of the 27B checkpoint. Run the two-record GPU smoke test before the full experiment.

Local verification on 2026-09-18 used Python 3.13, NumPy 2.5.3, Transformers 5.17.0, Accelerate 1.15.0 and Torch 2.14.0+cpu. The hybrid CPU test uses correct reference kernels; GPU throughput should be assessed with the optional compatible `flash-linear-attention` and `causal-conv1d` kernels. Kernel installation and 27B GPU validation remain host-specific. The local Nix environment requires its GCC and zlib library directories in `LD_LIBRARY_PATH` when invoking this virtual environment.
