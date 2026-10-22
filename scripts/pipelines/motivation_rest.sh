#!/usr/bin/env bash
# Unattended rest of the motivation experiments on the running vLLM judges (Qwen3.5 :8001, GLM-5.3 :8002).
# Run detached: setsid nohup scripts/pipelines/motivation_rest.sh > $L/motivation_rest.stdout 2>&1 &
#  A. E1 re-split of the 129 non-PSBench tasks with the ui_operation role
#  B. E3 candidates + judgments (2 judges x 3 repeats)        } in parallel
#  C. E4 questions from 4 manuals + closed/open-book answers  }
# Status: $L/motivation_rest.status ; every step is resumable, re-running continues where it stopped.
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd); cd "$ROOT"
L=/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data/logs
PY=/usr/bin/python3   # container python: has httpx, bs4, scikit-image, numpy
A=motivation/benchmark_audit
status(){ echo "$(date -u +%FT%TZ) $*" | tee -a $L/motivation_rest.log > $L/motivation_rest.status; }

status "A: E1 re-split of non-PSBench tasks"
# The first nonps_v2 run had no 'ui' in the JSON enum; keep it aside so the resume does not reuse it.
[ -f $A/split_nonps_v2_raw.jsonl ] && [ ! -f $L/.nonps_v2_invalid_moved ] && mv $A/split_nonps_v2_raw.jsonl $L/split_nonps_v2_raw.INVALID_no_ui_enum.jsonl && touch $L/.nonps_v2_invalid_moved
IDS=$($PY -c "import csv;print(','.join(r['benchmark']+':'+r['task_id'] for r in csv.DictReader(open('$A/task_inventory.csv')) if r['benchmark']!='PSBench'))")
$PY scripts/benchmark_audit/split_tasks.py --tag nonps_v2 --ids "$IDS" --models qwen35 glm53 --concurrency 48 >> $L/split_nonps_v2.log 2>&1
status "A done: $(tail -1 $L/split_nonps_v2.log)"

(
  [ -f motivation/e3/candidates_manifest.csv ] || $PY -W ignore scripts/e3/make_candidates.py >> $L/e3.log 2>&1
  $PY scripts/e3/judge.py --repeats 3 --concurrency 32 >> $L/e3.log 2>&1
  echo "$(date -u +%FT%TZ) E3 finished: $(tail -1 $L/e3.log)" >> $L/motivation_rest.log
) &
(
  $PY scripts/e4/gen_questions.py gimp darktable krita opentoonz --units 30 >> $L/e4.log 2>&1
  $PY scripts/e4/answer.py gimp darktable krita opentoonz --base-url http://localhost:8001/v1 --model Qwen3.5-397B-A17B-FP8 --tag qwen35 >> $L/e4.log 2>&1 &
  $PY scripts/e4/answer.py gimp darktable krita opentoonz --base-url http://localhost:8002/v1 --model GLM-5.3-Flash --tag glm53 >> $L/e4.log 2>&1 &
  wait
  echo "$(date -u +%FT%TZ) E4 finished" >> $L/motivation_rest.log
) &
status "B+C running: E3 judging and E4 questions/answers"
wait
status "done (see e3.log, e4.log)"
