#!/usr/bin/env bash
# Unattended E1 pipeline (run detached: setsid nohup ... &). Survives the editor closing, not a machine restart.
#  1. wait for the Qwen3.5 + GLM-5.3 split to finish (relaunch it if it dies; it is resumable)
#  2. stop both servers, serve DeepSeek-V4.1-Flash on all 8 GPUs, run the third vote
#  3. stop DeepSeek, bring Qwen3.5 (GPU 0-3) and GLM-5.3 (GPU 4-7) back for E3
# Writes progress to $DATA/logs/pipeline_e1.log and $DATA/logs/pipeline_e1.status
# If DeepSeek fails to start or vote, step 3 still runs so the judges are back; the status says what failed.
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
DATA=/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data
L=$DATA/logs; LOG=$L/pipeline_e1.log; STATUS=$L/pipeline_e1.status
PY=/tmp/instance_storage/visual_effect_models/envs/vllm/bin/python
RAW=$ROOT/motivation/benchmark_audit/split_full_raw.jsonl
TOTAL=$(($(python3 -c "import csv;print(sum(1 for _ in csv.DictReader(open('$ROOT/motivation/benchmark_audit/task_inventory.csv'))))")))
cd "$ROOT"
log(){ echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
status(){ echo "$(date -u +%FT%TZ) $*" > "$STATUS"; log "STATUS $*"; }
labelled(){ python3 -c "
import json;s=set()
for l in open('$RAW'):
    j=json.loads(l)
    if j['labels'] and j['model'] in '$1'.split(): s.add((j['model'],j['benchmark'],j['task_id']))
print(len(s))"; }
pids_of(){ ps -eo pid,args | awk -v pat="$1" 'index($0,pat) && !/awk/ && !/bash -c/ {print $1}'; }
healthy(){ [ "$(curl -s -o /dev/null -w '%{http_code}' localhost:$1/health)" = 200 ]; }
wait_health(){ local port=$1 logf=$2 i; for i in $(seq 1 160); do healthy "$port" && return 0
  grep -qE "EngineCore failed|Traceback|CUDA out of memory" "$logf" 2>/dev/null && return 1; sleep 15; done; return 1; }
stop_server(){ local name=$1 p; for p in $(pids_of "served-model-name $name"); do kill "$p"; done; sleep 20
  for p in $(pids_of "served-model-name $name"); do kill -9 "$p"; done; }
gpus_free(){ local i; for i in $(seq 1 40); do [ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)" ] && return 0; sleep 6; done
  for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader); do kill -9 "$p" 2>/dev/null; done; sleep 10; }
start_judges(){
  setsid nohup scripts/serve_vllm.sh Qwen3.5-397B-A17B-FP8 8001 0,1,2,3 --reasoning-parser qwen3 > $L/vllm_qwen35.log 2>&1 < /dev/null &
  setsid nohup scripts/serve_vllm.sh GLM-5.3-Flash 8002 4,5,6,7 > $L/vllm_glm53.log 2>&1 < /dev/null &
  wait_health 8001 $L/vllm_qwen35.log && wait_health 8002 $L/vllm_glm53.log; }

status "step1 waiting for qwen35+glm53 split"
for attempt in $(seq 1 5); do
  while [ -n "$(pids_of 'split_tasks.py --tag full')" ]; do sleep 60; done
  n=$(labelled "qwen35 glm53"); log "qwen35+glm53 labelled $n / $((TOTAL*2))"
  [ "$n" -ge $((TOTAL*2)) ] && break
  log "split not complete; relaunch attempt $attempt"
  $PY scripts/benchmark_audit/split_tasks.py --tag full --models qwen35 glm53 --concurrency 48 >> $L/split_full.log 2>&1
done

status "step2 swapping to DeepSeek-V4.1-Flash"
stop_server Qwen3.5-397B-A17B-FP8; stop_server GLM-5.3-Flash; gpus_free
setsid nohup scripts/serve_vllm.sh DeepSeek-V4.1-Flash 8003 0,1,2,3,4,5,6,7 --tokenizer-mode deepseek_v41 --reasoning-parser deepseek_v41 \
  > $L/vllm_dsv41.log 2>&1 < /dev/null &
ds_ok=no
if wait_health 8003 $L/vllm_dsv41.log; then
  for attempt in 1 2 3; do
    $PY scripts/benchmark_audit/split_tasks.py --tag full --models dsv41 --concurrency 64 >> $L/split_full.log 2>&1
    [ "$(labelled dsv41)" -ge "$TOTAL" ] && { ds_ok=yes; break; }
  done
  # Final three-way aggregate; qwen35/glm53 are complete, so only the CSV is rewritten.
  $PY scripts/benchmark_audit/split_tasks.py --tag full --models qwen35 glm53 dsv41 >> $L/split_full.log 2>&1
  log "aggregate: $(tail -1 $L/split_full.log)"
else
  log "DeepSeek server failed to start; see $L/vllm_dsv41.log"
fi

status "step3 restoring Qwen3.5 + GLM-5.3"
stop_server DeepSeek-V4.1-Flash; gpus_free
if start_judges; then status "done deepseek_vote=$ds_ok judges=up"; else status "done deepseek_vote=$ds_ok judges=FAILED (see vllm logs)"; fi
