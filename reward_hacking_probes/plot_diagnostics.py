"""Descriptive plots only; no trained thresholds or inferred behaviour labels."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser();p.add_argument('--artifacts',type=Path,required=True);args=p.parse_args()
    base=args.artifacts
    controls={}
    for path in (base/'controls').glob('*.json'):
        if path.name=='run.json':continue
        r=json.loads(path.read_text());controls[r['id'].replace('control:','')]=r['summary']
    order=['enactment_explicit','enactment_implicit','resist_same_vocabulary','consider_then_reject',
           'third_person','hypothetical','ordinary_uncertainty','evaluation_awareness','incentive_mention',
           'new_evidence','required_accuracy','legitimate_tradeoff']
    layers=[15,23,31,39,47,55,63]
    matrix=np.array([[controls[c][f'motivated__L{layer}']['mean'] for layer in layers] for c in order])
    z=(matrix-matrix.mean(0))/matrix.std(0)
    fig,ax=plt.subplots(figsize=(9,7))
    im=ax.imshow(z,cmap='RdBu_r',vmin=-2.5,vmax=2.5,aspect='auto')
    ax.set_xticks(range(7),[str(l+1) for l in layers]);ax.set_xlabel('Decoder block (1-based)')
    ax.set_yticks(range(len(order)),[c.replace('_',' ') for c in order])
    ax.set_title('Motivated-reasoning probe: diagnostic controls\nMean token score, standardized within each layer across these 12 controls',fontsize=11)
    fig.colorbar(im,ax=ax,label='Control-set z score (not a probability)')
    fig.tight_layout();fig.savefig(base/'control_specificity.png',dpi=160);plt.close(fig)
    with np.load(base/'pilot.npz') as data:
        families=['suite','validator','scorefile','acquire','report']
        cosine=[]
        for family in families:
            values=[]
            for layer in layers:
                a,b=data[f'motivated__L{layer}'],data[f'{family}__L{layer}']
                values.append(float(a@b/(np.linalg.norm(a)*np.linalg.norm(b))))
            cosine.append(values)
    fig,ax=plt.subplots(figsize=(8,4))
    im=ax.imshow(cosine,cmap='RdBu_r',vmin=-1,vmax=1,aspect='auto')
    ax.set_xticks(range(7),[str(l+1) for l in layers]);ax.set_xlabel('Decoder block (1-based)')
    ax.set_yticks(range(5),families);ax.set_title('Cosine similarity to the motivated-reasoning direction')
    for i in range(5):
        for j in range(7):ax.text(j,i,f'{cosine[i][j]:.2f}',ha='center',va='center',fontsize=9)
    fig.colorbar(im,ax=ax,label='Cosine similarity');fig.tight_layout()
    fig.savefig(base/'direction_similarity.png',dpi=160);plt.close(fig)
    if (base/'rollout_scores.csv').exists():
        with (base/'rollout_scores.csv').open() as f:rows=list(csv.DictReader(f))
        # All layers shown; no layer chosen by target behaviour.
        fig,axes=plt.subplots(2,4,figsize=(14,7));axes=axes.flatten()
        for ax,layer in zip(axes,layers):
            groups=[]
            for direction in ['baseline','below_good','above_good']:
                groups.append([float(r[f'motivated__L{layer}.p95']) for r in rows if r['direction']==direction])
            ax.boxplot(groups,tick_labels=['Baseline','Below-good','Above-good'],showfliers=False)
            ax.set_title(f'Block {layer+1}');ax.tick_params(axis='x',labelrotation=15)
            ax.set_ylabel('Raw CoT p95 score')
        axes[-1].axis('off')
        fig.suptitle('Motivated-reasoning probe distributions across all rollouts\nMixed conditions and collection dates; raw scores are not hacking probabilities',fontsize=12)
        fig.tight_layout();fig.savefig(base/'rollout_distributions.png',dpi=160);plt.close(fig)
        corrected=[r for r in rows if r['provenance']=='corrected_replacement_20260918']
        # Explicitly exploratory selection at a fixed illustrative layer, not calibration.
        chosen=max(corrected,key=lambda r:float(r['motivated__L39.p95']))
        name=hashlib.sha256(chosen['id'].encode()).hexdigest()+'.npz'
        with np.load(base/'targets'/name) as data:
            fig,axes=plt.subplots(7,1,figsize=(13,10),sharex=True)
            for ax,layer in zip(axes,layers):
                values=data[f'motivated__L{layer}']
                ax.plot(np.arange(len(values)),values,linewidth=.6,color='#395c9a')
                ax.set_ylabel(f'Block {layer+1}',fontsize=9)
                ax.grid(alpha=.15)
            axes[-1].set_xlabel('Selected CoT token index')
            fig.suptitle('Exploratory new-rollout example: motivated-reasoning token scores\nSelected by highest block-40 CoT p95 among the 600 replacements; scores are uncalibrated',fontsize=11)
            fig.tight_layout();fig.savefig(base/'example_token_scores.png',dpi=160);plt.close(fig)
        (base/'example_token_scores.json').write_text(json.dumps(dict(id=chosen['id'],selection='Highest motivated__L39 p95 among corrected replacements; exploratory',metadata=chosen),indent=2)+'\n')

if __name__=='__main__':main()
