#!/usr/bin/env bash
# Unattended E5: wait until e3_more_judges.sh has restored Qwen3.5 + GLM-5.3, then answer E5 with both.
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd); cd "$ROOT"
L=/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data/logs
status(){ echo "$(date -u +%FT%TZ) $*" | tee -a $L/e5.log > $L/e5.status; }
status "waiting for e3_more_judges to finish"
until grep -q "^.* done " $L/e3_more_judges.status 2>/dev/null; do sleep 60; done
for p in 8001 8002; do until [ "$(curl -s -o /dev/null -w '%{http_code}' localhost:$p/health)" = 200 ]; do sleep 30; done; done
status "answering with Qwen3.5 and GLM-5.3"
/usr/bin/python3 scripts/e5/answer.py --base-url http://localhost:8001/v1 --model Qwen3.5-397B-A17B-FP8 --tag qwen35 >> $L/e5.log 2>&1 &
/usr/bin/python3 scripts/e5/answer.py --base-url http://localhost:8002/v1 --model GLM-5.3-Flash --tag glm53 >> $L/e5.log 2>&1 &
wait
status "done"
