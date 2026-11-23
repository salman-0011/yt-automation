"""Captions: faster-whisper (local, CPU) first; ElevenLabs captions API
only if a key is set; otherwise NO burned-in captions.

ElevenLabs is captions ONLY in this project — never voice.
faster-whisper `small` model: ~10 min audio in ~3-5 min on this laptop.
Always hand-correct auto-captions in CapCut — never trust them blindly.

v2.3 rule (from the 2/10 Constantinople review): captions are ONE
layer, bottom safe zone, max 2 lines, short cues synced to the real
narration. Timings guessed from script word count are NOT timings —
the old code burned those guessed, full-sentence cues on top of the
scene text and they overlapped it. So:
  * faster-whisper (real ASR timing) -> captions.srt (burned in).
  * no ASR available -> captions.srt is NOT written. The estimate is
    saved separately as captions-estimated.srt + captions-note.txt
    for hand-correction in CapCut, and assemble never burns it in.
    A video with no captions is better than one with wrong, overlapping
    captions. make_captions() returns None in that case.
"""
from __future__ import annotations

import re
from pathlib import Path

from .config import Config

MAX_CAPTION_LINE_CHARS = 42
MAX_CAPTION_LINES = 2


def _srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _split_cue(text: str, start: float, end: float) -> list[tuple[float, float, str]]:
    """Split one ASR segment into short cues: <=42 chars/line, <=2 lines.

    A cue is at most 2 lines of 42 chars (~84 chars). Duration is
    split proportionally by word count. Long single-sentence cues are
    what overlapped the scene text in the old render — they must not
    come back.
    """
    words = text.split()
    if not words:
        return []
    lines, cur = [], ""
    for w in words:
        cand = (cur + " " + w).strip() if cur else w
        if len(cand) <= MAX_CAPTION_LINE_CHARS:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    cues: list[tuple[float, float, str]] = []
    total_dur = max(0.3, end - start)
    i = 0
    while i < len(lines):
        chunk = lines[i:i + MAX_CAPTION_LINES]
        chunk_words = sum(len(l.split()) for l in chunk)
        dur = total_dur * chunk_words / max(1, len(words))
        cue_start = start + (sum(len(l.split()) for l in lines[:i]) / max(1, len(words))) * total_dur
        cues.append((cue_start, cue_start + max(0.3, dur), "\n".join(chunk)))
        i += MAX_CAPTION_LINES
    return cues


def srt_from_script(script: str, wpm: int = 152) -> str:
    """Estimate an SRT from the script — ESTIMATE ONLY, never burned in.

    Kept only so a human can hand-correct it in CapCut. Callers must
    save it as captions-estimated.srt, never as captions.srt.
    """
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script.strip()) if s.strip()]
    cues, t = [], 0.0
    for i, sent in enumerate(sentences, 1):
        dur = max(1.0, len(sent.split()) / wpm * 60.0)
        for j, (cs, ce, ctext) in enumerate(_split_cue(sent, t, t + dur)):
            cues.append(f"{len(cues) + 1}\n{_srt_time(cs)} --> {_srt_time(ce)}\n{ctext}\n")
        t += dur + 0.2
    return "\n".join(cues)


def has_real_captions(job_dir: Path) -> bool:
    """True only when captions.srt exists AND it is real ASR timing.

    The estimated file is marked by captions-note.txt; if that note
    exists, captions.srt must not be trusted (and make_captions no
    longer writes one in that case).
    """
    job_dir = Path(job_dir)
    if not (job_dir / "captions.srt").exists():
        return False
    if (job_dir / "captions-note.txt").exists():
        return False
    return True


def transcribe_with_faster_whisper(audio_path: Path, out_srt: Path,
                                   model: str = "small") -> bool:
    """Local CPU transcription with short, bottom-safe cues. Returns False if missing."""
    if not Path(audio_path).exists():
        return False
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        return False
    try:
        m = WhisperModel(model, device="cpu", compute_type="int8")
        segments, _ = m.transcribe(str(audio_path), language="en")
        cues: list[tuple[float, float, str]] = []
        for seg in segments:
            cues.extend(_split_cue(seg.text.strip(), float(seg.start), float(seg.end)))
        lines = []
        for i, (cs, ce, ctext) in enumerate(cues, 1):
            lines.append(f"{i}\n{_srt_time(cs)} --> {_srt_time(ce)}\n{ctext}\n")
        Path(out_srt).write_text("\n".join(lines), encoding="utf-8")
        return True
    except Exception:
        return False


def make_captions(job_dir: Path, script: str,
                  audio_path: Path | None = None,
                  config: Config | None = None) -> Path | None:
    """Best available captions for a job. Returns the SRT path, or None.

    Returns a path ONLY for real ASR timing (faster-whisper). With no
    ASR, writes captions-estimated.srt + captions-note.txt for
    hand-correction in CapCut and returns None — assemble then renders
    NO captions rather than guessing overlapping ones.
    """
    cfg = config or Config()
    job_dir = Path(job_dir)
    out = job_dir / "captions.srt"
    if audio_path and transcribe_with_faster_whisper(audio_path, out):
        (job_dir / "captions-note.txt").unlink(missing_ok=True)
        return out
    # No real timing: estimate for the human only, never for burning in.
    est = job_dir / "captions-estimated.srt"
    est.write_text(srt_from_script(script, cfg.voice_wpm), encoding="utf-8")
    had_note = (job_dir / "captions-note.txt").exists()
    (job_dir / "captions-note.txt").write_text(
        "NOTE: captions-estimated.srt timings are estimated from script "
        "word count — they are NOT real timings and are NEVER burned into "
        "the video. Install faster-whisper (pip install faster-whisper) "
        "and re-run for real captions, or hand-correct in CapCut.\n",
        encoding="utf-8")
    # A stale captions.srt that was itself estimated (marked by a
    # pre-existing note) must not be mistaken for real timing later.
    # A real ASR captions.srt (no note) is left alone for manual use.
    if had_note and out.exists():
        out.unlink()
    return None
