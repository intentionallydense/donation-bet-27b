"""Token-weighted DoM fitting and token-level scoring with decoder-block hooks."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import numpy as np


def read_rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def span_mask(offsets, start, spans):
    """Fully contained, nonempty tokens only; excludes boundary-straddling tokens."""
    if not spans or any(a < 0 or b <= a for a, b in spans):
        raise ValueError('Expected nonempty [start,end) character spans')
    return np.array([b > a and any(start+lo <= a and b <= start+hi for lo, hi in spans)
                     for a, b in offsets], dtype=bool)


def direction(pos_sum, pos_n, neg_sum, neg_n):
    if not pos_n or not neg_n:
        raise ValueError('Both classes need selected tokens')
    v = np.asarray(pos_sum, dtype=np.float64)/pos_n - np.asarray(neg_sum, dtype=np.float64)/neg_n
    if not np.all(np.isfinite(v)) or np.linalg.norm(v) <= 1e-12:
        raise ValueError('Invalid or zero probe direction')
    return v.astype(np.float32)


def encode(tokenizer, row, max_tokens):
    prefix = tokenizer.apply_chat_template(row['messages'], tokenize=False,
                                          add_generation_prompt=True, enable_thinking=True)
    if not prefix.endswith('<think>\n'):
        raise ValueError('Unexpected generation prefix: verify the Qwen thinking template')
    text = prefix + row['continuation']
    encoded = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    ids, offsets = encoded['input_ids'], encoded['offset_mapping']
    if len(ids) > max_tokens:
        raise ValueError(f"{row['id']}: {len(ids)} tokens exceeds {max_tokens}; no truncation allowed")
    if any(hi > len(row['continuation']) for _, hi in row['spans']):
        raise ValueError('Span exceeds continuation length')
    mask = span_mask(offsets, len(prefix), row['spans'])
    if not mask.any():
        raise ValueError('No selected continuation tokens')
    return ids, offsets, mask, len(prefix)


def load_runtime(args):
    import torch
    import transformers
    from transformers import AutoModelForImageTextToText, AutoTokenizer
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA GPU required for the 27B runtime')
    tokenizer = AutoTokenizer.from_pretrained(args.model, revision=args.revision, use_fast=True)
    if not tokenizer.is_fast:
        raise ValueError('Offset mapping requires a fast tokenizer')
    model = AutoModelForImageTextToText.from_pretrained(
        args.model, revision=args.revision, dtype=torch.bfloat16,
        device_map='auto', attn_implementation='sdpa').eval()
    # Text-only forward bypasses vision and the expensive vocabulary logits.
    decoder = model.model.language_model
    if len(decoder.layers) != 64 or decoder.config.hidden_size != 5120:
        raise ValueError('Expected Qwen3.6-27B: 64 decoder blocks, hidden size 5120')
    if any(str(p.device) in ('cpu', 'meta') for p in decoder.parameters()):
        raise RuntimeError('Decoder CPU/disk offload detected; provide sufficient GPU memory')
    layers = sorted(set(args.layers))
    if not layers or min(layers) < 0 or max(layers) >= len(decoder.layers):
        raise ValueError('Layers must be zero-based decoder block indices in [0,63]')
    provenance = dict(model=args.model, revision=args.revision,
                      implementation_sha256=file_hash(__file__),
                      resolved_commit=getattr(model.config, '_commit_hash', None),
                      layers=layers, hidden_size=5120, dtype='bfloat16',
                      activation='decoder block output, before final model norm',
                      template_sha256=hashlib.sha256(tokenizer.chat_template.encode()).hexdigest(),
                      versions={p: importlib.metadata.version(p) for p in ('torch','transformers','numpy','accelerate')})
    return torch, model, decoder, tokenizer, provenance


def forward(torch, decoder, ids, layers, consume):
    handles = []
    for layer in layers:
        def hook(_module, _inputs, output, layer=layer):
            hidden = output[0] if isinstance(output, tuple) else output
            consume(layer, hidden[0].detach())
        handles.append(decoder.layers[layer].register_forward_hook(hook))
    try:
        device = decoder.embed_tokens.weight.device
        with torch.inference_mode():
            decoder(input_ids=torch.tensor([ids], device=device), use_cache=False,
                    output_hidden_states=False, return_dict=True)
    finally:
        for handle in handles:
            handle.remove()


def fit(args):
    rows = read_rows(args.input)
    pairs = {}
    for row in rows:
        if row.get('split') != 'train' or row.get('label') not in (0, 1):
            raise ValueError('Fit only accepts explicitly labelled training rows')
        key = (row['family'], row['pair'])
        pair = pairs.setdefault(key, {})
        if row['label'] in pair:
            raise ValueError(f'Duplicate pair member {key}')
        pair[row['label']] = row
    for key, pair in pairs.items():
        if set(pair) != {0, 1} or pair[0]['messages'] != pair[1]['messages']:
            raise ValueError(f'Unmatched pair {key}')
    torch, model, decoder, tokenizer, meta = load_runtime(args)
    sums, counts = {}, {}
    for index, row in enumerate(rows):
        ids, _, mask, _ = encode(tokenizer, row, args.max_tokens)
        def consume(layer, hidden):
            key = (row['family'], row['label'], layer)
            selected = hidden[torch.as_tensor(mask, device=hidden.device)]
            value = selected.double().sum(dim=0).cpu().numpy()
            sums[key] = sums.get(key, np.zeros_like(value)) + value
            counts[key] = counts.get(key, 0) + len(selected)
        forward(torch, decoder, ids, meta['layers'], consume)
        print(f'fit {index+1}/{len(rows)} {row["id"]}', flush=True)
    arrays = {}
    for family in sorted({r['family'] for r in rows}):
        for layer in meta['layers']:
            p, n = (family, 1, layer), (family, 0, layer)
            arrays[f'{family}__L{layer}'] = direction(sums[p], counts[p], sums[n], counts[n])
    meta.update(input_sha256=file_hash(args.input), token_weighted=True,
                counts={str(k): v for k, v in counts.items()},
                note='Uncalibrated raw directions; scores are not probabilities.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, **arrays)
    args.output.with_suffix('.json').write_text(json.dumps(meta, indent=2)+'\n')


def score(args):
    probe_meta = json.loads(args.probes.with_suffix('.json').read_text())
    args.layers = probe_meta['layers']
    torch, model, decoder, tokenizer, meta = load_runtime(args)
    for key in ('model', 'revision', 'resolved_commit', 'template_sha256', 'dtype', 'activation', 'versions', 'implementation_sha256'):
        if meta[key] != probe_meta[key]:
            raise ValueError(f'Probe/replay mismatch in {key}: {meta[key]} != {probe_meta[key]}')
    with np.load(args.probes, allow_pickle=False) as archive:
        vectors = {key: archive[key] for key in archive.files}
    if any(v.shape != (5120,) or not np.isfinite(v).all() for v in vectors.values()):
        raise ValueError('Invalid probe vectors')
    rows = read_rows(args.input)
    if args.limit:
        rows = rows[:args.limit]
    args.output.mkdir(parents=True, exist_ok=True)
    meta.update(input_sha256=file_hash(args.input), probes_sha256=file_hash(args.probes),
                limit=args.limit, max_tokens=args.max_tokens, score='raw inner product',
                status='Token scores; no calibrated claims or behavioural labels')
    manifest = args.output / 'run.json'
    if manifest.exists() and json.loads(manifest.read_text()) != meta:
        raise ValueError('Output belongs to a different run; use a fresh directory')
    manifest.write_text(json.dumps(meta, indent=2)+'\n')
    for index, row in enumerate(rows):
        safe_id = hashlib.sha256(row['id'].encode()).hexdigest()
        npz = args.output / f'{safe_id}.npz'
        sidecar = npz.with_suffix('.json')
        if npz.exists() and sidecar.exists():
            continue
        ids, offsets, mask, start = encode(tokenizer, row, args.max_tokens)
        scores = {}
        def consume(layer, hidden):
            names = [k for k in vectors if k.endswith(f'__L{layer}')]
            weights = torch.as_tensor(np.stack([vectors[k] for k in names]), device=hidden.device)
            selected = hidden[torch.as_tensor(mask, device=hidden.device)].float()
            values = (selected @ weights.T).cpu().numpy()
            for j, name in enumerate(names):
                scores[name] = values[:, j]
        forward(torch, decoder, ids, meta['layers'], consume)
        relative = np.array(offsets)[mask] - start
        payload = dict(offsets=relative, token_ids=np.array(ids)[mask], **scores)
        temporary = npz.with_suffix('.tmp.npz')
        np.savez_compressed(temporary, **payload)
        temporary.replace(npz)
        summary = {}
        for name, values in scores.items():
            top = np.argsort(values)[-min(10,len(values)):][::-1]
            summary[name] = dict(mean=float(values.mean()), max=float(values.max()),
                                 p95=float(np.quantile(values,.95)),
                                 top=[dict(start=int(relative[t,0]), end=int(relative[t,1]),
                                           score=float(values[t]),
                                           context=row['continuation'][max(0,int(relative[t,0])-100):int(relative[t,1])+100]) for t in top])
        sidecar.write_text(json.dumps(dict(id=row['id'], metadata=row.get('metadata',{}),
                                          selected_tokens=int(mask.sum()), summary=summary), indent=2)+'\n')
        print(f'score {index+1}/{len(rows)} {row["id"]}', flush=True)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='command', required=True)
    for command in ('fit', 'score'):
        s = sub.add_parser(command)
        s.add_argument('--model', default='Qwen/Qwen3.6-27B')
        s.add_argument('--revision', required=True, help='Pinned Hugging Face commit or local model revision label')
        s.add_argument('--input', type=Path, required=True)
        s.add_argument('--output', type=Path, required=True)
        s.add_argument('--max-tokens', type=int, default=16384)
        s.add_argument('--layers', type=int, nargs='+', default=[15,23,31,39,47,55,63])
        if command == 'score':
            s.add_argument('--probes', type=Path, required=True)
            s.add_argument('--limit', type=int, default=0)
    args = p.parse_args()
    if args.command == 'fit' and args.output.suffix != '.npz':
        p.error('Fit output must end in .npz')
    {'fit': fit, 'score': score}[args.command](args)

if __name__ == '__main__':
    main()
