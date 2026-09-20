"""Outcome-stratified ordinary casual traces, selected without probe scores."""
import csv,hashlib,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent
BASE=ROOT/'artifacts/h100_20260918'
OUT=BASE/'ordinary_outcome_examples'
OUT.mkdir(exist_ok=True)
rows=list(csv.DictReader((BASE/'rollout_scores.csv').open()))
rows=[r for r in rows if r['prompt_key']=='screen_giraffes_casual_good_cause_silent' and r['estimate'] and np.isfinite(float(r['estimate']))]
def is_good(r):
 return float(r['estimate'])>float(r['threshold']) if r['direction']=='above_good' else float(r['estimate'])<=float(r['threshold'])
selected=[]
for direction in ['above_good','below_good']:
 for good in [True,False]:
  group=[r for r in rows if r['direction']==direction and is_good(r)==good]
  ma=float(np.median([float(r['estimate']) for r in group]));ml=float(np.median([int(r['selected_tokens']) for r in group]))
  r=min(group,key=lambda r:(abs(float(r['estimate'])-ma),abs(int(r['selected_tokens'])-ml),r['id']))
  selected.append(dict(row=r,n=len(group),median_answer=ma,median_length=ml,good=good,slug=direction+'__'+('good_side' if good else 'bad_side')))
ids={s['row']['id'] for s in selected}
targets={}
with (ROOT/'data/targets_all.jsonl').open() as f:
 for line in f:
  t=json.loads(line)
  if t['id'] in ids:targets[t['id']]=t
vectors=np.load(BASE/'pilot.npz')
thresholds=json.loads((BASE/'outcome_comparison/thresholds.json').read_text())['casual']
arrays=[]
index=['# Ordinary casual donation: outcome-stratified examples','','One example per direction × final-outcome group. Selection minimizes distance to the group median final estimate, then distance to its median CoT length. No probe score was used. Good side means donation triggered; bad side means nothing happens.','','Plots use block 40. Signed projection = h·v / ||v||. Faint lines are individual tokens, bold lines average 64 consecutive tokens, dashed lines mark the casual-baseline p95 cutoff. These are exploratory, uncalibrated probes.','']
for s in selected:
 r=s['row'];t=targets[r['id']];stem=hashlib.sha256(r['id'].encode()).hexdigest()
 data=dict(np.load(BASE/'targets'/(stem+'.npz')));arrays.append(data)
 assert len(data['token_ids'])==int(r['selected_tokens'])
 title=('Donation >133M' if r['direction']=='above_good' else 'Donation ≤133M')+' — '+('good side' if s['good'] else 'bad side')
 s['title']=title
 (OUT/(s['slug']+'.md')).write_text('\n\n'.join(['# '+title,f"Estimate: {float(r['estimate']):,.0f}. CoT tokens: {r['selected_tokens']}. Selected from {s['n']} traces; median answer {s['median_answer']:,.0f}. Source: {r['provenance']}. ID: `{r['id']}`.",'## Prompt','\n\n'.join(m['content'] for m in t['messages']),'## Full recorded CoT',t['continuation'],'## Final answer',t['answer']])+'\n')
 index.append(f"- [{title}]({s['slug']}.md): {float(r['estimate'])/1e6:g}M; {r['selected_tokens']} tokens; group n={s['n']}.")
 names=[f+'__L39' for f in ['suite','validator','scorefile','acquire','report','motivated']]
 with (OUT/(s['slug']+'_scores.csv')).open('w') as f:
  w=csv.writer(f);w.writerow(['token_index','depth_percent']+names)
  n=len(data['token_ids']);scores=np.stack([data[k]/np.linalg.norm(vectors[k]) for k in names],axis=1)
  assert np.isfinite(scores).all()
  for i in range(n):w.writerow([i,100*i/(n-1),*scores[i]])
for families,name in [(['suite','report'],'suite_report'),(['suite','validator','scorefile','acquire','report','motivated'],'all_six')]:
 fig,axes=plt.subplots(len(families),4,figsize=(16,3*len(families)),sharex=True,sharey='row',squeeze=False)
 for col,(s,data) in enumerate(zip(selected,arrays)):
  n=len(data['token_ids']);x=np.linspace(0,100,n)
  for row,family in enumerate(families):
   ax=axes[row,col];key=family+'__L39';norm=np.linalg.norm(vectors[key]);y=data[key]/norm
   color='#2563a6' if family=='suite' else '#b54457' if family=='report' else '#546778'
   ax.plot(x,y,color=color,alpha=.22,lw=.5)
   starts=range(0,n,64)
   ax.plot([x[i:i+64].mean() for i in starts],[y[i:i+64].mean() for i in starts],color=color,lw=1.5)
   ax.axhline(thresholds[key][0]/norm,color='#555555',ls='--',lw=.9)
   ax.axhline(0,color='black',alpha=.3,lw=.5);ax.grid(alpha=.15)
   if row==0:ax.set_title(s['title']+f"\nAnswer {float(s['row']['estimate'])/1e6:g}M · {n:,} tokens",fontsize=10)
   if col==0:ax.set_ylabel(family+'\nSigned projection')
   if row==len(families)-1:ax.set_xlabel('CoT depth (%)')
 fig.suptitle('Ordinary casual good/nothing · block 40 · examples selected within each outcome group\nFaint: token scores · bold: 64-token means · dashed: baseline p95',fontsize=12)
 fig.tight_layout(rect=(0,0,1,.90 if len(families)==2 else .96))
 fig.savefig(OUT/(name+'.png'),dpi=160);fig.savefig(OUT/(name+'.pdf'));plt.close(fig)
(OUT/'selection.json').write_text(json.dumps(selected,indent=2))
(OUT/'README.md').write_text('\n'.join(index)+ '\n\n[Suite and report](suite_report.png) · [All six probes](all_six.png)\n')
print(json.dumps([dict(title=s['title'],estimate=s['row']['estimate'],n=s['n'],tokens=s['row']['selected_tokens'],id=s['row']['id']) for s in selected],indent=2))
