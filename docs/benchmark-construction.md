# Benchmark Construction — Design and Pipeline

> **Draft · 2026-10-21.** Design agreed in discussion; nothing below is implemented yet.
> Motivation: [motivation-benchmark-gaps.md](motivation-benchmark-gaps.md).

## 0. Principles

1. **Every task has a determinate answer.** Each task is generated from a hidden *operation program*
   executed on a start asset; the rendered result is the target. No purely aesthetic goals in the scored set.
2. **Difficulty comes from withheld information, not vague wording.** No free-form "professional terminology"
   instructions in the main benchmark.
3. **Evaluation is programmatic.** Outcome is compared with the target; process is read from the software's
   own edit history. VLMs are not used for scoring.
4. **Open-source professional software in one reproducible sandbox.**
5. **Knowledge is an explicit experimental variable** (documentation / skill conditions), so failures can be
   attributed to operation, effect knowledge, or tool selection.

## 1. Software and sandbox

One Ubuntu base image (start from the OSWorld QCOW2 already used in `motivation/`), all apps installed at pinned
versions, launched under QEMU+KVM with a disposable copy-on-write overlay per episode.

| App | Role | Edit history readable? | Status |
|---|---|---|---|
| darktable | RAW development / grading | Yes — XMP history stack (module, order, params) | Pilot candidate |
| GIMP 3.x (Flatpak) | Raster editing | Yes — non-destructive filters on layers via Python API (to verify) | Pilot candidate |
| Krita | Painting / raster | Filter & adjustment layers via Python API | Later |
| Inkscape | Vector design | SVG structure | Later; needs non-image attributes |
| Blender | 3D / materials / lighting | bpy scene state | Later; CPU-only rendering in VM is slow |

DaVinci Resolve and Photoshop are out of scope (GPU / commercial licence).

**Anti-cheating sandbox:** the target image is shown only in the model input, never placed inside the VM;
no network, no terminal or scripting access for the agent, no generative plugins. Importing external pixels or
pasting is detected from history and fails the task.

To verify before building: KVM-capable nodes, offline installation of each app into the image, history read-out
for darktable and GIMP 3, and deterministic re-rendering of the same program.

## 2. Task definition

A task = `(app, start asset, operation program, information level, step count)`.

### 2.1 Operation library (per app)

Each operation entry defines: tool/module name, editable parameters with realistic ranges, whether it is global
or local (needs a selection/mask), the script that applies it headlessly, and the history signature used to
recognise it. Start with 8–10 GIMP/darktable operations: curves, levels, colour balance, hue-saturation,
exposure, white balance, Gaussian blur, unsharp mask, vignette, selection + adjustment.

### 2.2 Workflow templates

Operation sequences come from real professional workflows (portrait retouch, product-photo grading, RAW
development, background separation), written as templates with parameter ranges. Random chains of unrelated
operations are not allowed.

### 2.3 Information levels (same hidden program, same target, same scoring)

| Level | Model receives | What the model must supply |
|---|---|---|
| **L1 Full steps** | Tools, order, parameter values | Operation only (find, click, enter values) |
| **L2 Tool set** | Start + target image + the set of tools used (no order, no parameters) | Effect knowledge: order and parameter values from the target |
| **L3 Target only** | Start + target image | Tool selection, order and parameters |

Gap interpretation: L1 fail → operation/grounding; L1 pass & L2 fail → tool-effect knowledge; L2 pass & L3 fail →
tool selection/composition.

### 2.4 Step counts

3, 5, 7, 11 operations. A *step* = one tool application with one parameter set; GUI action counts are recorded
separately. Global and local steps are counted and reported separately. For L3 local steps, the region is
given as a hint (mask or region name), otherwise the task is unidentifiable.

### 2.5 Sampling filters

Reject a sampled program unless every step:
- has a visible marginal effect (above a perceptual threshold, e.g. ΔE₀₀ or luminance change on its region);
- is not redundant (cannot be merged with an adjacent step of the same tool);
- is not cancelled by later steps;
- stays within ranges reachable in the GUI.

## 3. Generation pipeline

