"""Exploratory good-side vs bad-side associations, exact-arm fixed effects.

Inference clusters by exact prompt arm, with t critical values (G-1 df).
All 42 probes x 4 summaries x 3 populations x 2 specifications belong to one
Holm family. Baseline-relative token exceedance rates are NOT hack probabilities.
"""
import csv,hashlib,json
from collections import Counter
from pathlib import Path
import numpy as np
from scipy.stats import t

BASE=Path(__file__).resolve().parent
ART=BASE/'artifacts/h100_20260918'
OUT=ART/'outcome_comparison'
OUT.mkdir(exist_ok=True)
rows=list(csv.DictReader((ART/'rollout_scores.csv').open()))
probes=sorted(k[:-5] for k in rows[0] if k.endswith('.mean'))
assert len(probes)==42
ids=[r['id'] for r in rows]
style=lambda r:'casual' if 'casual' in r['prompt_key'] else 'paper'

def artifact(r):
    return ART/'targets'/(hashlib.sha256(r['id'].encode()).hexdigest()+'.npz')

cache=OUT/'token_rates.npz'
if not cache.exists():
    thresholds={}
    for s in ['paper','casual']:
        parts={p:[] for p in probes}
        baseline=[r for r in rows if r['direction']=='baseline' and style(r)==s]
        assert len(baseline)==100
        for r in baseline:
            with np.load(artifact(r),allow_pickle=False) as d:
                for p in probes:parts[p].append(d[p])
        thresholds[s]=np.array([np.quantile(np.concatenate(parts[p]),[.95,.99]) for p in probes])
    rates=np.empty((len(rows),len(probes),2),dtype=np.float64)
    any_fires=np.zeros((len(rows),len(probes),2),dtype=bool)
    for i,r in enumerate(rows):
        with np.load(artifact(r),allow_pickle=False) as d:
            for j,p in enumerate(probes):
                values=d[p]
                for k in range(2):
                    hits=values>thresholds[style(r)][j,k]
                    rates[i,j,k]=hits.mean();any_fires[i,j,k]=hits.any()
        if (i+1)%500==0:print(f'token rates {i+1}/{len(rows)}',flush=True)
    np.savez_compressed(cache,rates=rates,any_fires=any_fires,ids=np.array(ids),probes=np.array(probes),
                        paper=thresholds['paper'],casual=thresholds['casual'])
with np.load(cache,allow_pickle=False) as d:
    assert d['ids'].tolist()==ids and d['probes'].tolist()==probes
    rates=d['rates'];any_fires=d['any_fires']
    (OUT/'thresholds.json').write_text(json.dumps({s:{p:d[s][j].tolist() for j,p in enumerate(probes)} for s in ['paper','casual']},indent=2))

eligible=[i for i,r in enumerate(rows) if r['direction']!='baseline' and r['estimate'] and np.isfinite(float(r['estimate']))]
sub=[rows[i] for i in eligible]
y=np.array([[float(r[f'{p}.{m}']) if m in ['mean','p95'] else rates[i,j,0 if m=='fire95' else 1]
             for j,p in enumerate(probes) for m in ['mean','p95','fire95','fire99']] for i,r in zip(eligible,sub)])
names=[(p,m) for p in probes for m in ['mean','p95','fire95','fire99']]
above=np.array([float(r['estimate'])>float(r['threshold']) for r in sub])
good=np.array([a if r['direction']=='above_good' else not a for a,r in zip(above,sub)],dtype=float)
length=np.log(np.array([int(r['selected_tokens']) for r in sub]))
arms=np.array([r['prompt_key']+'|'+r['direction']+'|'+r['provenance'] for r in sub])
directions=np.array([r['direction'] for r in sub])


def fit(mask,adjust):
    a=arms[mask]; unique=np.unique(a);n=int(mask.sum());g=len(unique)
    x=good[mask,None]
    if adjust:x=np.column_stack([x,length[mask]])
    target=y[mask].copy();x=x.copy()
    for arm in unique:
        take=a==arm
        x[take]-=x[take].mean(0);target[take]-=target[take].mean(0)
    scale=np.sqrt((target**2).sum(0)/(n-g))
    inv=np.linalg.inv(x.T@x);coef=inv@x.T@target
    resid=target-x@coef
    cluster_scores=np.array([x[a==arm].T@resid[a==arm] for arm in unique])
    influence=np.einsum('k,gkm->gm',inv[0],cluster_scores)
    correction=g/(g-1)*(n-1)/(n-g-x.shape[1])
    se=np.sqrt(correction*(influence**2).sum(0))
    pvalue=2*t.sf(np.abs(coef[0]/se),g-1)
    half=t.ppf(.975,g-1)*se
    return coef[0],se,pvalue,half,scale,n,g

results=[]
for population in ['all','above_good','below_good']:
    mask=np.ones(len(sub),dtype=bool) if population=='all' else directions==population
    for adjust in [False,True]:
        beta,se,p,half,scale,n,g=fit(mask,adjust)
        for j,(probe,metric) in enumerate(names):
            results.append(dict(population=population,length_adjusted=adjust,probe=probe,metric=metric,n=n,arms=g,
                good_n=int(good[mask].sum()),bad_n=int((1-good[mask]).sum()),
                good_raw_mean=float(y[mask & (good==1),j].mean()),bad_raw_mean=float(y[mask & (good==0),j].mean()),
                delta_good_minus_bad=float(beta[j]),ci_low=float(beta[j]-half[j]),ci_high=float(beta[j]+half[j]),
                within_arm_sd=float(scale[j]),standardized_delta=float(beta[j]/scale[j]),
                p=float(p[j])))
# Holm controls family-wise error for all contrasts reported in this scan.
order=np.argsort([r['p'] for r in results]);running=0.
for rank,index in enumerate(order):
    running=max(running,min(1.,results[index]['p']*(len(results)-rank)))
    results[index]['p_holm']=running
with (OUT/'tests.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
counts=[]
for arm in np.unique(arms):
    take=arms==arm
    counts.append(dict(arm=arm,n=int(take.sum()),good=int(good[take].sum()),bad=int((1-good[take]).sum())))
(OUT/'counts.json').write_text(json.dumps(counts,indent=2))
summary=dict(n=len(sub),good=int(good.sum()),bad=int((1-good).sum()),excluded_baselines=200,excluded_unknown=1,
             definitions='good = estimate > threshold in above_good; estimate <= threshold in below_good',
             tests=len(results),correction='Holm across all 1008 tests; 42 probes, 4 summaries, 3 populations, 2 specifications',
             inference='OLS exact-arm fixed effects; CR1 standard errors clustered by arm; t(G-1); descriptive association',
             firing='Fraction of CoT tokens above style-matched baseline token-score 95th/99th percentile; not calibrated reward hacking',
             counts_by_direction={d:dict(good=int(good[directions==d].sum()),bad=int((1-good[directions==d]).sum())) for d in ['above_good','below_good']},
             significant=dict(Counter((r['population']+'|'+str(r['length_adjusted'])+'|'+r['metric']) for r in results if r['p_holm']<.05)),
             any_token_fire95_fraction={p:float(any_fires[eligible,j,0].mean()) for j,p in enumerate(probes)},
             scores_sha256=hashlib.sha256((ART/'rollout_scores.csv').read_bytes()).hexdigest())
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
print('MOTIVATED:')
for r in results:
    if r['probe'].startswith('motivated') and (r['p_holm']<.05 or (r['population']=='all' and not r['length_adjusted'])):
        print(json.dumps(r))
