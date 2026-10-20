# Motivation Experiments — Visual Effect Skills

> **Status: Research protocol, not completed experiments.** This document is intended for a coding/research agent. Do not claim results before running the studies.

## Research hypothesis

Strong professional GUI agents may know how to operate controls yet fail to predict **how an operation changes rendered content under the current document state**. We first test whether missing effect knowledge, rather than GUI grounding or long-horizon execution, explains an important fraction of failures.

**Research questions**
1. How prevalent are effect-dependent and state-dependent tasks in established professional GUI benchmarks?
2. For strong open-weight agents, which failures arise from effect understanding versus tool selection, grounding/execution, planning, or verification?
3. Does providing correct, *general* effect knowledge rescue failures without revealing per-task solutions?

**Go/no-go:** Stop or revise the hypothesis if effect-dependent tasks are rare or effect-knowledge interventions do not substantially improve the matched baseline.

## Models (open weights, no Claude API)

| Role | Candidate | Caveat |
| --- | --- | --- |
| Primary GUI executor | Holo4-35B-A3B | Verify checkpoint, license, action interface, and target software support |
| Strong multimodal reasoning | Qwen3.5-397B-A17B | Use as second-model replication; test GUI harness compatibility |
| Optional replication | Qwen3-VL-235B-A22B | Cross-model robustness |

Check precise checkpoint identifiers and access before spending compute. Hold a model and its harness **fixed across all knowledge conditions**. A model's general OSWorld score does not guarantee GIMP expertise.

## Benchmarks and task inventory

