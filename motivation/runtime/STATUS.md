# Reproduction status

Updated 2026-10-21. No valid model episode or benchmark result has been produced yet.

## Validated preparation

- Official OSWorld Ubuntu QCOW2 downloaded and extracted; user-space QEMU 9.1
  runs with KVM without Docker. Singularity's user namespace prevented KVM, so
  the extracted QEMU binary is launched directly with its own dynamic loader.
- GIMP 2.10.30 launched with the original task fixture; 1280x720 resolution and
  deterministic center cursor verified. GUI controller click changed the screen.
- Corrected empty-GIMP window readiness detection. Untouched T1 config verifier
  smoke checks ran separately from all model results.
- Holo4-27B BF16 snapshot is complete at the pinned revision in model_manifest.json.
- CPU import preflight passed: Torch 2.7.0+cu126, Transformers 5.6.2, Qwen3_5
  model classes/configuration, FastAPI, Uvicorn and BitsAndBytes. GPU execution
  is not implied by these checks.
- Five controller/tool parsing contract tests pass. Static trajectory viewer
  generated; currently no actual model episode rows.

## Jobs

- GPU allocation **4084039** (one A100 on aisct01): ran 15:48–15:54 and was
  released by the pilot on failure. No GPU allocation is currently held.
- Automatic pilot CPU job **4084568**: FAILED at 15:54. The first episode
  (A, gimp_T1) is `invalid`: the model server returned HTTP 500 because
  `processor.apply_chat_template` received a message whose `content` was a
  plain string (`TypeError: string indices must be integers` in
  `scripts/transformers_server.py`). String content must be wrapped as
  `[{"type": "text", "text": ...}]`. Not yet fixed or rerun; B was not run.
- Preparation CPU job **4084377**: explicitly released after setup/smoke checks.
- User's CPU entry job is untouched.

## Experiment scope and caveats

First pair: GIMP T1, A = no skill, B = original VisualSkill multimodal Stage 2.
This is a harness smoke pair, not a test of the professional-knowledge hypothesis.
Model precision will be BF16 on >=65 GiB GPU memory and NF4 otherwise, held
fixed across the pair and recorded in each config.

GIMP T4 has a verified sanity concern: a perfect mirror of the provided asset
fails the conjunction of its two original metrics. See
../task_audit/verifier_findings.md. No original verifier is silently changed.

Live status/results:
`/scratch/pioneer/jobs/wxy320/save/visual-effect-skills/pipeline_status.json`

Storage:
- Code/metadata: this project.
- Re-downloadable VM/container/model/runtime: /scratch/pioneer/jobs/wxy320/visual_effect_runtime
- Screenshots, verifier fixtures, episodes/viewer: /scratch/pioneer/jobs/wxy320/save/visual-effect-skills
