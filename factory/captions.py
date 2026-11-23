"""Captions: faster-whisper (local, CPU) first; ElevenLabs captions API
only if a key is set; otherwise a timed SRT estimated from the script.

ElevenLabs is captions ONLY in this project — never voice.
faster-whisper `small` model: ~10 min audio in ~3-5 min on this laptop.
Always hand-correct auto-captions in CapCut — never trust them blindly.
"""
from __future__ import annotations

import re
from pathlib import Path

from .config import Config


def _srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def srt_from_script(script: str, wpm: int = 152) -> str:
    """Estimate an SRT from the script (fallback when no audio/ASR is run).

    Splits on sentence boundaries; each cue's length comes from its word
    count at `wpm`. Clearly labelled as estimated — replace with
    faster-whisper output whenever audio exists.
    """
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script.strip()) if s.strip()]
    cues, t = [], 0.0
    for i, sent in enumerate(sentences, 1):
        dur = max(1.0, len(sent.split()) / wpm * 60.0)
        cues.append(f"{i}\n{_srt_time(t)} --> {_srt_time(t + dur)}\n{sent}\n")
        t += dur + 0.2
    # Pure SRT only — no NOTE header line: FFmpeg's subtitles filter
    # (libass) refuses to open an SRT whose first line is not a cue
    # number. The "estimated" warning lives in captions-note.txt instead.
    return "\n".join(cues)


def transcribe_with_faster_whisper(audio_path: Path, out_srt: Path,
                                   model: str = "small") -> bool:
    """Local CPU transcription. Returns False if the dep/audio is missing."""
    if not Path(audio_path).exists():
        return False
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        return False
    try:
        m = WhisperModel(model, device="cpu", compute_type="int8")
        segments, _ = m.transcribe(str(audio_path), language="en")
        lines = []
        for i, seg in enumerate(segments, 1):
            lines.append(f"{i}\n{_srt_time(seg.start)} --> {_srt_time(seg.end)}\n{seg.text.strip()}\n")
        Path(out_srt).write_text("\n".join(lines), encoding="utf-8")
        return True
    except Exception:
        return False


def make_captions(job_dir: Path, script: str,
                  audio_path: Path | None = None,
                  config: Config | None = None) -> Path:
    """Best available captions for a job. Returns the SRT path."""
    cfg = config or Config()
    out = Path(job_dir) / "captions.srt"
    if audio_path and transcribe_with_faster_whisper(audio_path, out):
        return out
    out.write_text(srt_from_script(script, cfg.voice_wpm), encoding="utf-8")
    (Path(job_dir) / "captions-note.txt").write_text(
        "NOTE: these timings are estimated from script word count. "
        "Replace with faster-whisper output after voice render, and "
        "hand-correct in CapCut — never trust auto-captions blindly.\n",
        encoding="utf-8")
    return out
