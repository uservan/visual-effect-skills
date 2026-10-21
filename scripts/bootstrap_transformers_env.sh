#!/bin/bash
# CPU-side setup only; inherits the cluster's existing CUDA torch installation.
set -euo pipefail
runtime=${VISUAL_EFFECT_RUNTIME:-/scratch/pioneer/jobs/wxy320/visual_effect_runtime}
uv=/home/wxy320/.local/bin/uv
export UV_CACHE_DIR="$runtime/uv-cache"
if ! test -x "$runtime/transformers-venv/bin/python"; then
  "$uv" venv --system-site-packages --python /home/wxy320/miniconda3/envs/eval/bin/python "$runtime/transformers-venv"
fi
# --no-deps prevents replacing the inherited CUDA PyTorch with a newer CUDA
# major version. The import preflight below must pass before a ready marker.
"$uv" pip install --no-deps --python "$runtime/transformers-venv/bin/python" \
  transformers==5.6.2 accelerate==1.15.0 bitsandbytes==0.50.2 \
  fastapi==0.115.14 starlette==0.46.2 uvicorn==0.54.0 \
  huggingface_hub==1.33.0 tokenizers==0.22.2 safetensors==0.8.0 \
  hf-xet==1.7.0 regex==2026.9.29 pillow==12.3.0 click==8.5.0 mistral-common==1.12.0 pydantic-extra-types pycountry
"$runtime/transformers-venv/bin/python" - <<'PY'
import json
from pathlib import Path
import torch,transformers,fastapi,uvicorn,bitsandbytes
from transformers import AutoProcessor,AutoModelForImageTextToText,AutoConfig
from transformers.models.qwen3_5.modeling_qwen3_5 import Qwen3_5ForConditionalGeneration
root=Path('/scratch/pioneer/jobs/wxy320/visual_effect_runtime')
config=AutoConfig.from_pretrained(root/'models/Holo4-27B')
processor=AutoProcessor.from_pretrained(root/'models/Holo4-27B')
(root/'transformers_env.ready').write_text(json.dumps({'torch':torch.__version__,'transformers':transformers.__version__,'model_type':config.model_type})+'\n')
print('CPU import preflight passed; GPU inference remains unverified')
PY
