"""Agent loop, recorder, run_episode and viewer on the mock desktop with a scripted model."""
import json
from pathlib import Path

import pytest

from ves import run_episode
from ves.actions import CoordSpace
from ves.agent import Agent, AgentConfig, Budget
from ves.envs import make_env
from ves.knowledge import build_knowledge
from ves.model_client import ModelReply, ToolCall
from ves.recorder import RunRecorder
from ves.viewer.build import build as build_viewer

SKILLS = Path(__file__).resolve().parents[1] / "third_party" / "VisualSkills" / "skills"
COORD = CoordSpace("norm1000", 1280, 720, 1920, 1080)


def reply(*calls, content=""):
    return ModelReply(content=content, tool_calls=[ToolCall(f"c{i}", n, json.dumps(a)) for i, (n, a) in enumerate(calls)],
                      finish_reason="tool_calls" if calls else "stop", prompt_tokens=100, completion_tokens=10,
                      reasoning_chars=0, latency_s=0.01, attempts=1)


class Scripted:
    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    def chat(self, messages, tools, route=0):
        self.seen.append((json.loads(json.dumps(messages)), [t["function"]["name"] for t in tools]))
        return self.replies.pop(0)


def app_cfg(tmp_path):
    eff = tmp_path / "effect.md"
    eff.write_text("General effect notes.\n")
    grd = tmp_path / "grounding.md"
    grd.write_text("General grounding notes.\n")
    return {"text_skill": str(SKILLS / "gimp-text-stage2"), "multimodal_skill": str(SKILLS / "gimp-multimodal-stage2"),
            "effect_oracle": str(eff), "grounding_oracle": str(grd)}


def count_screenshot_images(messages):
    n = 0
    for m in messages:
        if m["role"] == "user" and isinstance(m["content"], list):
            labels = [p.get("text") for p in m["content"] if p["type"] == "text"]
            if any(l in ("Current screenshot:", "Screenshot after your last action:") for l in labels):
                n += sum(p["type"] == "image_url" for p in m["content"])
    return n


def test_agent_loop_records_everything(tmp_path):
    k = build_knowledge("C3", app_cfg(tmp_path))
    topic = k.skill.topics()[0]
    env = make_env({"backend": "mock"})
    env.reset(0)
    rec = RunRecorder(tmp_path / "run", diff_ignore=env.diff_ignore_boxes())
    client = Scripted([
        reply(("load_topic", {"topic": topic})),
        reply(("click", {"x": 500, "y": 500}), ("type_text", {"text": "hi"})),
        reply(content="<tool_call><function=click> broken"),
        reply(("hotkey", {"keys": ["ctrl", "s"]}), ("click", {"x": 2000, "y": 1})),
        reply(content="The task is complete."),
    ])
    agent = Agent(env, client, k, rec, AgentConfig(COORD, keep_screenshots=2), Budget(10, 30, 600))
    out = agent.run("Do something.")
    rec.close()
    assert out["stop_reason"] == "agent_done"
    assert out["gui_steps"] == 3 and out["skill_calls"] == 1 and out["invalid_actions"] == 2
    assert out["knowledge_images_sent"] >= 0
    events = [json.loads(l) for l in (tmp_path / "run" / "trace.jsonl").read_text().splitlines()]
    steps = [e for e in events if e["type"] == "step"]
    assert [s["step"] for s in steps] == [0, 1, 2]
    for s in steps:
        assert (tmp_path / "run" / s["before"]).exists() and (tmp_path / "run" / s["after"]).exists()
    assert steps[0]["action"] == {"kind": "click", "x": 960, "y": 540, "button": "left"}
    assert "paths" in steps[0]["effect"] and (tmp_path / "run" / steps[0]["effect"]["paths"]["diff"]).exists()
    # step k's before image is the previous step's after image (same capture)
    assert (tmp_path / "run" / steps[1]["before"]).read_bytes() == (tmp_path / "run" / steps[0]["after"]).read_bytes()
    assert sum(e["type"] == "skill" for e in events) == 1
    # the oracle note and skill index are in the first user message; the skill tools are offered
    first_user = client.seen[0][0][1]["content"]
    texts = "\n".join(p["text"] for p in first_user if p["type"] == "text")
    assert "General effect notes." in texts and "Installed software skill" in texts and "Task: Do something." in texts
    assert "load_topic" in client.seen[0][1]
    # only the newest 2 screenshots stay as images
    last_messages = client.seen[-1][0]
    assert count_screenshot_images(last_messages) == 2
    assert len((tmp_path / "run" / "model_responses.jsonl").read_text().splitlines()) == 5


