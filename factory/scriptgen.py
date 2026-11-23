"""Script generation — the supervisor writes the script, Python runs it.

Rule: if the job already has a real script in script.md (not the
"[Write the narration here]" placeholder), that script is used as-is.
The supervisor never overwrites a human script.

Otherwise the LLM supervisor (Gemini API) writes it, using the saved
master prompt + the 5 storytelling rules from prompts.py. No API key
and no script = the auto-run stops with a clear error instead of
inventing a generic script. A generic script is worse than no script.
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from .config import Config
from .options import JobOptions
from .prompts import FIVE_RULES, LONGFORM_PROMPT, SHORTS_V2_PROMPT

PLACEHOLDER = "[Write the narration here]"


def clean_script_text(job_dir: Path) -> str:
    """Return the clean narration from script.md, or '' if none / placeholder."""
    p = Path(job_dir) / "script.md"
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    # Prefer the "## Clean script (copy-ready)" section if present.
    m = re.search(r"## Clean script.*?\n+(.*)", text, re.S)
    body = m.group(1).strip() if m else text
    body = re.sub(r"^#.*$", "", body, flags=re.M).strip()
    if not body or PLACEHOLDER in body or len(body.split()) < 20:
        return ""
    return body


def split_into_scenes(script: str, n_scenes: int, duration_sec: float,
                      wpm: int = 152) -> list[dict]:
    """Split narration into scenes, one sentence (or sentence pair) each.

    Scene durations are proportional to word count, then scaled so the
    total matches duration_sec. Every scene gets narration + a visual
    line the visuals backend can render.
    """
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script.strip()) if s.strip()]
    if not sentences:
        return []
    # Group sentences into ~n_scenes chunks.
    scenes: list[dict] = []
    per = max(1, len(sentences) // n_scenes)
    for i in range(0, len(sentences), per):
        chunk = sentences[i:i + per]
        text = " ".join(chunk)
        scenes.append({"narration": text, "words": len(text.split()),
                       "visual": text[:120]})
    # Merge the tail so we never exceed n_scenes + 2.
    while len(scenes) > n_scenes + 2:
        scenes[-2]["narration"] += " " + scenes[-1]["narration"]
        scenes[-2]["words"] += scenes[-1]["words"]
        scenes.pop()
    total_words = sum(s["words"] for s in scenes) or 1
    for s in scenes:
        s["duration"] = max(2.0, round(duration_sec * s["words"] / total_words, 1))
    # Fix rounding drift on the last scene.
    drift = round(duration_sec - sum(s["duration"] for s in scenes), 1)
    if scenes and drift:
        scenes[-1]["duration"] = max(2.0, scenes[-1]["duration"] + drift)
    return scenes


def generate_script_via_gemini(topic: str, options: JobOptions,
                               config: Config | None = None) -> str:
    """Ask Gemini API for a script. Returns '' on any failure (no key, no net)."""
    cfg = config or Config()
    if not cfg.gemini_api_key:
        return ""
    master = SHORTS_V2_PROMPT if options.kind == "short" else LONGFORM_PROMPT
    word_target = ("85-100 words" if options.kind == "short"
                   else "1150-1350 words")
    prompt = (
        f"{FIVE_RULES}\n\n{master}\n\nTopic: {topic}\n"
        f"Write ONLY the clean narration script, {word_target}, in natural "
        "conversational American English. No headings, no scene labels, "
        "no stage directions — narration only, ready to read aloud."
    )
    try:
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096},
        }).encode()
        req = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.5-flash:generateContent?key=" + cfg.gemini_api_key,
            data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            payload = json.loads(r.read())
        text = payload["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Strip any markdown fences / headings the model added anyway.
        text = re.sub(r"^```.*$", "", text, flags=re.M).strip()
        text = re.sub(r"^#.*$", "", text, flags=re.M).strip()
        return text if len(text.split()) >= 20 else ""
    except Exception:
        return ""


def get_or_generate_script(job_dir: Path, topic: str, options: JobOptions,
                           config: Config | None = None) -> tuple[str, str]:
    """Return (script, source). Source: 'job-script' | 'gemini-api' | ''."""
    script = clean_script_text(job_dir)
    if script:
        return script, "job-script"
    script = generate_script_via_gemini(topic, options, config)
    if script:
        p = Path(job_dir) / "script.md"
        p.write_text(f"# Script — {topic}\n\n## Clean script (copy-ready)\n\n{script}\n",
                     encoding="utf-8")
        return script, "gemini-api"
    return "", ""
