"""Group firing tokens when consecutive indices differ by strictly less than five."""
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
windows=[];gaps={}
for r in rows:
 with np.load(base/'targets'/(hashlib.sha256(r['id'].encode()).hexdigest()+'.npz')) as d:
  for family in ['suite','report']:
   hits=np.flatnonzero(d[family+'__L39']>thresholds[family+'__L39'][0]);delta=np.diff(hits)
   for scope in ['all_400']+(['four_displayed'] if r['id'] in selected else []):
    gaps.setdefault((scope,family),[]).extend(delta.tolist())
   clusters=np.split(hits,np.flatnonzero(delta>=5)+1) if len(hits) else []
   assert sum(len(c) for c in clusters)==len(hits)
   for c in clusters:
    windows.append(dict(id=r['id'],displayed=r['id'] in selected,probe=family,start=int(c[0]),end=int(c[-1]),span_tokens=int(c[-1]-c[0]+1),firing_tokens=len(c)))
summaries=[];hist=[]
for scope in ['four_displayed','all_400']:
 for family in ['suite','report']:
  ww=[w for w in windows if w['probe']==family and (scope=='all_400' or w['displayed'])]
  counts=np.array([w['firing_tokens'] for w in ww]);dd=np.array(gaps[scope,family])
  summary=dict(scope=scope,probe=family,gaps=len(dd),gaps_lt5=int(sum(dd<5)),gap_capture_pct=float(np.mean(dd<5)*100),windows=len(ww),firing_tokens=int(counts.sum()),mean=float(counts.mean()),median=float(np.median(counts)),p90=float(np.quantile(counts,.9)),p95=float(np.quantile(counts,.95)),max=int(counts.max()),singleton_window_pct=float(np.mean(counts==1)*100),tokens_in_multi_windows_pct=float(counts[counts>=2].sum()/counts.sum()*100))
  summaries.append(summary);print(summary)
  sizes,nums=np.unique(counts,return_counts=True)
  for size,num in zip(sizes,nums):hist.append(dict(scope=scope,probe=family,firing_tokens=int(size),windows=int(num),pct_windows=float(num/len(counts)*100)))
 fig,axes=plt.subplots(1,2,figsize=(11,4.6),sharey=True)
 for ax,family in zip(axes,['suite','report']):
  hh=[r for r in hist if r['scope']==scope and r['probe']==family]
  heights=[sum(r['pct_windows'] for r in hh if r['firing_tokens']==n) for n in range(1,21)]
  heights.append(sum(r['pct_windows'] for r in hh if r['firing_tokens']>20))
  ax.bar(range(1,22),heights,color='#2563a6' if family=='suite' else '#c46c25')
  ax.set_xticks([1,2,5,10,15,20,21],['1','2','5','10','15','20','>20']);ax.set_title(family)
  ax.set_xlabel('Firing tokens per window');ax.set_ylabel('Share of windows (%)');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
 fig.suptitle(('Four displayed traces' if scope=='four_displayed' else 'All 400 traces')+' · triggers linked when separation <5 tokens\nBlock 40 · baseline p95 cutoff · includes singleton windows',fontsize=12)
 fig.tight_layout(rect=(0,0,1,.88));fig.savefig(out/f'trigger_windows_lt5_{scope}.png',dpi=160);plt.close(fig)
for filename,records in [('trigger_windows_lt5.csv',windows),('trigger_windows_lt5_summary.csv',summaries),('trigger_windows_lt5_histogram.csv',hist)]:
 with open(out/filename,'w') as f:
  w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
