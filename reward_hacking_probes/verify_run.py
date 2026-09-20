"""Verify every saved score artifact and write a checksum manifest."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from probe import read_rows, file_hash


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--artifacts',type=Path,required=True)
    parser.add_argument('--targets',type=Path,required=True)
    parser.add_argument('--synthetic',type=Path,required=True)
    args=parser.parse_args()
    base=args.artifacts
    fit=json.loads((base/'pilot.json').read_text())
    if fit['input_sha256']!=file_hash(args.synthetic):raise ValueError('Training data mismatch')
    run=json.loads((base/'targets/run.json').read_text())
    if run['input_sha256']!=file_hash(args.targets):raise ValueError('Replay data mismatch')
    if run['probes_sha256']!=file_hash(base/'pilot.npz'):raise ValueError('Probe weight mismatch')
    with np.load(base/'pilot.npz',allow_pickle=False) as probes:
        names=set(probes.files)
        assert len(names)==42
        assert all(probes[k].shape==(5120,) and np.isfinite(probes[k]).all() for k in names)
    hashes={}
    tokens=0
    rows=read_rows(args.targets)
    for i,row in enumerate(rows):
        basename=hashlib.sha256(row['id'].encode()).hexdigest()
        npz=base/'targets'/f'{basename}.npz'
        side=npz.with_suffix('.json')
        summary=json.loads(side.read_text())
        assert summary['id']==row['id']
        with np.load(npz,allow_pickle=False) as data:
            assert set(data.files)==names|{'offsets','token_ids'}
            n=len(data['token_ids']); tokens+=n
            assert n==summary['selected_tokens']
            offsets=data['offsets']
            assert offsets.shape==(n,2)
            assert (offsets[:,0]>=0).all() and (offsets[:,1]<=len(row['continuation'])).all()
            assert (offsets[:,1]>offsets[:,0]).all() and (np.diff(offsets[:,0])>=0).all()
            for name in names:
                values=data[name]
                assert values.shape==(n,) and np.isfinite(values).all()
                assert np.isclose(values.mean(),summary['summary'][name]['mean'])
                assert np.isclose(values.max(),summary['summary'][name]['max'])
        hashes[str(npz.relative_to(base))]=file_hash(npz)
        hashes[str(side.relative_to(base))]=file_hash(side)
        if (i+1)%250==0:print(f'verified {i+1}/{len(rows)}',flush=True)
    result=dict(status='verified',rollouts=len(rows),selected_cot_tokens=tokens,probes=len(names),
                training_sha256=fit['input_sha256'],targets_sha256=run['input_sha256'],
                probes_sha256=run['probes_sha256'],files=hashes)
    (base/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'},indent=2))

if __name__=='__main__':main()
