#!/usr/bin/env bash
# Copy pinned models from shared storage to node-local NVMe before serving; never load from /shared.
# Idempotent: models whose local copy already matches are skipped. Re-run after every node restart
# (node-local storage does not survive the machine).
# Usage: scripts/stage_models.sh [model_dir_name ...]   (default: all models in motivation_models.json)
set -euo pipefail
DATA=${VE_DATA:-/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data}
LOCAL=${VE_LOCAL:-/tmp/instance_storage/visual_effect_models}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$LOCAL/models"
names=("$@")
[ ${#names[@]} -gt 0 ] || mapfile -t names < <(python3 -c "import json;print('\n'.join(json.load(open('$ROOT/motivation/runtime/motivation_models.json'))['models']))")
for n in "${names[@]}"; do
  src="$DATA/models/$n" dst="$LOCAL/models/$n"
  if [ -f "$dst/.staged" ] && [ "$(du -sb "$src" | cut -f1)" = "$(cat "$dst/.staged")" ]; then echo "$n already staged"; continue; fi
  echo "staging $n"
  mkdir -p "$dst"
  # Parallel per-file copies; FSx throughput scales with concurrent readers.
  (cd "$src" && find . -type f ! -path './.cache/*' -print0 | xargs -0 -P 32 -I{} cp --parents {} "$dst/")
  du -sb "$src" | cut -f1 > "$dst/.staged"
  echo "$n staged"
done
