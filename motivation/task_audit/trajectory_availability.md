# Trajectory availability check — 2026-10-21

## Finding

No downloadable full original evaluation-trajectory corpus was located in the checked sources. This is an availability finding, not proof that no public archive exists.

## Sources checked

- VisualSkills repository at 582e6ccb370b291bd31f3688629378e385e3731a: tracked tree, README, evaluation runner READMEs, .gitignore, GitHub releases and issues/PR listing.
- OSExpert repository at ed8673d900293967388615b95301596eb4a1cc15: tracked tree and README; GitHub releases.
- https://huggingface.co/datasets/Rushi2002/Expert recursive file listing: task inputs and golden/reference outputs; no stepwise trajectory corpus found.
- Web searches for VisualSkill/OSExpert trajectory downloads.

Both GitHub release APIs returned empty arrays. VisualSkills ignores generated workspaces; evaluation screenshots and event logs are not tracked in this checkout. Skill illustration screenshots are not complete evaluation episodes. Reference outputs are not trajectories.

## What the VisualSkills runner can record

CUA-World runner README documents result.json, score.txt, prompt.txt, screenshots/step_NNN.png, claude_output.txt (stream JSON events), and container_stdout.txt. OSExpert runner documents meta.json, result.txt, prompt.txt, screenshots, final screenshot, recording.mp4 and runtime logs.

The supplied Streamlit viewer reads evaluation workspaces through gcloud compute ssh by default. Having its source does not grant access to the authors' VM or results.

## Acquisition options

1. Obtain the original archived workspaces from the authors (external contact requires explicit user authorization). Request matched no-skill / original-skill conditions, screenshots, action and skill-loading events, task IDs, scores/verifier feedback, model/configuration versions and initial-state provenance. Preserve failures and successes.
2. Reproduce selected tasks with published code and skills, recording new trajectories. These are our reproduction results, not the original paper's trajectories; public original failures cannot be inferred from them. Check environment/virtualization feasibility and executor access before launching.
3. Paper case studies and skill screenshots support limited qualitative inspection, not full failure-distribution analysis.

No authors have been contacted, no paid inference launched, and no original full evaluation trajectories downloaded.
