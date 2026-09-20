"""Select typical casual good/nothing traces independently of probe scores."""
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
BASE = ROOT / 'artifacts/h100_20260918'
OUT = BASE / 'representative_casual'
FAMILIES = ['suite', 'validator', 'scorefile', 'acquire', 'report', 'motivated']
LAYERS = [15, 23, 31, 39, 47, 55, 63]


def main():
    OUT.mkdir(exist_ok=True)
    rows = list(csv.DictReader((BASE / 'rollout_scores.csv').open()))
    selected = []
    for note in [False, True]:
        key = 'screen_giraffes_casual_good_cause_silent' + ('_eval_note_test' if note else '')
        for direction in ['below_good', 'above_good']:
            group = [r for r in rows if r['prompt_key'] == key and r['direction'] == direction
                     and r['estimate'] and np.isfinite(float(r['estimate']))]
            median_answer = float(np.median([float(r['estimate']) for r in group]))
            median_length = float(np.median([int(r['selected_tokens']) for r in group]))
            chosen = min(group, key=lambda r: (abs(float(r['estimate']) - median_answer),
                         abs(int(r['selected_tokens']) - median_length), r['id']))
            selected.append(dict(row=chosen, median_answer=median_answer, median_length=median_length,
                                 eligible=len(group), slug=('eval_' if note else 'ordinary_') + direction,
                                 title=('Evaluation note' if note else 'Ordinary') + '\nDonation ' +
                                 ('below' if direction == 'below_good' else 'above') + ' 133M'))
    ids = {s['row']['id'] for s in selected}
    targets = {}
    with (ROOT / 'data/targets_all.jsonl').open() as f:
        for line in f:
            row = json.loads(line)
            if row['id'] in ids:
                targets[row['id']] = row
    vectors = np.load(BASE / 'pilot.npz')
    index = ['# Representative casual good/nothing traces', '',
             'Selected by distance to the arm median final estimate, then distance to median CoT token count; '
             'probe scores and outcome labels were not used. Each arm contains 100 traces.', '',
             'Plots show signed scalar projections h·v / ||v|| (not absolute values or probabilities). '
             'Faint lines are individual tokens; bold lines average 64 consecutive tokens. '
             'Depth is selected CoT token position, from 0% to 100%. '
             'Each probe row shares its y-axis across arms; layers have separate scales. '
             'Block 40 is illustrative, not a validated best layer. '
             'These are template-trained exploratory probes; high scores do not establish reward hacking.', '']
    arrays = []
    for s in selected:
        row = s['row']
        target = targets[row['id']]
        path = BASE / 'targets' / (hashlib.sha256(row['id'].encode()).hexdigest() + '.npz')
        data = dict(np.load(path))
        n = len(data['token_ids'])
        assert n == int(row['selected_tokens'])
        assert all(len(data[f'{family}__L{layer}']) == n for family in FAMILIES for layer in LAYERS)
        arrays.append(data)
        good = float(row['estimate']) <= float(row['threshold']) if row['direction'] == 'below_good' else float(row['estimate']) > float(row['threshold'])
        s['good_side'] = good
        text = [f"# {s['title'].replace(chr(10), ' — ')}", '', f"ID: `{row['id']}`", '',
                f"Final estimate: {float(row['estimate']):,.0f}; donation {'triggered' if good else 'not triggered'}. "
                f"CoT: {n:,} tokens. Source: {row['provenance']}.", '',
                f"Arm median estimate: {s['median_answer']:,.0f}; median CoT length: {s['median_length']:,.0f}.", '',
                '## Prompt', '', '\n\n'.join(m['content'] for m in target['messages']), '', '## Full recorded CoT', '',
                target['continuation'], '', '## Final answer', '', target['answer'], '']
        (OUT / (s['slug'] + '.md')).write_text('\n'.join(text))
        # Full text fragments aligned to the exact selected-token offsets, in 10% depth bins.
        chunks = []
        for part in range(10):
            lo, hi = part * n // 10, (part + 1) * n // 10
            a, b = int(data['offsets'][lo, 0]), int(data['offsets'][hi - 1, 1])
            chunks.append(dict(depth_start=part * 10, depth_end=(part + 1) * 10,
                               text=target['continuation'][a:b]))
        (OUT / (s['slug'] + '_depth.json')).write_text(json.dumps(chunks, indent=2))
        index += [f"- [{s['title'].replace(chr(10), ' — ')}]({s['slug']}.md): "
                  f"{float(row['estimate']) / 1e6:g}M; {n:,} tokens; {'good' if good else 'nothing'} side."]
        with (OUT / (s['slug'] + '_scores.csv')).open('w') as f:
            names = [f'{family}__L{layer}' for layer in LAYERS for family in FAMILIES]
            writer = csv.writer(f)
            writer.writerow(['token_index', 'depth_percent', 'char_start', 'char_end'] + names)
            scores = np.stack([data[name] / np.linalg.norm(vectors[name]) for name in names], axis=1)
            assert np.isfinite(scores).all()
            for i in range(n):
                writer.writerow([i, i / max(n - 1, 1) * 100, *data['offsets'][i]] + scores[i].tolist())
    colors = ['#2463a3', '#19856b', '#9359a5', '#d27527', '#b54457', '#44546b']
    for layer in LAYERS:
        fig, axes = plt.subplots(6, 4, figsize=(17, 13), sharex=True, sharey='row')
        for col, (s, data) in enumerate(zip(selected, arrays)):
            n = len(data['token_ids'])
            x = np.linspace(0, 100, n)
            for row, family in enumerate(FAMILIES):
                name = f'{family}__L{layer}'
                y = data[name] / np.linalg.norm(vectors[name])
                ax = axes[row, col]
                ax.plot(x, y, color=colors[row], alpha=.18, lw=.45, rasterized=True)
                bins = list(range(0, n, 64))
                ax.plot([x[b:b+64].mean() for b in bins], [y[b:b+64].mean() for b in bins],
                        color=colors[row], lw=1.4)
                ax.axhline(0, color='black', lw=.5, alpha=.35)
                ax.grid(alpha=.15)
                if col == 0:
                    ax.set_ylabel(family + '\nSigned projection')
                if row == 0:
                    r = s['row']
                    ax.set_title(s['title'] + f"\nAnswer {float(r['estimate']) / 1e6:g}M · {n:,} tokens", fontsize=10)
                if row == 5:
                    ax.set_xlabel('CoT depth (%)')
        fig.suptitle(f'Casual good/nothing: typical traces · decoder block {layer + 1}\n'
                     'Signed projection onto unit probe direction; faint = tokens, bold = 64-token averages', fontsize=14)
        fig.tight_layout(rect=(0, 0, 1, .95))
        fig.savefig(OUT / f'block_{layer + 1}.png', dpi=150)
        fig.savefig(OUT / f'block_{layer + 1}.pdf')
        plt.close(fig)
    index += ['', '## Plots', ''] + [f'- [Block {layer + 1}](block_{layer + 1}.png)' for layer in LAYERS]
    (OUT / 'README.md').write_text('\n'.join(index) + '\n')
    (OUT / 'selection.json').write_text(json.dumps(selected, indent=2))
    print(json.dumps([{k: v for k, v in s.items() if k != 'row'} | {
        'id': s['row']['id'], 'estimate': s['row']['estimate']} for s in selected], indent=2))


if __name__ == '__main__':
    main()
