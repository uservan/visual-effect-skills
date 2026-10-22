# M1 Annotation Guidelines — Task Form, Required Knowledge, Evaluator

> Version 0.2 · 2026-10-22 · Draft, to be frozen before the double-labelled sample is drawn.
> Changes from v0.1 ([annotation_guidelines_v0.1.md](annotation_guidelines_v0.1.md)), made **before any human labelling**
> after a spot check of v0.1 pre-labels found two systematic errors, both inflating `outcome_described`:
> (a) elementary operations with an unambiguous tool ("add a solid red circle in the corner", "paint the text black")
> had no fitting label → `attribute_direction` now covers them (§1); (b) scope phrases ("choose one area") were split
> into components → they are not components (§0). Both versions' pre-labels are kept.
> Protocol: [docs/motivation-benchmark-gaps.md §1](../../docs/motivation-benchmark-gaps.md).
> Input: `task_inventory.csv` (facts only). Output: `annotations.csv` (one row per task per annotator).

Label what the **agent is given** and what it **must supply itself**. Judge the instruction as written in the
benchmark, not what the author probably meant. Do not look at reference outputs or other annotators' labels.
When unsure, pick the more conservative label (the one less favourable to our hypothesis) and write a note.

## 0. Procedure per task

1. Read the instruction. Split it into **components**: one component = one requested change
   (e.g. "flip horizontally", "deepen the shadows"). Not components: preservation clauses ("keep the face unchanged"),
   scope phrases that only say where the next edit applies ("choose one area", "in the central area", "there"),
   and pure delivery steps are components only if they are part of the task (save/export/render to a path → `procedural_explicit`).
2. Give each component a form (§1). The task's `instruction_form` is the **most demanding** component's form,
   in the order `procedural_explicit < tool_named < attribute_direction < outcome_described`.
   Also record `n_components` and how many components fall in each form.
3. Label required knowledge (§2), initial state (§3), evaluator type (§4, from code), preservation clause (§5).

## 1. Instruction form (per component)

| Label | Definition | Examples from the data |
|---|---|---|
| `procedural_explicit` | The command is identifiable **and** every value needed to execute it is given or trivially fixed. Includes verbs that are themselves the command (flip, rotate 90°, invert, resize to W×H, crop to W×H, set opacity to N%). | PSBench 011 "Change the opacity of the current layer to 50%"; PSBench 167 "Resize the image to 1024x768"; OSExpert gimp_T3 "reducing the brightness to -40" |
| `tool_named` | A specific tool / filter / menu command of the app is named, but its parameter values are not given. | PSBench 199 "Use the Mosaic filter … large square pixel blocks"; PSBench 495 "Use Black & White … moderately increase tonal contrast" (the Black & White part) |
| `attribute_direction` (basic attribute **or elementary operation**) | No tool named, but the standard tool is unambiguous and no professional judgement is needed. Either (i) move **one basic image attribute** in a direction, where the attribute maps one-to-one to a standard control: brightness, contrast, saturation, hue shift, sharpness, blur, opacity, size, grayscale; or (ii) an **elementary content operation**: draw/fill a simple shape, paint a region a solid colour, add plain text, crop/cut out/move/scale/rotate a named object. Strength words (slightly, a bit) and a location ("in the upper-right corner") do not change the label. | PSBench 308 "Decrease brightness slightly"; OSWorld f723c744 "boosting the contrast"; PSBench 371 "Make details appear crisper" (= sharpen); PSBench 354 "add a solid red circle in the upper-right corner"; OSExpert data_low/02 "Paint all text on the box with solid black" |
| `outcome_described` | No tool named; describes an appearance, style, or semantic result that requires choosing **which** tools and how to combine or localise them: looks/grades, tonal-range-specific edits, retouching, compositing, realistic shadows/lighting, effects on a named subject. | PSBench 138 "rich chocolate color grade with warm brown shadows…"; PSBench 275 "reduce the visible dandruff…"; PSBench 258 "make the flowers emit a vivid luminous glow" |

Task-level only:

| Label | Definition |
|---|---|
| `reference_image` | A target image is provided **to the agent** (not merely to the evaluator). None expected in the four audited benchmarks; record if found. |
| `infeasible` | The evaluator is `infeasible` or the task is designed to be refused (OSWorld 2e6f678f, 38f48d40, 62f7fd55). Do not label components. |
| `non_visual` | The goal is app configuration, file management, or UI state with no visual content change (OSWorld d52d6308 "remove the dock"; OSExpert gimp_T1). Components may still be labelled, but exclude from visual-task denominators. |

### Edge cases

- **Effect nouns that are also menu names** (vignette, glow, blur, sharpen, noise, mosaic): label `tool_named` only when the
  phrase directs the use of that command ("use / apply / add a Gaussian blur"). "Add a subtle edge vignette" → `tool_named`
  (Vignette is a menu command). "Make the flowers glow" → `outcome_described` (no single command; requires selection + effect).
