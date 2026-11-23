"""Pipeline: topic -> demand check -> research -> script -> storyboard
-> voice -> visuals -> captions -> assemble -> QC.

This module creates the job folder and all the prompt/template files.
The auto-runner (factory/auto.py) is what actually generates the
video: supervisor plans, audio/video backends render, FFmpeg assembles.
Flow / Nano Banana still have no public API — their prompts stay
manual-only. That honesty is the point — no step is faked.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict, field
from pathlib import Path

from . import prompts as P
from .animation import scaffold_animation
from .config import Config
from .credits import CreditLedger
from .voice import write_voice_files

SHORT = "short"
LONG = "long"

PIPELINE_STEPS = [
    "01-demand-check",
    "02-research",
    "03-script",
    "04-storyboard",
    "05-voice",
    "06-visuals",
    "07-captions",
    "08-assemble",
    "09-qc-pre-publish-gate",
]


@dataclass
class Job:
    slug: str
    topic: str
    kind: str  # short | long
    channel: str
    status: str = "created"
    verdict: str = "PENDING-DEMAND-CHECK"
    options: dict = field(default_factory=dict)  # JobOptions, as a dict
    run: dict = field(default_factory=dict)      # auto-run progress / result

    def to_dict(self) -> dict:
        return asdict(self)


def slugify(topic: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return slug[:60] or "untitled"


def create_job(topic: str, kind: str, config: Config | None = None,
               options: dict | None = None) -> tuple[Job, Path]:
    cfg = config or Config()
    kind = kind.lower()
    if kind not in (SHORT, LONG):
        raise ValueError("kind must be 'short' or 'long'")
    from .options import JobOptions
    opts = JobOptions.from_dict(options, kind)
    # .env defaults apply only when the caller did not choose a backend.
    if not (options or {}).get("video_backend"):
        opts.video_backend = cfg.default_video_backend
    if not (options or {}).get("audio_backend"):
        opts.audio_backend = cfg.default_audio_backend
    if not (options or {}).get("supervisor_backend"):
        opts.supervisor_backend = cfg.default_supervisor_backend
    channel = cfg.shorts_channel if kind == SHORT else cfg.longform_channel
    slug = slugify(topic)
    job_dir = cfg.jobs_dir / slug
    job_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("clips", "voice", "stills", "prompts"):
        (job_dir / sub).mkdir(exist_ok=True)

    job = Job(slug=slug, topic=topic, kind=kind, channel=channel,
              options=opts.to_dict())
    (job_dir / "job.json").write_text(json.dumps(job.to_dict(), indent=2), encoding="utf-8")
    (job_dir / "options.json").write_text(json.dumps(opts.to_dict(), indent=2),
                                          encoding="utf-8")

    master = P.SHORTS_V2_PROMPT if kind == SHORT else P.LONGFORM_PROMPT
    (job_dir / "prompts" / "master-prompt.md").write_text(
        P.FIVE_RULES + "\n" + master, encoding="utf-8")
    (job_dir / "prompts" / "demand-check.md").write_text(
        P.DEMAND_CHECK_TEMPLATE.format(topic=topic), encoding="utf-8")
    (job_dir / "prompts" / "flow-prompts.txt").write_text(
        "# Paste ONE prompt per scene into Google Flow (Omni Flash, 720p).\n"
        "# Check the Flow cost screen before generating. One generation per scene.\n"
        "# Save clips as clips/scene-01.mp4, scene-02.mp4, ...\n"
        "# Scene prompts go here — write them from the storyboard (step 04).\n",
        encoding="utf-8")
    (job_dir / "prompts" / "flow-manual-steps.md").write_text(
        P.FLOW_MANUAL_STEPS.format(account="A (or B — track it in credits)"),
        encoding="utf-8")
    (job_dir / "script.md").write_text(
        f"# Script — {topic}\n\nChannel: {channel} ({kind})\n\n"
        "Status: DRAFT — write the script here using prompts/master-prompt.md\n"
        "and the 5 storytelling rules. Word target: "
        + ("85-100 words (Short, 35-45s)." if kind == SHORT
           else "1150-1350 words (long-form, 8-10 min, 5 acts).")
        + "\n\n## Clean script (copy-ready)\n\n[Write the narration here]\n",
        encoding="utf-8")
    (job_dir / "storyboard.md").write_text(
        "# Storyboard\n\n"
        + ("8-10 scenes, 3-4s each. Columns: Scene | Time | Narration | Visual | "
           "Omni Flash prompt | Kinetic text.\n" if kind == SHORT else
           "40-48 scenes. Tier 1 hero clip 6s (22-28), Tier 2 map/still, "
           "Tier 3 CapCut graphic/recut. Columns: Scene | Time | Narration | "
           "Visual | Visual prompt | Kinetic text.\n"),
        encoding="utf-8")
    (job_dir / "pronunciation.md").write_text(
        "# Pronunciation guide (Charon)\n\nWrite EVERY difficult name here with a "
        "plain respelling before recording. No name in the script without one.\n",
        encoding="utf-8")
    (job_dir / "checklist.md").write_text(
        "# Pre-publish gate — ALL must pass or do not upload\n\n"
        "- [ ] Demand check verdict: PROCEED\n"
        "- [ ] Facts checked against sources; do-not-say list checked\n"
        "- [ ] Every visual checked for wrong/misspelled AI text\n"
        "- [ ] Captions checked against the script (hand-corrected)\n"
        "- [ ] AI disclosure ticked at upload; reconstructions labelled illustrative\n"
        "- [ ] Music / SFX licensed or from CapCut library\n"
        "- [ ] Loudness -14 LUFS +/-1, true peak <= -1 dBTP\n"
        + ("- [ ] Loop-back ending works on replay; thumbnail has no baked-in text\n"
           if kind == SHORT else
           "- [ ] Outro present (20s); chapters match storyboard acts\n")
        + "- [ ] Same video NOT uploaded to the other channel\n",
        encoding="utf-8")
    scaffold_animation(job_dir, topic, kind)
    return job, job_dir


def credit_warning(kind: str, config: Config | None = None) -> str:
    ledger = CreditLedger(config)
    if kind == SHORT:
        need = ledger.estimate_short()
        est = ledger.check_before_spend(need, "A")
        return (f"Short (~40s): ~{need:.0f} Omni Flash credits. {est.message} "
                f"Total balance: {ledger.total_balance()}.")
    est = ledger.estimate_long()
    check = ledger.check_before_spend(est["max"], "A")
    return (f"Long-form: {est['primary']:.0f} primary + {est['retake_reserve']:.0f} "
            f"reserve = {est['max']:.0f} max. {check.message} "
            f"Total balance: {ledger.total_balance()}.")
