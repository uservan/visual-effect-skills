"""Knowledge supplements of the conditions C0-C4: VisualSkill-style skills and oracle notes.

C0 no skill | C1 text skill | C2 multimodal skill | C3 = C2 + effect oracle | C4 = C2 + grounding oracle.
Skill topics are loaded exactly as VisualSkill's tools/skill_server.py does: the guide text with every referenced
figure inserted right after the sentence that mentions it, then the unreferenced figures (multimodal skills only).
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

# superset of the stage-1 (figNN) and stage-2 (figNN, ui-*) figure references in VisualSkill guides
FIG_REF_RE = re.compile(r"`((?:fig\d+|ui-[^`\n]+)\.(?:png|jpe?g))`", re.IGNORECASE)
FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def tree_hash(root: Path) -> str:
    """sha256 over every file's relative path and bytes, so a run records exactly which material it saw."""
    h = hashlib.sha256()
    for p in sorted(q for q in root.rglob("*") if q.is_file()):
        h.update(str(p.relative_to(root)).encode())
        h.update(b"\0")
        h.update(p.read_bytes())
    return h.hexdigest()


@dataclass
class Skill:
    root: Path
    multimodal: bool

    @property
    def name(self) -> str:
        return self.root.name

    def index_text(self) -> str:
        """SKILL.md without its YAML front matter: the topic index with 'Use when' lines."""
        return FRONTMATTER_RE.sub("", (self.root / "SKILL.md").read_text(encoding="utf-8")).strip()

    def topics(self) -> list[str]:
        out = []
        for dirpath, _dirs, files in os.walk(self.root, followlinks=True):
            if "guide.md" in files:
                out.append(str(Path(dirpath).relative_to(self.root)))
        return sorted(out)

    def load_topic(self, topic: str) -> list[dict]:
        """Parts in order: {"type": "text", "text": ...} or {"type": "image", "path": Path}."""
        topic = str(topic).strip().strip("/")
        if topic.endswith("/guide.md"):
            topic = topic[: -len("/guide.md")]
        if ".." in Path(topic).parts:
            return [{"type": "text", "text": f"ERROR: topic path '{topic}' must not contain '..'."}]
        folder = self.root / topic
        if not topic or not folder.is_dir():
            return [{"type": "text", "text": f"ERROR: topic '{topic}' not found. "
                                             "Call list_topics() to see all valid topic paths."}]
        guide = folder / "guide.md"
        if not guide.exists():
            return [{"type": "text", "text": f"ERROR: no guide.md in topic '{topic}'."}]
        text = guide.read_text(encoding="utf-8")
        header = f"# {topic}/guide.md\n\n"
        if not self.multimodal:
            return [{"type": "text", "text": header + text}]
        figures = sorted(list(folder.glob("*.png")) + list(folder.glob("*.jpg")) + list(folder.glob("*.jpeg")))
        by_name = {f.name.lower(): f for f in figures}
        parts: list[dict] = []
        cursor, emitted = 0, set()
        for m in FIG_REF_RE.finditer(text):
            chunk = text[cursor:m.end()]
            parts.append({"type": "text", "text": (header + chunk) if cursor == 0 else chunk})
            cursor = m.end()
            name = m.group(1).lower()
            if name in by_name and name not in emitted:
                parts.append({"type": "image", "path": by_name[name]})
                emitted.add(name)
        tail = text[cursor:]
        if cursor == 0:
            tail = header + tail
        if tail:
            parts.append({"type": "text", "text": tail})
        parts += [{"type": "image", "path": f} for f in figures if f.name.lower() not in emitted]
        return parts


@dataclass
class OracleNote:
    """General notes given to every task of an application (never per-task answers), with optional figures
    referenced as `figNN.png` next to the markdown file."""
    kind: str  # "effect" or "grounding"
    path: Path

    def parts(self) -> list[dict]:
        text = self.path.read_text(encoding="utf-8")
        out, cursor = [], 0
        for m in FIG_REF_RE.finditer(text):
            out.append({"type": "text", "text": text[cursor:m.end()]})
            cursor = m.end()
            fig = self.path.parent / m.group(1)
            if fig.exists():
                out.append({"type": "image", "path": fig})
        if text[cursor:]:
            out.append({"type": "text", "text": text[cursor:]})
        return out

    def sha256(self) -> str:
        h = hashlib.sha256(self.path.read_bytes())
        for p in self.parts():
            if p["type"] == "image":
                h.update(p["path"].read_bytes())
        return h.hexdigest()


@dataclass
class Knowledge:
    condition: str
    skill: Skill | None = None
    oracle: OracleNote | None = None
    provenance: dict = field(default_factory=dict)


CONDITIONS = {
    "C0": {"skill": None, "oracle": None},
    "C1": {"skill": "text", "oracle": None},
    "C2": {"skill": "multimodal", "oracle": None},
    "C3": {"skill": "multimodal", "oracle": "effect"},
    "C4": {"skill": "multimodal", "oracle": "grounding"},
}


def build_knowledge(condition: str, app_cfg: dict) -> Knowledge:
    """app_cfg: {"text_skill": dir, "multimodal_skill": dir, "effect_oracle": md, "grounding_oracle": md}."""
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition!r}; expected one of {sorted(CONDITIONS)}")
    spec = CONDITIONS[condition]
    k = Knowledge(condition=condition)
    if spec["skill"]:
        root = Path(app_cfg[f"{spec['skill']}_skill"])
        if not (root / "SKILL.md").exists():
            raise FileNotFoundError(f"{condition}: no SKILL.md in {root}")
        k.skill = Skill(root=root, multimodal=spec["skill"] == "multimodal")
        k.provenance["skill"] = {"dir": str(root), "multimodal": k.skill.multimodal, "sha256": tree_hash(root)}
    if spec["oracle"]:
        path = Path(app_cfg[f"{spec['oracle']}_oracle"])
        if not path.exists():
            raise FileNotFoundError(f"{condition}: oracle file {path} does not exist")
        k.oracle = OracleNote(kind=spec["oracle"], path=path)
        k.provenance["oracle"] = {"kind": spec["oracle"], "path": str(path), "sha256": k.oracle.sha256()}
    return k
