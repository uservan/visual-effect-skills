#!/bin/bash
#SBATCH --job-name=visual_effect_desktop
#SBATCH --account=xxh584
#SBATCH --partition=batch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=/scratch/pioneer/jobs/wxy320/visual_effect_runtime/desktop_%j.log
set -euo pipefail
hostname
python3 - <<'PY'
import os,fcntl
fd=os.open('/dev/kvm',os.O_RDWR)
print('KVM_API_VERSION',fcntl.ioctl(fd,0xAE00,0),flush=True)
os.close(fd)
PY
# A single allocated CPU host is retained for the desktop smoke test.
sleep infinity
