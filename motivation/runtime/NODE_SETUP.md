# Node setup (motivation v2, 8×H200)

Rule: models and the Python env are **read from node-local NVMe only**, never loaded from `/shared`.
`/shared` holds the single durable copy of sources, models and results; node-local storage is lost
when the machine goes away, so redo the steps below after every restart or on a new node.

| What | Durable copy (`/shared/.../jwanyang/visual_effect_data/`) | Node-local (`$VE_LOCAL`) |
|---|---|---|
| Benchmark sources at pinned SHAs | `sources/` | — (read directly; small files) |
| Model weights | `models/<name>` | `/tmp/instance_storage/visual_effect_models/models/<name>` |
| Python env (vLLM 0.31.0, torch 2.13.0+cu130) | lock file in repo: `motivation/runtime/vllm_env.lock.txt` | `/tmp/instance_storage/visual_effect_models/envs/vllm` |
| Results, logs | `m3/`, `logs/`, repo `motivation/` | — |

## After every (re)start

```bash
cd /shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual-effect-skills
# fresh node only (the directory is root-owned):
sudo mkdir -p /tmp/instance_storage/visual_effect_models && sudo chown $USER /tmp/instance_storage/visual_effect_models
scripts/setup_node.sh                      # env from lock + copy all models (skips what is already there)
scripts/setup_node.sh Qwen3.5-397B-A17B-FP8 sam2.1-hiera-large   # or only the models you need
```

Serve (each model on its own GPUs; logs go to `/shared/.../visual_effect_data/logs`):

```bash
L=/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data/logs
setsid nohup scripts/serve_vllm.sh Qwen3.5-397B-A17B-FP8 8001 0,1,2,3 --reasoning-parser qwen3 > $L/vllm_qwen35.log 2>&1 &
setsid nohup scripts/serve_vllm.sh GLM-5.3-Flash 8002 4,5,6,7 > $L/vllm_glm53.log 2>&1 &
curl -s localhost:8001/health && curl -s localhost:8002/health
```

Experiment scripts run with `/tmp/instance_storage/visual_effect_models/envs/vllm/bin/python` and are
resumable: re-running the same command continues from the records already written.

## Changing the env

Install/upgrade in the local env, re-freeze, commit the lock, and rebuild elsewhere with `setup_env.sh`:

```bash
E=/tmp/instance_storage/visual_effect_models/envs/vllm
VIRTUAL_ENV=$E uv pip install <pkg>==<version>
VIRTUAL_ENV=$E uv pip freeze > motivation/runtime/vllm_env.lock.txt
```
