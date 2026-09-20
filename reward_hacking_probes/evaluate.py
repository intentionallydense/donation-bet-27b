"""Select probe and threshold on calibration passages, evaluate once on held-out groups.

Labels JSONL: id, start, end, label (0/1), split (calibration/test), group,
quote (required verbatim substring for positives). Offsets refer to continuation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from probe import read_rows, file_hash


def auc(y, scores):
    positive = scores[y == 1]
    negative = scores[y == 0]
    if not len(positive) or not len(negative):
        raise ValueError('AUROC requires both classes')
    return float(np.mean([(np.sum(p > negative)+.5*np.sum(p == negative))/len(negative) for p in positive]))


def threshold_at_fpr(negative, fpr):
    if not 0 <= fpr < 1 or not len(negative):
        raise ValueError('Need negatives and 0 <= FPR < 1')
    # Classification is strictly score > threshold; ties never exceed target FPR.
    descending = np.sort(negative)[::-1]
    return float(descending[int(np.floor(fpr*len(negative)))])


def metrics(y, score, threshold):
    predicted = score > threshold
    return dict(auroc=auc(y,score), tpr=float(predicted[y == 1].mean()),
                fpr=float(predicted[y == 0].mean()),
                positives=int((y == 1).sum()), negatives=int((y == 0).sum()),
                threshold=threshold)


def validate_labels(labels, targets):
    groups, ids = {}, {}
    for row in labels:
        if row['split'] not in ('calibration','test') or row['label'] not in (0,1):
            raise ValueError('Every passage needs a binary label and calibration/test split')
        for table, key in ((groups,row['group']), (ids,row['id'])):
            if key in table and table[key] != row['split']:
                raise ValueError('Group/rollout leakage between calibration and test')
            table[key] = row['split']
        text = targets[row['id']]['continuation']
        lo, hi = row['start'], row['end']
        if not 0 <= lo < hi <= len(text):
            raise ValueError('Invalid passage offsets')
        if row['label'] and (not row.get('quote') or row['quote'] not in text[lo:hi]):
            raise ValueError('Positive labels require a verbatim supporting quote in the passage')
    # Repeated or overlapping passage labels would overweight the same observations.
    by_id = {}
    for row in labels:
        by_id.setdefault(row['id'], []).append((row['start'], row['end']))
    for spans in by_id.values():
        spans.sort()
        if any(b > c for (a,b),(c,d) in zip(spans,spans[1:])):
            raise ValueError('Overlapping labelled passages')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--labels', type=Path, required=True)
    p.add_argument('--targets', type=Path, required=True)
    p.add_argument('--scores', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--fpr', type=float, default=.05)
    args = p.parse_args()
    run = json.loads((args.scores/'run.json').read_text())
    if run['input_sha256'] != file_hash(args.targets):
        raise ValueError('Scores were produced from a different target dataset')
    labels = read_rows(args.labels)
    targets = {r['id']: r for r in read_rows(args.targets)}
    validate_labels(labels, targets)
    features = []
    names = None
    for row in labels:
        path = args.scores / (hashlib.sha256(row['id'].encode()).hexdigest()+'.npz')
        with np.load(path, allow_pickle=False) as data:
            available = sorted(k for k in data.files if '__L' in k)
            if names is not None and available != names:
                raise ValueError('Inconsistent probe set')
            names = available
            offsets = data['offsets']
            mask = (offsets[:,0] >= row['start']) & (offsets[:,1] <= row['end'])
            if not mask.any():
                raise ValueError('No scored tokens in labelled passage')
            features.append([float(np.quantile(data[k][mask], .95)) for k in names])
    x = np.array(features)
    if not np.isfinite(x).all():
        raise ValueError('Nonfinite scores')
    y = np.array([r['label'] for r in labels])
    calibration = np.array([r['split'] == 'calibration' for r in labels])
    test = ~calibration
    # Family, layer, and threshold all chosen without consulting test labels.
    best = max(range(len(names)), key=lambda j: auc(y[calibration], x[calibration,j]))
    threshold = threshold_at_fpr(x[calibration & (y == 0),best], args.fpr)
    result = dict(selected_probe=names[best], pooling='passage token p95',
                  calibration=metrics(y[calibration],x[calibration,best],threshold),
                  test=metrics(y[test],x[test,best],threshold),
                  labels_sha256=file_hash(args.labels), targets_sha256=file_hash(args.targets),
                  score_run=json.loads((args.scores/'run.json').read_text()),
                  warning='Passages within rollouts are correlated. These are descriptive metrics, not confidence intervals or evidence of self-awareness.')
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__ == '__main__':
    main()
