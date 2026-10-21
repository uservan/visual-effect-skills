# Motivation Experiments — Professional Knowledge in GUI Skills

> **Current agreed research plan · October 2026**  
> Scope: **Motivation only**. Do not develop our active exploration method or train models yet. This protocol supersedes the earlier, broader effect-oracle-first plan.

## 0. Central hypothesis and paper story

Existing professional GUI skill-generation systems such as **OSExpert** and **VisualSkill** may primarily capture UI locations, functional descriptions, and procedures, while not consistently capturing the **professional, task-useful knowledge** needed to decide which edits produce a desired visual result.

We will test **two falsifiable claims**:

1. **Knowledge audit:** What types of professional knowledge are actually present in existing published/generated skills?
2. **Knowledge intervention:** Does adding **correct, professionally detailed knowledge** to the *same* skill improve the *same* GUI agent on the *same* tasks?

Only after demonstrating both should we investigate **how an agent can acquire such knowledge autonomously in a new environment**.

**Do not assume either claim is true.** OSExpert and VisualSkill already explore UIs and record action results. Report evidence even when it contradicts the hypothesis.

## 1. Experiment 1 — Audit OSExpert and VisualSkill skills

### 1.1 Obtain artifacts and define the audit population

Read the two papers and locate their official skill-generation code and **actual generated skill artifacts**:

