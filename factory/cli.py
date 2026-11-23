"""CLI: python -m factory.cli <command> ...

Commands:
  new --type short|long --topic "..."   create a job folder + prompts
  auto --job slug [--video-backend ...] [--audio-backend ...] [--duration N]
       [--aspect 9:16|16:9] [--style ...] [--captions on|off]
       ONE CLICK: supervisor plans, backends render, FFmpeg assembles.
       Finished video: jobs/<slug>/output-<type>.mp4
  options                               list every per-job option + what is installed
  status [--job slug]                   list jobs / show one job
  credits                               show balances + estimates
  voice --job slug                       write Charon act files / try Gemini TTS
  captions --job slug                    make captions.srt (faster-whisper or estimate)
  assemble --job slug [--type short|long]  FFmpeg assemble clips + voice
  review --job slug                      supervisor review (Gemini/AntiGravity CLI)
  serve                                 start the dashboard (http://localhost:8000)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .auto import approve_job, run_job_sync
from .captions import make_captions
from .config import Config
from .credits import CreditLedger
from .options import (AUDIO_BACKENDS, CAPTION_BACKENDS, STYLES,
                      SUPERVISOR_BACKENDS, VIDEO_BACKENDS, JobOptions,
                      detect_audio_backends, detect_supervisor_backends,
                      detect_video_backends)
from .pipeline import create_job, credit_warning
from .server import list_jobs, run_server
from .supervisor import run_supervisor_check
from .video import assemble
from .voice import synthesize_via_gemini, write_voice_files


def _job_dir(slug: str, cfg: Config) -> Path:
    d = cfg.jobs_dir / slug
    if not d.exists():
        print(f"Job not found: {slug}\nRun: python -m factory.cli status")
        sys.exit(1)
    return d


def _read_script(job_dir: Path) -> str:
    p = job_dir / "script.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _add_option_args(p: argparse.ArgumentParser) -> None:
    """Every per-job option, shared by `new` and `auto`."""
    p.add_argument("--duration", type=int, default=None,
                   help="Target duration in seconds (Short default 40, long default 540)")
    p.add_argument("--aspect", choices=["9:16", "16:9"], default=None)
    p.add_argument("--style", choices=STYLES, default=None,
                   help="auto (= channel default) | cinematic-realistic | 2.5d-cartoon | diagram | map")
    p.add_argument("--video-backend", choices=VIDEO_BACKENDS, default=None,
                   help="auto | code | motion-canvas | manim | flow-manual (manual only)")
    p.add_argument("--audio-backend", choices=AUDIO_BACKENDS, default=None,
                   help="auto | gemini-tts (Charon) | kokoro | piper | existing")
    p.add_argument("--voice", default=None, help="Voice name (default Charon)")
    p.add_argument("--captions", choices=["on", "off"], default=None)
    p.add_argument("--caption-backend", choices=CAPTION_BACKENDS, default=None)
    p.add_argument("--supervisor", choices=SUPERVISOR_BACKENDS, default=None,
                   help="auto | genai-sdk | gemini-api | gemini-cli | antigravity | none")
    p.add_argument("--assembler", choices=["auto", "ffmpeg", "moviepy"], default=None,
                   help="auto (= FFmpeg) | ffmpeg | moviepy (slower, Python timeline)")
    p.add_argument("--skill", default=None,
                   help="Skill to follow: auto | origin-loop-shorts | tiny-timeline-longform | <skills/*.md stem>")
    p.add_argument("--custom", default=None,
                   help="Per-job custom instructions (the job's own directions)")


def _options_from_args(args) -> dict:
    opts: dict = {}
    if getattr(args, "duration", None):
        opts["duration_sec"] = args.duration
    if getattr(args, "aspect", None):
        opts["aspect"] = args.aspect
    if getattr(args, "style", None):
        opts["style"] = args.style
    if getattr(args, "video_backend", None):
        opts["video_backend"] = args.video_backend
    if getattr(args, "audio_backend", None):
        opts["audio_backend"] = args.audio_backend
    if getattr(args, "voice", None):
        opts["voice_name"] = args.voice
    if getattr(args, "captions", None):
        opts["captions"] = args.captions == "on"
    if getattr(args, "caption_backend", None):
        opts["caption_backend"] = args.caption_backend
    if getattr(args, "supervisor", None):
        opts["supervisor_backend"] = args.supervisor
    if getattr(args, "skill", None):
        opts["skill"] = args.skill
    if getattr(args, "custom", None):
        opts["custom_instructions"] = args.custom
    if getattr(args, "assembler", None):
        opts["assembler"] = args.assembler
    return opts


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="factory.cli",
                                description="YT Production Factory — Origin Loop + Tiny Timeline Lab")
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("new", help="Create a new job")
    n.add_argument("--type", choices=["short", "long"], required=True)
    n.add_argument("--topic", required=True, help='Topic, e.g. "How 70 warships sailed over dry land"')
    _add_option_args(n)

    a2 = sub.add_parser("auto", help="ONE CLICK: run a job end to end and make the video")
    a2.add_argument("--job", required=True)
    a2.add_argument("--fresh", action="store_true",
                    help="Re-do every step instead of resuming from the last checkpoint")
    _add_option_args(a2)

    ap = sub.add_parser("approve", help="Human approval for a needs-review job (marks it done + publishes to the library)")
    ap.add_argument("--job", required=True)
    ap.add_argument("--note", default="", help="Short note on what you reviewed")

    sub.add_parser("options", help="List every per-job option and which backends are installed")

    s = sub.add_parser("status", help="List jobs or show one job")
    s.add_argument("--job", default=None)

    sub.add_parser("credits", help="Show credit balances and estimates")

    v = sub.add_parser("voice", help="Prepare Charon voice files for a job")
    v.add_argument("--job", required=True)

    c = sub.add_parser("captions", help="Make captions.srt for a job")
    c.add_argument("--job", required=True)

    a = sub.add_parser("assemble", help="FFmpeg-assemble clips + voice")
    a.add_argument("--job", required=True)
    a.add_argument("--type", choices=["short", "long"], default="short")

    r = sub.add_parser("review", help="Supervisor review of a job (Gemini/AntiGravity CLI)")
    r.add_argument("--job", required=True)

    sub.add_parser("serve", help="Start the dashboard at http://localhost:8000")

    args = p.parse_args(argv)
    cfg = Config()

    if args.cmd == "new":
        job, job_dir = create_job(args.topic, args.type, cfg, _options_from_args(args))
        print(f"Job created: {job.slug}")
        print(f"  Channel: {job.channel} ({job.kind})")
        print(f"  Folder:  {job_dir}")
        print(f"  Options: {job.options}")
        print(f"  {credit_warning(args.type, cfg)}")
        print("  One click: python -m factory.cli auto --job " + job.slug)
        print("  Or open the dashboard and press Run on this job.")
        return 0

    if args.cmd == "auto":
        job_dir = _job_dir(args.job, cfg)
        job_json = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
        merged = dict(job_json.get("options") or {})
        merged.update(_options_from_args(args))
        opts = JobOptions.from_dict(merged, job_json.get("kind", "short"))
        print(f"Auto-run: {args.job}  ({opts.kind}, {opts.duration_sec}s, "
              f"{opts.aspect}, video={opts.video_backend}, audio={opts.audio_backend}, "
              f"supervisor={opts.supervisor_backend}, skill={opts.skill})")
        res = run_job_sync(args.job, cfg, opts, fresh=getattr(args, "fresh", False))
        print(res.get("message", res))
        if res.get("output"):
            print(f"Video: {res['output']}")
        if res.get("library"):
            print(f"Library: {res['library']['video']}")
        return 0 if res.get("status") == "done" else 1

    if args.cmd == "approve":
        _job_dir(args.job, cfg)
        res = approve_job(args.job, cfg, args.note)
        print(res.get("message", res))
        if res.get("library"):
            print(f"Library: {res['library']['video']}")
        return 0 if res.get("approved") else 1

    if args.cmd == "options":
        print("Per-job options (dashboard + CLI `new` / `auto` share these):")
        print(f"  video backends:  {', '.join(VIDEO_BACKENDS)}")
        print(f"  audio backends:  {', '.join(AUDIO_BACKENDS)}  (ElevenLabs is captions only — never voice)")
        print(f"  caption backends:{', '.join(CAPTION_BACKENDS)}")
        print(f"  supervisors:     {', '.join(SUPERVISOR_BACKENDS)}  (supervisor is Muse via the Gen AI SDK agent; gemini-cli/antigravity are manual fallback only)")
        from .options import ASSEMBLERS, detect_assemblers
        print(f"  assemblers:      {', '.join(ASSEMBLERS)}  (auto = FFmpeg; moviepy = slower Python timeline)")
        for name, info in detect_assemblers().items():
            print(f"    assembler/{name}: {'available' if info['available'] else 'NOT available'} — {info['note']}")
        print(f"  styles:          {', '.join(STYLES)}  (auto = cinematic-realistic for Shorts, 2.5d-cartoon for long-form)")
        from .skills import list_skills
        print("  skills (skills/*.md — pick per job with --skill):")
        for s in list_skills():
            print(f"    {s['name']} — {s['title']} [{s['kind']}]")
        print("  custom instructions: --custom \"...\" (per job, honoured by the supervisor, checked in QC)")
        print("Detected on this machine:")
        for name, info in detect_video_backends().items():
            print(f"  video/{name}: {'available' if info['available'] else 'NOT available'} — {info['note']}")
        for name, info in detect_audio_backends(cfg.gemini_api_key).items():
            print(f"  audio/{name}: {'available' if info['available'] else 'NOT available'} — {info['note']}")
        for name, info in detect_supervisor_backends(cfg.gemini_api_key, cfg.gemini_cli, cfg.antigravity_cli).items():
            print(f"  supervisor/{name}: {'available' if info['available'] else 'NOT available'} — {info['note']}")
        return 0

    if args.cmd == "status":
        jobs = list_jobs(cfg)
        if args.job:
            for j in jobs:
                if j["slug"] == args.job:
                    print(json.dumps(j, indent=2))
                    return 0
            print(f"Job not found: {args.job}")
            return 1
        if not jobs:
            print("No jobs yet. Create one:\n  python -m factory.cli new --type short --topic \"...\"")
            return 0
        for j in jobs:
            print(f"- {j['slug']}  [{j['kind']}] {j['topic']}  ({j['channel']}) "
                  f"status={j.get('status')} clips={j.get('clips', 0)} "
                  f"output={'yes' if j.get('has_output') else 'no'}")
        return 0

    if args.cmd == "credits":
        print(CreditLedger(cfg).summary())
        return 0

    if args.cmd == "voice":
        job_dir = _job_dir(args.job, cfg)
        script = _read_script(job_dir)
        files = write_voice_files(job_dir, script)
        print(f"Wrote {len(files)} act file(s) to {job_dir}/voice/")
        # Try API TTS only if a key is configured; otherwise manual steps.
        if cfg.gemini_api_key and files:
            out = job_dir / "voice" / "act-01.mp3"
            if synthesize_via_gemini(files[0].read_text(encoding="utf-8"), out, cfg):
                print(f"Gemini TTS (Charon) rendered: {out}")
            else:
                print("Gemini TTS failed — follow voice/HOW-TO-CHARON.md (AI Studio).")
        else:
            print("No GEMINI_API_KEY — follow voice/HOW-TO-CHARON.md in Google AI Studio.")
        return 0

    if args.cmd == "captions":
        job_dir = _job_dir(args.job, cfg)
        audio = next(iter(sorted((job_dir / "voice").glob("*.mp3"))), None)
        out = make_captions(job_dir, _read_script(job_dir), audio, cfg)
        print(f"Captions: {out}  (faster-whisper if installed, else estimated from script)")
        print("Hand-correct them in CapCut — never trust auto-captions blindly.")
        return 0

    if args.cmd == "assemble":
        job_dir = _job_dir(args.job, cfg)
        ok, msg = assemble(job_dir, args.type)
        print(msg)
        return 0 if ok else 1

    if args.cmd == "review":
        job_dir = _job_dir(args.job, cfg)
        print(run_supervisor_check(job_dir, cfg))
        return 0

    if args.cmd == "serve":
        run_server()
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
