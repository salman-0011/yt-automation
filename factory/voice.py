"""Voiceover: Gemini Flash TTS (Charon) via API, else manual AI Studio.

Voice is ALWAYS Charon (Google AI Studio, masculine, low-pitched).
ElevenLabs is for captions ONLY — never use it for voice here.
If no API key is set, this module does NOT fake a voice file: it writes
exact manual steps + the script split into act files for AI Studio.
Local fallback (no credits, no API): Piper / Kokoro — documented in
README, not a default, because the channel voice must stay Charon.
"""
from __future__ import annotations

import json
import shutil
import urllib.request
from pathlib import Path

from .config import Config

CHARON_VOICE = "Charon"
MANUAL_STEPS = """CHARON VOICE — MANUAL STEPS (Google AI Studio, no API key needed)
  1. Open Google AI Studio -> Generate speech / TTS.
  2. Voice: Charon. Same voice on every video, never change it.
  3. Paste ONE act file at a time from jobs/<job>/voice/ (act-01.txt ...).
  4. Speed: brisk for Shorts (~145-165 wpm feel), natural ~152 wpm for long-form.
  5. Check EVERY difficult name against jobs/<job>/pronunciation.md before
     recording. If a name sounds wrong, re-record that line only.
  6. Save as act-01.mp3 ... into jobs/<job>/voice/ and run:
       python -m factory.cli captions --job <job>
       python -m factory.cli assemble --job <job>
Local fallback (voice will NOT match Charon — use only as a draft):
  Piper (CPU, offline): pip install piper-tts — pick an English male voice.
  Kokoro-82M (CPU): see README. Draft only; final must be Charon.
"""


def split_script_for_voice(script: str, words_per_chunk: int = 180) -> list[str]:
    """Split a script into act-sized chunks for TTS (AI Studio has limits)."""
    words = script.split()
    return [" ".join(words[i:i + words_per_chunk])
            for i in range(0, len(words), words_per_chunk)] or [""]


def write_voice_files(job_dir: Path, script: str) -> list[Path]:
    """Write act-*.txt files + manual steps. Returns the act files."""
    voice_dir = Path(job_dir) / "voice"
    voice_dir.mkdir(parents=True, exist_ok=True)
    chunks = split_script_for_voice(script)
    out = []
    for i, chunk in enumerate(chunks, 1):
        p = voice_dir / f"act-{i:02d}.txt"
        p.write_text(chunk, encoding="utf-8")
        out.append(p)
    (voice_dir / "HOW-TO-CHARON.md").write_text(MANUAL_STEPS, encoding="utf-8")
    return out


def synthesize_via_gemini(text: str, out_path: Path,
                          config: Config | None = None) -> bool:
    """Gemini Flash TTS via REST (needs GEMINI_API_KEY). Returns True on success.

    Guarded: if no key, or no network, or the API errors, returns False and
    the caller falls back to the manual Charon steps. Never raises for a
    missing key — a missing key is a normal setup state, not a crash.
    """
    cfg = config or Config()
    key = cfg.gemini_api_key
    if not key:
        return False
    try:
        import google.genai  # type: ignore  # optional dep
        client = google.genai.Client(api_key=key)
        resp = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=text,
            config={"response_modalities": ["AUDIO"],
                    "speech_config": {"voice_config": {
                        "prebuilt_voice_config": {"voice_name": CHARON_VOICE}}}},
        )
        data = resp.candidates[0].content.parts[0].inline_data.data
        import base64
        Path(out_path).write_bytes(base64.b64decode(data))
        return True
    except Exception:
        # Fall back to REST-free manual path; do not crash the pipeline.
        return _synthesize_via_rest(text, out_path, key)


def _synthesize_via_rest(text: str, out_path: Path, key: str) -> bool:
    try:
        body = json.dumps({
            "model": "gemini-2.5-flash-preview-tts",
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {
                                     "prebuiltVoiceConfig": {"voiceName": CHARON_VOICE}}}},
        }).encode()
        req = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.5-flash-preview-tts:generateContent?key=" + key,
            data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            payload = json.loads(r.read())
        b64 = payload["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
        import base64
        Path(out_path).write_bytes(base64.b64decode(b64))
        return True
    except Exception:
        return False


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None
