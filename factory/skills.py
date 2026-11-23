"""Skills — Markdown instruction files a job follows (Claude-skills style).

A skill lives in skills/*.md in the repo root. The pipeline reads the
chosen skill and applies its rules to the script, scenes, voice and
style. No code change is needed to change how videos are made.

Shipped defaults:
  origin-loop-shorts      — Origin Loop Shorts (35-45s, 85-100 words)
  tiny-timeline-longform  — Tiny Timeline Lab long-form (8-10 min)
"""
from __future__ import annotations

import re
from pathlib import Path

from .config import ROOT

SKILLS_DIR = ROOT / "skills"
DEFAULT_SHORT_SKILL = "origin-loop-shorts"
DEFAULT_LONG_SKILL = "tiny-timeline-longform"


def _safe_name(name: str) -> str:
    """Skill names are plain file stems — no paths, no traversal."""
    return re.sub(r"[^a-z0-9_-]+", "-", (name or "").lower()).strip("-")


def list_skills() -> list[dict]:
    """Every skill in skills/*.md, with its title and default kind."""
    out = []
    if not SKILLS_DIR.exists():
        return out
    for p in sorted(SKILLS_DIR.glob("*.md")):
        if p.name == "README.md":
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"^#\s+(.+)$", text, re.M)
        title = m.group(1).strip() if m else p.stem
        kind = ("long" if "long" in p.stem or "long-form" in text[:500].lower()
                else "short")
        out.append({"name": p.stem, "title": title, "kind": kind,
                    "path": f"skills/{p.name}", "chars": len(text)})
    return out


def load_skill(name: str) -> str:
    """Return the skill text, or '' if the skill does not exist."""
    stem = _safe_name(name)
    if not stem:
        return ""
    p = SKILLS_DIR / f"{stem}.md"
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def resolve_skill(requested: str | None, kind: str) -> str:
    """'auto' (or an unknown name) resolves to the shipped default for the kind."""
    if requested and requested != "auto" and load_skill(requested):
        return _safe_name(requested)
    return DEFAULT_LONG_SKILL if kind == "long" else DEFAULT_SHORT_SKILL
