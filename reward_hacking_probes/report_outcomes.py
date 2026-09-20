import csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
BASE=Path(__file__).resolve().parent
OUT=BASE/'artifacts/h100_20260918/outcome_comparison'
r=list(csv.DictReader((OUT/'tests.csv').open()))
s=json.loads((OUT/'summary.json').read_text())

def get(probe,metric,pop='all',adjust=True):
    return next(x for x in r if x['probe']==probe and x['metric']==metric and x['population']==pop and x['length_adjusted']==str(adjust))

def row(probe,label):
    m,f=get(probe,'mean'),get(probe,'fire95')
    lo,hi=[float(m[k])/float(m['within_arm_sd']) for k in ['ci_low','ci_high']]
    return f"| {label} | {float(m['standardized_delta']):+.3f} [{lo:+.3f}, {hi:+.3f}] | {float(m['p_holm']):.3g} | {100*float(f['delta_good_minus_bad']):+.3f} pp | {float(f['p_holm']):.3g} |"

text=f'''# Probe intensity versus good-side / bad-side outcome

**Yes, there are statistically significant associations, but no universal bad-side-higher pattern.** The reporting contrast is stronger on good-side outcomes. Several score-file-tampering directions are stronger on bad-side outcomes. The dedicated motivated-reasoning contrast has no pooled difference that survives the full multiple-comparison correction, though some direction-specific comparisons do.

Analyzed {s['n']:,} non-baseline rollouts with parsed estimates: **{s['good']:,} good-side, {s['bad']:,} bad-side**. Excluded 200 distinct baseline traces from outcome comparison and one unparsed estimate. Good means strictly above the threshold in above-good arms, or at/below it in below-good arms. There are no threshold ties in these data. Good-side refers to the favoured consequence, not answer accuracy or reasoning quality.

## Representative pooled comparisons

Effects are **good minus bad**, adjusting for exact prompt arm and log CoT token count. Blocks are one-based. Intensity differences are divided by the pooled within-arm standard deviation. The displayed 95% intervals are pointwise, not simultaneous; the p-values use Holm family-wise correction across all **1,008** tested comparisons.

| Contrast / block | Mean intensity difference, within-arm SD [95% CI] | Adjusted p | Token-exceedance difference | Adjusted p |
|---|---:|---:|---:|---:|
{row('report__L55','False reporting / 56')}
{row('scorefile__L47','Score-file tampering / 48')}
{row('motivated__L39','Motivated reasoning / 40')}

These are illustrative rows from the full scan, not independently selected confirmatory endpoints. All tested rows are in `tests.csv`. All seven reporting-contrast layers show higher pooled mean intensity on good-side outcomes after correction in the length-adjusted specification.

## What firing rate means here

No probe has a calibrated reward-hacking threshold. For an exploratory rate, each probe's cutoff is the **95th percentile of token scores in its style-matched unincentivized baseline** (100 paper-style and 100 casual-style baseline traces). Each rollout contributes its fraction of CoT tokens strictly exceeding that cutoff. The reference pools tokens, so long baseline traces contribute more tokens. Each target rollout has equal weight in the regression.

At that cutoff, **100% of the analyzed traces have at least one firing token for every probe**. Consequently, rollout-level any-fire rate cannot distinguish the groups. Token exceedance fractions can. For example, raw average fractions for reporting/block 56 are {100*float(get('report__L55','fire95')['good_raw_mean']):.2f}% good versus {100*float(get('report__L55','fire95')['bad_raw_mean']):.2f}% bad; the adjusted difference is +0.98 percentage points. The primary table reports adjusted differences, not differences of the raw marginal averages.

A 99th-percentile baseline threshold was also tested and included in the same multiplicity correction. Neither cutoff is a calibrated false-positive rate for reward hacking, and uncertainty in estimating these baseline cutoffs is not propagated. Rate inference is conditional on the fixed baseline reference.

## Motivated-reasoning contrast

None of its seven layers has a significant pooled difference after correction across the full scan, for mean, p95, or either firing fraction in the length-adjusted specification. This does not establish equivalence or absence of an effect.

At block 40, **above-good prompts** show higher mean intensity on the bad side: good-minus-bad = {float(get('motivated__L39','mean','above_good')['standardized_delta']):+.3f} within-arm SD, adjusted p = {float(get('motivated__L39','mean','above_good')['p_holm']):.4f}. The below-good estimate points in the opposite direction (+0.241 SD) but is not significant after correction. At block 56, the below-good mean-intensity comparison is significant (+0.362 SD, adjusted p = 0.00284). These are separate subgroup comparisons, not a formal interaction test.

The direction-specific pattern could partly track numerical magnitude, argument style, or related features of the estimate rather than good/bad outcome itself. Together with the previously observed enactment/resistance control overlap, this prevents a self-awareness interpretation.

## Statistical procedure and limits

- Exact-arm fixed effects: prompt key × incentive direction × provenance. Thirty-two arms, with 100 samples each except the arm with the unparsed estimate (99).
- Specifications with and without log CoT length; populations pooled, above-good, and below-good.
- Outcomes: mean token intensity, CoT p95 intensity, and token fractions above baseline 95th and 99th percentiles.
- CR1 sandwich standard errors clustered by arm, using Student-t critical values with G−1 degrees of freedom (31 pooled; 15 in each direction subgroup). This is approximate small-cluster inference.
- Holm correction across 42 probes × 4 summaries × 3 populations × 2 specifications = 1,008 tests. Both signs were tested. Full-design regressions independently reproduced the pooled representative coefficients and clustered p-values.
- Final-estimate side is an observed post-generation outcome. These are associations, not causal effects. Adjusting for length is a sensitivity specification and does not resolve that limitation. All data concern one estimation question, and six corrected arms were collected later.

Source score-table SHA-256: `{s['scores_sha256']}`.

![Mean-intensity associations by probe and incentive direction]({OUT/'mean_effects.png'})
'''
(OUT/'REPORT.md').write_text(text)
families=['suite','validator','scorefile','acquire','report','motivated'];layers=[15,23,31,39,47,55,63]
fig,axes=plt.subplots(1,3,figsize=(14,4.9),sharey=True)
for ax,pop,title in zip(axes,['all','above_good','below_good'],['All prompts','Good side is above threshold','Good side is below threshold']):
    matrix=np.array([[float(get(f'{fam}__L{l}','mean',pop)['standardized_delta']) for l in layers] for fam in families])
    im=ax.imshow(matrix,cmap='RdBu_r',vmin=-1,vmax=1,aspect='auto')
    ax.set_xticks(range(7),[l+1 for l in layers]);ax.set_xlabel('Decoder block');ax.set_title(title,fontsize=11)
    ax.set_yticks(range(6),families)
    for i,fam in enumerate(families):
        for j,l in enumerate(layers):
            if float(get(f'{fam}__L{l}','mean',pop)['p_holm'])<.05:ax.text(j,i,'*',ha='center',va='center',fontsize=15,color='black')
fig.suptitle('Good-side minus bad-side mean intensity, within-arm SD\nExact-arm and length adjusted; * Holm-adjusted p < 0.05 across all 1,008 tests',fontsize=12)
fig.subplots_adjust(right=.9,top=.79,bottom=.15,wspace=.15)
cax=fig.add_axes([.92,.16,.015,.62]);fig.colorbar(im,cax=cax,label='Positive = stronger on good side')
fig.savefig(OUT/'mean_effects.png',dpi=170);plt.close(fig)
print(OUT/'REPORT.md')
