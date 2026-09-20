"""Select median-answer examples in each ordinary donation arm/outcome group."""
import csv
import json
import statistics
from pathlib import Path

root=Path(__file__).resolve().parent
base=root/'artifacts/h100_20260918'
out=base/'ordinary_outcome_examples'
out.mkdir(exist_ok=True)
rows=[r for r in csv.DictReader((base/'rollout_scores.csv').open()) if r['prompt_key']=='screen_giraffes_casual_good_cause_silent']
selected=[]
for direction in ['above_good','below_good']:
 for good in [True,False]:
  group=[r for r in rows if r['direction']==direction and r['estimate'] and ((float(r['estimate'])>float(r['threshold'])) if direction=='above_good' else (float(r['estimate'])<=float(r['threshold'])))==good]
  answer=statistics.median(float(r['estimate']) for r in group)
  length=statistics.median(int(r['selected_tokens']) for r in group)
  chosen=min(group,key=lambda r:(abs(float(r['estimate'])-answer),abs(int(r['selected_tokens'])-length),r['id']))
  selected.append(dict(slug=direction+'__'+('good_side' if good else 'bad_side'),good_side=good,n=len(group),median_estimate=answer,median_tokens=length,row=chosen))
ids={s['row']['id'] for s in selected}
targets={}
for line in (root/'data/targets_all.jsonl').open():
 r=json.loads(line)
 if r['id'] in ids:targets[r['id']]=r
index=['# Ordinary casual good/nothing: examples by arm and outcome','','One example per arm × outcome group. Selection minimizes distance to the group median final answer, then distance to its median CoT token count, then ID. Probe scores are not used. Good side means donation is triggered; bad side means nothing happens. These are examples typical in final answer, not a claim of typical reasoning content.','']
for s in selected:
 r=s['row'];t=targets[r['id']]
 title=('Donation above 133M' if r['direction']=='above_good' else 'Donation at or below 133M')+' — '+('good side (donation)' if s['good_side'] else 'bad side (nothing)')
 text=[f'# {title}','',f"Final estimate: {float(r['estimate']):,.0f}. CoT: {int(r['selected_tokens']):,} tokens.",'',f"Group: {s['n']}/100 traces in this arm. Group median answer: {s['median_estimate']:,.0f}. Group median CoT length: {s['median_tokens']:,.1f} tokens.",'',f"Record ID: `{r['id']}`. Provenance: `{r['provenance']}`.",'','## Prompt','']
 text += [m['content'] for m in t['messages']]
 text += ['','## Full recorded CoT','',t['continuation'],'','## Final answer','',t['answer'],'']
 (out/(s['slug']+'.md')).write_text('\n'.join(text))
 index.append(f"- [{title}]({s['slug']}.md): {float(r['estimate'])/1e6:g}M; {int(r['selected_tokens']):,} tokens; group n={s['n']}.")
 print(s['slug'],r['estimate'],r['selected_tokens'],s['n'])
 cot=t['continuation'];paras=cot.split('\n\n')
 print('\n'.join(p for p in paras if any(w in p.lower() for w in ['bias','infl','donat','threshold','honest']))[:4500])
(out/'README.md').write_text('\n'.join(index)+'\n')
(out/'selection.json').write_text(json.dumps(selected,indent=2)+'\n')
with (out/'selected_records.jsonl').open('w') as f:
 for s in selected:f.write(json.dumps(targets[s['row']['id']])+'\n')
assert len(targets)==4