Sources:
- [OSExpert / OSExpert-Eval](https://arxiv.org/abs/2603.07978): audit all tasks and prioritize relevant GIMP tasks.
- [VisualSkill](https://arxiv.org/abs/2606.18448) and its CUA-World evaluation: examine GIMP, OpenToonz, and other genuinely visual editing apps.

First retrieve original task manifests, evaluators and environment configurations. Do **not** assume that either benchmark contains enough effect-dependent tasks. Record the entire audited denominator, including excluded tasks and reasons. If coverage is too small, introduce a separately labeled, controlled diagnostic set of document-state variants; never pass these off as standard benchmark tasks.

**Per-task labels:**
- `effect_dependent`: target requires choosing an operation according to its visual consequences; explicitly supplied parameter values generally do not qualify.
- `state_dependent`: the relevant effect changes with current layers, image contents, masks, opacity or other document settings.
- `objective_verifier`: verifier available? specify rendered-image, exact state, region constraint or reviewer rubric.
- `potential_confounders`: grounding, action execution, planning, ambiguous request, verification.

Have independent annotators label a representative sample; document ambiguous cases and disagreements.

## Experiment A — Prevalence

Create **Table 1**: benchmark × application × total audited × effect-dependent × state-dependent × intersection × verifiable. Report counts and ratios with denominators. Do not cherry-pick only observed failures.

## Experiment B — Paired knowledge intervention

For the **same tasks and the same executor**, run:

| Condition | Information | Why |
| --- | --- | --- |
| C0: No Skill | Task + original GUI observation | Original capability |
| C1: Operational Text Skill | Tool semantics, entry points and procedure | Procedural knowledge |
| C2: VisualSkill-style | C1 plus screenshots and interface examples | Strong multimodal-skill comparison |
| C3: C2 + Effect Oracle | Validated, general state→action→visual-effect principles | Is missing effect knowledge limiting? |
| C4: C2 + Grounding Oracle | Tool/control location only, not effect choice or final parameter | Is GUI grounding the bottleneck? |

Run a 10–20 task **viability pilot** on Holo4 before scaling. Suggested order: C0/C2/C3, then C1/C4, then cross-model replication.

**Crucial controls:** identical initial document, software version, model, prompts excluding the knowledge supplement, screenshot interface, action budget, retries, token logging, and verifier. Reset between runs. Report differences in context length and image count. If possible, prepare oracle statements without seeing the target's failed trace.

**Oracle leakage prohibition:** General statement such as “Multiply depends on base/blend colors and opacity” is allowed. “For task 17 use Multiply at 63%” or a provided exact target image/answer is forbidden. Grounding oracle may locate an interface control but cannot pick the tool or parameters that solve the task.

## Experiment C — Fixed-grounding effect diagnosis

End-to-end GUI trajectories mix effects with navigation. Create a second, separately reported **diagnostic** setup that gives the agent the correct preconfigured document, layer selection, and bounded legal candidate actions.

Evaluate:
- **Forward effect understanding:** given state and candidate action, predict the rendered change.
- **Inverse effect selection:** given state and a target visual change, select an action/parameters; execute and score the result.

Ground truth should come from the **actual software renderer and document state**, not only a VLM judge. Where meaningful and aligned, use MAE/SSIM; additionally evaluate target-region improvement and unintended changes outside it. Do not report fixed-grounding accuracy as a standard benchmark GUI success rate.

## Failure attribution

For each failure, annotate evidence from trajectory and before/after render. Multiple tags may apply:
1. Tool selection failure.
2. Effect direction, magnitude, or state-dependence misunderstanding.
3. Grounding / action execution failure.
4. Multi-step planning failure.
5. Verification / termination failure.
6. Ambiguous goal, verifier issue, or other.

Record `first_error_step`, `failure_tags`, and `evidence_paths`. Do not treat a model's self-explanation as proof of causation. Include successful cases and regressions.

## Core measurements

- Standard task success rate for C0–C4, using upstream verifiers where applicable.
- **Effect rescue rate** = #(C2 fails, C3 succeeds) / #(C2 fails).
- **Regression rate** = #(C2 succeeds, C3 fails) / #(C2 succeeds).
- **Net effect gain** = success(C3) − success(C2).
- Matched grounding rescue C2→C4.
- Tool-effect forward prediction and inverse selection accuracy on the diagnostic set.
- Paired confidence intervals over task IDs and stratification by effect-dependence, software and model.
- Tool calls, tokens, runtime, screenshots, inference/exploration costs.

**Paper outputs:** Table 1 (task prevalence), Figure 1 (trace-based failure taxonomy), Figure 2 (paired oracle-rescue transition and effect-vs-grounding contrast). If sample size is tiny, report task-level results and uncertainty rather than broad claims.

## Required files and trace layout

```text
motivation/
  task_manifest.csv
  annotation_guidelines.md
  oracles/
    operational/
    effect/
    grounding/
  runs/<model>/<condition>/<task_id>/<run_id>/
    config.json
    trace.jsonl
    final_state.json
    result.json
  analysis/
    task_composition.csv
    failure_annotations.csv
    paired_outcomes.csv
    motivation_summary.md
```

At minimum `result.json` must contain: task_id, model_id/checkpoint, condition, software_version, seed, success, verifier, failure_tags, first_error_step, actions, tokens, runtime, evidence_paths.

## Execution checklist

- [ ] Verify real checkpoint/model availability and target GUI-harness interfaces.
- [ ] Obtain OSExpert-Eval and CUA-World task manifests, setups and verifiers; record source commit SHAs.
- [ ] Audit task composition **before** filtering on agent outcome.
- [ ] Run 10–20 task Holo4 viability pilot.
- [ ] Prepare and review operational, multimodal, effect and grounding materials.
- [ ] Run matched C0/C2/C3 followed by C1/C4.
- [ ] Perform fixed-grounding diagnostics and trace-based failure attribution.
- [ ] Reproduce key comparisons with Qwen3.5; optional Qwen3-VL replication.
- [ ] Produce figures, confidence intervals, examples, failure analyses, and a falsifiable go/no-go recommendation.

**Do not implement the new Active Effect Explorer until this motivation study establishes a real effect-knowledge gap.**


## Mandatory visual trajectory capture and human inspection

**Every experiment run must be inspectable after the fact.** Do not report aggregate success rates without retaining enough evidence to independently inspect a task and identify exactly where execution or effect reasoning went wrong.

### Capture requirements (all conditions C0–C4, all evaluated models)

- **Initial state:** task instruction, task ID, software/version, environment reset identifier, starting screenshot, and available document/layer metadata (when permitted).
- **For every agent step:** timestamp, monotonically increasing step ID, full-resolution **observation screenshot before the action**, selected action with parameters/coordinates, relevant model/tool response and tool result, and **screenshot after the action**. Maintain a canonical `trace.jsonl` referencing the saved images.
- **Effect edits:** additionally save **before/after render crops or full rendered documents**, target region/mask if available, and a computed difference image/heatmap (visual aids do not replace raw screenshots).
- **Final state:** final screenshot, actual saved output file where possible, verifier result and detailed reason, task completion status, failed-step evidence, cost/runtime statistics.
- **Model decisions:** save raw available model replies and structured actions. Preserve decision explanations *only if the model outputs them in its normal response*; do not request or record private internal reasoning/chain-of-thought.
- **Repeatability:** store model checkpoint, sampling parameters, prompt/skill/oracle content and hashes, harness commit SHA, screen resolution, OS/software versions, seed, action budget and run ID. Any screenshot redaction must be explicit and consistent.

### Storage layout (extend the required run layout)

```text
motivation/runs/<model>/<condition>/<task_id>/<run_id>/
  config.json
  task.json
  trace.jsonl
  screenshots/
    step_000_before.png
    step_000_after.png
    step_001_before.png
    step_001_after.png
    ...
    final.png
  effects/
    edit_000_before.png
    edit_000_after.png
    edit_000_diff.png
  model_responses.jsonl
  result.json
  final_state.json
  replay.html                      # or link to a generated central viewer
```

### Viewer deliverable (required, not optional)

Implement a **local static HTML trajectory viewer** (no remote service dependency) that works directly from recorded traces, enabling the researcher to:
1. Filter runs by model, condition, task, and success/failure; display a summary table.
2. Select a task and **compare C2 (VisualSkill) vs C3 (Effect Oracle) side by side**, beginning at the same initial document state.
3. Step through actions with *previous / next* controls or a slider; see **before screenshot, action text/coordinates, after screenshot**, timestamp and verifier feedback.
4. Toggle **before / after / difference** for effect edits; open originals at full resolution.
5. Jump to the annotated **first failure step** and show evidence and failure tags.
6. Export a concise task report with screenshot paths and outcome, suitable for assembling paper case studies.

The viewer can be generated by Python into a self-contained static site referencing local assets. It must function without needing to rerun the model. Avoid embedding all full-resolution images as base64 into one giant HTML file; use relative links. A short `motivation/README.md` must explain how to open the viewer (including a local static HTTP server command if required).

### Protocol integrity and storage policy

- Record **all runs** (including invalid runs, failed executions and regressions), not just successful cases.
- Keep raw traces unchanged; generate summaries and failure annotations in separate files so audit history is preserved.
- Sample or compress only copies for visualization. Keep original-resolution frames for actions, or explicitly document any unavoidable loss of fidelity.
- Avoid capturing personal content or secrets in test environments. Redact credentials and sensitive information before sharing artifacts.
- **Do not commit large screenshots, videos, model logs or benchmark assets to Git by default.** Store under a gitignored artifact directory or external experiment storage; commit *viewer source code, schemas, small anonymized example traces and metadata manifests*. For larger runs, save a manifest indicating where artifacts live and how to retrieve them.
- Optional screen recordings are supplementary. **Step-aligned screenshots + action logs are mandatory** and are sufficient for deterministic step-by-step replay.

### Acceptance criteria for the implementation agent

Before running large experiments, demonstrate one completed test run with: (a) all step screenshots and actions saved; (b) final verifier result and failure reason; (c) local HTML viewer opening that run; and (d) a side-by-side C2/C3 comparison once both conditions have been run.

**The researcher must be able to inspect and replay every claimed result visually without launching the model again.**
