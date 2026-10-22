#!/usr/bin/env bash
# Serve one pinned open model with vLLM (see motivation/runtime/motivation_models.json).
# Weights and env are read from node-local NVMe only; run scripts/setup_node.sh after every restart.
# Usage: scripts/serve_vllm.sh <model_dir_name> <port> <gpu_ids e.g. 0,1,2,3> [extra vllm args...]
set -euo pipefail
DATA=${VE_DATA:-/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data}
LOCAL=${VE_LOCAL:-/tmp/instance_storage/visual_effect_models}
name=$1 port=$2 gpus=$3; shift 3
[ -f "$LOCAL/models/$name/.staged" ] || { echo "$name is not staged; run scripts/stage_models.sh $name" >&2; exit 1; }
[ -x "$LOCAL/envs/vllm/bin/vllm" ] || { echo "local env missing; run scripts/setup_env.sh" >&2; exit 1; }
tp=$(awk -F, '{print NF}' <<<"$gpus")
mkdir -p "$DATA/logs"
CUDA_VISIBLE_DEVICES=$gpus exec "$LOCAL/envs/vllm/bin/vllm" serve "$LOCAL/models/$name" \
  --served-model-name "$name" --port "$port" --tensor-parallel-size "$tp" \
  --max-model-len 32768 --limit-mm-per-prompt '{"image":4}' --gpu-memory-utilization 0.9 "$@"
