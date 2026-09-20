"""CPU-only template/span/context audit before loading model weights."""
import argparse
import json
from pathlib import Path
import numpy as np
from transformers import AutoTokenizer
from probe import encode, read_rows, file_hash


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model',default='Qwen/Qwen3.6-27B')
    p.add_argument('--revision',required=True)
    p.add_argument('--input',type=Path,nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--max-tokens',type=int,default=16384)
    args = p.parse_args()
    tokenizer = AutoTokenizer.from_pretrained(args.model,revision=args.revision,use_fast=True)
    reports = []
    failed = False
    for path in args.input:
        lengths, errors = [], []
        for row in read_rows(path):
            try:
                ids,_,_,_ = encode(tokenizer,row,args.max_tokens)
                lengths.append(len(ids))
            except ValueError as error:
                errors.append(str(error))
        failed |= bool(errors)
        reports.append(dict(path=str(path),sha256=file_hash(path),valid=len(lengths),errors=errors,
                            total_tokens=sum(lengths),max_tokens=max(lengths,default=0),
                            median_tokens=float(np.median(lengths)) if lengths else None,
                            p95_tokens=float(np.quantile(lengths,.95)) if lengths else None))
    result = dict(model=args.model,revision=args.revision,reports=reports,
                  note='Tokenizer/span validation only; no activations or model conclusions.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if failed:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
