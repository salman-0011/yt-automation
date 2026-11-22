"""Video assembly: FFmpeg, local, CPU-first.

Encoder choice (auto): Intel Quick Sync (h264_qsv) if FFmpeg has it,
else libx264 veryfast. 720p is the credit/quality sweet spot for Omni
Flash clips; export 1080x1920 (Short) / 1920x1080 (long) at 24 fps.
Loudness target -14 LUFS +/-1, true peak <= -1 dBTP (check in CapCut /
ffmpeg loudnorm on final export — this module prints the filter, it
does not pretend to master audio by itself).
No GPU required. No local Stable Diffusion / Blender in this path.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

SHORT_SIZE = "1080x1920"
LONG_SIZE = "1920x1080"
FPS = 24


def ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


def pick_encoder() -> str:
    """qsv if available, else libx264 veryfast. Never fails hard."""
    ff = ffmpeg_path()
    if not ff:
        return "libx264"
    try:
        out = subprocess.run([ff, "-hide_banner", "-encoders"],
                             capture_output=True, text=True, timeout=30).stdout
        if "h264_qsv" in out:
            return "h264_qsv"
    except Exception:
        pass
    return "libx264"


def build_assemble_command(job_dir: Path, kind: str = "short") -> list[str] | None:
    """FFmpeg concat command for clips/ + voice/. Returns None if nothing to assemble."""
    job_dir = Path(job_dir)
    clips = sorted((job_dir / "clips").glob("*.mp4"))
    voice = sorted((job_dir / "voice").glob("*.mp3"))
    if not clips:
        return None
    size = SHORT_SIZE if kind == "short" else LONG_SIZE
    enc = pick_encoder()
    enc_args = (["-c:v", "h264_qsv"] if enc == "h264_qsv"
                else ["-c:v", "libx264", "-preset", "veryfast"])
    lst = job_dir / "clips.txt"
    lst.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    # NOTE: clips.txt uses relative names; run ffmpeg with cwd=clips dir.
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
           "-i", str(lst), "-s", size, "-r", str(FPS)] + enc_args
    if voice:
        cmd += ["-i", str(voice[0]), "-c:a", "aac", "-shortest"]
    cmd += [str(job_dir / f"output-{kind}.mp4")]
    return cmd


def assemble(job_dir: Path, kind: str = "short") -> tuple[bool, str]:
    """Run the assemble command. Returns (ok, message)."""
    if not ffmpeg_path():
        return False, "ffmpeg not found. Install FFmpeg, then re-run assemble."
    cmd = build_assemble_command(job_dir, kind)
    if cmd is None:
        return False, ("No clips in jobs/<job>/clips/ yet. Generate the Omni "
                       "Flash clips first (see prompts/flow-prompts.txt), "
                       "then re-run assemble.")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        if r.returncode == 0:
            return True, f"Assembled: {job_dir}/output-{kind}.mp4"
        return False, f"FFmpeg failed: {r.stderr[-500:]}"
    except Exception as e:  # noqa: BLE001 - report, don't crash CLI
        return False, f"Assemble error: {e}"


def loudnorm_filter() -> str:
    return "loudnorm=I=-14:TP=-1.0:LRA=11"
