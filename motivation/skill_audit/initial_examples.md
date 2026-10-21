# Qualitative counterexamples to a broad knowledge-gap claim

These are deliberately selected examples, not a representative coverage audit.
They establish that some published VisualSkill guides already describe effects,
conditions and goal-to-action relationships. Technical correctness and adequacy
for held-out tasks have not been independently verified. Do not calculate corpus
coverage from these examples or call them human-adjudicated labels.

Source: XMHZZ2018/VisualSkills commit
`582e6ccb370b291bd31f3688629378e385e3731a`, under `skills/`.

| Guide | Existing knowledge observed | Implication for our hypothesis |
|---|---|---|
| gimp-multimodal-stage2/color-adjustments/levels-and-curves/guide.md | Tonal slider directions, curve slope and contrast, channel-specific corrections, and suggested S-curves | Broad professional effect knowledge is already present, not merely menu paths |
| gimp-multimodal-stage2/layers/layer-masks/guide.md | Mask values control visibility; initialization depends on whether the user wants to reveal or hide; editing requires the mask to be active | Existing guidance includes state/target conditions and goal-to-operation advice |
| gimp-multimodal-stage2/painting-and-drawing/blur-sharpen-smudge-dodge-burn/guide.md | Repeated-stroke accumulation, Rate/Opacity distinctions, and transparency-related smudge options | Parameter interactions and input-state effects are discussed; correctness still needs checking |
| opentoonz-multimodal-stage2/animation/creating-movements/guide.md | Parent/child motion inheritance, orientation along paths, depth and compositing order | Existing skill extends beyond point-and-click navigation |
| opentoonz-multimodal-stage2/animation/editing-curves-and-expressions/guide.md | Interpolation types, expressions for oscillation/noise, parameter references and cycles | Relevant procedural and effect knowledge exists for animation tasks |
| opentoonz-multimodal-stage2/effects-and-rendering/using-the-particles-effect/guide.md | Control-image values influence parameters; texture sources inherit transformations; birth timing, forces, fading and variation are explained | Strong overlap with the proposed state-conditioned effect-knowledge scope |

Several of these paragraphs already occur in Stage 1; Stage 2 adds UI-reference
sections. This supports authored documentation as a source of professional
knowledge, but does not by itself establish the provenance of every sentence.

Related code evidence: `preprocess/skill-pipeline/stage2/prompts.py` asks targeted
explorers to vary input/control states and record mechanisms, disabled-state
transitions, value reversion and side effects. Thus, state-dependent exploration
is not absent by design. Whether those experiments cover rendered-content
outcomes deeply enough remains an empirical question.

Next decision should be based on inspectable failures: what original skill was
available, what the executor actually loaded, which decision/action first failed,
and whether the verifier agrees with the requested result. Low aggregate score
alone cannot identify professional knowledge as the limiting factor.
