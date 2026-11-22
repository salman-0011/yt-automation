"""LLM supervisor: Gemini CLI / AntiGravity CLI via subprocess.

The supervisor does NOT hide the CLI. If `gemini` is installed it is
invoked; otherwise the exact command is printed so the user can run it.
Same for AntiGravity (`antigravity`). No API keys are read here beyond
what the CLI itself already uses. Never hardcode a key.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .config import Config


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


def supervisor_commands(topic: str, kind: str = "short") -> str:
    return (
        "# Supervisor (LLM) — run one of these, paste the job folder path:\n"
        f"gemini \"Review jobs/<job> for topic '{topic}' ({kind}): demand check, "
        "facts with sources, 5 storytelling rules, pre-publish gate.\"\n"
        f"antigravity \"Review jobs/<job> for topic '{topic}' ({kind}): demand check, "
        "facts with sources, 5 storytelling rules, pre-publish gate.\"\n"
    )
