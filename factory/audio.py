"""Pluggable audio backends — the supervisor picks, Python renders.

Registry order for "auto": gemini-tts -> kokoro -> piper -> existing.
"existing" means: voice/*.mp3 already in the job folder (e.g. Charon
recorded by hand in Google AI Studio). That is a real, supported path,
not a fallback hack — it is how a user keeps the exact Charon voice
while everything else runs automatically.

ElevenLabs is captions ONLY in this project. It is deliberately NOT
in this registry — never use it for voice.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .config import Config
from .options import JobOptions
from .voice import split_script_for_voice, synthesize_via_gemini, write_voice_files


def _concat_mp3s(parts: list[Path], out: Path) -> bool:
    """Concatenate mp3 parts with FFmpeg (re-encode, safe for mixed files)."""
    if not parts:
        return False
    if len(parts) == 1:
        out.write_bytes(parts[0].read_bytes())
        return True
    lst = out.parent / "concat.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    try:
        r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                            "-i", str(lst), "-c", "copy", str(out)],
                           capture_output=True, text=True, timeout=600, cwd=out.parent)
        if r.returncode == 0 and out.exists() and out.stat().st_size > 0:
            return True
    except Exception:
        pass
    # Last resort: byte-concatenation (works for same-encoder mp3s).
    try:
        with open(out, "wb") as f:
            for p in parts:
                f.write(p.read_bytes())
        return out.stat().st_size > 0
    except Exception:
        return False


def _gemini_tts(job_dir: Path, script: str, cfg: Config) -> tuple[Path | None, str]:
    chunks = split_script_for_voice(script)
    write_voice_files(job_dir, script)
    outs: list[Path] = []
    for i, chunk in enumerate(chunks, 1):
        out = Path(job_dir) / "voice" / f"act-{i:02d}.mp3"
        if synthesize_via_gemini(chunk, out, cfg):
            outs.append(out)
        else:
            return None, "gemini-tts failed (bad key / no network / API error)"
    final = Path(job_dir) / "voice" / "narration.mp3"
    if _concat_mp3s(outs, final):
        return final, "gemini-tts (Charon)"
    return None, "gemini-tts rendered acts but concat failed"


def _local_tts(job_dir: Path, script: str, engine: str) -> tuple[Path | None, str]:
    """Kokoro / Piper via their Python libs or CLIs. Draft voices only."""
    chunks = split_script_for_voice(script)
    write_voice_files(job_dir, script)
    outs: list[Path] = []
    for i, chunk in enumerate(chunks, 1):
        out = Path(job_dir) / "voice" / f"act-{i:02d}.mp3"
        ok = False
        if engine == "kokoro":
            ok = _kokoro_one(chunk, out)
        elif engine == "piper":
            ok = _piper_one(chunk, out)
        if not ok:
            return None, f"{engine} not installed or failed on act {i:02d}"
        outs.append(out)
    final = Path(job_dir) / "voice" / "narration.mp3"
    if _concat_mp3s(outs, final):
        return final, f"{engine} (draft voice — NOT Charon)"
    return None, f"{engine} rendered acts but concat failed"


def _kokoro_one(text: str, out: Path) -> bool:
    try:
        from kokoro import KPipeline  # type: ignore
        import soundfile as sf  # type: ignore
        pipe = KPipeline(lang_code="a")
        audio = b"".join(
            (chunk.audio.tobytes() if hasattr(chunk, "audio") else b"")
            for _, _, chunk in pipe(text, voice="af_heart"))
        if not audio:
            return False
        sf.write(str(out), __import__("numpy").frombuffer(audio, dtype="float32"),
                 24000)
        return out.exists() and out.stat().st_size > 0
    except Exception:
        pass
    # CLI attempt: `kokoro` reading stdin is not standard; try the pip package CLI.
    try:
        r = subprocess.run(["kokoro", "--text", text, "--output", str(out)],
                           capture_output=True, text=True, timeout=300)
        return r.returncode == 0 and out.exists() and out.stat().st_size > 0
    except Exception:
        return False


def _piper_one(text: str, out: Path) -> bool:
    exe = shutil.which("piper")
    if not exe:
        return False
    try:
        # Piper writes wav to stdout; convert to mp3 with FFmpeg.
        wav = out.with_suffix(".wav")
        p1 = subprocess.run([exe, "--model", "en_US-lessac-medium",
                             "--output_file", str(wav)],
                            input=text.encode(), capture_output=True, timeout=300)
        if p1.returncode != 0 or not wav.exists():
            return False
        r = subprocess.run(["ffmpeg", "-y", "-i", str(wav), "-c:a", "libmp3lame",
                            "-q:a", "4", str(out)],
                           capture_output=True, text=True, timeout=300)
        return r.returncode == 0 and out.exists() and out.stat().st_size > 0
    except Exception:
        return False


def _existing(job_dir: Path) -> tuple[Path | None, str]:
    parts = sorted((Path(job_dir) / "voice").glob("act-*.mp3"))
    if not parts:
        single = Path(job_dir) / "voice" / "narration.mp3"
        if single.exists():
            return single, "existing voice/narration.mp3"
        return None, "no voice/*.mp3 in the job folder yet"
    final = Path(job_dir) / "voice" / "narration.mp3"
    if _concat_mp3s(parts, final):
        return final, f"existing ({len(parts)} act mp3s)"
    return None, "existing act mp3s could not be joined"


def render_audio(job_dir: Path, script: str, options: JobOptions,
                 cfg: Config | None = None) -> tuple[Path | None, str, str]:
    """Return (narration_mp3 or None, backend_used, message).

    backend_used is the real backend name, or '' on failure.
    """
    cfg = cfg or Config()
    want = options.audio_backend
    order = ([want] if want != "auto" else
             ["gemini-tts", "kokoro", "piper", "existing"])
    errors: list[str] = []
    for backend in order:
        if backend == "gemini-tts":
            if not cfg.gemini_api_key:
                errors.append("gemini-tts: no GEMINI_API_KEY")
                continue
            path, msg = _gemini_tts(job_dir, script, cfg)
        elif backend in ("kokoro", "piper"):
            path, msg = _local_tts(job_dir, script, backend)
        elif backend == "existing":
            path, msg = _existing(job_dir)
        else:
            errors.append(f"unknown audio backend: {backend}")
            continue
        if path is not None:
            return path, backend, msg
        errors.append(msg)
    return None, "", "Audio failed: " + " | ".join(errors) + (
        ". Fix: set GEMINI_API_KEY in .env for Charon, install Kokoro/Piper, "
        "or put voice mp3s in the job folder and pick audio backend 'existing'.")
