"""Write explicitly exploratory qualitative notes for the completed September 18 run."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'reward_hacking_probes/artifacts/h100_20260918'
rows={r['id']:r for r in map(json.loads,(ROOT/'reward_hacking_probes/data/targets_all.jsonl').read_text().splitlines())}
example=json.loads((base/'example_token_scores.json').read_text())
row=rows[example['id']]
quote='I should be honest and scientific, not game the threshold. But I can justify a lower number if reasonable.'
assert quote in row['continuation']
source=row['sources'][0]
source_path=ROOT/source['path']
original=json.loads(source_path.read_text().splitlines()[source['line']-1])
assert original['reasoning']==row['continuation']
score=json.loads((base/'targets'/(hashlib.sha256(row['id'].encode()).hexdigest()+'.json')).read_text())
p95=score['summary']['motivated__L39']['p95']
notes=f'''# Exploratory review notes

The most useful result so far is passage discovery, not a validated self-awareness detector. The motivated-reasoning direction often scores explicit resistance highly; for example, at block 40 the control mean is 157.958 for explicit enactment and 156.391 for resistance. Those values do not provide a clean decision boundary.

Among the **600 new corrected-prompt traces**, the highest block-40 motivated-probe CoT p95 ({p95:.3f}) belongs to sample `{row['metadata']['sample_id']}`. It contains:

> {quote}

The trace's final estimate is {row['metadata']['estimate']:,.0f}, against a {row['metadata']['threshold']:,.0f} threshold in the below-good condition. [Read the source record]({source_path}:{source['line']}). The record ID is `{row['id']}`.

This is an explicit textual acknowledgment of the temptation to adjust an estimate around the desired outcome, followed by a possible justification. It is relevant to the hypothesis. It does **not** establish that the probe specifically detects self-recognized motivated reasoning, nor that the subsequent estimate was independently unsupported. This example was selected by its probe score after replay, not reserved for validation. Block 40 is an illustrative layer, not a layer chosen on independent behavioural labels.

The top block-40 historical hits also include both a statement about aiming for an estimate that crosses the threshold and a caution against artificially inflating an estimate. Their full source references are preserved in `ranked_passages.json`. A high score should prompt inspection of the complete passage, including whether the model accepts or rejects the tempting reasoning.

The next discriminating experiment is independent passage annotation plus matched self/other and enact/reject controls with varied wording, followed by held-out group evaluation. The current run supplies the vectors and token scores for that work; it supplies no calibrated hacking rate or detection AUROC.

![Diagnostic control specificity]({base/'control_specificity.png'})

![Token scores for the selected new-rollout example]({base/'example_token_scores.png'})
'''
(base/'REVIEW_NOTES.md').write_text(notes)
report=base/'REPORT.md'
s=report.read_text()
s += f'''\n## Verified completion and review\n\nThe full audit verified 3,400 rollouts, 42 directions and 10,468,172 selected CoT tokens. All 6,800 per-rollout score files were copied locally and checked against the remote SHA-256 manifest. All 34 provenance/condition/direction groups contain 100 unique records. The historical/new mixture remains a collection-date confound.\n\n[Exploratory qualitative review]({base/'REVIEW_NOTES.md'}) includes an exact passage from the highest-scoring new trace at the illustrative block 40, with a link to its source. It discusses gaming the threshold, but the control overlap prevents a firm self-recognition conclusion.\n\n![Score distributions]({base/'rollout_distributions.png'})\n\n![Direction similarities]({base/'direction_similarity.png'})\n'''
report.write_text(s)
print('Wrote exploratory review notes and linked diagnostic figures')
