# GIMP T4 verifier sanity finding

Checked 2026-10-21. This is a verifier unit check, not a model run.

The original OSExpert long-horizon GIMP T4 instruction requests a horizontal mirror and export. Its evaluator requires both `check_file_exists_and_structure_sim(prediction, original)` and `check_image_mirror(prediction, original)` to pass (`conj: and`).

For the provided original asset, an exact left-right reflection created solely as a verifier fixture gives:

| Metric | Exact mirror |
|---|---:|
| check_file_exists_and_structure_sim | 0 |
| check_image_mirror | 1 |
| Required conjunction | false |

This holds for both the VisualSkill-pinned OSWorld metric file (commit `2d17022886881e12a114a3be45d2315cf6d8416f`, file SHA256 `c0aeea13928927a97e06a15088d6049cef7a8dfdc9251203badbb6f17f931346`) and the checked current upstream file. This shows that a semantically correct reflection can fail the combined verifier for this asset; it does not prove every task is invalid, nor that the paper's particular run failed for this reason. The verifier inputs use the source asset URL in the task definition. Assets and JSON evidence are under `/scratch/pioneer/jobs/wxy320/save/visual-effect-skills/verifier_audit/`.

Reproduce:

```bash
uv run python scripts/audit_t4_verifier.py
```

Action: use GIMP T1 for the initial A/B harness smoke pair. Keep T4 as flagged verifier diagnostics, and do not silently modify its original score or count it as an effect-knowledge failure.

## Task-version check

All six GIMP task JSON objects in VisualSkill's pinned OSWorld commit were
retrieved and compared against the checked OSExpert repository: all six are
identical as parsed JSON. The T4 concern therefore also applies to that pinned
task definition, not just to a newer task revision.

## Additional static concern: GIMP T6

T6's evaluator postconfig types the export base name `edited_darker`, but its
result getter looks for `/home/user/Desktop/revise_dog_with_background.png`.
This is a static path inconsistency in the task definition, not yet an executed
end-to-end verifier finding. A run could still produce the expected path by
other means, so do not describe it as universally impossible or attribute the
paper's failure to it without trajectories.
