"""Linear-axis histograms with one-token bins and a separate full-range view."""
import csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
out=Path(__file__).resolve().parent/'artifacts/h100_20260918/representative_casual'
rows=list(csv.DictReader((out/'trigger_gap_histogram.csv').open()))
for scope,title in [('four_displayed','Four displayed traces'),('all_400','All 400 casual good/nothing traces')]:
 for full in [False,True]:
  fig,axes=plt.subplots(2,2,figsize=(12,7),sharex=True)
  for i,probe in enumerate(['suite','report']):
   for j,(metric,label,color) in enumerate([('trigger_distance','Distance between firing tokens','#2563a6'),('silent_gap','Non-firing tokens between bursts','#c46c25')]):
    rr=[r for r in rows if r['scope']==scope and r['probe']==probe and r['metric']==metric]
    x=np.array([int(r['tokens']) for r in rr]);counts=np.array([int(r['count']) for r in rr]);ax=axes[i,j]
    ax.bar(x,counts/counts.sum()*100,width=.9,color=color)
    ax.set_title(probe+' — '+label,fontsize=11)
    ax.set_ylabel('Share of all gaps (%)');ax.set_xlabel('Separation (tokens)')
    ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    if not full:
     ax.set_xlim(.5,100.5);ax.set_xticks([1,20,40,60,80,100])
     tail=counts[x>100].sum()/counts.sum()*100
     ax.text(.98,.92,f'{tail:.1f}% of gaps exceed 100 tokens',transform=ax.transAxes,ha='right',fontsize=9)
    else:ax.set_xlim(left=.5)
  fig.suptitle(title+' · suite and report\nLinear axes · one-token bins · block 40 · baseline p95 cutoff',fontsize=13)
  fig.tight_layout(rect=(0,0,1,.92))
  name=f'trigger_gaps_linear_{scope}'+('_full' if full else '')
  fig.savefig(out/(name+'.png'),dpi=160);fig.savefig(out/(name+'.pdf'));plt.close(fig)
print('Saved linear histograms.')
