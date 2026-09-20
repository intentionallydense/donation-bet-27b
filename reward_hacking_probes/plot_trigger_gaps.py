"""Within-trace trigger spacing at the fixed casual-baseline p95 cutoff."""
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

BASE = Path(__file__).resolve().parent / 'artifacts/h100_20260918'
OUT = BASE / 'representative_casual'
FAMILIES = ['suite', 'validator', 'scorefile', 'acquire', 'report', 'motivated']


def main():
    selected = {s['row']['id'] for s in json.loads((OUT / 'selection.json').read_text())}
    thresholds = json.loads((BASE / 'outcome_comparison/thresholds.json').read_text())['casual']
    with (BASE / 'rollout_scores.csv').open() as f:
        rows = [r for r in csv.DictReader(f) if r['prompt_key'] in [
            'screen_giraffes_casual_good_cause_silent',
            'screen_giraffes_casual_good_cause_silent_eval_note_test']]
    assert len(rows) == 400
    gaps = defaultdict(list)
    per_trace = []
    for r in rows:
        with np.load(BASE / 'targets' / (hashlib.sha256(r['id'].encode()).hexdigest() + '.npz')) as d:
            for family in FAMILIES:
                probe = family + '__L39'
                hits = d[probe] > thresholds[probe][0]
                indices = np.flatnonzero(hits)
                starts = np.flatnonzero(hits & ~np.r_[False, hits[:-1]])
                ends = np.flatnonzero(hits & ~np.r_[hits[1:], False])
                measures = {
                    'trigger_distance': np.diff(indices),
                    'silent_gap': starts[1:] - ends[:-1] - 1,
                    'burst_start_distance': np.diff(starts),
                }
                assert len(starts) == len(ends)
                for metric, values in measures.items():
                    assert np.all(values >= 1)
                    for scope in ['all_400'] + (['four_displayed'] if r['id'] in selected else []):
                        gaps[scope, family, metric].extend(values.tolist())
                    per_trace.append(dict(id=r['id'], probe=probe, metric=metric, n=len(values),
                                          mean=float(np.mean(values)) if len(values) else None))
    summaries, histogram = [], []
    for (scope, family, metric), values in gaps.items():
        values = np.array(values)
        summaries.append(dict(scope=scope, probe=family, metric=metric, n=len(values),
                              mean=float(values.mean()), median=float(np.median(values)),
                              p90=float(np.quantile(values, .9)), p95=float(np.quantile(values, .95)),
                              p99=float(np.quantile(values, .99)), maximum=int(values.max()),
                              fraction_one=float(np.mean(values == 1))))
        unique, counts = np.unique(values, return_counts=True)
        for value, count in zip(unique, counts):
            histogram.append(dict(scope=scope, probe=family, metric=metric,
                                  tokens=int(value), count=int(count)))
    for filename, records in [('trigger_gap_summary.csv', summaries), ('trigger_gap_histogram.csv', histogram),
                              ('trigger_gap_per_trace.csv', per_trace)]:
        with (OUT / filename).open('w') as f:
            w = csv.DictWriter(f, fieldnames=list(records[0]))
            w.writeheader()
            w.writerows(records)
    for scope, label in [('four_displayed', 'Four displayed traces'), ('all_400', 'All 400 casual good/nothing traces')]:
        fig, axes = plt.subplots(2, 3, figsize=(13, 8), sharex=True, sharey=True)
        for ax, family in zip(axes.flat, FAMILIES):
            for metric, color, legend in [
                ('trigger_distance', '#2563a6', 'Consecutive firing-token distance'),
                ('silent_gap', '#c46c25', 'Non-firing tokens between bursts'),
            ]:
                values = np.array(gaps[scope, family, metric])
                x, counts = np.unique(values, return_counts=True)
                ax.step(x, counts.cumsum() / len(values) * 100, where='post', color=color, label=legend, lw=1.8)
                ax.scatter([1], [np.mean(values == 1) * 100], color=color, s=16)
            ax.set_title(family)
            ax.set_xscale('log')
            ax.set_ylim(0, 101)
            ax.set_xlim(left=.9)
            ax.grid(alpha=.2, which='both')
            ax.set_xlabel('Separation in tokens (log scale)')
            ax.set_ylabel('Cumulative share of gaps (%)')
        handles, labels = axes.flat[0].get_legend_handles_labels()
        fig.legend(handles, labels, loc='lower center', ncol=2, frameon=False)
        fig.suptitle(f'{label}: distribution of probe-trigger separations\n'
                     'Block 40 · casual-baseline 95th-percentile cutoff · gaps pooled within traces', fontsize=13)
        fig.tight_layout(rect=(0, .05, 1, .93))
        fig.savefig(OUT / f'trigger_gaps_{scope}.png', dpi=160)
        fig.savefig(OUT / f'trigger_gaps_{scope}.pdf')
        plt.close(fig)
    (OUT / 'TRIGGER_GAPS.md').write_text(
        '# Probe trigger separations\n\n'
        'Block 40, using strict score > the existing casual-baseline pooled-token 95th-percentile cutoff. '
        'No smoothing. A firing-token distance is the difference in indices of consecutive firing tokens; '
        '1 means adjacent tokens. A silent gap counts only non-firing tokens between consecutive bursts. '
        'Burst-start distance is also included in the CSVs. Gaps never cross trace boundaries; '
        'leading and trailing censored intervals are omitted. Each observed gap has equal weight, '
        'so traces with more triggers contribute more observations. These are descriptive distributions, '
        'not independent-event significance tests.\n\n'
        '- [Four displayed traces](trigger_gaps_four_displayed.png)\n'
        '- [All 400 traces](trigger_gaps_all_400.png)\n'
        '- [Summary statistics](trigger_gap_summary.csv)\n'
        '- [Exact discrete distributions](trigger_gap_histogram.csv)\n'
        '- [Per-trace means](trigger_gap_per_trace.csv)\n')
    for r in summaries:
        if r['metric'] == 'trigger_distance' or r['probe'] == 'motivated':
            print(r)


if __name__ == '__main__':
    main()
