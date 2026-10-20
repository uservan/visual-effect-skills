"""load_topic must deliver exactly what VisualSkill's own skill_server.py delivers (text chunks and figures, in order).
The reference server is loaded with a stub of mcp.server.fastmcp, so the test does not depend on the mcp version."""
import importlib.util
import sys
import types
from pathlib import Path

import pytest

from ves.knowledge import CONDITIONS, Skill, build_knowledge

SKILLS = Path(__file__).resolve().parents[1] / "third_party" / "VisualSkills" / "skills"
MM = SKILLS / "gimp-multimodal-stage2"
TXT = SKILLS / "gimp-text-stage2"
pytestmark = pytest.mark.skipif(not MM.exists(), reason="VisualSkills checkout missing")


class _Image:
    def __init__(self, data=None, format=None, path=None):
        self.data, self.format = data, format


class _FastMCP:
    def __init__(self, name):
        pass

    def tool(self):
        return lambda f: f


def _reference(skill_dir: Path):
    fake = types.ModuleType("mcp.server.fastmcp")
    fake.FastMCP, fake.Image = _FastMCP, _Image
    names = ("mcp", "mcp.server", "mcp.server.fastmcp")
    saved = {n: sys.modules.get(n) for n in names}
    sys.modules.update({"mcp": types.ModuleType("mcp"), "mcp.server": types.ModuleType("mcp.server"),
                        "mcp.server.fastmcp": fake})
    try:
        spec = importlib.util.spec_from_file_location(f"ref_{skill_dir.name.replace('-', '_')}",
                                                      skill_dir / "tools" / "skill_server.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        for n, m in saved.items():
            if m is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = m
    return mod.load_topic, mod.list_topics


def _normalize_ref(parts):
    out = []
    for p in parts:
        if isinstance(p, str):
            out.append(("text", p))
        else:  # mcp Image
            out.append(("image", bytes(p.data)))
    return out


def _normalize_ours(parts):
    return [("text", p["text"]) if p["type"] == "text" else ("image", p["path"].read_bytes()) for p in parts]


@pytest.mark.parametrize("skill_dir,multimodal", [(MM, True), (TXT, False)])
def test_load_topic_matches_visualskill(skill_dir, multimodal):
    ref_load, ref_list = _reference(skill_dir)
    ours = Skill(skill_dir, multimodal=multimodal)
    topics = ours.topics()
    assert topics == ref_list().split("\n")
    assert len(topics) > 20
    for topic in topics:
        assert _normalize_ours(ours.load_topic(topic)) == _normalize_ref(ref_load(topic)), topic
    assert ours.load_topic("no/such/topic")[0]["text"].startswith("ERROR")
    assert ours.load_topic("../x")[0]["text"].startswith("ERROR")


def test_multimodal_topics_carry_figures():
    ours = Skill(MM, multimodal=True)
    n_images = sum(p["type"] == "image" for t in ours.topics() for p in ours.load_topic(t))
    assert n_images > 50


def test_conditions(tmp_path):
    eff = tmp_path / "effect.md"
    eff.write_text("Multiply darkens.\n")
    grd = tmp_path / "grounding.md"
    grd.write_text("Filters menu is in the menu bar.\n")
    app = {"text_skill": str(TXT), "multimodal_skill": str(MM), "effect_oracle": str(eff), "grounding_oracle": str(grd)}
    assert set(CONDITIONS) == {"C0", "C1", "C2", "C3", "C4"}
    k0 = build_knowledge("C0", app)
    assert k0.skill is None and k0.oracle is None
    k1 = build_knowledge("C1", app)
    assert k1.skill and not k1.skill.multimodal and k1.oracle is None
    k3 = build_knowledge("C3", app)
    assert k3.skill.multimodal and k3.oracle.kind == "effect" and len(k3.provenance["oracle"]["sha256"]) == 64
    k4 = build_knowledge("C4", app)
    assert k4.oracle.kind == "grounding"
    assert k3.provenance["skill"]["sha256"] == k4.provenance["skill"]["sha256"]
    assert "Guides" in k1.skill.index_text() and not k1.skill.index_text().startswith("---")
