# Motivation — Gaps in Professional-Software GUI Benchmarks

> **Current agreed plan · revised 2026-10-22.** Supersedes the skill-audit / paired-intervention plan in
> [motivation-experiments.md](motivation-experiments.md). Priority: build the benchmark first; a method is decided later
> from what the benchmark shows. Every claim is a hypothesis to be tested and reported even if it fails.

## Revised framing (2026-10-22) — read this first

The G1/G2/G3 split below proved hard to operationalise: "imperative vs outcome-described" has no clear boundary, and a
first LLM pre-label (guidelines v0.1/v0.2) over-counted outcome tasks (e.g. "Exposure +1.0 → Midtones green -20" was
labelled outcome). Those pre-labels are **withdrawn**. The claim is now:

> Existing professional-software benchmarks contain **explicit** tasks, which can be scored but only test operating the
> UI (and models score high on them), and **vague** tasks, which test judgement but cannot be scored reliably (models
> either fail or are judged by direction only). Professional software also needs knowledge that models lack, so manuals
> belong in the environment.

| # | Experiment | Question | Method | Status |
|---|---|---|---|---|
| E1 | Task split | Share of explicit vs vague tasks per benchmark | Per clause: is a real command named (incl. control names like Brightness, presets) and are values exact or not needed? Task class derived by rule: **explicit** if every edit clause has both; else **vague_missing_values** or **vague_missing_tool**. Three open models vote (Qwen3.5-397B, GLM-5.3, DeepSeek-V4.1-Flash); 2–1 splits spot-checked, 3-way splits adjudicated by a human. Script `scripts/benchmark_audit/split_tasks.py`. | Pilot 30 tasks: Qwen–GLM agreement 87 %. Full run in progress |
| E1b | Published scores by class | Do models score high on explicit and low (or suspiciously high) on vague tasks? | Join E1 classes with published per-task results (OSWorld-Verified trajectories: 99 agent runs; others if released) | **PSBench paper** gives the cleanest evidence: success falls easy→hard for every agent (Agent S3 69.9→18.1 %), and image-generation models that never open Photoshop pass 100 % easy/medium and 72–90 % hard under the same evaluation (see `code_findings.md` §7–9). OSWorld GIMP (94 agents) is too small and mostly UI-operation tasks to separate classes |
| E2 | Evaluator audit | How are vague tasks scored? | Evaluator type from code, cross-tabbed with E1 | Done: `code_findings.md`, `evaluator_labels.csv` |
| E3 | Judge stress test (was M3) | Can the published judge separate correct from wrong results on vague tasks? | 30 vague + 30 explicit PSBench tasks; candidates END, identity, ×0.5, ×3, opposite, naive global; PSBench prompt verbatim; judges Qwen3.5 and GLM-5.3 (open models only); human acceptability ratings on a subset. **Control**: the judge should work on explicit tasks; if it fails only on vague ones, vagueness is the cause. | Candidates built for 60 hard tasks; resample by E1 class |
| E4 | Knowledge probe (was M2) | Do models know these apps, and do manuals help? | Q1 location / Q2 function / Q3 effect / Q4 goal→tool from official manuals; closed vs open book. Exposure contrast: **GIMP = high exposure; darktable, OpenToonz = low exposure** (Krita in between). Photoshop only if the user supplies Adobe's PDF guide (helpx.adobe.com blocks automated access; not circumvented). Questions must quote the manual verbatim (checked by script); two generator models alternate and results are split by generator; human verification before counting. Scripts `scripts/e4/` | Manuals: GIMP 2.10 (273 units), Krita 5.3 (93), OpenToonz (118 sections), darktable 5.6 refetching |

