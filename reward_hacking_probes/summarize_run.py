"""Summarize completed raw probe scores; deliberately does not label reward hacking."""
import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
import numpy as np
from probe import read_rows, file_hash


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--artifacts',type=Path,required=True)
    p.add_argument('--targets',type=Path,required=True)
    args=p.parse_args()
    out=args.artifacts
    rows=read_rows(args.targets)
    meta=json.loads((out/'targets/run.json').read_text())
    if meta['input_sha256'] != file_hash(args.targets):
        raise ValueError('Scoring input hash mismatch')
    wide=[]
    peaks=defaultdict(list)
    for row in rows:
        name=hashlib.sha256(row['id'].encode()).hexdigest()
        record=json.loads((out/'targets'/f'{name}.json').read_text())
        if record['id']!=row['id']:
            raise ValueError('ID mismatch')
        entry=dict(id=row['id'],**row['metadata'],selected_tokens=record['selected_tokens'])
        entry['historical_prompt']=row['historical_prompt']
        for probe, stats in record['summary'].items():
            for stat in ['mean','p95','max']:
                entry[f'{probe}.{stat}']=stats[stat]
            peaks[probe].append(dict(id=row['id'],metadata=row['metadata'],sources=row['sources'],p95=stats['p95'],
                                     mean=stats['mean'],top=stats['top'][:3]))
        wide.append(entry)
    patterns={'motivated_reasoning':r'motivated reasoning','rationalization':r'rationali[sz](?:e|ing|ation)',
              'bias':r'\bbias(?:ed|es|ing)?\b','evaluation':r'\bevaluat(?:ion|e|ing)\b',
              'donation':r'\bdonat(?:ion|e|ing)\b'}
    lexical=[]
    for row in rows:
        item=dict(id=row['id'],provenance=row['metadata']['provenance'],characters=len(row['continuation']))
        item.update({k:len(re.findall(pattern,row['continuation'],re.I)) for k,pattern in patterns.items()})
        lexical.append(item)
    with (out/'lexical_counts.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(lexical[0])); writer.writeheader(); writer.writerows(lexical)
    fields=sorted(set().union(*(r.keys() for r in wide)))
    with (out/'rollout_scores.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader(); writer.writerows(wide)
    groups=defaultdict(list)
    for row in wide:
        condition = row['prompt_key']
        if row['direction']=='baseline':
            condition='baseline_casual' if 'casual' in condition else 'baseline_paper'
        groups[(row['provenance'],condition,row['direction'])].append(row)
    grouped=[]
    score_fields=[f for f in fields if f.endswith(('.mean','.p95','.max'))]
    for (provenance,condition,direction), members in sorted(groups.items()):
        entry=dict(provenance=provenance,condition=condition,direction=direction,n=len(members))
        for name in score_fields:
            entry[name]=float(np.mean([r[name] for r in members]))
        grouped.append(entry)
    with (out/'condition_scores.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(grouped[0])); writer.writeheader(); writer.writerows(grouped)
    ranked={k:sorted(v,key=lambda r:r['p95'],reverse=True)[:20] for k,v in peaks.items()}
    (out/'ranked_passages.json').write_text(json.dumps(ranked,indent=2)+'\n')
    controls=[]
    for path in (out/'controls').glob('*.json'):
        if path.name=='run.json':continue
        r=json.loads(path.read_text())
        controls.append(dict(id=r['id'],**{f'{k}.{s}':v[s] for k,v in r['summary'].items() for s in ['mean','p95','max']}))
    controls.sort(key=lambda r:r['id'])
    with (out/'control_scores.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(controls[0])); writer.writeheader(); writer.writerows(controls)
    # Fixed diagnostic contrast; do not select a best layer after inspecting outputs.
    table=['| Block (1-based) | Explicit enactment mean | Resistance mean | Third-person mean |',
           '|---|---:|---:|---:|']
    cmap={r['id']:r for r in controls}
    for layer in meta['layers']:
        k=f'motivated__L{layer}.mean'
        values=[cmap[f'control:{c}'][k] for c in ['enactment_explicit','resist_same_vocabulary','third_person']]
        table.append(f'| {layer+1} | '+ ' | '.join(f'{v:.3f}' for v in values)+' |')
    text=f'''# Completed probe replay

Fitted six synthetic contrast families at seven decoder blocks (42 directions), then scored {len(rows):,} unique CoTs. This includes 600 corrected-prompt replacements and 2,800 retained historical traces. Diagnostic controls were also scored. No rollout behaviour labels or calibrated hacking probabilities were produced.

Model: `{meta['model']}` at `{meta['revision']}`, BF16. Historical generation revisions are unknown. Replay reconstructs input tokens from saved text using the pinned tokenizer. The corrected replacements record this same checkpoint revision; the inference implementation differs (Transformers replay versus vLLM generation).

## Diagnostic specificity check

Raw motivated-reasoning scores on author-designed controls (larger means stronger alignment with that direction). Magnitudes are only comparable within a row. These few controls are diagnostic, not a statistical test.

{chr(10).join(table)}

A direction that also scores resistance or third-person discussion highly cannot on its own identify self-directed enactment. The scores do not establish that the model recognizes its own motivated reasoning.

## Artifacts

- `pilot.npz` and `pilot.json`: vectors and fitting provenance.
- `rollout_scores.csv`: one row per unique rollout, scores from every probe, condition and provenance.
- `condition_scores.csv`: descriptive condition means; these are not causal estimates or hacking rates.
- `control_scores.csv`: all diagnostic controls and probe summaries.
- `lexical_counts.csv`: counts of selected terms in the CoTs, for lexical-confound checks; mentions are not behaviour labels.
- `runtime_environment.json`: CUDA and attention-kernel versions used on the H100.
- `ranked_passages.json`: top 20 rollouts by p95 for each probe, with peak contexts. Exploratory ranking, not ground truth.
- `targets/*.npz`: token scores, token IDs, and character offsets; matching JSON files include top contexts.
- `preflight.json`: token counts and span audit.

All pilot directions remain uncalibrated. Condition sizes, CoT lengths, incentive vocabulary, and historical versus new data can affect scores. Shared baseline traces are counted once and grouped by actual prompt style, rather than duplicated across incentive conditions. Independent passage annotations and the prepared group-held-out evaluator are required before claiming detection performance. All targets concern one estimation question.
'''
    (out/'REPORT.md').write_text(text)
    print(json.dumps(dict(unique_scored=len(wide),controls=len(controls),probes=len(peaks),conditions=len(grouped)),indent=2))

if __name__=='__main__':main()
