"""Backend server: FastAPI if installed, stdlib fallback if not.

Serves:
  GET  /            -> dashboard (factory/static/index.html)
  GET  /api/jobs   -> JSON list of jobs (from jobs/*/job.json)
  GET  /api/jobs/<slug> -> one job + its files + credit estimate
  GET  /api/credits -> balances + estimates
  GET  /api/tools  -> tool status (installed / configured / manual-only)
  GET  /api/options -> every per-job option + live backend detection
  POST /api/jobs   -> create a new job (topic, kind, + all options)
  POST /api/jobs/<slug>/run -> ONE CLICK: start the auto-run in background
  GET  /api/jobs/<slug>/run -> live run progress (step, %, message, output)
  GET  /api/health -> {"ok": true}

Live updates: the dashboard polls /api/jobs every 3 seconds (simple,
reliable on a low-end laptop — no websockets, no SSE complexity).
Run:  python -m factory.server   then open http://localhost:8000
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .auto import run_job_async, run_status
from .config import Config
from .credits import CreditLedger
from .options import (AUDIO_BACKENDS, CAPTION_BACKENDS, STYLES, ASPECTS,
                      SUPERVISOR_BACKENDS, VIDEO_BACKENDS, JobOptions,
                      detect_audio_backends, detect_supervisor_backends,
                      detect_video_backends)
from .pipeline import create_job

try:
    from fastapi import FastAPI  # type: ignore
    from fastapi.responses import FileResponse, JSONResponse  # type: ignore
    from fastapi.staticfiles import StaticFiles  # type: ignore
    HAS_FASTAPI = True
except ImportError:
    FastAPI = None  # type: ignore
    HAS_FASTAPI = False

STATIC_DIR = Path(__file__).resolve().parent / "static"


def list_jobs(config: Config | None = None) -> list[dict]:
    cfg = config or Config()
    jobs = []
    if not cfg.jobs_dir.exists():
        return jobs
    for job_file in sorted(cfg.jobs_dir.glob("*/job.json")):
        try:
            data = json.loads(job_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        job_dir = job_file.parent
        files = sorted(p.name for p in job_dir.rglob("*") if p.is_file())
        data["files"] = files[:50]
        data["file_count"] = len(files)
        data["clips"] = len(list((job_dir / "clips").glob("*.mp4")))
        data["has_output"] = any(job_dir.glob("output-*.mp4"))
        try:
            data["created"] = job_file.stat().st_mtime
        except OSError:
            data["created"] = 0
        jobs.append(data)
    return jobs


def options_payload(config: Config | None = None) -> dict:
    """Everything the dashboard lets the user choose, with live detection."""
    cfg = config or Config()
    return {
        "kinds": ["short", "long"],
        "aspects": ASPECTS,
        "styles": STYLES,
        "video_backends": VIDEO_BACKENDS,
        "audio_backends": AUDIO_BACKENDS,
        "caption_backends": CAPTION_BACKENDS,
        "supervisor_backends": SUPERVISOR_BACKENDS,
        "detected": {
            "video": detect_video_backends(),
            "audio": detect_audio_backends(cfg.gemini_api_key),
            "supervisor": detect_supervisor_backends(
                cfg.gemini_api_key, cfg.gemini_cli, cfg.antigravity_cli),
        },
        "defaults": JobOptions(kind="short").to_dict(),
        "defaults_long": JobOptions(kind="long").to_dict(),
    }


def tool_status(config: Config | None = None) -> list[dict]:
    """Honest status per tool. 'manual' = no public API, human opens it."""
    import shutil

    cfg = config or Config()
    ffmpeg = shutil.which("ffmpeg") is not None
    detected_video = detect_video_backends()
    detected_audio = detect_audio_backends(cfg.gemini_api_key)
    return [
        {"name": "Supervisor (Gemini API)", "kind": "supervisor",
         "status": "configured" if cfg.gemini_api_key else "not-configured",
         "note": "Central Project Manager. Plans the job + writes the script. Needs GEMINI_API_KEY."},
        {"name": "Gemini CLI", "kind": "supervisor",
         "status": "installed" if shutil.which(cfg.gemini_cli) else "not-installed",
         "note": "LLM supervisor. Run `gemini` in terminal, or use Tools card."},
        {"name": "AntiGravity CLI", "kind": "supervisor",
         "status": "installed" if shutil.which(cfg.antigravity_cli) else "not-installed",
         "note": "Alternative supervisor CLI."},
        {"name": "Google Flow", "kind": "video", "status": "manual",
         "note": "NO public API. App prepares exact prompts; you paste them in Flow."},
        {"name": "Omni Flash", "kind": "video", "status": "manual",
         "note": "3 credits/sec at 720p, inside Flow. Check Flow cost screen first."},
        {"name": "Nano Banana", "kind": "thumbnail", "status": "manual",
         "note": "NO public API. Clean image only, text added in CapCut."},
        {"name": "Auto visuals — code (Pillow + FFmpeg)", "kind": "video",
         "status": "installed" if detected_video["code"]["available"] else "not-installed",
         "note": "Scene cards + kinetic text + Ken Burns zoom. 0 Flow credits."},
        {"name": "Charon TTS (Gemini API)", "kind": "voice",
         "status": "configured" if cfg.gemini_api_key else "manual",
         "note": "Voice = Charon always. API if GEMINI_API_KEY set, else AI Studio by hand."},
        {"name": "Kokoro TTS (local, draft voice)", "kind": "voice",
         "status": "installed" if detected_audio["kokoro"]["available"] else "not-installed",
         "note": "Local CPU. Draft only — will NOT match Charon."},
        {"name": "Piper TTS (local, draft voice)", "kind": "voice",
         "status": "installed" if detected_audio["piper"]["available"] else "not-installed",
         "note": "Local CPU, offline. Draft only — will NOT match Charon."},
        {"name": "ElevenLabs captions", "kind": "captions",
         "status": "configured" if cfg.elevenlabs_api_key else "not-configured",
         "note": "Captions ONLY, never voice. Local faster-whisper is the default."},
        {"name": "Motion Canvas", "kind": "animation",
         "status": "installed" if detected_video["motion-canvas"]["available"] else "not-installed",
         "note": "2.5D cartoon / diagram motion. Needs Node + npm; scaffold in jobs/<job>/animation/."},
        {"name": "Manim", "kind": "animation",
         "status": "installed" if detected_video["manim"]["available"] else "not-installed",
         "note": "Mechanism animations, 720p on this laptop."},
        {"name": "faster-whisper", "kind": "captions",
         "status": "installed" if _has("faster_whisper") else "not-installed",
         "note": "Local CPU captions. pip install faster-whisper."},
        {"name": "FFmpeg", "kind": "assemble",
         "status": "installed" if ffmpeg else "not-installed",
         "note": "Local assembly. Quick Sync if available, else libx264 veryfast."},
    ]


def _has(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


def create_app(config: Config | None = None):
    """FastAPI app, or None if FastAPI is not installed."""
    if not HAS_FASTAPI:
        return None
    cfg = config or Config()
    app = FastAPI(title="YT Production Factory",
                  description="Origin Loop (Shorts) + Tiny Timeline Lab (long-form)")

    @app.get("/api/health")
    def health():
        return {"ok": True, "version": "2.0.0"}

    @app.get("/api/options")
    def options():
        return options_payload(cfg)

    @app.post("/api/jobs/{slug}/run")
    def run_job(slug: str, payload: dict | None = None):
        job_dir = cfg.jobs_dir / slug
        if not job_dir.exists():
            return JSONResponse({"error": f"job not found: {slug}"}, status_code=404)
        opts = None
        if payload:
            job_json = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
            merged = dict(job_json.get("options") or {})
            merged.update({k: v for k, v in payload.items() if v not in (None, "")})
            opts = JobOptions.from_dict(merged, job_json.get("kind", "short"))
            (job_dir / "options.json").write_text(json.dumps(opts.to_dict(), indent=2),
                                                  encoding="utf-8")
            job_json["options"] = opts.to_dict()
            (job_dir / "job.json").write_text(json.dumps(job_json, indent=2),
                                              encoding="utf-8")
        res = run_job_async(slug, cfg, opts)
        return res if res.get("started") else JSONResponse(res, status_code=409)

    @app.get("/api/jobs/{slug}/run")
    def run_progress(slug: str):
        return run_status(slug, cfg)

    @app.get("/api/jobs")
    def jobs():
        return {"jobs": list_jobs(cfg)}

    @app.get("/api/jobs/{slug}")
    def job_detail(slug: str):
        for j in list_jobs(cfg):
            if j.get("slug") == slug:
                return j
        return JSONResponse({"error": f"job not found: {slug}"}, status_code=404)

    @app.get("/api/credits")
    def credits():
        ledger = CreditLedger(cfg)
        return {"balances": ledger.balances(), "total": ledger.total_balance(),
                "short_estimate": ledger.estimate_short(),
                "long_estimate": ledger.estimate_long()}

    @app.get("/api/tools")
    def tools():
        return {"tools": tool_status(cfg)}

    @app.post("/api/jobs")
    def new_job(payload: dict):
        topic = (payload.get("topic") or "").strip()
        kind = (payload.get("kind") or "short").lower()
        if not topic:
            return JSONResponse({"error": "topic is required"}, status_code=400)
        if kind not in ("short", "long"):
            return JSONResponse({"error": "kind must be short or long"}, status_code=400)
        opts = {k: payload.get(k) for k in
                ("duration_sec", "aspect", "style", "video_backend",
                 "audio_backend", "voice_name", "captions", "caption_backend",
                 "supervisor_backend", "language", "resolution")
                if payload.get(k) not in (None, "")}
        if isinstance(opts.get("duration_sec"), str):
            try:
                opts["duration_sec"] = int(opts["duration_sec"])
            except ValueError:
                opts.pop("duration_sec")
        job, job_dir = create_job(topic, kind, cfg, opts)
        return {"job": job.to_dict(), "path": str(job_dir)}

    if STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    return app


# --- stdlib fallback server (no FastAPI needed) -------------------------
def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Serve the dashboard. FastAPI+uvicorn if available, else stdlib."""
    cfg = Config()
    if HAS_FASTAPI:
        try:
            import uvicorn  # type: ignore
            uvicorn.run(create_app(cfg), host=host, port=port, log_level="info")
            return
        except ImportError:
            pass
    # Fallback: pure stdlib, same /api/* routes, same static files.
    import http.server
    import urllib.parse

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _json(self, obj, code=200):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/api/health":
                return self._json({"ok": True, "version": "2.0.0"})
            if parsed.path == "/api/options":
                return self._json(options_payload(cfg))
            if parsed.path == "/api/jobs":
                return self._json({"jobs": list_jobs(cfg)})
            if parsed.path.endswith("/run") and parsed.path.startswith("/api/jobs/"):
                slug = parsed.path.split("/")[-2]
                return self._json(run_status(slug, cfg))
            if parsed.path.startswith("/api/jobs/"):
                slug = parsed.path.split("/")[-1]
                for j in list_jobs(cfg):
                    if j.get("slug") == slug:
                        return self._json(j)
                return self._json({"error": f"job not found: {slug}"}, 404)
            if parsed.path == "/api/credits":
                ledger = CreditLedger(cfg)
                return self._json({"balances": ledger.balances(),
                                   "total": ledger.total_balance(),
                                   "short_estimate": ledger.estimate_short(),
                                   "long_estimate": ledger.estimate_long()})
            if parsed.path == "/api/tools":
                return self._json({"tools": tool_status(cfg)})
            # static dashboard
            path = parsed.path.lstrip("/") or "index.html"
            f = STATIC_DIR / path
            if f.is_file():
                return super().do_GET()
            self.path = "/index.html"
            return super().do_GET()

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path.endswith("/run") and parsed.path.startswith("/api/jobs/"):
                slug = parsed.path.split("/")[-2]
                length = int(self.headers.get("Content-Length") or 0)
                try:
                    payload = json.loads(self.rfile.read(length) or b"{}")
                except json.JSONDecodeError:
                    payload = {}
                job_dir = cfg.jobs_dir / slug
                if not job_dir.exists():
                    return self._json({"error": f"job not found: {slug}"}, 404)
                opts = None
                if payload:
                    job_json = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
                    merged = dict(job_json.get("options") or {})
                    merged.update({k: v for k, v in payload.items() if v not in (None, "")})
                    opts = JobOptions.from_dict(merged, job_json.get("kind", "short"))
                    (job_dir / "options.json").write_text(json.dumps(opts.to_dict(), indent=2), encoding="utf-8")
                    job_json["options"] = opts.to_dict()
                    (job_dir / "job.json").write_text(json.dumps(job_json, indent=2), encoding="utf-8")
                res = run_job_async(slug, cfg, opts)
                return self._json(res, 200 if res.get("started") else 409)
            if parsed.path == "/api/jobs":
                length = int(self.headers.get("Content-Length") or 0)
                try:
                    payload = json.loads(self.rfile.read(length) or b"{}")
                except json.JSONDecodeError:
                    return self._json({"error": "invalid JSON"}, 400)
                topic = (payload.get("topic") or "").strip()
                kind = (payload.get("kind") or "short").lower()
                if not topic:
                    return self._json({"error": "topic is required"}, 400)
                if kind not in ("short", "long"):
                    return self._json({"error": "kind must be short or long"}, 400)
                opts = {k: payload.get(k) for k in
                        ("duration_sec", "aspect", "style", "video_backend",
                         "audio_backend", "voice_name", "captions", "caption_backend",
                         "supervisor_backend", "language", "resolution")
                        if payload.get(k) not in (None, "")}
                if isinstance(opts.get("duration_sec"), str):
                    try:
                        opts["duration_sec"] = int(opts["duration_sec"])
                    except ValueError:
                        opts.pop("duration_sec")
                job, job_dir = create_job(topic, kind, cfg, opts)
                return self._json({"job": job.to_dict(), "path": str(job_dir)})
            return self._json({"error": "not found"}, 404)

    import os as _os
    _os.chdir(STATIC_DIR)
    print(f"Factory dashboard: http://{host}:{port}  (stdlib server, no FastAPI)")
    http.server.ThreadingHTTPServer((host, port), Handler).serve_forever()


def main() -> None:
    host = os.environ.get("FACTORY_HOST", "127.0.0.1")
    port = int(os.environ.get("FACTORY_PORT", "8000"))
    print(f"Starting YT Production Factory dashboard on http://{host}:{port}")
    print("Open that URL in your browser. Ctrl+C to stop.")
    run_server(host, port)


if __name__ == "__main__":
    main()
