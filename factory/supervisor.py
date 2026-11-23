"""Supervisor: Muse is the central Project Manager.

Muse PLANS and COORDINATES; Python does the rendering. Muse works
through the Google Gen AI SDK (factory/genai_client.py + factory/
agent.py) — the SDK with an API key is the stable supervisor path.
The Gemini CLI / AntiGravity CLI are MANUAL FALLBACK ONLY (they have
session-time and authentication problems): they review a job folder
when asked, they never drive a run, and they are never the default.

Angle first, then script — the two halves of the plan are separate
functions so the agent tools (factory/agent.py) can call them one at
a time: plan_angle, then write_script. The sequential runner
(factory/auto.py) calls the same two functions when the agent loop
is not available. One code path, two drivers.

Muse never renders video/audio itself, never fakes a Flow call, and
never overwrites a human script.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .config import Config
from .genai_client import sdk_ready
from .options import JobOptions
from .prompts import FIVE_RULES, LONGFORM_PROMPT, SHORTS_V2_PROMPT
from .scriptgen import choose_angle, clean_script_text, get_or_generate_script, split_into_scenes


def cli_available(name: str) -> str | None:
    return shutil.which(name)


def supervisor_label(options: JobOptions, cfg: Config) -> str:
    """How Muse is working on this job (shown in the log + usage.json)."""
    want = getattr(options, "supervisor_backend", "auto")
    if want in ("auto", "genai-sdk", "gemini-api") and sdk_ready(cfg):
        return "Muse via Gen AI SDK"
    if want == "gemini-cli" and cli_available(cfg.gemini_cli):
        return "Muse via Gemini CLI (manual fallback)"
    if want == "antigravity" and cli_available(cfg.antigravity_cli):
        return "Muse via AntiGravity CLI (manual fallback)"
    return "Muse (no LLM tool — using the job's own script.md)"


def run_supervisor_check(job_dir: Path, config: Config | None = None) -> str:
    """MANUAL fallback only: ask a supervisor CLI to review a job folder.

    This is NOT part of an auto-run. The auto-run supervisor is the
    Gen AI SDK agent (factory/agent.py). Use this when you want a
    human-triggered review from a terminal.
    """
    cfg = config or Config()
    job_dir = Path(job_dir)
    prompt = (
        "Review this YouTube production job folder and list, in order: "
        "(1) facts that still need a source, (2) any scene whose visual does "
        "not explain its narration, (3) any AI-generated text risk, "
        "(4) whether the pre-publish gate passes. Job: " + str(job_dir))
    for cli in (cfg.gemini_cli, cfg.antigravity_cli):
        exe = cli_available(cli)
        if exe:
            try:
                r = subprocess.run([exe, prompt], capture_output=True,
                                   text=True, timeout=300)
                if r.returncode == 0 and r.stdout.strip():
                    return f"[{cli}]\n{r.stdout.strip()}"
            except Exception:
                continue
    return (
        "No supervisor CLI found on PATH. Install Gemini CLI, then run:\n"
        f"  gemini \"{prompt}\"\n"
        "or with AntiGravity CLI:\n"
        f"  antigravity \"{prompt}\"\n"
        "Until then, run the manual pre-publish gate in prompts/checklist.md."
    )


def save_job_inputs(job_dir: Path, skill_name: str, skill_text: str,
                    custom: str) -> None:
    """Save exactly what this job follows, for the audit trail."""
    job_dir = Path(job_dir)
    (job_dir / "prompts" / "skill.md").write_text(
        f"# Skill for this job: {skill_name}\n\n{skill_text}", encoding="utf-8")
    (job_dir / "custom-instructions.md").write_text(
        custom or "(none — no custom instructions for this job)\n", encoding="utf-8")


def save_angle(job_dir: Path, angle: dict) -> dict:
    """Write angle.md + angle.json + prompts/thumbnail.md for one angle."""
    job_dir = Path(job_dir)
    angle = dict(angle or {})
    angle.setdefault("existing_angles", [])
    angle.setdefault("demand_verdict", "PENDING")
    (job_dir / "angle.md").write_text(
        "# Chosen angle — one angle per job\n\n"
        f"Angle: {angle.get('angle', '')}\n\nPerson: {angle.get('person', '')}\n"
        f"Problem: {angle.get('problem', '')}\nHook: {angle.get('hook', '')}\n"
        f"Thumbnail angle: {angle.get('thumbnail_angle', '')}\n"
        f"Why different: {angle.get('why_different', '')}\n"
        f"Existing angles: {', '.join(angle.get('existing_angles') or []) or '(not listed)'}\n"
        f"Demand verdict: {angle.get('demand_verdict', 'PENDING')} "
        f"(source: {angle.get('source', 'fallback')})\n",
        encoding="utf-8")
    (job_dir / "angle.json").write_text(json.dumps(angle, indent=2), encoding="utf-8")
    (job_dir / "prompts" / "thumbnail.md").write_text(
        "# Thumbnail — follows the SAME angle as the script\n\n"
        f"Angle: {angle.get('angle', '')}\n"
        f"Thumbnail angle: {angle.get('thumbnail_angle', '')}\n"
        "Image: clean, no text, no letters, no words, no logos. "
        "One dominant subject, strong contrast, cinematic lighting.\n"
        "Thumbnail words (CapCut overlay only, 2-4 words): "
        f"{angle.get('thumbnail_angle', '')[:40]}\n",
        encoding="utf-8")
    return angle


def plan_angle_step(job_dir: Path, topic: str, options: JobOptions,
                    config: Config | None = None) -> dict:
    """ANGLE FIRST (sequential path): pick the angle via the SDK.

    Returns {"angle", "skill", "skill_text", "custom", "supervisor"}.
    The angle files are written; the script is NOT written here.
    """
    from .skills import load_skill, resolve_skill
    cfg = config or Config()
    skill_name = resolve_skill(getattr(options, "skill", "auto"), options.kind)
    skill_text = load_skill(skill_name)
    custom = getattr(options, "custom_instructions", "") or ""
    save_job_inputs(job_dir, skill_name, skill_text, custom)
    angle = save_angle(job_dir, choose_angle(topic, custom, cfg))
    return {"angle": angle, "skill": skill_name, "skill_text": skill_text,
            "custom": custom, "supervisor": supervisor_label(options, cfg)}


def validate_script(script: str, kind: str) -> tuple[bool, str]:
    """Word-count + hook sanity check for an agent-written script."""
    words = len((script or "").split())
    if words < 20:
        return False, f"Script is only {words} words — too short to narrate."
    if kind == "short" and not (60 <= words <= 140):
        return False, (f"Short script is {words} words (target 85-100). "
                       "Rewrite it to 85-100 words.")
    if kind == "long" and not (900 <= words <= 1600):
        return False, (f"Long-form script is {words} words (target 1150-1350). "
                       "Rewrite it to 1150-1350 words.")
    return True, f"Script OK: {words} words."


def save_agent_angle(job_dir: Path, angle_args: dict) -> dict:
    """Save an angle the AGENT (model) chose. Validates, then saves."""
    angle = {
        "angle": (angle_args.get("angle") or "").strip(),
        "person": (angle_args.get("person") or "").strip(),
        "problem": (angle_args.get("problem") or "").strip(),
        "hook": (angle_args.get("hook") or "").strip(),
        "thumbnail_angle": (angle_args.get("thumbnail_angle") or "").strip(),
        "why_different": (angle_args.get("why_different") or "").strip(),
        "existing_angles": angle_args.get("existing_angles") or [],
        "demand_verdict": (angle_args.get("demand_verdict") or "PENDING").upper(),
        "source": "agent",
    }
    if not angle["angle"] or not angle["hook"]:
        raise ValueError("plan_angle needs at least 'angle' and 'hook'.")
    if angle["demand_verdict"] not in ("PROCEED", "REFRAME", "DROP"):
        angle["demand_verdict"] = "PENDING"
    return save_angle(job_dir, angle)


def save_agent_script(job_dir: Path, topic: str, options: JobOptions,
                      script_text: str, angle: dict) -> tuple[str, list[dict]]:
    """Save a script the AGENT (model) wrote. Validates, then saves."""
    ok, msg = validate_script(script_text, options.kind)
    if not ok:
        raise ValueError(msg)
    cfg = Config()
    p = Path(job_dir) / "script.md"
    p.write_text(f"# Script — {topic}\n\n## Clean script (copy-ready)\n\n{script_text.strip()}\n",
                 encoding="utf-8")
    script = clean_script_text(job_dir)
    n_scenes = 9 if options.kind == "short" else 44
    scenes = split_into_scenes(script, n_scenes, float(options.duration_sec),
                               cfg.voice_wpm)
    _write_storyboard(job_dir, angle, scenes)
    return script, scenes


def _write_storyboard(job_dir: Path, angle: dict, scenes: list[dict]) -> None:
    (Path(job_dir) / "storyboard.md").write_text(
        "# Storyboard (auto-generated by the supervisor)\n\n"
        f"Angle: {angle.get('angle', '')}\n\n" +
        "\n".join(f"{i+1}. [{s['duration']}s] {s['narration']}\n   Visual: {s['visual']}\n"
                  for i, s in enumerate(scenes)), encoding="utf-8")


def write_script_step(job_dir: Path, topic: str, options: JobOptions,
                      config: Config | None = None, skill_text: str = "",
                      angle: dict | None = None,
                      custom_instructions: str = "") -> tuple[str, str, list[dict]]:
    """SCRIPT (sequential path): job script.md, or Muse via the SDK.

    Returns (script, script_source, scenes). Source: 'job-script' |
    'genai-sdk' | ''. The script is saved to script.md when generated.
    """
    cfg = config or Config()
    script, source = get_or_generate_script(job_dir, topic, options, cfg,
                                            skill_text, angle, custom_instructions)
    if not script:
        return "", "", []
    n_scenes = 9 if options.kind == "short" else 44
    scenes = split_into_scenes(script, n_scenes, float(options.duration_sec),
                               cfg.voice_wpm)
    _write_storyboard(job_dir, angle or {}, scenes)
    return script, source, scenes


def plan_job(job_dir: Path, topic: str, options: JobOptions,
             config: Config | None = None) -> dict:
    """Central plan (sequential path): angle first, then script + scenes.

    Returns {script, script_source, scenes, supervisor, angle, skill,
    demand_verdict}. If the demand verdict is DROP, the script is ''
    and the caller stops the job before spending anything.
    """
    from .skills import load_skill, resolve_skill  # noqa: F401 - kept for callers
    cfg = config or Config()
    first = plan_angle_step(job_dir, topic, options, cfg)
    angle = first["angle"]
    verdict = angle.get("demand_verdict", "PENDING")
    if verdict == "DROP":
        return {"script": "", "script_source": "", "scenes": [],
                "supervisor": first["supervisor"], "angle": angle,
                "skill": first["skill"], "demand_verdict": "DROP"}
    script, source, scenes = write_script_step(
        job_dir, topic, options, cfg, first["skill_text"], angle, first["custom"])
    return {"script": script, "script_source": source, "scenes": scenes,
            "supervisor": first["supervisor"], "angle": angle,
            "skill": first["skill"], "demand_verdict": verdict}


def supervisor_commands(topic: str, kind: str = "short") -> str:
    return (
        "# Supervisor (LLM) — MANUAL fallback only, paste the job folder path:\n"
        f"gemini \"Review jobs/<job> for topic '{topic}' ({kind}): demand check, "
        "facts with sources, 5 storytelling rules, pre-publish gate.\"\n"
        f"antigravity \"Review jobs/<job> for topic '{topic}' ({kind}): demand check, "
        "facts with sources, 5 storytelling rules, pre-publish gate.\"\n"
        "# The auto-run supervisor is the Gen AI SDK agent (factory/agent.py), "
        "not these CLIs.\n"
    )
