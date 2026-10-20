# Motivation study: harness, runs and viewer

Implementation of [docs/motivation-experiments.md](../docs/motivation-experiments.md). Status: harness under
construction; no experimental results yet.

## Layout

```text
motivation/
  configs/apps/<app>.yaml        knowledge material per application (skills, oracle notes)
  configs/batches/<batch>.yaml   one batch = one model x tasks x conditions x seeds
  oracles/{effect,grounding}/    general oracle notes (C3, C4); drafts until reviewed
  runs/<model>/<condition>/<task_id>/<run_id>/   raw run records (git-ignored)
  analysis/                      task_composition.csv, failure_annotations.csv, paired_outcomes.csv, summary
  viewer/                        generated static viewer (git-ignored; rebuild any time)
  ctl/                           job outcome files and completion markers of the requeue loop (git-ignored)
```

The harness code is the `ves` package at the repository root (`ves/agent.py` is the agent loop).

## Conditions

| id | knowledge given to the agent |
|----|------------------------------|
| C0 | none |
| C1 | VisualSkill text skill (figures verbalised), loaded with `load_topic` |
| C2 | VisualSkill multimodal skill (text and figures), loaded with `load_topic` |
| C3 | C2 + general effect notes (`oracles/effect/<app>.md`) in the first message |
| C4 | C2 + general control-location notes (`oracles/grounding/<app>.md`) in the first message |

Model, prompts (apart from the knowledge blocks), screenshot size, tools, step budget, sampling and verifier are
identical across conditions. Every run directory contains `config.json` (model checkpoint and revision, sampling,
knowledge hashes, harness hash, budget, host), `task.json`, `trace.jsonl` (one event per step with before / after
screenshots and the action), `model_responses.jsonl` (model replies and tool calls; no hidden reasoning is stored),
`screenshots/`, `effects/` (crops and difference images of steps that changed the screen), `final_state/` (files
copied out of the desktop after the episode), `final_state.json` and `result.json`.

## Viewing runs

Build the viewer from the recorded runs (no model is run again):

```bash
python -m ves.viewer.build      # writes motivation/viewer/
```

Then open `motivation/viewer/index.html` in a browser. It works directly from disk (`file://`) because run data
is loaded with script tags and images by relative paths; keep `viewer/` and `runs/` side by side. If a browser
blocks local files, serve the folder instead and open http://localhost:8000/viewer/ :

```bash
cd motivation && python -m http.server 8000
```

The viewer lists runs with filters (model, condition, task, outcome), shows a task x condition outcome matrix,
opens any two runs side by side (button "C2 | C3" in the matrix), steps through actions with before / after /
difference images and the model's reply for each step, jumps to the annotated first error step, and exports a
markdown report for a task.

Failure annotations live in `analysis/failure_annotations.csv` with the columns
`model,condition,task_id,run_id,first_error_step,failure_tags,evidence_paths,notes,annotator`
(`failure_tags` separated by `;`). Rebuild the viewer after editing it.
