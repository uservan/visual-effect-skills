#!/bin/bash
#SBATCH --job-name=visual_effect_pilot
#SBATCH --account=xxh584
#SBATCH --partition=batch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=/scratch/pioneer/jobs/wxy320/visual_effect_runtime/pilot_%j.log
set -euo pipefail
cd /home/wxy320/ondemand/program/visual-effect-skills
exec .venv/bin/python scripts/pilot_pipeline.py --gpu-job "${VISUAL_EFFECT_GPU_JOB:?GPU allocation required}"
