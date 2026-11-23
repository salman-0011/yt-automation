"""Configuration: loads .env, keeps secrets out of code.

Two Google AI Pro accounts, Omni Flash only, Charon voice, ElevenLabs
captions only. Nothing here calls Google Flow / Veo / Nano Banana —
those have no public API (see README.md).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path = ROOT / ".env") -> None:
    """Tiny .env loader — no dependency on python-dotenv."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()


@dataclass
class Account:
    name: str
    starting_credits: int = 1000
    daily_credits: int = 50


@dataclass
class Config:
    """All settings. Change values in .env, never by editing code."""

    root: Path = ROOT
    # Channels — locked split, see MEMORY / skills.
    shorts_channel: str = "Origin Loop"          # Shorts ONLY
    longform_channel: str = "Tiny Timeline Lab"  # Long-form 8-10 min (+ Shorts as trailers)
    # Video generation — Omni Flash ONLY. Veo is NOT used (100 credits / 8s,
    # leaves 5 Dec). Omni Flash = 3 credits/sec at 720p.
    video_model: str = "omni-flash-1.2"
    video_credits_per_sec: float = 3.0
    # Voice — Google AI Studio, Charon, masculine low-pitched. Same voice always.
    voice_provider: str = "google-ai-studio"
    voice_name: str = "Charon"
    voice_wpm: int = 152
    # Captions — ElevenLabs ONLY (for captions, not voice).
    captions_provider: str = "elevenlabs"
    # Thumbnails / stills — Nano Banana, clean image, text added in CapCut.
    thumbnail_tool: str = "nano-banana"
    editor: str = "capcut-free"
    # Accounts
    accounts: list = field(default_factory=lambda: [Account("A"), Account("B")])
    # Local, CPU-first
    cpu_first: bool = True
    gpu_required: bool = False
    ffmpeg_encoder: str = os.environ.get("VIDEO_ENCODER", "auto")  # auto|qsv|libx264
    loudness_lufs: float = -14.0
    # Optional API keys — read ONLY from environment / .env, never hardcoded.
    gemini_api_key: str = os.environ.get("GEMINI_API_KEY", "")
    elevenlabs_api_key: str = os.environ.get("ELEVENLABS_API_KEY", "")
    gemini_cli: str = os.environ.get("GEMINI_CLI", "gemini")
    antigravity_cli: str = os.environ.get("ANTIGRAVITY_CLI", "antigravity")
    # Auto-run defaults (dashboard / CLI can override per job).
    default_video_backend: str = os.environ.get("AUTO_VIDEO_BACKEND", "auto")
    default_audio_backend: str = os.environ.get("AUTO_AUDIO_BACKEND", "auto")
    default_supervisor_backend: str = os.environ.get("SUPERVISOR_BACKEND", "auto")
    gemini_model: str = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    @property
    def jobs_dir(self) -> Path:
        return self.root / "jobs"

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    def total_starting_credits(self) -> int:
        return sum(a.starting_credits for a in self.accounts)

    def total_daily_credits(self) -> int:
        return sum(a.daily_credits for a in self.accounts)


def get_config() -> Config:
    return Config()
