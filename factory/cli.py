"""CLI: python -m factory.cli <command> ...

Commands:
  new --type short|long --topic "..."   create a job folder + prompts
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

from .captions import make_captions
from .config import Config
from .credits import CreditLedger
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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="factory.cli",
                                description="YT Production Factory — Origin Loop + Tiny Timeline Lab")
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("new", help="Create a new job")
    n.add_argument("--type", choices=["short", "long"], required=True)
    n.add_argument("--topic", required=True, help='Topic, e.g. "How 70 warships sailed over dry land"')

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
        job, job_dir = create_job(args.topic, args.type, cfg)
        print(f"Job created: {job.slug}")
        print(f"  Channel: {job.channel} ({job.kind})")
        print(f"  Folder:  {job_dir}")
        print(f"  {credit_warning(args.type, cfg)}")
        print("  Next: 1) fill prompts/demand-check.md  2) write script.md")
        print("       3) paste scene prompts from prompts/flow-prompts.txt into Flow")
        print("       4) python -m factory.cli assemble --job " + job.slug)
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
