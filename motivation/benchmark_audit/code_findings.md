# M1 code findings (evaluators and task data)

> 2026-10-22. Read from the pinned sources listed in `task_inventory.csv` (`source_rev`).
> These are code facts, not adjudicated annotation results. Each item cites file and line/function.

## Evaluator types (`evaluator_labels.csv`)

| Benchmark | n | Evaluator types | Label source |
|---|---|---|---|
| PSBench | 600 | vlm_rubric 600 | code (fixed) |
| OSWorld GIMP | 26 | exact_state 6 · metric_vs_reference 5 · direction_only 3 · threshold_heuristic 3 · infeasible_check 9 | code (fixed map) |
| OSExpert GIMP | 20 | **unreleased 16** · exact_state 2 · direction_only 1 · metric_vs_reference 1 | code (fixed map) |
| CUA-World OpenToonz | 83 | threshold_heuristic 54 · exact_state 19 · hybrid_vlm_and_programmatic 8 · vlm_rubric 1 · metric_vs_reference 1 | Qwen3.5 pre-label from verifier.py; **needs human check** |

Primary type = weakest function in the task (guidelines §4). Across the four benchmarks only **8 of 729** tasks
compare the result with a reference output (OSWorld 5 incl. a derived flip, OSExpert 1, CUA-World 1, plus
PSBench references that the judge never sees).

## Findings

1. **PSBench judge never sees the reference and is told to be lenient.** `PSBench/photoshop_evaluators.py`
   `PhotoshopEvaluator._build_messages`: judge receives instruction, rubric, START and RESULT only; system prompt says
   "accept a subtle but visible directional change" and "do not fail solely because the exact UI value cannot be
   proven". Two looser `judge_policy` modes exist in code but **no rubric in HF @929d071 uses them** (600/600 default).
   → tested directly in M3.
2. **OSWorld "increase/decrease" checks compare with the input, not a target.**
   `OSWorld/desktop_env/evaluators/metrics/gimp.py` `check_brightness_decrease_and_structure_sim`,
   `check_contrast_increase_and_structure_sim`, `check_saturation_increase_and_structure_sim`: pass if the statistic
   moved in the right direction and structure is similar to the input. Any amount of change passes.
3. **OSExpert evaluators for 16/20 GIMP tasks are not released.** Functions `crop_cat_face`, `blackout_text`,
   `blur_cat_body`, `erase_cat`, `image_similarity`, `check_palette_only`, `check_rect_overlay_position_and_size`
   are referenced by task JSONs but defined in neither OSExpert @ed8673d nor OSWorld @90a245c (= origin/main on
   2026-10-22) nor VisualSkills @582e6cc. These tasks cannot be scored by third parties.
4. **CUA-World `apply_mosaic_censor_fx` grants free "VLM" points.** `verifier.py` L49–117: 20 (≥10 frames) + 20
   (not blank) + 20 ("weak" blockiness 0.10–0.15, while its own comment says normal images are <0.10 and mosaic >0.30)
   = 60; at ≥60 a further 20 "implicit visual verification" points are added without any VLM call; pass ≥70.
   A barely-blocky render passes.
5. **CUA-World instruction defect.** `underwater_wave_distortion_fx/task.json` `description` contains leaked LLM
   drafting text ("Wait, I'll remove…", "Actually…") and is truncated.
6. **OSExpert T4 conjunction rejects a perfect mirror** (earlier audit, `../task_audit/verifier_findings.md`).

## Evidence from the PSBench paper (ICML 2026, OpenReview O93cZGxYB1; copy in `visual_effect_data/sources/papers/`)

7. **Success falls with difficulty** (Table 3, Agent S3, best agent): easy 69.9 % (non-layer) / 41.1 % (layer);
   medium 40.6 / 25.0; hard 0.0 / 18.1. E1 classes: easy 57 % explicit, hard 98 % vague-missing-tool. All GUI agents
   show the same ordering.
8. **Image-generation models that never open Photoshop score higher than every GUI agent** (Table 8, same evaluation
   functions): GPT-Image-1 100 / 100 / 90 %, Qwen-Image-Edit 100 / 100 / 80.5 %, FLUX.1 Kontext 100 / 100 / 72.5–75 %
   (easy / medium / hard). These models cannot execute exact operations ("Resize to 800×800", "Exposure +1.0") and the
   paper's Table 9 notes they destroy original pixels, yet they pass. The evaluation accepts approximate visual
   outcomes and cannot distinguish an exact professional edit from a regenerated image.
9. **Paper vs released evaluator differ.** Paper: GPT-4o judge, Cohen's κ = 0.71 vs a 3-expert panel on 150 tasks,
   "more stringent when compared against expert-edited reference images". Released code: `gpt-5.4` default, judge
   never sees the reference. E3 tests the released version.

## To do

- Human check of all 83 CUA-World evaluator pre-labels (the 4 verifiers that mention VLM without calling it were
  checked: labels correct).
- Look for further free-credit / fallback patterns across CUA-World verifiers (grep `Benefit of doubt`, `>= 60`).
