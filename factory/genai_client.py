"""Google Gen AI SDK client — the ONE way this app talks to Gemini.

The supervisor (Muse) uses the Google Gen AI SDK (`google-genai`
package, `from google import genai`), NOT the Gemini CLI or the
AntiGravity CLI. The CLIs have session-time and authentication
problems; the SDK with an API key is the stable alternative (the same
shape as OpenAI's Agents SDK: a client + tools the agent calls).

Models — only real Gen AI SDK models, no invented names:
  - Planning / script / supervision: ``gemini-2.5-flash`` (default,
    ``GEMINI_MODEL`` in .env can switch to ``gemini-2.5-pro``).
  - Voice (Charon TTS): ``gemini-2.5-flash-preview-tts`` (see voice.py).
  - Omni Flash / Neon are video-generation models inside Google Flow.
    They have NO public API, so they stay manual-only — the app
    prepares exact prompts, the user pastes them in Flow.
  - "Carbon" / "Hydrogen" are NOT Gen AI SDK models. If anyone
    mentions them, they are not used here; the models above are.

No key or no SDK installed is a normal setup state, not a crash:
every function here returns None / False and the caller falls back
to the job's own script.md or to a clear error.
"""
from __future__ import annotations

import json
import re

from .config import Config

TEXT_MODEL_DEFAULT = "gemini-2.5-flash"
TTS_MODEL = "gemini-2.5-flash-preview-tts"


def sdk_available() -> bool:
    """Is the google-genai package importable on this machine?"""
    try:
        import google.genai  # type: ignore  # noqa: F401
        return True
    except ImportError:
        return False


def sdk_ready(config: Config | None = None) -> bool:
    """SDK installed AND an API key is set — the agent can run."""
    cfg = config or Config()
    return bool(cfg.gemini_api_key) and sdk_available()


def get_client(config: Config | None = None):
    """Return a genai.Client, or None if the SDK / key is missing."""
    cfg = config or Config()
    if not cfg.gemini_api_key or not sdk_available():
        return None
    import google.genai  # type: ignore
    return google.genai.Client(api_key=cfg.gemini_api_key)


def generate_text(config: Config | None = None, prompt: str = "",
                  max_tokens: int = 4096, temperature: float = 0.7) -> str:
    """One text generation via the SDK. Returns '' on any failure."""
    cfg = config or Config()
    client = get_client(cfg)
    if client is None or not prompt:
        return ""
    try:
        resp = client.models.generate_content(
            model=cfg.gemini_model or TEXT_MODEL_DEFAULT,
            contents=prompt,
            config={"temperature": temperature,
                    "max_output_tokens": max_tokens},
        )
        text = (resp.text or "").strip()
        text = re.sub(r"^```.*$", "", text, flags=re.M).strip()
        text = re.sub(r"^#.*$", "", text, flags=re.M).strip()
        return text
    except Exception:
        return ""


def generate_json(config: Config | None = None, prompt: str = "",
                  max_tokens: int = 2048, temperature: float = 0.7) -> dict:
    """One JSON generation via the SDK (JSON response mode). {} on failure."""
    cfg = config or Config()
    client = get_client(cfg)
    if client is None or not prompt:
        return {}
    try:
        resp = client.models.generate_content(
            model=cfg.gemini_model or TEXT_MODEL_DEFAULT,
            contents=prompt,
            config={"temperature": temperature,
                    "max_output_tokens": max_tokens,
                    "response_mime_type": "application/json"},
        )
        text = (resp.text or "").strip()
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}
