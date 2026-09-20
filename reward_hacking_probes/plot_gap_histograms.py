"""Plot saved exact gap counts; bar heights are probability mass per labeled bin."""
import csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

out=Path(__file__).resolve().parent/'artifacts/h100_20260918/representative_casual'
rows=list(csv.DictReader((out/'trigger_gap_histogram.csv').open()))
families=['suite','validator','scorefile','acquire','report','motivated']
edges=np.array([1,2,3,5,9,17,33,65,129,257,513,np.inf])
labels=['1','2','3–4','5–8','9–16','17–32','33–64','65–128','129–256','257–512','513+']
for scope,title in [('four_displayed','Four displayed traces'),('all_400','All 400 casual good/nothing traces')]:
 fig,axes=plt.subplots(2,3,figsize=(15,8.5),sharey=True)
 for ax,family in zip(axes.flat,families):
  for metric,shift,color,label in [('trigger_distance',-.2,'#2563a6','Consecutive firing-token distance'),('silent_gap',.2,'#c46c25','Non-firing tokens between bursts')]:
   rr=[r for r in rows if r['scope']==scope and r['probe']==family and r['metric']==metric]
   counts,_=np.histogram([int(r['tokens']) for r in rr],bins=edges,weights=[int(r['count']) for r in rr])
   assert sum(counts)==sum(int(r['count']) for r in rr)
   ax.bar(np.arange(len(labels))+shift,100*counts/counts.sum(),width=.38,color=color,label=label)
  ax.set_title(family)
  ax.set_xticks(np.arange(len(labels)),labels,rotation=55,ha='right')
  ax.set_ylabel('Share of gaps (%)')
  ax.set_xlabel('Token-separation bin')
  ax.grid(axis='y',alpha=.2)
  ax.set_axisbelow(True)
 handles,legend=axes.flat[0].get_legend_handles_labels()
 fig.legend(handles,legend,loc='lower center',ncol=2,frameon=False)
 fig.suptitle(title+': histograms of probe-trigger separations\nBlock 40 · baseline p95 cutoff · heights are percentages per bin, not density',fontsize=14)
 fig.tight_layout(rect=(0,.055,1,.92))
 fig.savefig(out/f'trigger_gap_histograms_{scope}.png',dpi=160)
 fig.savefig(out/f'trigger_gap_histograms_{scope}.pdf')
 plt.close(fig)
print('Saved both histogram figures.')
