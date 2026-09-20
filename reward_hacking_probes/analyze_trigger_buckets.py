"""Clusters join consecutive firing tokens iff their index distance is <5."""
import csv,hashlib,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
base=Path(__file__).resolve().parent/'artifacts/h100_20260918'
out=base/'representative_casual'
selected={s['row']['id'] for s in json.load(open(out/'selection.json'))}
thresholds=json.load(open(base/'outcome_comparison/thresholds.json'))['casual']
rows=[r for r in csv.DictReader(open(base/'rollout_scores.csv')) if r['prompt_key'] in ['screen_giraffes_casual_good_cause_silent','screen_giraffes_casual_good_cause_silent_eval_note_test']]
buckets=[];gaps={}
for r in rows:
 with np.load(base/'targets'/(hashlib.sha256(r['id'].encode()).hexdigest()+'.npz')) as d:
  for family in ['suite','report']:
   hits=np.flatnonzero(d[family+'__L39']>thresholds[family+'__L39'][0]);dist=np.diff(hits)
   groups=np.split(hits,np.flatnonzero(dist>=5)+1)
   for scope in ['all_400']+(['four_displayed'] if r['id'] in selected else []):
    gaps.setdefault((scope,family),[]).extend(dist.tolist())
    for group in groups:
     if len(group):buckets.append(dict(scope=scope,probe=family,id=r['id'],start=int(group[0]),end=int(group[-1]),span=int(group[-1]-group[0]+1),firing_tokens=len(group)))
summary=[];distribution=[]
for (scope,family),dist in gaps.items():
 sizes=np.array([b['firing_tokens'] for b in buckets if b['scope']==scope and b['probe']==family]);multi=sizes[sizes>=2];dist=np.array(dist)
 r=dict(scope=scope,probe=family,gaps=len(dist),gaps_lt5=int(sum(dist<5)),fraction_gaps_lt5=float(np.mean(dist<5)),buckets=len(sizes),singletons=int(sum(sizes==1)),multi_buckets=len(multi),total_firing_tokens=int(sum(sizes)),fraction_tokens_in_multi=float(sum(multi)/sum(sizes)),mean_multi=float(np.mean(multi)),median_multi=float(np.median(multi)),p90_multi=float(np.quantile(multi,.9)),p95_multi=float(np.quantile(multi,.95)),max_multi=int(max(multi)))
 summary.append(r);print(r)
 for size,count in zip(*np.unique(sizes,return_counts=True)):
  distribution.append(dict(scope=scope,probe=family,firing_tokens=int(size),buckets=int(count),percent_all_buckets=float(count/len(sizes)*100),percent_multi_buckets=float(count/len(multi)*100) if size>=2 else None))
for name,records in [('trigger_buckets.csv',buckets),('trigger_bucket_summary.csv',summary),('trigger_bucket_sizes.csv',distribution)]:
 with open(out/name,'w') as f:
  w=csv.DictWriter(f,fieldnames=records[0].keys());w.writeheader();w.writerows(records)
for scope,label in [('four_displayed','Four displayed traces'),('all_400','All 400 casual good/nothing traces')]:
 fig,axes=plt.subplots(1,2,figsize=(11,4.7))
 for ax,family in zip(axes,['suite','report']):
  rr=[r for r in distribution if r['scope']==scope and r['probe']==family and r['firing_tokens']>=2]
  ax.bar([r['firing_tokens'] for r in rr],[r['percent_multi_buckets'] for r in rr],width=.85,color='#2563a6' if family=='suite' else '#c46c25')
  ax.set_title(family);ax.set_xlabel('Firing tokens per bucket');ax.set_ylabel('Share of multi-trigger buckets (%)');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
 fig.suptitle(label+' · bucket sizes after merging trigger distances <5\nBlock 40 · baseline p95 · singleton buckets excluded',fontsize=12)
 fig.tight_layout(rect=(0,0,1,.87));fig.savefig(out/f'trigger_bucket_sizes_{scope}.png',dpi=160);plt.close(fig)
