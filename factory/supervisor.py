"""LLM supervisor: the central Project Manager.

The supervisor PLANS and COORDINATES; Python does the rendering.
Order of authority for a plan:
  1. gemini-api  — Gemini API (GEMINI_API_KEY) writes the script + scene
                   plan as JSON. This is the supervisor when a key is set.
  2. gemini-cli / antigravity — CLIs review a job folder (no script write).
  3. none — no LLM; the job's own script.md is used as-is.

The supervisor never renders video/audio itself, never fakes a Flow
call, and never overwrites a human script. See factory/auto.py for the
runner that executes the plan step by step.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

from .config import Config
from .options import JobOptions
from .prompts import FIVE_RULES, LONGFORM_PROMPT, SHORTS_V2_PROMPT
from .scriptgen import generate_script_via_gemini, split_into_scenes


def cli_available(name: str) -> str | None:
    return shutil.which(name)


def run_supervisor_check(job_dir: Path, config: Config | None = None) -> str:
    """Ask the supervisor CLI to review a job folder, or print the command."""
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


def plan_job(job_dir: Path, topic: str, options: JobOptions,
             config: Config | None = None) -> dict:
    """Central plan: supervisor writes script + scenes, runner executes.

    Returns a plan dict: {script, script_source, scenes, supervisor,
    angle}. If no LLM is available and no script exists, script is ''
    and the caller (auto.py) stops with a clear error.
    """
    from .scriptgen import clean_script_text, get_or_generate_script
    cfg = config or Config()
    want = options.supervisor_backend
    supervisor = "none"
    if want in ("auto", "gemini-api") and cfg.gemini_api_key:
        supervisor = "gemini-api"
    elif want == "gemini-cli" and cli_available(cfg.gemini_cli):
        supervisor = "gemini-cli"
    elif want == "antigravity" and cli_available(cfg.antigravity_cli):
        supervisor = "antigravity"

    script, source = get_or_generate_script(job_dir, topic, options, cfg)
    if supervisor == "gemini-api" and source == "":
        # Gemini was the supervisor but could not write a script.
        supervisor = "gemini-api (failed — check key / network)"
    n_scenes = 9 if options.kind == "short" else 44
    scenes = split_into_scenes(script, n_scenes, float(options.duration_sec),
                               cfg.voice_wpm) if script else []
    return {"script": script, "script_source": source, "scenes": scenes,
            "supervisor": supervisor,
            "angle": "The Engineer in the Story — one problem, one impossible "
                     "constraint, one clever machine/trick, one cost."}


def supervisor_commands(topic: str, kind: str = "short") -> str:
    return (
        "# Supervisor (LLM) — run one of these, paste the job folder path:\n"
        f"gemini \"Review jobs/<job> for topic '{topic}' ({kind}): demand check, "
        "facts with sources, 5 storytelling rules, pre-publish gate.\"\n"
        f"antigravity \"Review jobs/<job> for topic '{topic}' ({kind}): demand check, "
        "facts with sources, 5 storytelling rules, pre-publish gate.\"\n"
    )
