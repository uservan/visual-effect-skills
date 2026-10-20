# Viability pilot: Holo4-35B-A3B, C0 / C2 / C3, 18 CUA-World GIMP tasks (provisional)

Run on ABCI 2026-10-20 20:59 - 2026-10-21 01:13 JST in six job segments (five preemptions, resumed automatically).
**This is a viability check of the harness and of Experiment B's setup, not a result**: one seed, greedy decoding, a
provisional task choice and DRAFT effect notes for C3.

## Setup

- Model: `Hcompany/Holo4-35B-A3B` @ `508458727831368da85d53a8055c2b0f923ed4f3` (BF16, vLLM 0.31.0), temperature 0,
  thinking off, positions in 0-1000 coordinates (verified: tool calls parse, coordinate error 0.14% of the screen).
- Tasks: 18 tasks of CUA-World `gimp_env_all` whose instruction states a target visual outcome instead of naming a
  filter or parameter value, chosen before any run (list in `configs/batches/pilot_holo4.yaml`).  The Experiment A
  audit, not this list, will define the formal task set.
- Conditions: C0 no skill; C2 VisualSkill `gimp-multimodal-stage2` through `load_topic`; C3 = C2 + `oracles/effect/gimp.md`
  (draft v0: general state -> operation -> visual-effect principles, written without seeing any trace).
- Environment: CUA-World's own setup hooks and verifiers, run in a rootless Singularity desktop (Ubuntu 24.04,
  GIMP 2.10.36, fluxbox, GIMP window maximized, 1920x1080 screen, 1280x720 screenshots to the model) because ABCI jobs
  have no root, Docker or KVM.  Step budget = each task's `init.max_steps` (5-10 GUI actions; 75 for the retouch task).

## Per task (pass / verifier score / how the episode ended)

| task | C0 | C2 | C3 |
|---|---|---|---|
| brightness_adjust | fail 0.5 (agent stop) | fail 0.25 (agent stop) | fail 0.5 (budget) |
| brightness_contrast | fail 0.5 (agent stop) | fail 0.5 (agent stop) | fail 0.5 (budget) |
| levels_adjust | fail 0.0 (budget) | fail 0.25 (budget) | fail 0.0 (agent stop) |
| shadows_highlights | fail 0.0 (budget) | fail 0.0 (budget) | **pass** 1.0 (budget) |
| auto_stretch_contrast | fail 0.0 (budget) | **pass** 1.0 (agent stop) | fail 0.4 (budget) |
| contrast_adjust | **pass** 0.75 (budget) | **pass** 0.75 (budget) | **pass** 0.75 (agent stop) |
| color_balance | fail 0.6 (budget) | fail 0.0 (budget) | fail 0.4 (budget) |
| color_enhance | fail 0.0 (budget) | **pass** 1.0 (budget) | **pass** 1.0 (budget) |
| color_temperature | fail 0.2 (budget) | **pass** 0.8 (budget) | **pass** 1.0 (agent stop) |
| saturation_enhance | fail 0.6 (agent stop) | fail 0.6 (budget) | fail 0.2 (agent stop) |
| sepia_tone | fail 0.4 (budget) | **pass** 0.8 (agent stop) | **pass** 0.8 (agent stop) |
| threshold_convert | **pass** 1.0 (agent stop) | **pass** 1.0 (agent stop) | **pass** 1.0 (agent stop) |
| remove_background | fail 0.0 (budget) | fail 0.0 (budget) | fail 0.0 (budget) |
| color_to_alpha | fail 0.0 (budget) | fail 0.0 (budget) | fail 0.0 (budget) |
| eraser_transparency | fail 0.4 (budget) | fail 0.0 (budget) | fail 0.0 (budget) |
| fuzzy_select_fill | fail 0.25 (budget) | fail 0.25 (budget) | fail 0.0 (budget) |
| image_rotation | fail 0.0 (budget) | **pass** 0.75 (budget) | fail 0.25 (budget) |
| graphic_designer_photo_retouch | fail 0.0 (budget, 75) | fail 0.0 (budget, 75) | fail 0.0 (budget, 75) |

## Summary

| | C0 | C2 | C3 |
|---|---|---|---|
| passed | 2 / 18 | 7 / 18 | 6 / 18 |
| ended at the step budget | 14 | 13 | 12 |
| mean GUI actions per episode | 10.8 | 10.6 | 10.3 |
| mean model turns per episode | 11.2 | 13.2 | 12.6 |
| mean prompt tokens per episode (sum over turns) | 81k | 240k | 220k |
| mean wall time per episode | 100 s | 103 s | 100 s |

Paired on the same task:
- C0 -> C2: 5 tasks fail -> pass (auto_stretch_contrast, color_enhance, color_temperature, sepia_tone, image_rotation);
  none pass -> fail.
- C2 -> C3: effect rescue 1 of 11 C2 failures (shadows_highlights, 9%); regression 2 of 7 C2 passes
  (auto_stretch_contrast, image_rotation, 29%); net -1 task (-5.6 points).

## Observations to check in the failure annotation (not claims)

1. Most episodes end at the benchmark's step budget, which binds for Holo4; e.g. C2 brightness_contrast still has the
   Brightness-Contrast dialog open at step 10.  This mixes effect understanding with step efficiency, so the budget
   policy (benchmark budget vs. one larger uniform budget) needs a decision before formal runs.
2. All four transparency tasks (remove_background, color_to_alpha, eraser_transparency, fuzzy_select_fill) fail under
   every condition, all at the budget.
3. An effect-magnitude error as the study defines it: C3 levels_adjust brightened the image by 11.4% (the verifier
   needs >= 15%) with 5.2% highlight clipping, then declared success.
4. Run-to-run sensitivity: brightness_contrast C2 passed on the first desktop version (archived on ABCI) and failed on
   the fixed desktop, with greedy decoding in both.

## Caveats

One seed and 18 tasks give no statistical power; differences of one or two tasks are noise.  The C3 notes are an
unreviewed draft.  The desktop differs from VisualSkill's (no GNOME, fluxbox, maximized window); it is the same for all
conditions.  10 interrupted attempts (preemptions) are kept in the run manifest, as the protocol requires.

## Proposed next steps

Failure annotation of the 54 episodes with the viewer (first_error_step, tags); review the effect (C3) and grounding
(C4) notes; decide the step-budget policy; C1 / C4 on the same tasks; Qwen3.5-397B-A17B replication; the
Experiment A audit for the formal task set; more seeds or sampling for paired confidence intervals.

Data: `analysis/runs_manifest.csv` (one row per attempt).  Traces, screenshots and the viewer stay on ABCI
(`motivation/runs/`, `motivation/viewer/`).
