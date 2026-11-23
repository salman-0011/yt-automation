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


_ENCODER_CACHE: str | None = None


def pick_encoder() -> str:
    """qsv ONLY if a real QSV encode works, else libx264 veryfast.

    Listing h264_qsv in `ffmpeg -encoders` is NOT proof: on machines
    without Quick Sync hardware the encoder exists but fails to open
    ("Could not open encoder before EOF"). So we test-encode one frame
    before trusting it. Never fails hard — worst case is libx264.
    """
    global _ENCODER_CACHE
    if _ENCODER_CACHE:
        return _ENCODER_CACHE
    ff = ffmpeg_path()
    if not ff:
        _ENCODER_CACHE = "libx264"
        return _ENCODER_CACHE
    try:
        out = subprocess.run([ff, "-hide_banner", "-encoders"],
                             capture_output=True, text=True, timeout=30).stdout
        if "h264_qsv" in out:
            test = subprocess.run(
                [ff, "-y", "-v", "error", "-f", "lavfi", "-i",
                 "testsrc=duration=0.1:size=128x128:rate=24",
                 "-c:v", "h264_qsv", "-f", "null", "-"],
                capture_output=True, text=True, timeout=60)
            if test.returncode == 0:
                _ENCODER_CACHE = "h264_qsv"
                return _ENCODER_CACHE
    except Exception:
        pass
    _ENCODER_CACHE = "libx264"
    return _ENCODER_CACHE


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


def assemble_with_moviepy(job_dir: Path, clips: list, audio_path,
                          options, config=None) -> tuple[bool, object, str]:
    """Timeline assembly with MoviePy 2.x (CPU only — no GPU needed).

    MoviePy builds every frame in Python, so it is MUCH slower than
    FFmpeg for the same video (a 15-second slideshow took ~8 minutes
    on one CPU in published measurements). It is kept as a pluggable
    option for timeline work (cuts / ordering / fades) where Python
    control matters, not as the default. No TextClip / ImageMagick is
    used (Pillow makes the text), and no subtitles are burned in here
    — if captions are requested, the caller uses FFmpeg instead.
    Returns (ok, output_path_or_None, message).
    """
    job_dir = Path(job_dir)
    try:
        from moviepy import AudioFileClip, VideoFileClip, concatenate_videoclips  # type: ignore
    except ImportError:
        return False, None, "MoviePy is not installed (pip install moviepy)."
    if not clips:
        return False, None, "No scene clips to assemble."
    out = job_dir / f"output-{options.kind}.mp4"
    try:
        video_clips = [VideoFileClip(str(c)) for c in clips]
        final = concatenate_videoclips(video_clips, method="compose")
        if audio_path and Path(audio_path).exists():
            final = final.with_audio(AudioFileClip(str(audio_path)))
        final = final.with_duration(float(options.duration_sec))
        final.write_videofile(str(out), codec="libx264", audio_codec="aac",
                              fps=FPS, preset="veryfast", threads=2,
                              logger=None)
        for c in video_clips:
            c.close()
        if out.exists() and out.stat().st_size > 0:
            return True, out, (f"Assembled with MoviePy: {out} "
                               f"({options.size}, libx264, captions=no)")
        return False, None, "MoviePy assemble produced no output."
    except Exception as e:  # noqa: BLE001
        return False, None, f"MoviePy assemble failed: {e}"


def assemble_auto(job_dir: Path, clips: list, audio_path, caption_path,
                  options, config=None) -> tuple[bool, object, str]:
    """Assemble auto-rendered scene clips + narration + captions into one mp4.

    Returns (ok, output_path_or_None, message). Assembler: FFmpeg by
    default (fast, burned-in subtitles, loudnorm -14 LUFS); MoviePy
    only when options.assembler == "moviepy" AND no captions are
    requested (MoviePy cannot burn in subtitles here) — otherwise the
    run logs why FFmpeg was used instead. Encoder: Quick Sync
    if FFmpeg has it, else libx264 veryfast. 720p by default.
    """
    from .options import JobOptions  # local import: avoids a cycle at module load
    job_dir = Path(job_dir)
    options = options if isinstance(options, JobOptions) else JobOptions.from_dict(
        options if isinstance(options, dict) else {}, "short")
    assembler = getattr(options, "assembler", "auto") or "auto"
    if assembler == "moviepy" and not caption_path:
        ok, out, msg = assemble_with_moviepy(job_dir, clips, audio_path, options, config)
        if ok:
            return ok, out, msg
        # MoviePy failed — fall through to FFmpeg rather than failing the job.
        msg = f"MoviePy assemble failed ({msg}) — falling back to FFmpeg."
    elif assembler == "moviepy" and caption_path:
        msg = ("MoviePy cannot burn in subtitles — using FFmpeg for this job "
               "(captions are on).")
    else:
        msg = ""
    if not ffmpeg_path():
        return False, None, "ffmpeg not found. Install FFmpeg, then re-run."
    if not clips:
        return False, None, "No scene clips to assemble."
    size = options.size
    enc = pick_encoder()
    enc_args = (["-c:v", "h264_qsv"] if enc == "h264_qsv"
                else ["-c:v", "libx264", "-preset", "veryfast"])
    lst = job_dir / "clips" / "auto-clips.txt"
    lst.write_text("".join(f"file '{Path(c).name}'\n" for c in clips),
                   encoding="utf-8")
    # Clips live in clips/, so run ffmpeg with cwd=clips and relative names.
    out = job_dir / f"output-{options.kind}.mp4"
    vf = f"scale={options.width}:{options.height},format=yuv420p"
    if caption_path and Path(caption_path).exists():
        srt = str(Path(caption_path).resolve()).replace("\\", "/").replace(":", "\\:")
        vf += (f",subtitles='{srt}':force_style="
               "'Fontsize=22,PrimaryColour=&HFFFFFF&,OutlineColour=&H80000000&,"
               "BorderStyle=1,Outline=2,Alignment=2,MarginV=40'")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "auto-clips.txt",
           "-i", str(audio_path), "-vf", vf, "-r", "24"] + enc_args + [
           "-c:a", "aac", "-b:a", "128k",
           "-af", "loudnorm=I=-14:TP=-1.0:LRA=11,apad",
           "-t", str(options.duration_sec), str(out)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600,
                           cwd=job_dir / "clips")
        if r.returncode == 0 and out.exists() and out.stat().st_size > 0:
            return True, out, ((msg + " " if msg else "") + f"Assembled: {out} "
                               f"({options.size}, {enc}, captions="
                               f"{'yes' if caption_path else 'no'})")
        if out.exists() and out.stat().st_size == 0:
            out.unlink(missing_ok=True)  # never leave a 0-byte "output" behind
        return False, None, f"FFmpeg assemble failed: {r.stderr[-800:]}"
    except Exception as e:  # noqa: BLE001
        return False, None, f"Assemble error: {e}"


def loudnorm_filter() -> str:
    return "loudnorm=I=-14:TP=-1.0:LRA=11"
