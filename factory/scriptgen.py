"""Script generation — the supervisor writes the script, Python runs it.

Rule: if the job already has a real script in script.md (not the
"[Write the narration here]" placeholder), that script is used as-is.
The supervisor never overwrites a human script.

Otherwise Muse (the supervisor) writes it through the Google Gen AI
SDK (factory/genai_client.py), using the saved master prompt + the 5
storytelling rules from prompts.py. No API key / no SDK and no script
= the auto-run stops with a clear error instead of inventing a generic
script. A generic script is worse than no script.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .config import Config
from .genai_client import generate_json, generate_text
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


def choose_angle(topic: str, custom_instructions: str = "",
                 config: Config | None = None) -> dict:
    """ANGLE FIRST — before any script is written.

    Asks Muse (via the Gen AI SDK) for 5 different angles on the topic, the
    angle big channels already used, and picks ONE angle they did NOT
    use — one person, one decision, one machine, or one impossible
    problem. The hook, the script AND the thumbnail all follow this
    one angle. Returns a dict with angle/person/problem/hook/
    thumbnail_angle/why_different/existing_angles/demand_verdict.
    Without an API key, returns a topic-specific fallback angle (the
    topic itself in the wording) and demand verdict PENDING — the human
    demand-check template in the job folder still applies.
    """
    fallback = {
        "angle": (f"Through the eyes of the person who had to solve it: "
                  f"{topic} — one impossible problem, one clever trick, one cost."),
        "person": "the person facing the problem",
        "problem": f"the impossible problem at the heart of {topic}",
        "hook": f"What if the only way through {topic} was the one nobody dared try?",
        "thumbnail_angle": f"The one moment in {topic} that changes everything",
        "why_different": "Fallback angle (no Gen AI SDK key) — check it against "
                         "existing videos in prompts/demand-check.md before running.",
        "existing_angles": [],
        "demand_verdict": "PENDING",
        "source": "fallback",
    }
    cfg = config or Config()
    if not cfg.gemini_api_key:
        return fallback
    prompt = (
        "You are planning ONE YouTube video. Topic: " + topic + "\n"
        "Custom instructions for this job: " + (custom_instructions or "(none)") + "\n"
        "First: demand check. Is there real search interest? Name 3-5 existing "
        "videos on this exact topic and the angle each one used. Verdict: "
        "PROCEED, REFRAME or DROP (DROP only if the topic has no demand).\n"
        "Then: list 5 DIFFERENT angles (one person, one decision, one machine, "
        "one impossible problem, one hidden cost — each in one sentence). "
        "Pick ONE angle the big channels did NOT use. The hook, the script and "
        "the thumbnail must all follow that one angle.\n"
        "Reply with JSON ONLY, no other text: {\"angle\": ..., \"person\": ..., "
        "\"problem\": ..., \"hook\": ..., \"thumbnail_angle\": ..., "
        "\"why_different\": ..., \"existing_angles\": [\"...\"], "
        "\"demand_verdict\": \"PROCEED\"|\"REFRAME\"|\"DROP\"}"
    )
    data = generate_json(cfg, prompt, max_tokens=2048, temperature=0.7)
    if not data.get("angle"):
        return fallback
    data["source"] = "genai-sdk"
    data.setdefault("existing_angles", [])
    data.setdefault("demand_verdict", "PROCEED")
    return data


def generate_script_via_gemini(topic: str, options: JobOptions,
                               config: Config | None = None,
                               skill_text: str = "", angle: dict | None = None,
                               custom_instructions: str = "") -> str:
    """Ask Muse (via the Gen AI SDK) for a script. Returns '' on any failure."""
    cfg = config or Config()
    if not cfg.gemini_api_key:
        return ""
    master = SHORTS_V2_PROMPT if options.kind == "short" else LONGFORM_PROMPT
    word_target = ("85-100 words" if options.kind == "short"
                   else "1150-1350 words")
    angle = angle or {}
    prompt = (
        f"{FIVE_RULES}\n\n"
        f"SKILL TO FOLLOW (this job's rules — script, scenes, voice, style):\n{skill_text}\n\n"
        f"CHOSEN ANGLE — everything follows this one angle:\n{angle.get('angle', '')}\n"
        f"Person: {angle.get('person', '')}\nProblem: {angle.get('problem', '')}\n"
        f"Hook (first line): {angle.get('hook', '')}\n"
        f"Why this angle is different: {angle.get('why_different', '')}\n\n"
        f"PER-JOB CUSTOM INSTRUCTIONS (must be honoured — they are the job's "
        f"own directions, not a template):\n{custom_instructions or '(none)'}\n\n"
        f"{master}\n\nTopic: {topic}\n"
        f"Write ONLY the clean narration script, {word_target}, in natural "
        "conversational American English. Start with the hook above, tell it "
        "through the person above, leave a question every ~60 seconds, and "
        "end with a curiosity/surprise left open — not a summary. "
        "No headings, no scene labels, no stage directions — narration only, "
        "ready to read aloud. Never write generic textbook wording."
    )
    text = generate_text(cfg, prompt, max_tokens=4096, temperature=0.7)
    return text if len(text.split()) >= 20 else ""


def get_or_generate_script(job_dir: Path, topic: str, options: JobOptions,
                           config: Config | None = None,
                           skill_text: str = "", angle: dict | None = None,
                           custom_instructions: str = "") -> tuple[str, str]:
    """Return (script, source). Source: 'job-script' | 'genai-sdk' | ''."""
    script = clean_script_text(job_dir)
    if script:
        return script, "job-script"
    script = generate_script_via_gemini(topic, options, config, skill_text,
                                        angle, custom_instructions)
    if script:
        p = Path(job_dir) / "script.md"
        p.write_text(f"# Script — {topic}\n\n## Clean script (copy-ready)\n\n{script}\n",
                     encoding="utf-8")
        return script, "genai-sdk"
    return "", ""
