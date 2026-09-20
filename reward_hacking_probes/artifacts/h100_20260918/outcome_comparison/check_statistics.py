import csv
from pathlib import Path
import numpy as np
from scipy.stats import t
p=Path('reward_hacking_probes/artifacts/h100_20260918')
r=[r for r in csv.DictReader((p/'rollout_scores.csv').open()) if r['direction']!='baseline' and r['estimate']]
arms=[r['prompt_key']+'|'+r['direction']+'|'+r['provenance'] for r in r]
u=sorted(set(arms));a=np.array(arms);n=len(r);g=len(u)
good=np.array([(float(x['estimate'])>float(x['threshold']))==(x['direction']=='above_good') for x in r],float)
x=np.column_stack([(a[:,None]==np.array(u)[None,:]).astype(float),good,np.log([int(z['selected_tokens']) for z in r])])
inv=np.linalg.inv(x.T@x)
tests=list(csv.DictReader((p/'outcome_comparison/tests.csv').open()))
for probe in ['report__L55','scorefile__L47','motivated__L39']:
 y=np.array([float(z[probe+'.mean']) for z in r]);beta=np.linalg.lstsq(x,y,rcond=None)[0];resid=y-x@beta
 meat=sum(np.outer(x[a==arm].T@resid[a==arm],x[a==arm].T@resid[a==arm]) for arm in u)
 cov=inv@meat@inv*g/(g-1)*(n-1)/(n-x.shape[1]);se=np.sqrt(cov[g,g])
 target=next(z for z in tests if z['probe']==probe and z['metric']=='mean' and z['population']=='all' and z['length_adjusted']=='True')
 assert np.isclose(beta[g],float(target['delta_good_minus_bad']),rtol=1e-8,atol=1e-8)
 assert np.isclose(2*t.sf(abs(beta[g]/se),g-1),float(target['p']),rtol=1e-6,atol=1e-12)
 print(probe,'independent full-design regression matches')
