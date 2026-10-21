# Recorded open-weight GUI reproduction

The immediate objective is to reproduce a small set of original GUI tasks with
an open-weight executor and inspect failures. No claim of professional-knowledge
deficiency is assumed, and these runs are not the original paper's trajectories.

## Scope and current status

See `runtime/STATUS.md` and the live artifact file
`/scratch/pioneer/jobs/wxy320/save/visual-effect-skills/pipeline_status.json`.
The first pair is **GIMP T1**, A = no skill and B = the original VisualSkill
multimodal Stage 2 skill. This is a harness smoke pair, not a study of missing
professional effect knowledge. T4 is flagged for a verifier issue; see
`task_audit/verifier_findings.md`.

## Environment

- Project Python dependencies: `uv sync`, locked in `uv.lock`.
- Desktop: the official OSWorld Ubuntu QCOW2, launched using a user-space QEMU
  extracted from `happysixd/osworld-docker`, with KVM. The Slurm host needs access
  to `/dev/kvm`. Each boot uses a new temporary disk/firmware overlay.
- Screen: 1280x720 (explicit guest xrandr setup).
- Software observed during smoke check: GIMP 2.10.30.
- Model: `Hcompany/Holo4-27B`, revision in `runtime/model_manifest.json`.
- Inference: a separate scratch venv with Transformers 5.6.2 and the existing
  CUDA PyTorch. BF16 if GPU memory >=65 GiB, otherwise NF4. Precision is recorded
  and identical for A/B; neither configuration is asserted equivalent to Claude.
- The published Claude runner is replaced by a restricted GUI-tool client and
  an HTTP model server. This is a declared reproduction adaptation.
- No Claude/API inference is used by these scripts.

Re-downloadable resources live outside save:
`/scratch/pioneer/jobs/wxy320/visual_effect_runtime/`.
Large episode artifacts live in:
`/scratch/pioneer/jobs/wxy320/save/visual-effect-skills/`.

## Run flow

1. Submit the one-GPU A100 script under
   `/home/wxy320/ondemand/program/LCTMerge/occupy/forai/test2.sh` and record Job ID.
2. Prepare all runtime files first; GPU availability does not imply dependencies
   or desktop functionality are ready.
3. Submit the CPU pilot job once, tied to the existing GPU allocation:

```bash
sbatch --dependency=after:GPU_JOB_ID --kill-on-invalid-dep=yes \
  --export=ALL,VISUAL_EFFECT_GPU_JOB=GPU_JOB_ID scripts/pilot_pipeline.sbatch
```

The pipeline waits for prepared files, starts inference inside the existing GPU
allocation with `srun`, boots a fresh desktop for A and B, records trajectories,
scores with pinned original GIMP metrics, and regenerates the local viewer. It
stops on invalid runs and records the infrastructure error separately from a
completed task failure. On exit it releases only the explicitly passed GPU
reservation; it does not cancel unrelated jobs.

No additional GPU requests are automatically submitted. Check Slurm state and
`pipeline_status.json` before resubmission to avoid duplicate runs.

## Inspect recorded evidence

Each actual model run saves task/config, trace.jsonl, model-visible replies,
original-resolution before/after screenshots, screen differences, result.json,
verifier files and final state. B additionally saves the index and hashes of
loaded original skill guides/figures. Raw model reasoning fields are not stored.
Screen differences are UI diagnostic aids, not rendered-document quality scores.

```bash
uv run python scripts/build_viewer.py
cd /scratch/pioneer/jobs/wxy320/save/visual-effect-skills
python3 -m http.server 8765 --bind 127.0.0.1
```

Open `index.html` locally or through an SSH tunnel. The basic static viewer
selects two recorded runs and shows step screenshots/actions side by side,
plus outcomes and JSON report export. It has no remote UI dependency.
It is an initial viewer, not yet the full final study's filtering/annotation UI.

`smoke_fixture/`, `desktop_smoke_initial.png`, and `verifier_audit/` are explicitly
**not model episodes** and are not included in the viewer's run score table.

## Validation

```bash
uv run python -m unittest discover -s tests -v
uv run python scripts/audit_t4_verifier.py
```

Do not infer model success from successful imports, environment boot, or a
hand-coded controller smoke test. Model/GPU execution remains unverified until
an actual episode and verifier output exist.
