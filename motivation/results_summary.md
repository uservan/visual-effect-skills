# Motivation results (2026-10-22)

Plan: [docs/motivation-benchmark-gaps.md](../docs/motivation-benchmark-gaps.md). Open-weight models only, served with
vLLM 0.31.0. Human ratings for E3 are being collected; every number below is model- or code-derived unless stated.

## Claim supported by the results

Existing professional-software GUI benchmarks either state the tool and values (scorable, but only UI operation) or
describe the goal vaguely and score it with a reference-free VLM judge that cannot verify magnitude. Models know the
software in words, but cannot map a visible change to the operation and setting that produced it. A benchmark with a
target image and programmatic scoring measures exactly that gap.

## E1 — explicit vs vague tasks

Per clause: is a real command named, and are its values exact or not needed? Task class by rule. Three voters
(Qwen3.5-397B, GLM-5.3, DeepSeek-V4.1-Flash): 77 % unanimous, 8 / 729 three-way splits. `benchmark_audit/split_full.csv`.

| Benchmark | Explicit | Vague (missing values) | Vague (missing tool) |
|---|---|---|---|
| PSBench easy (200) | 114 | 44 | 41 |
| PSBench medium (203) | 25 | 42 | 134 |
| PSBench hard (197) | 0 | 3 | 194 |

Non-PSBench tasks re-split with a `ui_operation` class (`split_nonps_v2.csv`, two voters, 48 / 129 disagreements awaiting adjudication).

## E2 — how tasks are scored (code + PSBench paper)

See [benchmark_audit/code_findings.md](benchmark_audit/code_findings.md). PSBench's judge never sees the reference;
OSWorld "increase/decrease" checks test direction only; 16 / 20 OSExpert GIMP evaluators are unreleased. PSBench paper:
best agent 69.9 → 18.1 % from easy to hard; image-generation models that never open Photoshop score 100 / 100 / 72–90 %.

## E3 — can the judge tell right from wrong? (60 PSBench tasks, PSBench prompt verbatim)

Pass rate (%) over 5 open judge families × 3 repeats (`e3/judgments.jsonl`), explicit / vague tasks:

| Candidate | END | ×0.5 | ×3 | opposite | naive global | identity |
|---|---|---|---|---|---|---|
| All 5 judges | 82 / 86 | 45 / 64 | 52 / 63 | 25 / 26 | 42 / 32 | 3 / 8 |

Every judge (Qwen3.5, GLM-5.3, DeepSeek-V4.1, Step-3.7, Nemotron-3.5) passes 33–73 % of wrong-magnitude results.
Reference-based scoring on the same candidates (`e3/reference_metrics.csv`, CIEDE2000 ≤ 3 at ≤1024 px):
END 100 %, ×0.9 87 %, ×1.1 90 %, ×0.5 18 %, ×3 5 %, opposite 2 %, identity 5 %.

## E4 — knowledge from manuals (356 manual-grounded MCQs, unverified by humans)

Closed → open book: GIMP 93–94 → 97–98 %, Krita 85–87 → 94–95 %, darktable 83–88 → 95 %, OpenToonz 87 → 95 %.
Effect questions are not harder than location questions. Models know the software in words; manuals still help.

## E5 — effect from images (200 before/after pairs, 11 canonical operations × 4 settings)

| Model | op from text | op from image | setting from image |
|---|---|---|---|
| Qwen3.5-397B | 98 % | 75 % | 64 % |
| GLM-5.3 | 98 % | 68 % | 44 % |

Chance is 25 %. Worst on tonal operations: Levels gamma op 38–56 %, setting 0–19 %; brightness op 33–50 %.
Operations are canonical implementations, not application renders.

## Open items

- E3 human ratings (annotation page: 300 items, 3 batches; key in `e3/annotation_key.csv`).
- Human adjudication of E1 disagreements; human verification of E4 questions.
- E3 judges are substitutes for PSBench's default `gpt-5.4`.
