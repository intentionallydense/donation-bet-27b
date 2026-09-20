"""Add the completed corrected-prompt batch without changing historical inputs."""
import json
from pathlib import Path
from prepare import ROOT, historical, clean, digest, write_jsonl


def main():
    rows, historical_count = historical()
    unique = {r['id']: r for r in rows}
    source = ROOT/'corrected_screen_20260918/results_with_traces.jsonl'
    manifest = json.loads((source.parent/'manifest.json').read_text())
    import hashlib
    if hashlib.sha256(source.read_bytes()).hexdigest() != manifest['annotated_sha256']:
        raise ValueError('Corrected rollout file does not match its completed manifest')
    count = 0
    for line, text in enumerate(source.read_text().splitlines(),1):
        row = clean(json.loads(text))
        if not row.get('reasoning'):
            raise ValueError(f'Missing reasoning at {line}')
        key = digest([row['prompt'],row['reasoning'],row['answer']])
        reference = dict(path=str(source.relative_to(ROOT)),line=line,prompt_key=row['prompt_key'],
                         direction=row['direction'],sample_id=row['sample_id'],provenance=row['provenance'])
        count += 1
        if key in unique:
            unique[key]['sources'].append(reference)
            continue
        unique[key] = dict(id=key,messages=[dict(role='user',content=row['prompt'])],
                           continuation=row['reasoning'],spans=[[0,len(row['reasoning'])]],
                           answer=row['answer'],sources=[reference],
                           metadata={k:row.get(k) for k in ('prompt_key','direction','estimate','threshold',
                                     'finish_reason','eval_aware','eval_awareness_score','sample_id','provenance')},
                           label=None,split='exploration',group=digest(row['prompt']),historical_prompt=False)
    for row in rows:
        row['metadata']['provenance'] = 'historical_retained'
    out = Path(__file__).parent/'data'
    write_jsonl(out/'targets_all.jsonl',list(unique.values()))
    summary = dict(historical_entries=historical_count,new_entries=count,unique_replays=len(unique),
                   model_revision=manifest['model_revision'],historical_revision_known=False,
                   corrected_manifest_sha256=hashlib.sha256((source.parent/'manifest.json').read_bytes()).hexdigest(),
                   targets_sha256=hashlib.sha256((out/'targets_all.jsonl').read_bytes()).hexdigest())
    (out/'manifest_all.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__ == '__main__':
    main()
