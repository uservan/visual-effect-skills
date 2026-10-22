#!/usr/bin/env bash
# Build the serving/experiment Python env on node-local NVMe from the exact lock file.
# Idempotent: skipped when the env exists and was built from the current lock.
# Lock: motivation/runtime/vllm_env.lock.txt (uv pip freeze of the validated env; vllm 0.31.0, torch 2.13.0+cu130).
set -euo pipefail
LOCAL=${VE_LOCAL:-/tmp/instance_storage/visual_effect_models}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
LOCK=$ROOT/motivation/runtime/vllm_env.lock.txt
ENV=$LOCAL/envs/vllm
want=$(sha256sum "$LOCK" | cut -d' ' -f1)
if [ -f "$ENV/.lock_sha256" ] && [ "$(cat "$ENV/.lock_sha256")" = "$want" ] && "$ENV/bin/python" -c 'import vllm' 2>/dev/null; then
  echo "env up to date: $ENV"; exit 0
fi
rm -rf "$ENV"; mkdir -p "$(dirname "$ENV")"
# uv's cache also goes to local disk so a rebuild never reads packages from /shared.
export UV_CACHE_DIR=$LOCAL/uv-cache
uv venv -q -p 3.12 "$ENV"
VIRTUAL_ENV=$ENV uv pip install -q -r "$LOCK" --torch-backend=cu130
"$ENV/bin/python" -c 'import vllm,torch;print("vllm",vllm.__version__,"torch",torch.__version__,"cuda",torch.cuda.is_available())'
echo "$want" > "$ENV/.lock_sha256"
