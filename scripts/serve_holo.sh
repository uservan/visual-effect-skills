#!/bin/bash
set -euo pipefail
runtime=${VISUAL_EFFECT_RUNTIME:-/scratch/pioneer/jobs/wxy320/visual_effect_runtime}
export HF_HOME=/scratch/pioneer/jobs/wxy320/huggingface
export OMP_NUM_THREADS=4
export TOKENIZERS_PARALLELISM=false
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
# Reuse the cluster's working CUDA PyTorch in an isolated system-site venv.
# BF16 on large-memory A100; a fixed NF4 configuration otherwise.
exec "$runtime/transformers-venv/bin/python" \
  /home/wxy320/ondemand/program/visual-effect-skills/scripts/transformers_server.py
