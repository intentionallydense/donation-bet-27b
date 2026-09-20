import csv,json,hashlib
from pathlib import Path
import numpy as np
base=Path('/home/iodide/projects/donation-bet-27b/reward_hacking_probes/artifacts/h100_20260918')
out=base/'representative_casual'
selected={s['row']['id'] for s in json.load(open(out/'selection.json'))}
thresholds=json.load(open(base/'outcome_comparison/thresholds.json'))['casual']
rows=[r for r in csv.DictReader(open(base/'rollout_scores.csv')) if r['prompt_key'] in ['screen_giraffes_casual_good_cause_silent','screen_giraffes_casual_good_cause_silent_eval_note_test']]
results=[]
for r in rows:
 with np.load(base/'targets'/(hashlib.sha256(r['id'].encode()).hexdigest()+'.npz')) as d:
  for probe,threshold in thresholds.items():
   hits=d[probe]>threshold[0]
   results.append(dict(id=r['id'],prompt_key=r['prompt_key'],direction=r['direction'],displayed=r['id'] in selected,probe=probe,tokens=len(hits),firing_tokens=int(hits.sum()),bursts=int(np.sum(hits & ~np.r_[False,hits[:-1]])),fraction=float(hits.mean())))
with open(out/'firing_counts.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
summaries=[]
for scope in ['four_displayed','all_400']:
 for probe in thresholds:
  rr=[r for r in results if r['probe']==probe and (scope=='all_400' or r['displayed'])]
  summaries.append(dict(scope=scope,probe=probe,n=len(rr),mean_firing_tokens=float(np.mean([r['firing_tokens'] for r in rr])),mean_bursts=float(np.mean([r['bursts'] for r in rr])),mean_token_fraction=float(np.mean([r['fraction'] for r in rr])),traces_with_any=sum(r['firing_tokens']>0 for r in rr),mean_length=float(np.mean([r['tokens'] for r in rr]))))
json.dump(summaries,open(out/'firing_summary.json','w'),indent=2)
for r in summaries:
 if r['probe'].endswith('__L39'):print(r)