- [OSExpert](https://arxiv.org/abs/2603.07978)
- [VisualSkill](https://arxiv.org/abs/2606.18448)

Prefer overlapping professional visual applications (e.g. GIMP), then additional visual editing software where skills and tasks exist. Verify application coverage from the actual source repositories; do not presume both projects include the same apps or task counts.

For each collected skill, retain source project, repository SHA, application/version, skill ID/path, complete raw text, referenced screenshots/media, and availability status. If full published skill corpora are unavailable, state that explicitly: use the accessible subset or reproducibly generate samples, **never present convenience samples as complete population statistics**.

Unit of audit: **one tool/function/skill unit**, with optional task-to-skill links. Distinguish counts of skill units from counts of tasks.

### 1.2 Knowledge rubric (multi-label)

| Tag | Operational definition | Example (GIMP Curves) |
| --- | --- | --- |
| K1 UI / control location | Where to find or interact with controls | Open Colors → Curves |
| K2 Function / procedure | Tool purpose and how to operate it | Adjust curves to change tonal mapping |
| K3 **Professional effect knowledge** | Direction/extent/visual consequences of parameter changes | Raising midtones brightens affected midtone values |
| K4 **Conditional professional knowledge** | When an effect holds or varies with input/document state | Selection masks, active channels, existing tonal distribution change the outcome |
| K5 **Goal-to-action knowledge** | How to translate an intended visual result into a justified tool/parameter choice | To lift shadows without blowing highlights, constrain curve edits appropriately |

For K3–K5 record **absent / mentioned only / actionable and technically correct / incorrect or misleading**. “Blur makes images blurry” is a shallow K3 mention, not automatically adequate for a task requiring selective blur with subject preservation.

Use fixed guidelines and a representative independently double-labeled sample; adjudicate disagreements. A strong VLM/LLM may propose labels, but its labels are **not ground truth**. Make raw skill snippets and decisions available for reviewer inspection.

### 1.3 Outputs

- **Figure 1:** K1–K5 coverage across the actually accessible OSExpert and VisualSkill skill units, reporting denominator and completeness.
- A second **task-linked sufficiency table:** Does the original relevant skill contain correct, actionable professional knowledge required by a specific eligible task? Include uncertain cases.
- Qualitative examples showing original instructions and missing/partial/incorrect professional effect knowledge. Avoid selectively showing only negative examples.

Store `motivation/skill_audit/skill_inventory.csv`, `annotation_guidelines.md`, `skill_annotations.csv`, `knowledge_coverage.csv`, `task_skill_links.csv`, and original/linked artifacts when licenses permit.

## 2. Experiment 2 — Paired Professional Skill intervention

### 2.1 Task selection

Use **existing** professional GUI tasks from OSExpert-Eval and the VisualSkill CUA-World evaluation where possible, especially available GIMP or other visual-editing applications.

Before running any model:
1. Obtain original task IDs, instructions, initial documents, action harnesses, and verifiers.
2. Audit all eligible tasks by app, marking **effect-dependent**, **state-dependent**, **normal/procedural control**, **verifiable**, and any uncertain cases.
3. Select a pilot of up to 10 effect-relevant tasks **without choosing based on which baseline later fails**. Include procedural control tasks. If fewer than 10 suitable tasks exist, report the actual count.
4. Preserve original benchmark identity and split. If constructing additional controlled task variations, label them **diagnostic extensions**, never original benchmark tasks.

Do not cherry-pick tasks whose answer is visible in the intended skill.

### 2.2 Creating the Professional Skill supplement (Claude is allowed **offline**)

Claude may be used solely to **draft** professional knowledge, not to execute or judge test episodes. Our GUI evaluation remains **open-weight**.

Two distinct supplements:

- **Primary: Tool-level Professional Skill.** Claude sees the software/version, relevant tool, official documentation, and existing OSExpert/VisualSkill skill, but **not** individual held-out test-task instructions, target outputs, ground-truth actions or prior test failures. One supplement must be reusable across multiple tasks.
- **Exploratory upper bound: Task-aware Professional Skill.** Claude may see the user task description, but **not** the solution, hidden target parameters, screenshot of the desired answer, or failed run traces. Only general/tool knowledge may appear in the skill; mark this as a weaker, potentially task-specific diagnostic, **not** primary evidence.

Each supplement must be fact-checked against official documentation and/or a controlled software test; preserve Claude prompt, raw generation, reviewed/corrected final text, source citations, tool family, and knowledge tags. Freeze all supplements **before evaluation**. Do not let the same Claude generation output act as a success judge.

If Claude API is unavailable, allow a comparably strong model to draft supplements, but record the substitution and use identical reviewed skill artifacts across executor comparisons.

### 2.3 Matched conditions

For each paired task run, hold fixed: executor model/checkpoint, software version and starting document, prompt except for skill contents, screenshot resolution, tools/actions, max steps, retry policy, and verifier.

| Condition | Agent input | Role |
| --- | --- | --- |
| **A — No Skill** | Goal + GUI only | Natural capability |
| **B — Original Skill** | Original VisualSkill or OSExpert skill in its native supported format | **Primary baseline** |
| **C — B + Professional Skill** | Identical B plus reviewed K3–K5 professional knowledge | **Primary intervention** |
| **D — B + Matched Generic Supplement** | Identical B plus additional generic operational explanation, matched approximately by token/image budget | Context-length / more-help confound control |
| **E — B + Task-aware Professional Skill** | Optional upper-bound analysis | Test-specific knowledge usefulness, not generality |

**Primary paired comparison: B vs C.** A and D improve interpretability. Do not pool VisualSkill and OSExpert baselines unless their execution format, coverage and target tasks are genuinely comparable; run separately where appropriate. “VisualSkill-style” reimplementation on a different model is not a literal reproduction of its original published score.

### 2.4 Models

Use strong open-weight models for **the task executor**, as previously agreed:

- **Primary GUI executor:** Holo4-35B-A3B, contingent on verifying exact checkpoint, tool interface, screenshot support and GUI software compatibility.
- **Second-model replication:** Qwen3.5-397B-A17B, contingent on a working GUI harness. If harness support is insufficient, run it only in a clearly labeled action-isolated diagnostic, not as a standard online GUI result.
- **Optional:** Qwen3-VL-235B-A22B.

Start with a 10–20-task harness viability check, then small paired pilot A/B/C/D, then expand. Do **not** require a Claude API for GUI task runs. Check actual checkpoint names/availability instead of relying on model names in this planning document.

### 2.5 Evaluation, attribution and statistical analysis

Save actual benchmark success/failure, using upstream verifiers if available. Compute:

- Overall success rate by model × condition × task type.
- **Paired B→C rescue:** `#(B fail, C succeed) / #(B fail)`.
- **Paired B→C regression:** `#(B succeed, C fail) / #(B succeed)`.
- **Net success gain:** `Success(C) − Success(B)`.
- Compare **C vs D** to separate professional substance from more tokens/instructions.
- Stratify results by task relevance, software and model; give counts, paired intervals and examples.

Label failure stages using evidence, multi-label if appropriate: wrong tool, professional-effect misunderstanding, GUI grounding/execution, planning, verification, ambiguous instruction. A task success gain alone is **not** proof that the model previously lacked effect understanding; inspect the before/after decisions and traces.

**Figure 2:** paired success transitions B→C, with B→D control and a few step-level trace case studies. Include negative effects and unchanged failures.

### 2.6 Mandatory full visual trace retention and human replay viewer

**Every run must be auditable without rerunning the agent.** Save original-resolution screenshots before **and after each step**, actual actions/coordinates and tool results, model-visible responses (not hidden reasoning), initial/final document states and saved outputs, and verifier details. For edits, preserve before/after rendered content and a difference image where meaningful.

Required layout:

```text
motivation/
  skill_audit/
    skill_inventory.csv
    annotation_guidelines.md
    skill_annotations.csv
    knowledge_coverage.csv
    task_skill_links.csv
  skills/
    original/
    professional_tool_level/
    professional_task_aware_optional/
    generic_controls/
  runs/<model>/<condition>/<task_id>/<run_id>/
    config.json
    task.json
    trace.jsonl
    model_responses.jsonl
    screenshots/step_000_before.png
    screenshots/step_000_after.png
    screenshots/final.png
    effects/edit_000_before.png
    effects/edit_000_after.png
    effects/edit_000_diff.png
    final_state.json
    result.json
  analysis/
    paired_outcomes.csv
    failure_annotations.csv
    motivation_summary.md
    figures/
  viewer/
    index.html
```

Implement a **local static HTML viewer** that can filter by task, model, condition, success, and failure label, inspect step-by-step `before → action → after`, jump to the first failure, compare **B (Original Skill) vs C (Professional Skill)** side by side, and open full-resolution original screenshots and rendered differences. Show A/D as additional comparison options. Use local relative assets and provide instructions to launch; no paid/cloud UI service required.

**Before the large run**, demonstrate one recorded episode and one B/C pair inside the viewer. Preserve all failures, regressions and invalid runs. Do not commit huge screenshot datasets or sensitive environment data into Git by default; store artifacts on experiment storage and commit viewer code/configs/manifests.

## 3. Deliverables and stopping rule

The other coding agent should produce, in order:

1. **Skill inventory and audit report** for OSExpert and VisualSkill, with raw representative examples and carefully defined denominators.
2. **Task inventory and eligibility report** from existing benchmarks (including verified harness availability).
3. **Frozen reviewed professional skill supplements** (Claude-generated, if available), with no held-out answer leakage.
4. **Runnable A/B/C/D configs, reproducible recorded trajectories, and local B-vs-C replay viewer**.
5. **Motivation figures, success/rescue/regression tables, trace-grounded failure analyses, and short go/no-go decision**.

**Do not start our new active skill exploration algorithm before experiments 1 and 2 are completed and analyzed.**

## References

- OSExpert: https://arxiv.org/abs/2603.07978
- VisualSkill: https://arxiv.org/abs/2606.18448
- PhotoAgent (related visual feedback, not direct baseline): https://proceedings.mlr.press/v306/yao26r.html
