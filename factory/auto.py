"""One-click auto runner — Muse (supervisor) plans, Python executes.

ONE video at a time. No batch mode, no queue: a global lock means a
second Run waits (409) while one video is running. The runner is a
small state machine, not a swarm:

  created -> planning -> scripting -> voice -> visuals -> captions
          -> assembling -> qc -> done | needs-review | failed

Two drivers, ONE set of steps (factory/auto.py _Runner):
  1. The Muse supervisor AGENT (factory/agent.py, Google Gen AI SDK,
     proper tool-calling): when the SDK + API key are ready, the
     agent calls the seven tools in order — plan_angle, write_script,
     make_voice, make_visuals, make_captions, assemble_video, run_qc.
     The model decides content (angle, script); the tools do the work.
  2. The sequential runner below: if the agent loop is unavailable
     (no SDK / no key) or ends early, the same steps run in order
     here. Nothing is left half-done because the model stopped talking.

Patterns applied (from modern workflow automation):
  - Typed state: one job.json holds the whole run state; every step
    reads what it needs and writes what it produced. The graph (this
    file) decides control flow; the LLM decides content only.
  - Checkpoint after every step: job.json "run" records the step,
    progress and completed_steps, so a re-run resumes from the first
    incomplete step instead of starting over.
  - Idempotent steps: a step whose output already exists and is valid
    is skipped on resume (script, narration.mp3, scene clips, SRT,
    output mp4). Re-running never double-spends or double-renders.
  - Capped retries: transient failures (network / API) retry at most
    twice with backoff; deterministic failures fail fast into "failed".
  - Human-in-the-loop QC gate: the automated QC gate (factory/qc.py)
    must pass before a job is marked done. If it blocks, the job goes
    to "needs-review" — no library copy, not done — and a human
    approves (dashboard Approve button / CLI approve) after reviewing.
  - Audit log: run-log.md records every step, the real backend used,
    and every QC decision.

Steps, in order:
  1. plan_angle — Muse picks ONE angle first (demand PROCEED/REFRAME/DROP)
  2. write_script — from job script.md, or Muse via the Gen AI SDK (never generic)
  3. make_voice  — audio backends: gemini-tts (Charon) -> kokoro -> piper -> existing
  4. make_visuals — video backends: motion-canvas -> manim -> code (Pillow+FFmpeg)
                 flow-manual is NOT a render backend (no public API)
  5. make_captions — faster-whisper CPU if installed, else SRT from script timing
  6. assemble_video — FFmpeg (default) or MoviePy, Quick Sync if it really
                 works else libx264 veryfast, 720p
  7. run_qc     — monetisation QC gate (repetitive / generic / pronunciation)
  8. publish    — copy to output/<channel>/ with auto-numbering (never overwrite)
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import threading
import time
from pathlib import Path

from .audio import render_audio
from .captions import make_captions
from .config import Config
from .credits import CreditLedger
from .genai_client import sdk_ready
from .library import publish as publish_to_library
from .options import JobOptions
from .qc import run_qc
from .supervisor import (plan_angle_step, save_agent_angle, save_agent_script,
                         supervisor_label, write_script_step)
from .video import assemble_auto, pick_encoder
from .visuals import make_thumbnail, render_visuals

# One video at a time, across the whole app.
_GLOBAL_RUN_LOCK = threading.Lock()
_RUN_LOCKS: dict[str, threading.Lock] = {}
_RUN_THREADS: dict[str, threading.Thread] = {}
MAX_STEP_RETRIES = 2
STATES = ["created", "planning", "scripting", "voice", "visuals", "captions",
          "assembling", "qc", "needs-review", "done", "failed"]
AGENT_TOOL_ORDER = ["plan_angle", "write_script", "make_voice", "make_visuals",
                    "make_captions", "assemble_video", "run_qc"]


def _lock(slug: str) -> threading.Lock:
    return _RUN_LOCKS.setdefault(slug, threading.Lock())


def _options_hash(options: JobOptions) -> str:
    return hashlib.sha256(
        json.dumps(options.to_dict(), sort_keys=True).encode()).hexdigest()[:12]


def _update_job(job_dir: Path, **fields) -> dict:
    p = Path(job_dir) / "job.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    run = data.setdefault("run", {})
    run.update(fields)
    run["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if "status" in fields:
        data["status"] = fields["status"]
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


def _retry(fn, log: list[str], job_dir: Path, what: str):
    """Run fn(); retry transient failures at most twice, then raise."""
    last: Exception | None = None
    for attempt in range(1, MAX_STEP_RETRIES + 2):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - retry, then report
            last = e
            _log(job_dir, log, f"Retry {attempt}/{MAX_STEP_RETRIES + 1} for {what}: {e}")
            time.sleep(5 * attempt)
    raise last  # type: ignore[misc]


class _StepFail(Exception):
    """A step failed deterministically. Carries the failed-run dict fields."""

    def __init__(self, message: str, step: str, progress: int):
        super().__init__(message)
        self.message = message
        self.step = step
        self.progress = progress


class _Runner:
    """One job's run: the seven steps, callable by the agent or in order."""

    def __init__(self, slug: str, cfg: Config, options: JobOptions | None,
                 fresh: bool = False):
        self.slug = slug
        self.cfg = cfg
        self.job_dir = cfg.jobs_dir / slug
        self.job_json = json.loads((self.job_dir / "job.json").read_text(encoding="utf-8"))
        self.options = options or JobOptions.from_dict(
            self.job_json.get("options"), self.job_json.get("kind", "short"))
        self.topic = self.job_json.get("topic", slug)
        self.log_lines: list[str] = []
        self.started = time.time()
        run_state = self.job_json.get("run") or {}
        self.completed: set[str] = set(run_state.get("completed_steps") or [])
        if fresh or run_state.get("options_hash") != _options_hash(self.options):
            self.completed = set()  # options changed (or --fresh): re-do every step
        self.options_hash = _options_hash(self.options)
        # State produced by the steps, in order.
        self.angle: dict = {}
        self.skill_name = ""
        self.skill_text = ""
        self.custom = ""
        self.supervisor = ""
        self.script = ""
        self.script_source = ""
        self.scenes: list[dict] = []
        self.plan_done = False
        self.audio_path: Path | None = None
        self.audio_backend = ""
        self.clips: list = []
        self.video_backend = ""
        self.caption_path = None
        self.caption_backend = "off"
        self.out_path: Path | None = None
        self.thumb = None
        self.qc: dict | None = None
        self.final_result: dict | None = None

    # -- helpers ---------------------------------------------------------
    def log(self, text: str) -> None:
        _log(self.job_dir, self.log_lines, text)

    def checkpoint(self, step: str, pct: int, state: str, message: str = "",
                   **extra) -> None:
        if step:
            self.completed.add(step)
        _update_job(self.job_dir, step=step, progress=pct, status=state,
                    message=message, state=state, options_hash=self.options_hash,
                    completed_steps=sorted(self.completed), **extra)

    def step(self, name: str, pct: int, state: str) -> None:
        _update_job(self.job_dir, step=name, progress=pct, status="running",
                    message=f"{name}…", state=state, options_hash=self.options_hash,
                    completed_steps=sorted(self.completed))
        self.log(f"{name} ({pct}%)")

    def _save_angle_to_job(self) -> None:
        self.job_json["angle"] = self.angle
        (self.job_dir / "job.json").write_text(
            json.dumps(self.job_json, indent=2), encoding="utf-8")

    # -- step 1: angle ----------------------------------------------------
    def do_plan_angle(self, agent_args: dict | None = None) -> dict:
        """Pick the ONE angle. Returns {"angle", "dropped", "message"}."""
        from .scriptgen import clean_script_text, split_into_scenes
        from .skills import resolve_skill
        options, cfg = self.options, self.cfg
        if self.plan_done:
            # Already planned in this run (e.g. by the agent) — never
            # re-pick the angle, or the agent's angle would be overwritten.
            return {"angle": self.angle, "dropped": False, "message": "already planned"}
        if "plan" in self.completed and (self.job_dir / "angle.md").exists():
            self.log("plan: resumed — angle + script already planned, reusing")
            script = clean_script_text(self.job_dir)
            angle = json.loads((self.job_dir / "angle.json").read_text(encoding="utf-8")) \
                if (self.job_dir / "angle.json").exists() else {}
            scenes = split_into_scenes(script, 9 if options.kind == "short" else 44,
                                       float(options.duration_sec), cfg.voice_wpm) if script else []
            self.angle, self.script, self.scenes = angle, script, scenes
            self.script_source = "job-script (resumed)"
            self.supervisor = "Muse (resumed)"
            self.skill_name = resolve_skill(options.skill, options.kind)
            from .skills import load_skill
            self.skill_text = load_skill(self.skill_name)
            self.custom = getattr(options, "custom_instructions", "") or ""
            self._save_angle_to_job()
            self.plan_done = True
            return {"angle": angle, "dropped": False, "message": "resumed"}
        self.step("01-plan-supervisor", 5, "planning")
        if agent_args is not None:
            # The AGENT chose the angle; this step validates + saves it.
            from .skills import load_skill, resolve_skill
            self.skill_name = resolve_skill(options.skill, options.kind)
            self.skill_text = load_skill(self.skill_name)
            self.custom = getattr(options, "custom_instructions", "") or ""
            from .supervisor import save_job_inputs
            save_job_inputs(self.job_dir, self.skill_name, self.skill_text, self.custom)
            self.angle = save_agent_angle(self.job_dir, agent_args)
            self.supervisor = "Muse via Gen AI SDK (agent)"
        else:
            first = _retry(lambda: plan_angle_step(self.job_dir, self.topic, options, cfg),
                           self.log_lines, self.job_dir, "supervisor plan")
            self.angle = first["angle"]
            self.skill_name, self.skill_text = first["skill"], first["skill_text"]
            self.custom, self.supervisor = first["custom"], first["supervisor"]
        self._save_angle_to_job()
        self.plan_done = True
        self.log(f"Supervisor: {self.supervisor}; skill: {self.skill_name}; "
                 f"angle: {self.angle.get('angle', '')[:100]}; "
                 f"demand: {self.angle.get('demand_verdict', 'PENDING')}")
        if self.angle.get("demand_verdict") == "DROP":
            return {"angle": self.angle, "dropped": True,
                    "message": ("Demand check said DROP — this topic has no demand. "
                                "Job stopped before spending anything. Pick another topic.")}
        return {"angle": self.angle, "dropped": False, "message": "angle chosen"}

    # -- step 2: script ---------------------------------------------------
    def do_write_script(self, agent_script: str | None = None) -> dict:
        """Write the script + scenes. Returns {"script", "scenes", "source"}."""
        options, cfg = self.options, self.cfg
        if self.script and self.scenes:
            return {"script": self.script, "scenes": len(self.scenes),
                    "source": self.script_source}
        if agent_script is not None:
            script, scenes = save_agent_script(
                self.job_dir, self.topic, options, agent_script, self.angle)
            self.script, self.scenes = script, scenes
            self.script_source = "genai-sdk (agent)"
        else:
            script, source, scenes = write_script_step(
                self.job_dir, self.topic, options, cfg,
                self.skill_text, self.angle, self.custom)
            if not script or not scenes:
                msg = ("No script and no Gemini API key. Add a script to "
                       "jobs/<job>/script.md (under '## Clean script'), or set "
                       "GEMINI_API_KEY in .env so Muse can write one.")
                raise _StepFail(msg, "01-plan-supervisor", 5)
            self.script, self.script_source, self.scenes = script, source, scenes
        self.log(f"Script: {self.script_source}; {len(self.script.split())} words; "
                 f"{len(self.scenes)} scenes")
        self.checkpoint("plan", 10, "scripting", "plan done")
        return {"script": self.script, "scenes": len(self.scenes),
                "source": self.script_source}

    # -- step 3: voice ----------------------------------------------------
    def do_voice(self) -> dict:
        options, cfg = self.options, self.cfg
        audio_path = self.job_dir / "voice" / "narration.mp3"
        if ("voice" in self.completed and audio_path.exists()
                and audio_path.stat().st_size > 0):
            self.log("voice: resumed — reusing voice/narration.mp3")
            self.audio_path = audio_path
            self.audio_backend = (self.job_json.get("run") or {}).get("backends", {}).get("audio", "existing")
            return {"audio": str(audio_path), "backend": self.audio_backend}
        self.step("05-voice", 25, "voice")
        audio_path, audio_backend, audio_msg = render_audio(
            self.job_dir, self.script, options, cfg)
        self.log(f"Audio: {audio_backend or 'FAILED'} — {audio_msg}")
        if audio_path is None:
            raise _StepFail(audio_msg, "05-voice", 25)
        self.audio_path, self.audio_backend = audio_path, audio_backend
        self.checkpoint("voice", 30, "visuals", "voice done")
        return {"audio": str(audio_path), "backend": audio_backend}

    # -- step 4: visuals --------------------------------------------------
    def do_visuals(self) -> dict:
        options = self.options
        expected = len(self.scenes)
        existing_clips = sorted((self.job_dir / "clips").glob("auto-scene-*.mp4"))
        if ("visuals" in self.completed and len(existing_clips) >= expected
                and all(c.stat().st_size > 0 for c in existing_clips)):
            self.clips = existing_clips[:expected]
            self.video_backend = (self.job_json.get("run") or {}).get("backends", {}).get("video", "code")
            self.log(f"visuals: resumed — reusing {len(self.clips)} scene clips")
            return {"clips": len(self.clips), "backend": self.video_backend}
        self.step("06-visuals", 45, "visuals")
        clips, video_backend, visual_msg = render_visuals(
            self.job_dir, self.scenes, options)
        self.log(f"Visuals: {video_backend or 'FAILED'} — {visual_msg}")
        if not clips:
            raise _StepFail(visual_msg, "06-visuals", 45)
        self.clips, self.video_backend = clips, video_backend
        self.checkpoint("visuals", 55, "captions", "visuals done")
        return {"clips": len(clips), "backend": video_backend}

    # -- step 5: captions -------------------------------------------------
    def do_captions(self) -> dict:
        options, cfg = self.options, self.cfg
        if "captions" in self.completed and (self.job_dir / "captions.srt").exists():
            self.caption_path = self.job_dir / "captions.srt"
            self.caption_backend = ("script-srt" if (self.job_dir / "captions-note.txt").exists()
                                    else "faster-whisper")
            self.log("captions: resumed — reusing captions.srt")
            return {"captions": str(self.caption_path), "backend": self.caption_backend}
        if options.captions and options.caption_backend != "off":
            self.step("07-captions", 65, "captions")
            caption_path = make_captions(self.job_dir, self.script, self.audio_path, cfg)
            self.caption_path = caption_path
            self.caption_backend = ("script-srt" if (self.job_dir / "captions-note.txt").exists()
                                    else "faster-whisper")
            self.log(f"Captions: {self.caption_backend} -> {caption_path.name}")
            self.checkpoint("captions", 70, "assembling", "captions done")
            return {"captions": str(caption_path), "backend": self.caption_backend}
        self.log("Captions: off (user choice)")
        return {"captions": None, "backend": "off"}

    # -- step 6: assemble + thumbnail --------------------------------------
    def do_assemble(self) -> dict:
        options, cfg = self.options, self.cfg
        out_path = self.job_dir / f"output-{options.kind}.mp4"
        if ("assemble" in self.completed and out_path.exists()
                and out_path.stat().st_size > 0):
            self.log("assemble: resumed — reusing output mp4")
            self.out_path = out_path
        else:
            self.step("08-assemble", 80, "assembling")
            ok, out_path, assemble_msg = assemble_auto(
                self.job_dir, self.clips, self.audio_path, self.caption_path, options, cfg)
            self.log(assemble_msg)
            if not ok or out_path is None:
                raise _StepFail(assemble_msg, "08-assemble", 80)
            self.out_path = out_path
            self.checkpoint("assemble", 85, "qc", "assemble done")
        thumb = make_thumbnail(self.job_dir, self.topic, self.angle, options)
        self.thumb = thumb
        if thumb:
            self.log(f"Thumbnail: {thumb.name} (same angle as script)")
        return {"output": str(self.out_path),
                "thumbnail": str(thumb) if thumb else None}

    # -- step 7: QC gate + finish ------------------------------------------
    def do_qc(self) -> dict:
        options = self.options
        self.step("09-qc", 95, "qc")
        probe = _probe(self.out_path)
        qc = run_qc(self.job_dir, self.script, self.angle, self.scenes,
                    self.clips, self.audio_path, self.out_path,
                    float(options.duration_sec), options.custom_instructions)
        qc["media"] = {"has_video": probe.get("has_video", False),
                       "has_audio": probe.get("has_audio", False),
                       "duration_sec": probe.get("duration", 0),
                       "encoder": pick_encoder()}
        if not qc["media"]["has_video"] or not qc["media"]["has_audio"]:
            qc["blockers"].append("media check failed: output is missing video or audio.")
            qc["passed"] = False
        self.qc = qc
        blockers_txt = "\n".join(f"- {b}" for b in qc["blockers"]) or "- none"
        warnings_txt = "\n".join(f"- {w}" for w in qc["warnings"]) or "- none"
        (self.job_dir / "qc-report.md").write_text(
            "# QC report — pre-publish gate\n\n"
            f"Passed: {qc['passed']}\n\n## Blockers\n{blockers_txt}\n\n"
            f"## Warnings\n{warnings_txt}\n\n"
            f"## Details\n```json\n{json.dumps(qc['details'], indent=2)}\n```\n",
            encoding="utf-8")
        self.log(f"QC: passed={qc['passed']} blockers={len(qc['blockers'])} warnings={len(qc['warnings'])}")
        for b in qc["blockers"]:
            self.log("QC BLOCKER: " + b)
        for w in qc["warnings"]:
            self.log("QC warning: " + w)

        ledger = CreditLedger(self.cfg)
        usage = {
            "supervisor": self.supervisor or supervisor_label(options, self.cfg),
            "script_source": self.script_source,
            "skill": self.skill_name, "angle": self.angle.get("angle", ""),
            "demand_verdict": self.angle.get("demand_verdict", "PENDING"),
            "audio_backend": self.audio_backend, "video_backend": self.video_backend,
            "caption_backend": self.caption_backend, "flow_credits_spent": 0,
            "omni_credits_estimate": 0,
            "note": "Auto visuals cost 0 Omni Flash credits. Flow credits only apply "
                    "if you later generate manual Flow clips (see prompts/flow-prompts.txt).",
            "elapsed_sec": round(time.time() - self.started, 1),
            "output": str(self.out_path), "qc": qc,
        }
        (self.job_dir / "usage.json").write_text(json.dumps(usage, indent=2), encoding="utf-8")

        backends = {"audio": self.audio_backend, "video": self.video_backend,
                    "captions": self.caption_backend, "supervisor": usage["supervisor"]}
        if not qc["passed"]:
            msg = ("QC gate blocked this job: " + "; ".join(qc["blockers"][:2]) +
                   " — fix the issues and press Run again (it resumes from the "
                   "failed step), or review and Approve in the dashboard.")
            self.checkpoint("09-qc", 95, "needs-review", msg,
                            qc=qc, output=str(self.out_path), backends=backends)
            self.log(msg)
            self.final_result = {"status": "needs-review", "step": "09-qc",
                                 "progress": 95, "message": msg,
                                 "output": str(self.out_path), "qc": qc}
            return self.final_result

        library = publish_to_library(self.cfg.root, options.kind, self.out_path, self.thumb)
        self.log(f"Published to library: {library['video']}")
        msg = (f"Done: {self.out_path.name} ({probe.get('duration', 0):.0f}s, "
               f"{probe.get('size', 0)//1024} KB) — library: {library['video']}")
        self.checkpoint("09-qc", 100, "done", msg, output=str(self.out_path), qc=qc,
                        library=library, backends=backends)
        self.log(msg)
        self.final_result = {"status": "done", "step": "09-qc", "progress": 100,
                             "message": msg, "output": str(self.out_path),
                             "qc": qc, "library": library}
        return self.final_result

    # -- agent tools (wrappers around the steps) ---------------------------
    def _tool(self, fn):
        try:
            out = fn()
            return {"ok": True, **out}
        except _StepFail as e:
            self.checkpoint(e.step, e.progress, "failed", e.message)
            self.log("ERROR: " + e.message)
            return {"ok": False, "error": e.message}
        except Exception as e:  # noqa: BLE001 - tool errors go back to the model
            return {"ok": False, "error": str(e)}

    def tool_plan_angle(self, args: dict) -> dict:
        def _run():
            res = self.do_plan_angle(agent_args=args)
            if res["dropped"]:
                return {"angle": res["angle"].get("angle", ""),
                        "demand_verdict": "DROP", "message": res["message"]}
            return {"angle": res["angle"].get("angle", ""),
                    "demand_verdict": res["angle"].get("demand_verdict", "PENDING")}
        return self._tool(_run)

    def tool_write_script(self, args: dict) -> dict:
        def _run():
            res = self.do_write_script(agent_script=args.get("script", ""))
            return {"words": len(self.script.split()), "scenes": res["scenes"],
                    "source": res["source"]}
        return self._tool(_run)

    def tool_make_voice(self, args: dict) -> dict:
        return self._tool(lambda: self.do_voice())

    def tool_make_visuals(self, args: dict) -> dict:
        return self._tool(lambda: self.do_visuals())

    def tool_make_captions(self, args: dict) -> dict:
        return self._tool(lambda: self.do_captions())

    def tool_assemble_video(self, args: dict) -> dict:
        return self._tool(lambda: self.do_assemble())

    def tool_run_qc(self, args: dict) -> dict:
        def _run():
            res = self.do_qc()
            return {"status": res["status"], "qc_passed": bool(self.qc and self.qc.get("passed")),
                    "message": res["message"]}
        return self._tool(_run)

    # -- drivers -------------------------------------------------------------
    def run_sequential(self) -> dict:
        """Run the steps in order (used when the agent is unavailable)."""
        if self.final_result is not None:
            return self.final_result
        try:
            plan = self.do_plan_angle()
            if plan["dropped"]:
                msg = plan["message"]
                self.checkpoint("01-plan-supervisor", 5, "failed", msg)
                self.log("STOP: " + msg)
                return {"status": "failed", "step": "01-plan-supervisor",
                        "progress": 5, "message": msg}
            self.do_write_script()
            self.do_voice()
            self.do_visuals()
            self.do_captions()
            self.do_assemble()
            return self.do_qc()
        except _StepFail as e:
            self.checkpoint(e.step, e.progress, "failed", e.message)
            self.log("ERROR: " + e.message)
            return {"status": "failed", "step": e.step, "progress": e.progress,
                    "message": e.message}

    def run(self) -> dict:
        """Agent first (if the SDK is ready), then sequential for the rest."""
        options, cfg = self.options, self.cfg
        try:
            want = getattr(options, "supervisor_backend", "auto")
            if want in ("auto", "genai-sdk", "gemini-api") and sdk_ready(cfg):
                from .agent import run_agent_loop
                from .skills import load_skill, resolve_skill
                skill_name = resolve_skill(options.skill, options.kind)
                context = {
                    "topic": self.topic, "kind": options.kind,
                    "duration_sec": options.duration_sec, "aspect": options.aspect,
                    "style": options.style,
                    "skill_text": load_skill(skill_name),
                    "custom_instructions": options.custom_instructions or "(none)",
                }
                tools = {name: getattr(self, "tool_" + name)
                         for name in AGENT_TOOL_ORDER}
                self.log("Supervisor agent: Muse via Gen AI SDK (tool-calling) — "
                         "calling plan_angle, write_script, make_voice, make_visuals, "
                         "make_captions, assemble_video, run_qc in order.")
                res = run_agent_loop(tools, context, cfg, log_fn=self.log)
                self.log(f"Agent loop: used={res['used']} completed={res['completed']} — "
                         f"{res['reason']}")
                if res["completed"] and "run_qc" in res["completed"] and self.final_result:
                    return self.final_result
            else:
                self.log("Supervisor agent skipped (Gen AI SDK not ready or "
                         "supervisor=none/CLI) — sequential runner.")
            return self.run_sequential()
        except Exception as e:  # noqa: BLE001 - a failed run must be reported, not crash the server
            msg = f"Auto-run crashed: {e}"
            _update_job(self.job_dir, step="error", progress=0, status="failed",
                        message=msg, state="failed")
            self.log("ERROR: " + msg)
            return {"status": "failed", "step": "error", "progress": 0, "message": msg}


