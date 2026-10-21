# Motivation — Gaps in Professional-Software GUI Benchmarks

> **Current agreed plan · 2026-10-21.** Supersedes the skill-audit / paired-intervention plan in
> [motivation-experiments.md](motivation-experiments.md) as the motivation for the benchmark.
> No result below exists yet; every claim is a hypothesis to be tested and reported even if it fails.

## 0. Claims to test

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
  `outcome_described` (desired result, no tool) · `reference_image` (target image given) · `infeasible`.
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
the PSBench judge only receives START and RESULT and is told to accept "subtle but directionally correct" edits;
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
