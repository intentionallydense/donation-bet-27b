import os,json
from pathlib import Path
os.environ['HF_HOME']='/dev/shm/donation-hf'
os.environ['HF_XET_CACHE']='/workspace/donation-replacement/xet'
from huggingface_hub import HfApi,snapshot_download
secret=Path('/workspace/donation-replacement/hf-token')
token=secret.read_text().strip()
info=HfApi(token=token).model_info('Qwen/Qwen3.6-27B')
Path('/workspace/donation-replacement/model_revision.json').write_text(json.dumps({'model':'Qwen/Qwen3.6-27B','revision':info.sha}))
snapshot_download('Qwen/Qwen3.6-27B',revision=info.sha,token=token,allow_patterns=['*.json','*.safetensors','*.jinja','*.txt','*.model'],max_workers=8)
secret.unlink()
print('DOWNLOAD_COMPLETE',flush=True)