```
start assets (licensed, provenance recorded)
  → workflow template → sample program for step count k ∈ {3,5,7,11}
  → apply headlessly in the pinned app → target + per-step intermediates + history
  → sampling filters → region masks for local steps (SAM + human check)
  → emit L1 / L2 / L3 instructions from the program (no free text written by an LLM)
  → validation (§5) → freeze
```

## 4. Scoring

### 4.1 Outcome (primary — determines success)

- **Match:** ΔE₀₀ (mean and 95th percentile) and SSIM between result and target; for local steps computed per
  region. Success requires all within tolerance.
- **Side effects:** changes outside requested regions/attributes (clipping ratio, subject colour shift,
  banding/noise) relative to the target.
- Tolerances calibrated from perceptual thresholds and a human study (§5.3), fixed before evaluation.

### 4.2 Process (gate + diagnostics), read from edit history

| Item | Use |
|---|---|
| Legality: only tools in the allowed set (L2) or any in-app tool (L3); no imported/pasted pixels | **Gate** — violation fails the task |
| Coverage: each tool of the set used (L2) | Reported |
| Order agreement with the hidden program | Diagnostic |
| Parameter closeness to hidden parameters | Diagnostic only — different parameters can give equivalent results |

Screenshot trace is kept as supporting evidence and for the replay viewer.

## 5. Validation (every task, before freezing)

1. **Oracle:** replaying the hidden program passes.
2. **Alternative solution:** an independent solution (different tool or parameters, by a person or a second
   template) that visually matches passes — guards against tolerances that accept only one exact recipe.
3. **Negatives must fail:** identity, single naive global edit, over-strength, opposite direction, wrong region.
4. **GUI reachability:** a human (or scripted GUI replay) completes L1 within the step budget.
5. **Human calibration (sampled):** experts rank a set of results; the metric ranking must agree (report Kendall τ).

Tasks failing any check are fixed or dropped; the log of dropped tasks is kept.

## 6. Knowledge conditions and splits

| Condition | Agent additionally gets |
|---|---|
| S0 | Nothing |
| S1 | Retrieval over the pinned official manual (offline copy) |
| S2 | Existing skills (OSExpert / VisualSkill style) where available |
| S3 | Self-built skills: before testing the agent may read the manual and explore the app, without seeing test tasks |

Splits: a public **dev** split (may be used for skill building and prompt tuning) and a hidden **test** split.
Templates may be shared across splits; programs, assets and targets may not.

A **grounding-oracle mode** (element coordinates from the accessibility tree) is offered as a diagnostic so
knowledge effects are not masked by clicking errors.

## 7. Task record

```json
{
  "task_id": "gimp-portrait-005-L2",
  "app": "gimp", "app_version": "3.0.x",
  "template": "portrait_retouch_v1", "steps": 5, "level": "L2",
  "start": "assets/portrait_017.png",
  "target": "targets/gimp-portrait-005.png",
  "program": "programs/gimp-portrait-005.json",
  "allowed_tools": ["curves", "hue_saturation", "gaussian_blur", "selection"],
  "region_hints": {"step_4": "masks/portrait_017_background.png"},
  "tolerances": {"de00_mean": 2.5, "de00_p95": 6.0, "ssim": 0.95},
  "checks": ["oracle", "alternative", "negatives", "gui_reachable"]
}
```

Layout: definitions and programs in the repo under `benchmark/`; assets, targets and episode traces on
`/scratch/pioneer/jobs/wxy320/save/visual-effect-skills/benchmark/`.

## 8. Pilot

- Apps: GIMP 3 or darktable (whichever has verified history read-out first).
- 2–3 templates; step counts 3/5/7, five programs each → 15 programs × L1/L2/L3 = 45 tasks.
- Executor: open-weight model on one A100, S0 only; then S1.
- Questions the pilot must answer: (1) do L1/L2/L3 success rates differ; (2) does success fall with steps;
  (3) do negatives fail and alternatives pass under the chosen tolerances.

## 9. Open issues

- Tolerance values and the human calibration protocol.
- Attribute sets for non-image apps (Inkscape, Blender).
- Asset licensing for start images.
- Whether L3 is solvable at 11 steps; may need region hints for all local steps.
- A curated professional-terminology subset (e.g. print bleed, aspect-ratio letterboxing) is a possible
  later extension, outside the main scored set.
