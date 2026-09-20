"""Resumable, interleaved replacement sampling; preserves every completed response."""
import concurrent.futures,datetime,hashlib,json,random,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PARAMS=dict(model='Qwen/Qwen3.6-27B',max_tokens=16000,temperature=1,top_p=.95,presence_penalty=0,top_k=20,min_p=0,repetition_penalty=1,chat_template_kwargs={'enable_thinking':True})
def main():
 arms=json.loads((ROOT/'arms.json').read_text()); out=ROOT/'raw_rollouts.jsonl'
 done={r['sample_id'] for r in map(json.loads,out.read_text().splitlines())} if out.exists() else set()
 tasks=[(a,i) for i in range(100) for a in arms if f"{a['arm_id']}:{i}" not in done]
 random.Random(20260918).shuffle(tasks)
 def sample(task):
  a,i=task; payload={**PARAMS,'messages':[{'role':'user','content':a['prompt']}]}
  for attempt in range(4):
   try:
    req=urllib.request.Request('http://127.0.0.1:8000/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=1800) as response: raw=json.load(response)
    choice=raw['choices'][0]; msg=choice['message']
    return dict(sample_id=f"{a['arm_id']}:{i}",arm_id=a['arm_id'],prompt_key=a['prompt_key'],direction=a['direction'],threshold=a['threshold'],notice=a['notice'],prompt=a['prompt'],prompt_sha256=a['prompt_sha256'],reasoning=msg.get('reasoning_content') or msg.get('reasoning') or '',answer=msg.get('content') or '',finish_reason=choice['finish_reason'],usage_metadata=raw.get('usage'),raw_response=raw,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),provenance='corrected_replacement_20260918')
   except Exception:
    if attempt==3:raise
    time.sleep(2**attempt)
 with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool, out.open('a',buffering=1) as f:
  futures={pool.submit(sample,t):t for t in tasks}; errors=[]
  for future in concurrent.futures.as_completed(futures):
   try:
    row=future.result();f.write(json.dumps(row)+'\n');done.add(row['sample_id'])
    print(json.dumps({'completed':len(done),'sample_id':row['sample_id'],'finish_reason':row['finish_reason']}),flush=True)
   except Exception as e:
    a,i=futures[future];errors.append([a['arm_id'],i,type(e).__name__]);print('REQUEST_FAILED',errors[-1],flush=True)
 if errors:raise RuntimeError(f'{len(errors)} requests failed; rerun to resume')
 assert len(done)==600
 (ROOT/'GENERATION_COMPLETE').write_text(datetime.datetime.now(datetime.timezone.utc).isoformat())
if __name__=='__main__':main()
