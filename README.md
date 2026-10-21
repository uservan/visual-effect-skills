# Visual Effect Skills for Professional GUI Agents

> **Research in progress.** This repository studies whether strong professional GUI agents lack reusable knowledge of how software operations affect visual content, and how that knowledge might be learned through active exploration.

**Working paper title:** *Beyond Operational Skills: Learning State-Conditioned Visual Effects of Professional Software Tools through Active Exploration*

## Central research question

Professional editing requests often specify a desired appearance rather than a click sequence. A software agent may know **where a tool is** and **how to invoke it** without reliably knowing **what visual result the tool will produce given the current document**.

We investigate a falsifiable hypothesis: existing operational and multimodal skills may inadequately capture state-dependent visual effects, and acquiring such effect knowledge may improve success on effect-driven tasks.

**First priority: establish the problem experimentally.** We are *not* claiming the hypothesis has already been validated.

## Current phase: Motivation experiments

**[Read the full Motivation Experimental Protocol →](docs/motivation-experiments.md)**

We will:

1. **Audit tasks** in OSExpert-Eval and the VisualSkill CUA-World evaluation for effect-dependence and state-dependence.
2. **Study strong open-weight models**: Holo4-35B-A3B as primary GUI executor; Qwen3.5-397B-A17B for replication; Qwen3-VL-235B-A22B optionally. Verify model checkpoints and GUI harness compatibility before running.
3. **Compare matched interventions**: No Skill, Operational Skill, VisualSkill-style multimodal skill, VisualSkill + **general Effect Oracle**, and VisualSkill + **Grounding Oracle**.
4. **Attribute failures** using trajectories and rendered visual outcomes, distinguishing effect misunderstanding from tool selection, grounding/execution, planning and verification.
5. **Measure causal rescue and uncertainty**, not only success averages. If correct general effect knowledge fails to rescue relevant errors, revise or stop the project.

No Claude API is required for this phase. All experimental results remain pending.

## Research direction if Motivation succeeds

The proposed method, **State-Conditioned Active Effect Exploration**, aims to learn reusable knowledge from controlled experiments:

`(document state, tool, parameters) → observed visual change`

A future explorer would formulate competing effect hypotheses, select informative starting states and parameter changes, compare actual before/after visual results, and consolidate verified **Conditional Effect Skills** with applicability conditions and counterexamples.

At execution time, an agent could use these skills in reverse: `(current state, desired visual effect) → candidate operation`.

This method is a **proposal, not an implemented or validated contribution**.

## Evaluation principles

- Existing professional GUI benchmarks for end-to-end task outcomes, with original task IDs and verifiers.
- Separately labeled controlled diagnostic states for isolated forward effect prediction and inverse edit selection, if necessary.
- Fixed model/harness/action budget across knowledge conditions.
- Critical baseline: a VisualSkill-style guide with comparable screenshot evidence and context budget.
- Objective software/rendered-state verification where possible.
- Explicit go/no-go decision based on the Motivation results.

## Related work

- [OSExpert — Computer-Use Agents Learning Professional Skills via Exploration](https://arxiv.org/abs/2603.07978): professional software function discovery and skill reuse.
- [VisualSkill — Multimodal Skills for Computer-Use Agents](https://arxiv.org/abs/2606.18448): documentation plus GUI exploration and screenshot-grounded skills; key methodological baseline.
- [PhotoAgent — Exploratory Visual Aesthetic Planning with Large Vision Models](https://proceedings.mlr.press/v306/yao26r.html): edit search with visual feedback for a current task.
- [RetouchIQ](https://openaccess.thecvf.com/content/CVPR2026/html/Wu_RetouchIQ_MLLM_Agents_for_Instruction-Based_Image_Retouching_with_Generalist_Reward_CVPR_2026_paper.html): visual-edit parameter selection and reward learning.

These papers already study real GUI exploration, visual screenshots, or effect-driven editing. Our potential distinction is **learning reusable, state-conditioned effect knowledge from a limited number of controlled tool experiments**. Novelty remains to be established against broader active experimentation and visual-control literature.

## Roadmap

- [ ] **M0** — Verify public benchmark tasks, verifiers, and open model/harness setup.
- [ ] **M1** — Task composition and effect-dependence audit.
- [ ] **M2** — Matched Effect Oracle versus Grounding Oracle failure attribution.
- [ ] **M3** — Decide whether the hypothesized bottleneck is sufficiently supported.
- [ ] **M4** — Only then prototype hypothesis-driven effect exploration and compare to equal-budget visual skill baselines.

## Status

**Environment and harness preparation:** Official OSWorld desktop/GIMP smoke checks are working. The first Holo4-27B A/B pilot run was invalid (model-server chat-template error) and has not been rerun. No model episode or benchmark result has been produced yet; no model weights have been trained.

For the next implementation agent, start with **[docs/motivation-benchmark-gaps.md](docs/motivation-benchmark-gaps.md)** (current motivation plan) and **[docs/benchmark-construction.md](docs/benchmark-construction.md)** (benchmark design). The earlier skill-audit plan in [docs/motivation-experiments.md](docs/motivation-experiments.md) is superseded as the motivation.
