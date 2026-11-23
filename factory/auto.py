"""One-click auto runner — the central Project Manager in action.

The supervisor (supervisor.plan_job) plans: script + scenes.
This runner then executes, in order, with the pluggable backends:
  1. plan      — supervisor (Gemini API / CLI / none)
  2. script    — from job script.md, or Gemini-written (never generic)
  3. voice     — audio backends: gemini-tts (Charon) -> kokoro -> piper -> existing
  4. visuals   — video backends: motion-canvas -> manim -> code (Pillow+FFmpeg)
                 flow-manual is NOT a render backend (no public API)
  5. captions  — faster-whisper CPU if installed, else SRT from script timing
  6. assemble  — FFmpeg, Quick Sync if present else libx264 veryfast, 720p
  7. QC        — automated checks, logged; output only marked done if they pass

Progress is written to jobs/<slug>/job.json under "run" after every
step, so the dashboard (polling /api/jobs) shows it live. A full log
goes to jobs/<slug>/run-log.md and usage to jobs/<slug>/usage.json.
Runs in a background thread from the server; the CLI runs it in the
foreground. Only one run per job at a time.
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path

from .audio import render_audio
from .captions import make_captions
from .config import Config
from .credits import CreditLedger
from .options import JobOptions
from .pipeline import PIPELINE_STEPS
from .supervisor import plan_job
from .video import assemble_auto, pick_encoder
from .visuals import render_visuals

_RUN_LOCKS: dict[str, threading.Lock] = {}
_RUN_THREADS: dict[str, threading.Thread] = {}


def _lock(slug: str) -> threading.Lock:
    return _RUN_LOCKS.setdefault(slug, threading.Lock())


def _update_job(job_dir: Path, **fields) -> dict:
    p = Path(job_dir) / "job.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    run = data.setdefault("run", {})
    run.update(fields)
    run["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    data["status"] = fields.get("status", data.get("status", "created"))
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def _log(job_dir: Path, lines: list[str], text: str) -> None:
    lines.append(text)
    (Path(job_dir) / "run-log.md").write_text(
        "# Auto-run log\n\n" + "\n".join(f"- {l}" for l in lines) + "\n",
        encoding="utf-8")


def _probe(path: Path) -> dict:
    """ffprobe: duration + has audio/video streams. {} if ffprobe missing."""
    try:
        r = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                            "-show_format", "-show_streams", str(path)],
                           capture_output=True, text=True, timeout=120)
        info = json.loads(r.stdout)
        streams = info.get("streams", [])
        return {"duration": float(info.get("format", {}).get("duration", 0) or 0),
                "has_video": any(s.get("codec_type") == "video" for s in streams),
                "has_audio": any(s.get("codec_type") == "audio" for s in streams),
                "size": path.stat().st_size}
    except Exception:
        return {}


def run_job_sync(slug: str, cfg: Config | None = None,
                 options: JobOptions | None = None) -> dict:
    """Run one job end to end. Returns the final run dict (also in job.json)."""
    cfg = cfg or Config()
    job_dir = cfg.jobs_dir / slug
    if not job_dir.exists():
        return {"status": "error", "step": "start", "progress": 0,
                "message": f"Job not found: {slug}"}
    job_json = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    options = options or JobOptions.from_dict(job_json.get("options"), job_json.get("kind", "short"))
    topic = job_json.get("topic", slug)
    log: list[str] = []
    started = time.time()

    def step(name: str, pct: int, status: str = "running") -> None:
        _update_job(job_dir, step=name, progress=pct, status=status,
                    message=f"{name}…")
        _log(job_dir, log, f"{name} ({pct}%)")

    try:
        # 1. Supervisor plan -------------------------------------------
        step("01-plan-supervisor", 5)
        plan = plan_job(job_dir, topic, options, cfg)
        _log(job_dir, log, f"Supervisor: {plan['supervisor']}; script source: {plan['script_source'] or 'NONE'}")
        if not plan["script"] or not plan["scenes"]:
            msg = ("No script and no Gemini API key. Add a script to "
                   "jobs/<job>/script.md (under '## Clean script'), or set "
                   "GEMINI_API_KEY in .env so the supervisor can write one.")
            _update_job(job_dir, step="01-plan-supervisor", progress=5,
                        status="error", message=msg)
            _log(job_dir, log, "ERROR: " + msg)
            return {"status": "error", "step": "01-plan-supervisor", "progress": 5, "message": msg}
        script, scenes = plan["script"], plan["scenes"]
        (job_dir / "storyboard.md").write_text(
            "# Storyboard (auto-generated by supervisor)\n\n" +
            "\n".join(f"{i+1}. [{s['duration']}s] {s['narration']}\n   Visual: {s['visual']}\n"
                      for i, s in enumerate(scenes)), encoding="utf-8")

        # 2. Voice ------------------------------------------------------
        step("05-voice", 25)
        audio_path, audio_backend, audio_msg = render_audio(job_dir, script, options, cfg)
        _log(job_dir, log, f"Audio: {audio_backend or 'FAILED'} — {audio_msg}")
        if audio_path is None:
            _update_job(job_dir, step="05-voice", progress=25, status="error", message=audio_msg)
            return {"status": "error", "step": "05-voice", "progress": 25, "message": audio_msg}

        # 3. Visuals ----------------------------------------------------
        step("06-visuals", 45)
        clips, video_backend, visual_msg = render_visuals(job_dir, scenes, options)
        _log(job_dir, log, f"Visuals: {video_backend or 'FAILED'} — {visual_msg}")
        if not clips:
            _update_job(job_dir, step="06-visuals", progress=45, status="error", message=visual_msg)
            return {"status": "error", "step": "06-visuals", "progress": 45, "message": visual_msg}

        # 4. Captions ----------------------------------------------------
        step("07-captions", 65)
        caption_path = None
        caption_backend = "off"
        if options.captions and options.caption_backend != "off":
            caption_path = make_captions(job_dir, script, audio_path, cfg)
            caption_backend = ("script-srt" if (job_dir / "captions-note.txt").exists()
                               else "faster-whisper")
            _log(job_dir, log, f"Captions: {caption_backend} -> {caption_path.name}")
        else:
            _log(job_dir, log, "Captions: off (user choice)")

        # 5. Assemble ----------------------------------------------------
        step("08-assemble", 80)
        ok, out_path, assemble_msg = assemble_auto(job_dir, clips, audio_path,
                                                   caption_path, options, cfg)
        _log(job_dir, log, assemble_msg)
        if not ok or out_path is None:
            _update_job(job_dir, step="08-assemble", progress=80, status="error", message=assemble_msg)
            return {"status": "error", "step": "08-assemble", "progress": 80, "message": assemble_msg}

        # 6. QC ----------------------------------------------------------
        step("09-qc", 95)
        probe = _probe(out_path)
        checks = {
            "file_exists": out_path.exists() and out_path.stat().st_size > 0,
            "has_video": probe.get("has_video", False),
            "has_audio": probe.get("has_audio", False),
            "duration_ok": abs(probe.get("duration", 0) - options.duration_sec) <= max(10, options.duration_sec * 0.25),
            "encoder": pick_encoder(),
        }
        qc_pass = all([checks["file_exists"], checks["has_video"], checks["has_audio"]])
        _log(job_dir, log, f"QC: {checks} (duration {probe.get('duration', 0):.1f}s vs target {options.duration_sec}s)")
        # Record (auto visuals cost 0 Flow credits; Gemini TTS is API, not Omni credits).
        ledger = CreditLedger(cfg)
        flow_credits = 0 if video_backend != "flow-manual" else None
        (job_dir / "usage.json").write_text(json.dumps({
            "supervisor": plan["supervisor"], "script_source": plan["script_source"],
            "audio_backend": audio_backend, "video_backend": video_backend,
            "caption_backend": caption_backend, "flow_credits_spent": flow_credits,
            "omni_credits_estimate": 0,
            "note": "Auto visuals cost 0 Omni Flash credits. Flow credits only apply "
                    "if you later generate manual Flow clips (see prompts/flow-prompts.txt).",
            "elapsed_sec": round(time.time() - started, 1),
            "output": str(out_path), "qc": checks,
        }, indent=2), encoding="utf-8")

        status = "done" if qc_pass else "error"
        msg = (f"Done: {out_path.name} ({probe.get('duration', 0):.0f}s, "
               f"{probe.get('size', 0)//1024} KB)" if qc_pass else
               "QC failed: " + ", ".join(k for k, v in checks.items() if not v))
        _update_job(job_dir, step="09-qc", progress=100, status=status,
                    message=msg, output=str(out_path), qc=checks,
                    backends={"audio": audio_backend, "video": video_backend,
                              "captions": caption_backend,
                              "supervisor": plan["supervisor"]})
        _log(job_dir, log, msg)
        return {"status": status, "step": "09-qc", "progress": 100,
                "message": msg, "output": str(out_path), "qc": checks}
    except Exception as e:  # noqa: BLE001 - a failed run must be reported, not crash the server
        msg = f"Auto-run crashed: {e}"
        _update_job(job_dir, step="error", progress=0, status="error", message=msg)
        _log(job_dir, log, "ERROR: " + msg)
        return {"status": "error", "step": "error", "progress": 0, "message": msg}


def run_job_async(slug: str, cfg: Config | None = None,
                  options: JobOptions | None = None) -> dict:
    """Start a background run. Returns {started: bool, ...}."""
    cfg = cfg or Config()
    lock = _lock(slug)
    if not lock.acquire(blocking=False):
        return {"started": False, "message": f"A run for {slug} is already in progress."}
    job_dir = cfg.jobs_dir / slug
    _update_job(job_dir, step="queued", progress=0, status="running",
                message="Queued — supervisor starting…")

    def _target() -> None:
        try:
            run_job_sync(slug, cfg, options)
        finally:
            lock.release()

    t = threading.Thread(target=_target, daemon=True, name=f"auto-{slug}")
    _RUN_THREADS[slug] = t
    t.start()
    return {"started": True, "message": f"Auto-run started for {slug}. Watch the dashboard — it refreshes every 3 seconds."}


def run_status(slug: str, cfg: Config | None = None) -> dict:
    cfg = cfg or Config()
    p = cfg.jobs_dir / slug / "job.json"
    if not p.exists():
        return {"error": f"job not found: {slug}"}
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("run", {"status": data.get("status", "created"), "progress": 0})
