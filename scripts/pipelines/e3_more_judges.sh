#!/usr/bin/env bash
# Unattended: add three more open judge families to E3, then restore Qwen3.5 + GLM-5.3.
#  1. download + stage Step-3.7-Flash-FP8 and Nemotron-3.5-Super-VL (DeepSeek-V4.1-Flash is already staged)
#  2. DeepSeek-V4.1-Flash on 8 GPUs -> judge
#  3. Step-3.7-Flash (GPU 0-3) + Nemotron-3.5-VL (GPU 4-7) -> judge
#  4. restore Qwen3.5 (GPU 0-3) + GLM-5.3 (GPU 4-7)
# A judge whose server fails to start is skipped; the status says so. Status: $L/e3_more_judges.status
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd); cd "$ROOT"
DATA=/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data; L=$DATA/logs
PY=/usr/bin/python3
status(){ echo "$(date -u +%FT%TZ) $*" | tee -a $L/e3_more_judges.log > $L/e3_more_judges.status; }
pids_of(){ ps -eo pid,args | awk -v pat="$1" 'index($0,pat) && !/awk/ && !/bash -c/ {print $1}'; }
wait_health(){ local i; for i in $(seq 1 160); do [ "$(curl -s -o /dev/null -w '%{http_code}' localhost:$1/health)" = 200 ] && return 0
  grep -qE "EngineCore failed|Engine core initialization failed|CUDA out of memory" "$2" 2>/dev/null && return 1
  [ -z "$(pids_of "served-model-name $3")" ] && return 1; sleep 15; done; return 1; }
stop_all(){ local p; for p in $(pids_of "vllm serve"); do kill "$p"; done; sleep 25
  for p in $(pids_of "vllm serve"); do kill -9 "$p"; done
  for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader); do kill -9 "$p" 2>/dev/null; done; sleep 10; }
serve(){ # name port gpus extra...
  local name=$1 port=$2 gpus=$3; shift 3
  setsid nohup scripts/serve_vllm.sh "$name" "$port" "$gpus" "$@" > "$L/vllm_$name.log" 2>&1 < /dev/null &
}
judge(){ for k in "$@"; do $PY scripts/e3/judge.py --judges "$k" --repeats 3 --concurrency 32 >> $L/e3.log 2>&1; done; }

status "1 downloading Step-3.7-Flash-FP8 + Nemotron-3.5-VL"
hf download stepfun-ai/Step-3.7-Flash-FP8 --revision b3d7916fccac844cca050d7520f2aaa513f9a84f --local-dir $DATA/models/Step-3.7-Flash-FP8 --max-workers 16 > $L/dl_step37.log 2>&1 &
hf download nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-BF16 --revision 1f8953f7f0935358e3605150d22bc15df062061c --local-dir $DATA/models/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-BF16 --max-workers 16 > $L/dl_nemo35.log 2>&1 &
wait
scripts/stage_models.sh Step-3.7-Flash-FP8 NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-BF16 DeepSeek-V4.1-Flash >> $L/e3_more_judges.log 2>&1

status "2 DeepSeek-V4.1-Flash judging"
stop_all
serve DeepSeek-V4.1-Flash 8003 0,1,2,3,4,5,6,7 --tokenizer-mode deepseek_v41 --reasoning-parser deepseek_v41
ok=""
if wait_health 8003 $L/vllm_DeepSeek-V4.1-Flash.log DeepSeek-V4.1-Flash; then judge dsv41; ok="$ok dsv41"; else status "DeepSeek failed to start"; fi

status "3 Step-3.7 + Nemotron-3.5 judging"
stop_all
serve Step-3.7-Flash-FP8 8004 0,1,2,3 --reasoning-parser step3p5 --trust-remote-code
serve NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-BF16 8005 4,5,6,7 --reasoning-parser nemotron_v3 --trust-remote-code
up=()
wait_health 8004 $L/vllm_Step-3.7-Flash-FP8.log Step-3.7-Flash-FP8 && up+=(step37)
wait_health 8005 $L/vllm_NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-BF16.log NVIDIA-Nemotron && up+=(nemo35)
# Wait only for the judge jobs: a bare `wait` would also wait for the vLLM servers started above, forever.
jobs_=(); for k in "${up[@]}"; do judge "$k" & jobs_+=($!); done; for p in "${jobs_[@]}"; do wait "$p"; done; ok="$ok ${up[*]}"

status "4 restoring Qwen3.5 + GLM-5.3"
stop_all
serve Qwen3.5-397B-A17B-FP8 8001 0,1,2,3 --reasoning-parser qwen3
serve GLM-5.3-Flash 8002 4,5,6,7
wait_health 8001 $L/vllm_Qwen3.5-397B-A17B-FP8.log Qwen3.5 && wait_health 8002 $L/vllm_GLM-5.3-Flash.log GLM-5.3 && j=up || j=FAILED
status "done judges_completed:$ok qwen_glm=$j"