- **Tonal-range or region-restricted attribute changes** ("deepen the shadows", "lift the highlights", "boost contrast in the
  central area") are **not** `attribute_direction`: they require choosing a tool that can restrict the range/region (curves, levels,
  masks). Label `outcome_described`.
- **Colour casts** ("introduce a warm, golden cast"): `outcome_described` unless a tool is named (Color Balance, Photo Filter).
- **Exact geometric targets without a tool name** ("crop out the car and save as 450×300"): the crop/scale part is
  `procedural_explicit`; locating the car is captured by K4/K5 and the local flag, not by the form.
- **"Monochrome / black and white / grayscale"** without tool → `attribute_direction`.
- **Animation / scene tasks (OpenToonz)**: named FX or node (Blur FX, RGB Shift, Pegbar) → `tool_named`; technical settings
  stated exactly (1280×720, 24 fps, 120 frames) → `procedural_explicit`; behavioural description (parallax, "fixed to the camera's
  viewport") without the mechanism → `outcome_described`.
- **Instruction defects** (truncated, leaked drafting text, contradictory): label as written and set `instruction_defect=yes`
  with a note. Known: CUA-World `underwater_wave_distortion_fx` (leaked LLM drafting text, truncated).

## 2. Required knowledge (multi-label, beyond what the instruction states)

Definitions follow [motivation-experiments.md §1.2](../../docs/motivation-experiments.md). Tag every level the agent must supply
itself to succeed; also record `k_max`.

| Tag | Required when… |
|---|---|
| K1 UI location | Always for GUI tasks, unless the task is `infeasible`. |
| K2 Function / procedure | The agent must know how to operate a tool beyond one dialog (multi-step procedure, layer/mask workflow, render/export settings). |
| K3 Effect of parameters | A value is not given and must be chosen from its visual consequence ("moderately", "large blocks", "subtle"). |
| K4 State-conditional effect | The result depends on the current document state: selections/masks, a specific subject or region, layer structure, existing tonal/colour distribution, animation timeline. |
| K5 Goal → action | No tool is named for at least one component and the agent must pick which tool(s) achieve the described appearance. |

Rules: `procedural_explicit` tasks normally carry K1 (+K2); `tool_named` adds K3; `attribute_direction` adds K3 and a trivial K5
(record K5 only if more than one standard control could reasonably be meant); `outcome_described` normally carries K3+K5, plus K4
when a region/subject or state matters.

## 3. Initial state

`flat_image` (single raster image) · `stateful_project` (layers, masks, history, scene file, timeline) ·
`no_document` (app config / empty app) · `multi_file` (several input files).

## 4. Evaluator type (label from code, cite the function)

Read the evaluator function at the pinned SHA; do not rely on the paper. One primary label, plus `evaluator_note` with file:function.

| Label | Definition |
|---|---|
| `exact_state` | Checks a config value, file existence/format, document property, or scene parameter for equality. |
| `metric_vs_reference` | Compares the output to a stored reference with a similarity metric (SSIM, structure similarity) and threshold. |
| `direction_only` | Checks only that a statistic moved in the requested direction relative to the input (e.g. brightness decreased), possibly with a structure check. |
| `threshold_heuristic` | Custom image/scene statistics with hand-set thresholds and no reference (common in CUA-World `verifier.py`). |
| `vlm_rubric` | A VLM judges the result (PSBench). Record whether the judge sees a reference (PSBench: no — START and RESULT only). |
| `infeasible_check` | Passes if the agent declares the task infeasible. |
| `unreleased` | The task names an evaluator function whose code is not in the pinned sources, so it cannot be inspected or reproduced. |

For multi-function evaluators, label each function in `evaluator_note` and use the **weakest** as primary
(`unreleased` is weakest; `direction_only`/`vlm_rubric`/`threshold_heuristic` are weaker than `metric_vs_reference`, which is weaker than `exact_state`
for the property it checks).

## 5. Other fields

- `preservation_clause`: yes if the instruction asks to keep something unchanged ("keep the outer area unchanged",
  "preserve the face"). Used to select M3 subject-damage candidates.
- `scope`: `global` · `local` (named region/subject/selection) · `mixed`.
- `confidence`: high / medium / low. `note`: free text, required for low confidence and for every edge case invoked.

## 6. annotations.csv columns

`benchmark, task_id, annotator, instruction_form, n_components, n_procedural, n_tool_named, n_attribute, n_outcome,
k_tags, k_max, initial_state, evaluator_type, evaluator_note, preservation_clause, scope, instruction_defect, confidence, note`

Pre-labels (rule-based or LLM) use `annotator=prelabel_<method>` and are proposals only.

## 7. Agreement and adjudication

- Sample: stratified by benchmark × difficulty, ≥20% per benchmark and ≥30 tasks each (all tasks where a benchmark has ≤30).
- Report Cohen's κ for `instruction_form`, `k_max`, `evaluator_type`; percent agreement for the rest.
- Disagreements are adjudicated by discussion; the adjudicated label and reason go to `annotator=adjudicated`.
- If pre-label vs adjudicated disagreement on `instruction_form` exceeds 10% in any benchmark, hand-correct that benchmark fully.
