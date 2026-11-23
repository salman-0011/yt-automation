"""Job options + pluggable tool backends.

Every choice the user makes per job lives here, in one place, so the
dashboard, the CLI and the auto-runner can never drift apart.

Video backends (pluggable, first available in the fallback order wins
when the user picks "auto"):
  code          — Pillow scene cards + kinetic text, FFmpeg zoompan Ken Burns.
                  Always available (Pillow + FFmpeg). Costs 0 Flow credits.
  motion-canvas — Motion Canvas project per scene, rendered with Node.
                  Needs Node + npm + @motion-canvas/cli installed.
  manim         — Manim scene per scene, 720p, CPU. Needs `manim` installed.
  flow-manual   — NOT a backend. Google Flow / Omni Flash has no public API.
                  The job folder still gets Flow prompts; the human pastes
                  them. Choosing this means: do NOT auto-render visuals.

Audio backends (pluggable):
  gemini-tts    — Gemini Flash TTS API, voice Charon. Needs GEMINI_API_KEY.
  kokoro        — Kokoro-82M, local CPU. Needs `kokoro` installed.
  piper         — Piper TTS, local CPU, offline. Needs `piper` installed.
  existing      — Use voice/*.mp3 already in the job folder (e.g. Charon
                  recorded by hand in Google AI Studio). No synthesis.
ElevenLabs is captions ONLY in this project — it is never a voice backend.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field

VIDEO_BACKENDS = ["auto", "code", "motion-canvas", "manim", "flow-manual"]
AUDIO_BACKENDS = ["auto", "gemini-tts", "kokoro", "piper", "existing"]
CAPTION_BACKENDS = ["auto", "faster-whisper", "script-srt", "off"]
SUPERVISOR_BACKENDS = ["auto", "gemini-api", "gemini-cli", "antigravity", "none"]
STYLES = ["2.5d-cartoon", "diagram", "cinematic-code", "map"]
ASPECTS = ["auto", "9:16", "16:9"]

# Fallback orders when the user picks "auto".
VIDEO_FALLBACK = ["motion-canvas", "manim", "code"]
AUDIO_FALLBACK = ["gemini-tts", "kokoro", "piper", "existing"]


def _has(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


def detect_video_backends() -> dict[str, dict]:
    """Live detection: what is actually installed on this machine."""
    return {
        "code": {"available": _has("PIL") and shutil.which("ffmpeg") is not None,
                 "note": "Pillow + FFmpeg. Always the safe fallback, 0 credits."},
        "motion-canvas": {"available": shutil.which("npx") is not None and shutil.which("node") is not None,
                          "note": "Needs Node + npm install in the job animation folder."},
        "manim": {"available": shutil.which("manim") is not None,
                  "note": "Needs `pip install manim`. 720p on this laptop."},
        "flow-manual": {"available": False,
                        "note": "No public API. Prompts are prepared; the human pastes them in Flow."},
    }


def detect_audio_backends(gemini_key: str = "") -> dict[str, dict]:
    return {
        "gemini-tts": {"available": bool(gemini_key),
                       "note": "Gemini Flash TTS API, voice Charon. Needs GEMINI_API_KEY."},
        "kokoro": {"available": _has("kokoro") or shutil.which("kokoro") is not None,
                   "note": "Local CPU Kokoro-82M. Draft voice — will NOT match Charon."},
        "piper": {"available": _has("piper") or shutil.which("piper") is not None,
                  "note": "Local CPU Piper, offline. Draft voice — will NOT match Charon."},
        "existing": {"available": True,
                     "note": "Use voice/*.mp3 already in the job folder (e.g. Charon from AI Studio)."},
    }


def detect_supervisor_backends(gemini_key: str = "", gemini_cli: str = "gemini",
                               antigravity_cli: str = "antigravity") -> dict[str, dict]:
    return {
        "gemini-api": {"available": bool(gemini_key),
                       "note": "Gemini API (GEMINI_API_KEY). Plans the job, writes the script."},
        "gemini-cli": {"available": shutil.which(gemini_cli) is not None,
                       "note": "Gemini CLI on PATH. Supervisor review only."},
        "antigravity": {"available": shutil.which(antigravity_cli) is not None,
                        "note": "AntiGravity CLI on PATH. Supervisor review only."},
        "none": {"available": True, "note": "No LLM supervisor — use the script.md already in the job."},
    }


@dataclass
class JobOptions:
    """Everything the dashboard lets the user choose per job."""
    kind: str = "short"            # short | long
    duration_sec: int = 40         # Short default 40; long default 540
    aspect: str = "auto"           # auto | 9:16 | 16:9 (auto = kind)
    style: str = "2.5d-cartoon"    # 2.5d-cartoon | diagram | cinematic-code | map
    video_backend: str = "auto"    # auto | code | motion-canvas | manim | flow-manual
    audio_backend: str = "auto"    # auto | gemini-tts | kokoro | piper | existing
    voice_name: str = "Charon"     # Charon always for final videos
    captions: bool = True
    caption_backend: str = "auto"  # auto | faster-whisper | script-srt | off
    supervisor_backend: str = "auto"  # auto | gemini-api | gemini-cli | antigravity | none
    language: str = "en"
    resolution: str = "720p"       # 720p on this laptop; 1080p is slow

    def __post_init__(self) -> None:
        if self.kind not in ("short", "long"):
            self.kind = "short"
        if self.aspect == "auto":
            self.aspect = "9:16" if self.kind == "short" else "16:9"
        if self.duration_sec <= 0:
            self.duration_sec = 40 if self.kind == "short" else 540
        if self.video_backend not in VIDEO_BACKENDS:
            self.video_backend = "auto"
        if self.audio_backend not in AUDIO_BACKENDS:
            self.audio_backend = "auto"
        if self.caption_backend not in CAPTION_BACKENDS:
            self.caption_backend = "auto"
        if self.supervisor_backend not in SUPERVISOR_BACKENDS:
            self.supervisor_backend = "auto"
        if self.style not in STYLES:
            self.style = "2.5d-cartoon"

    @property
    def width(self) -> int:
        return 720 if self.aspect == "9:16" else 1280

    @property
    def height(self) -> int:
        return 1280 if self.aspect == "9:16" else 720

    @property
    def size(self) -> str:
        return f"{self.width}x{self.height}"

    @classmethod
    def from_dict(cls, data: dict | None, kind: str = "short") -> "JobOptions":
        data = dict(data or {})
        data.setdefault("kind", kind)
        if "duration_sec" not in data:
            data["duration_sec"] = 40 if data.get("kind") == "short" else 540
        # Accept the dashboard's "captions" as bool or "on"/"off".
        cap = data.get("captions", True)
        if isinstance(cap, str):
            data["captions"] = cap.lower() in ("on", "true", "1", "yes")
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}
