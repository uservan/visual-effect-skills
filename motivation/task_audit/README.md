# Initial task inspection (2026-10-21)

This is a source inventory, not a complete benchmark audit or experimental result.

Sources:
- OSExpert: https://github.com/Lumos-Jiateng/OSExpert/tree/ed8673d900293967388615b95301596eb4a1cc15
- VisualSkills configuration: https://github.com/XMHZZ2018/VisualSkills/blob/582e6ccb370b291bd31f3688629378e385e3731a/scripts/run-cua-world/experiments/configs/opentoonz_mm_stage2.yaml
- CUA-World fork pinned by VisualSkills: https://github.com/XMHZZ2018/gym-anything/tree/f667d6b277c8d8b8d35c91f817213dad91cfc552

`initial_task_inventory.csv` contains 122 task definitions: six OSExpert long-horizon GIMP tasks, 33 OSExpert fine-grained files (mixed applications), and 83 OpenToonz definitions in the pinned CUA-World checkout. These groups are not the full benchmark population. The 21 OpenToonz tasks explicitly selected in the VisualSkills stage2 multimodal evaluation config are marked separately. Other OpenToonz tasks must not be described as part of that published evaluation without additional evidence.

Initial observations:
- GIMP T1/T2 concern preferences and opening controls; T3 supplies brightness/contrast values; T4 specifies a flip/export; T5 concerns indexed mode and text movement; T6 specifies overlay size and position.
- Fine-grained tasks include selective cat-body blur, background removal, region-preserving edits, cropping, object moves and text formatting. These may mix effect knowledge with selection/grounding difficulty.
- Selected OpenToonz examples include reference-animation matching (`animate_ghibli_scene`), interpolation (`animate_ease_motion`), composition, opacity/timing effects and many technical render/export tasks. Many specify the technique and parameters already.
- OpenToonz task.json files declare program verifiers, while selected tasks also have VLM checklists. Actual evaluation scoring requires inspecting the runner; declarations alone do not establish which verifier was used.
- No environment has been launched and no verifier has been executed. Initial assets and reference videos have not been visually inspected.