def test_step_budget(tmp_path):
    k = build_knowledge("C0", app_cfg(tmp_path))
    env = make_env({"backend": "mock"})
    env.reset(0)
    rec = RunRecorder(tmp_path / "run")
    client = Scripted([reply(("click", {"x": 1, "y": 1}), ("click", {"x": 2, "y": 2}), ("click", {"x": 3, "y": 3}))])
    out = Agent(env, client, k, rec, AgentConfig(COORD), Budget(2, 30, 600)).run("Click thrice.")
    assert out["stop_reason"] == "max_steps" and out["gui_steps"] == 2
    assert "load_topic" not in client.seen[0][1]


def test_run_episode_and_viewer(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    for cond in ("C2", "C3"):
        client = Scripted([reply(("click", {"x": 300, "y": 300})), reply(content="done")])
        monkeypatch.setattr(run_episode, "ModelClient", lambda *a, **kw: client)
        run_dir = runs / "mockmodel" / cond / "mock.task" / "s0_a1"
        spec = {"run_dir": str(run_dir), "run_id": "s0_a1", "seed": 0, "condition": cond,
                "model": {"name": "mockmodel", "served_name": "m", "base_urls": ["http://x"], "coord": "norm1000"},
                "app": app_cfg(tmp_path), "env": {"backend": "mock"},
                "task": {"task_id": "mock.task", "benchmark": "mock", "instruction": "Click.", "max_steps": 5},
                "budget": {"max_steps_cap": 120, "timeout_s": 600}}
        assert run_episode.run(spec) == 0
        res = json.loads((run_dir / "result.json").read_text())
        assert res["status"] == "completed" and res["success"] is True and res["actions"] == 1
        for key in ("task_id", "model_id", "checkpoint", "condition", "software_version", "seed", "success",
                    "verifier", "failure_tags", "first_error_step", "actions", "tokens", "runtime", "evidence_paths"):
            assert key in res
        for f in ("config.json", "task.json", "trace.jsonl", "model_responses.jsonl", "final_state.json",
                  "screenshots/initial.png", "screenshots/step_000_before.png", "screenshots/step_000_after.png",
                  "screenshots/final.png", "final_state/final.png"):
            assert (run_dir / f).exists(), f
    (tmp_path / "ann.csv").write_text("model,condition,task_id,run_id,first_error_step,failure_tags,evidence_paths,notes,annotator\n"
                                      "mockmodel,C2,mock.task,s0_a1,0,effect_misunderstanding;tool_selection,,test,me\n")
    out = tmp_path / "viewer"
    assert build_viewer(runs, out, tmp_path / "ann.csv") == 2
    index = json.loads((out / "data" / "index.js").read_text().split("=", 1)[1].rstrip().rstrip(";"))
    assert {r["condition"] for r in index} == {"C2", "C3"}
    c2 = next(r for r in index if r["condition"] == "C2")
    assert c2["first_error_step"] == 0 and c2["failure_tags"] == ["effect_misunderstanding", "tool_selection"]
    assert c2["path"] == "../runs/mockmodel/C2/mock.task/s0_a1"
    for f in ("index.html", "app.js", "style.css", f"data/runs/{c2['key']}.js"):
        assert (out / f).exists()