Dropped: skill-content audit (the paper's point is that manuals belong in the environment, which E4 tests).
Falsifiers: E3 judges reject wrong results on vague tasks as well as on explicit ones; humans agree on a narrow
acceptable range for vague instructions (then a better judge, not a determinate benchmark, is the fix); vague tasks
are rare.

## 0. Claims to test (original, superseded by the section above)

Existing GUI benchmarks for professional software may not measure what real professional use requires.
We test three falsifiable gaps:

| Gap | Claim | Evidence we need |
|---|---|---|
| **G1 Imperative tasks** | Most tasks state the tool and/or parameter values; success mostly requires finding and operating controls, not professional judgment. | Task-form audit across benchmarks (M1). |
| **G2 Unfamiliar software is ignored** | Benchmarks give agents no manual/documentation and implicitly assume models already know the software; models may have little knowledge of less popular professional apps. | Documentation audit (M1) + software-knowledge probe (M2). |
| **G3 Hard tasks are not evaluated to a standard** | Outcome-described hard tasks are judged by lenient, direction-only VLM rubrics that cannot separate a correct professional edit from a naive one. | Evaluator stress test on PSBench (M3). |

Stopping rule: if M1 shows outcome-described, knowledge-demanding tasks are already common **and** M3 shows the
existing judges reliably reject naive edits, the benchmark motivation must be revised.

## 1. M1 — Task-form and documentation audit

### 1.1 Population (pin every source)

| Benchmark | Source | Scope |
|---|---|---|
| PSBench (ICML 2026) | HF `zyn1216/PSBench` @ `929d0710eb7c86a988f8a69a74619052b60ac293`; GitHub `zyn1216/PSBench` @ `5a9a91119bc1fbbc03a4c4a86498741846f0fad1` | All 600 tasks |
| OSWorld GIMP | `OSWorld/evaluation_examples/examples/gimp` (local checkout; record SHA) | All 26 tasks |
| OSExpert-Eval | `Lumos-Jiateng/OSExpert` @ `ed8673d900293967388615b95301596eb4a1cc15` | GIMP long-horizon + fine-grained visual tasks |
| CUA-World (VisualSkill eval) | `XMHZZ2018/gym-anything` @ `f667d6b277c8d8b8d35c91f817213dad91cfc552` | 83 OpenToonz definitions; mark the 21 VisualSkill-selected ones |
| ProSoftArena, CutVerse | Papers/project pages; task data only if publicly released | Published examples and statistics only; state this limitation |

Unit: one task. Report denominators per benchmark; never pool benchmarks into a single "population".

### 1.2 Labels (multi-field)

- **Instruction form:** `procedural_explicit` (tool + parameters/steps) · `tool_named` (tool, no parameters) ·
  `attribute_direction` (one basic attribute + direction, e.g. "slightly brighter"; no tool) ·
  `outcome_described` (desired result, no tool) · `reference_image` (target image given) · `infeasible` · `non_visual`.
  Labelled per component; the task takes its most demanding component. Full rules:
  [annotation_guidelines.md](../motivation/benchmark_audit/annotation_guidelines.md).
- **Required knowledge:** K1 UI location · K2 function/procedure · K3 effect of parameters · K4 state-conditional effect ·
  K5 goal-to-action (definitions as in motivation-experiments.md §1.2).
- **Initial state:** flat image · stateful project (layers/masks/history/scene).
- **Evaluator type:** exact state/file check · metric vs reference · direction-only check · VLM rubric · milestone QA.
- **Documentation given to agent:** none · action-API notes only · manual/knowledge cards · skills.

### 1.3 Protocol

1. Write `motivation/benchmark_audit/annotation_guidelines.md` with examples and edge cases first.
2. An LLM may pre-label all tasks; its labels are proposals only.
3. Two humans independently label a stratified sample (≥20% per benchmark, ≥30 tasks each); report Cohen's κ;
   adjudicate; correct the rest if pre-label error rate is material.
4. Evaluator type and documentation are labelled from **code**, not paper text, where code exists.

Known so far (unadjudicated, heuristic): PSBench hard tier 175/197 instructions name no tool and no value;
the PSBench judge only receives START and RESULT and is told to accept "subtle but directionally correct" edits
(the code also defines two looser `judge_policy` modes, but no rubric in the pinned HF data uses them — all 600 are `default`);
CUA-World `underwater_wave_distortion_fx` ships an instruction with leaked LLM drafting text and is truncated;
PSBench and CutVerse evaluation code pass no documentation to the agent (CutVerse's `knowledge_context` is
hard-coded to `""`); ProSoftArena reports a ChemDraw knowledge-card ablation only.

### 1.4 Outputs

`motivation/benchmark_audit/{task_inventory.csv, annotations.csv, agreement.json, summary.md}` and
**Figure 1**: share of instruction forms and required-knowledge levels per benchmark and difficulty tier.

## 2. M2 — Software-knowledge probe

Question: do models know professional software well enough that benchmarks can ignore documentation?

### 2.1 Software

Photoshop (high-exposure reference) and the open-source targets of our benchmark: GIMP, darktable, Krita,
Inkscape, Blender. Pin the manual version for each (e.g. GIMP 3.0 manual, darktable 5.x user manual).

### 2.2 Questions

Generated from official manual passages; the gold answer must be quotable from the cited passage.

| Type | Example (GIMP) |
|---|---|
| Q1 Location | Which menu contains Curves? |
| Q2 Function | What does the Curves tool change? |
| Q3 Effect | Raising the curve's midpoint does what to midtones and to highlights? |
| Q4 Goal→tool | To brighten shadows without clipping highlights, which tool/adjustment is appropriate and why? |

- 40–60 questions per app, balanced across Q1–Q4; multiple-choice (4 options) for automatic scoring plus a
  short-answer subset scored by rubric.
- An LLM may draft questions; a human verifies every gold answer against the manual. Discard ambiguous items.
- Record manual URL/version/section per item.

### 2.3 Conditions and models

- **Closed-book** vs **open-book** (the cited manual section supplied in context) — shows documentation helps.
- Executors: the open-weight models planned for the benchmark (e.g. Holo4 checkpoint actually available,
  a Qwen-VL model). Closed models only if API access is confirmed; label them separately.

### 2.4 Outputs

Accuracy per app × question type × condition, with 95% CIs. **Figure 2**: knowledge accuracy by app.
Expected (not assumed): high on Photoshop, lower on less-exposed apps, and Q3/Q4 < Q1/Q2.
Contamination caveat: manuals are public and may be in training data; report it.

## 3. M3 — Evaluator stress test (PSBench hard tier)

Question: does the published judge distinguish a correct professional edit from naive or wrong edits?

### 3.1 Sample

60 hard tasks, stratified by `type` (color grading, retouching, compositing, glow/effects, typography).
Exclude tasks whose START or END cannot be loaded.

### 3.2 Candidates per task

| Candidate | Construction | Expected verdict |
|---|---|---|
| END (positive) | Author's reference result | PASS |
| Identity | START unchanged | FAIL |
| Naive global | One global adjustment in the requested direction (e.g. warm shift + contrast) | FAIL for multi-attribute tasks |
| Over-strength | Requested direction ×3 strength, clipped | FAIL |
| Opposite | Requested direction reversed | FAIL |
| Subject damage | Correct global edit + visible damage inside the subject mask (SAM mask, human-checked) | FAIL when the task has a preservation clause |

Candidates are produced by scripts with fixed seeds; save all images and scripts.

### 3.3 Judge

Run the PSBench judge prompt **verbatim** (`photoshop_evaluators.py` at the pinned SHA) with its default
`gpt-5.4` if API access exists. Otherwise use an open VLM with the identical prompt and label results as
"PSBench rubric, substitute judge". Repeat each judgment 3× and report variance.

### 3.4 Outputs

Pass rate per candidate type; discrimination = PASS(END) − PASS(negative). **Figure 3**: pass rates.
Also report a reference-based score (ΔE/SSIM to END) for the same candidates to show what a standard
reference metric would decide. Human spot-check 50 judgments.

## 4. Deliverables and order

1. M1 audit (CPU only) → Figure 1.
2. M2 probe (one A100) → Figure 2.
3. M3 stress test (API or one A100) → Figure 3.
4. `motivation/benchmark_audit/motivation_summary.md`: findings per gap, including contrary evidence, and go/no-go.

Large artifacts go to `/scratch/pioneer/jobs/wxy320/save/visual-effect-skills/motivation_v2/`; commit
code, configs, manifests and small CSVs only.