def run_job_sync(slug: str, cfg: Config | None = None,
                 options: JobOptions | None = None,
                 fresh: bool = False) -> dict:
    """Run one job end to end. Returns the final run dict (also in job.json).

    Resume: completed steps recorded in job.json are skipped (their
    outputs are reused) unless fresh=True or the options changed.
    """
    cfg = cfg or Config()
    job_dir = cfg.jobs_dir / slug
    if not job_dir.exists():
        return {"status": "error", "step": "start", "progress": 0,
                "message": f"Job not found: {slug}"}
    return _Runner(slug, cfg, options, fresh=fresh).run()


def approve_job(slug: str, cfg: Config | None = None, note: str = "") -> dict:
    """Human-in-the-loop approval for a needs-review job.

    The human has reviewed the output + QC report. Mark the job done
    and publish it to the channel library (if not already published).
    Nothing here re-renders — approval is a human decision, recorded.
    """
    cfg = cfg or Config()
    job_dir = cfg.jobs_dir / slug
    if not job_dir.exists():
        return {"approved": False, "message": f"Job not found: {slug}"}
    data = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    run = data.get("run") or {}
    if run.get("status") == "done":
        return {"approved": True, "message": "Already done.",
                "library": run.get("library")}
    out_name = f"output-{data.get('kind', 'short')}.mp4"
    out_path = job_dir / out_name
    if not out_path.exists():
        return {"approved": False, "message": "No finished output to approve yet."}
    options = JobOptions.from_dict(data.get("options"), data.get("kind", "short"))
    thumb = job_dir / "thumbnail.jpg"
    library = run.get("library") or publish_to_library(
        cfg.root, options.kind, out_path, thumb if thumb.exists() else None)
    _update_job(job_dir, step="09-qc", progress=100, status="done",
                message=f"Approved by human{': ' + note if note else ''}. "
                        f"Library: {library['video']}",
                state="done", library=library,
                approved_by_human=True)
    (job_dir / "run-log.md").write_text(
        (job_dir / "run-log.md").read_text(encoding="utf-8", errors="ignore")
        + f"\n- APPROVED by human{': ' + note if note else ''} — library: {library['video']}\n",
        encoding="utf-8")
    return {"approved": True, "message": f"Approved. Library: {library['video']}",
            "library": library}


def run_job_async(slug: str, cfg: Config | None = None,
                  options: JobOptions | None = None,
                  fresh: bool = False) -> dict:
    """Start a background run. Returns {started: bool, ...}.

    One video at a time: if any run is already in progress, this
    returns started=False instead of queueing a second video.
    """
    cfg = cfg or Config()
    if not _GLOBAL_RUN_LOCK.acquire(blocking=False):
        return {"started": False,
                "message": "Another video is already running. One video at a "
                           "time — wait for it to finish, then press Run."}
    lock = _lock(slug)
    if not lock.acquire(blocking=False):
        _GLOBAL_RUN_LOCK.release()
        return {"started": False, "message": f"A run for {slug} is already in progress."}
    job_dir = cfg.jobs_dir / slug
    _update_job(job_dir, step="queued", progress=0, status="running",
                message="Queued — Muse (supervisor) starting…", state="planning")

    def _target() -> None:
        try:
            run_job_sync(slug, cfg, options, fresh=fresh)
        finally:
            lock.release()
            _GLOBAL_RUN_LOCK.release()

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
