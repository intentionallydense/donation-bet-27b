"""Compact, read-only progress snapshot for the supervised GPU run."""
import json
import time
from pathlib import Path
base=Path(__file__).resolve().parent
files=list((base/'artifacts/targets').glob('*.npz'))
times=sorted(p.stat().st_mtime for p in files)
log=(base/'run.log').read_text(errors='replace').splitlines()
result=dict(fitted=(base/'artifacts/FIT_COMPLETE').exists(),scored=len(files),total=3400,
            completed=(base/'artifacts/SCORING_COMPLETE').exists(),
            recent=[s for s in log if s.startswith(('score ','fit ','Traceback','RuntimeError','ValueError','torch.OutOfMemoryError'))][-3:])
if len(times)>2:
    rate=(len(times)-1)/(times[-1]-times[0])
    result.update(rollouts_per_minute=round(rate*60,1),estimated_minutes_remaining=round((3400-len(files))/rate/60,1),
                  seconds_since_last_record=round(time.time()-times[-1],1))
print(json.dumps(result))
