"""Pluggable video backends — the supervisor picks, Python renders.

  code          — Pillow scene cards (gradient + big kinetic title text +
                  simple explanatory shapes) rendered to stills, then
                  FFmpeg zoompan Ken Burns motion per scene. Always
                  available, 0 Flow credits, CPU-only.
  motion-canvas — Motion Canvas project per scene; rendered with Node.
                  Falls back to "code" if Node / render fails.
  manim         — Manim scene per scene, 720p. Falls back to "code".
  flow-manual   — NOT a render backend. Flow has no public API; the job
                  folder keeps Flow prompts for the human. Auto-run with
                  this backend stops with a clear message.

Every backend returns scene mp4s in jobs/<job>/clips/auto-scene-NN.mp4
plus a log of which backend actually rendered each scene. Nothing here
pretends a manual step happened.
"""
from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

from .options import JobOptions

# 2.5D cartoon palette: bright fills, dark text, big banners.
PALETTE = [
    ((15, 23, 42), (56, 189, 248)),   # dark blue / sky
    ((30, 27, 75), (251, 191, 36)),   # indigo / amber
    ((12, 74, 110), (52, 211, 153)),  # teal / green
    ((69, 26, 3), (253, 224, 71)),    # brown / yellow
    ((76, 29, 149), (244, 114, 182)), # purple / pink
]


def _scene_card(text: str, path: Path, width: int, height: int,
                idx: int, style: str) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except ImportError:
        return False
    bg, accent = PALETTE[idx % len(PALETTE)]
    img = Image.new("RGB", (width, height), bg)
    d = ImageDraw.Draw(img)
    # Accent banner at top, big arrow shape at the bottom (diagram feel).
    d.rectangle([0, 0, width, int(height * 0.10)], fill=accent)
    d.polygon([(width * 0.42, height * 0.88), (width * 0.58, height * 0.88),
               (width * 0.50, height * 0.96)], fill=accent)
    d.ellipse([width * 0.08, height * 0.82, width * 0.16, height * 0.90],
              outline=accent, width=6)
    try:
        font_big = ImageFont.truetype("DejaVuSans-Bold.ttf", int(height * 0.055))
        font_small = ImageFont.truetype("DejaVuSans.ttf", int(height * 0.032))
    except Exception:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()
    wrap = max(8, width // (int(height * 0.055) // 2 + 1))
    lines = textwrap.wrap(text, width=wrap)[:8]
    y = int(height * 0.18)
    for line in lines:
        d.text((width * 0.08, y), line, font=font_big, fill=(255, 255, 255))
        y += int(height * 0.075)
    d.text((width * 0.08, int(height * 0.76)),
           f"Scene {idx + 1}  •  {style}", font=font_small, fill=accent)
    img.save(path)
    return True


def _zoompan_clip(still: Path, out: Path, duration: float,
                  width: int, height: int) -> bool:
    """One still -> one moving clip (slow zoom-in, Ken Burns)."""
    frames = max(24, int(duration * 24))
    filt = (f"scale={width*2}:{height*2},"
            f"zoompan=z='min(zoom+0.0012,1.18)':d={frames}:s={width}x{height}:fps=24,"
            f"format=yuv420p")
    try:
        r = subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", str(still),
                            "-vf", filt, "-t", str(duration),
                            "-c:v", "libx264", "-preset", "veryfast",
                            "-pix_fmt", "yuv420p", str(out)],
                           capture_output=True, text=True, timeout=600)
        return r.returncode == 0 and out.exists() and out.stat().st_size > 0
    except Exception:
        return False


def render_code(job_dir: Path, scenes: list[dict], options: JobOptions) -> tuple[list[Path], str]:
    """Pillow + FFmpeg backend. Returns (scene clips, log line)."""
    job_dir = Path(job_dir)
    stills = job_dir / "stills" / "auto"
    stills.mkdir(parents=True, exist_ok=True)
    clips_dir = job_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    clips: list[Path] = []
    for i, scene in enumerate(scenes):
        still = stills / f"scene-{i+1:02d}.png"
        if not _scene_card(scene["visual"], still, options.width, options.height,
                           i, options.style):
            return clips, "code backend failed: Pillow is not installed (pip install pillow)"
        clip = clips_dir / f"auto-scene-{i+1:02d}.mp4"
        if not _zoompan_clip(still, clip, float(scene["duration"]),
                             options.width, options.height):
            return clips, f"code backend failed: FFmpeg zoompan failed on scene {i+1}"
        clips.append(clip)
    return clips, f"code backend rendered {len(clips)} scene clips (Pillow + FFmpeg zoompan)"


def render_motion_canvas(job_dir: Path, scenes: list[dict],
                         options: JobOptions) -> tuple[list[Path], str]:
    """Try Motion Canvas; fall back to code on any failure (logged)."""
    import shutil
    if shutil.which("node") is None or shutil.which("npx") is None:
        clips, log = render_code(job_dir, scenes, options)
        return clips, "motion-canvas not available (no Node) — fell back to code. " + log
    # Write one scene file per scene, then try a render. If the render
    # fails for any reason, fall back to code rather than failing the job.
    base = Path(job_dir) / "animation" / "motion-canvas"
    scene_dir = base / "src" / "scenes"
    scene_dir.mkdir(parents=True, exist_ok=True)
    for i, scene in enumerate(scenes):
        (scene_dir / f"scene-{i+1:02d}.tsx").write_text(
            "import {makeScene2D, Txt} from '@motion-canvas/2d';\n"
            "import {createRef, waitFor} from '@motion-canvas/core';\n"
            f"export default makeScene2D(function* (view) {{\n"
            f"  const t = createRef<Txt>();\n"
            f"  view.add(<Txt ref={{t}} fontSize={{64}} fill={{'#ffffff'}}>"
            f"{scene['visual'][:60].replace('<', '').replace('>', '')}</Txt>);\n"
            f"  yield* waitFor({scene['duration']});\n}});\n", encoding="utf-8")
    (base / "README.md").write_text(
        "Motion Canvas scenes generated by the auto-runner.\n"
        "Render manually if the auto render fell back: npm install && npm run serve\n",
        encoding="utf-8")
    try:
        r = subprocess.run(["npx", "@motion-canvas/cli", "render",
                            "--project", str(base)],
                           capture_output=True, text=True, timeout=900, cwd=base)
        rendered = sorted(base.rglob("*.mp4"))
        if r.returncode == 0 and rendered:
            clips: list[Path] = []
            for i, src in enumerate(rendered[:len(scenes)]):
                dst = Path(job_dir) / "clips" / f"auto-scene-{i+1:02d}.mp4"
                dst.write_bytes(src.read_bytes())
                clips.append(dst)
            if clips:
                return clips, f"motion-canvas rendered {len(clips)} scene clips"
    except Exception:
        pass
    clips, log = render_code(job_dir, scenes, options)
    return clips, "motion-canvas render failed — fell back to code. " + log


def render_manim(job_dir: Path, scenes: list[dict],
                 options: JobOptions) -> tuple[list[Path], str]:
    """Try Manim (720p); fall back to code on any failure (logged)."""
    import shutil
    if shutil.which("manim") is None:
        clips, log = render_code(job_dir, scenes, options)
        return clips, "manim not installed — fell back to code. " + log
    base = Path(job_dir) / "animation" / "manim"
    base.mkdir(parents=True, exist_ok=True)
    (base / "scene.py").write_text(
        "from manim import *\n\n" + "\n".join(
            f"class Scene{i+1:02d}(Scene):\n"
            f"    def construct(self):\n"
            f"        t = Text({scene['visual'][:50]!r}, font_size=30)\n"
            "        self.play(Write(t))\n"
            f"        self.wait({scene['duration']})\n"
            for i, scene in enumerate(scenes)), encoding="utf-8")
    try:
        r = subprocess.run(["manim", "render", "-qm", "--format=mp4",
                            "scene.py"] + [f"Scene{i+1:02d}" for i in range(len(scenes))],
                           capture_output=True, text=True, timeout=1800, cwd=base)
        rendered = sorted(base.rglob("*.mp4"))
        if r.returncode == 0 and rendered:
            clips: list[Path] = []
            for i, src in enumerate(rendered[:len(scenes)]):
                dst = Path(job_dir) / "clips" / f"auto-scene-{i+1:02d}.mp4"
                dst.write_bytes(src.read_bytes())
                clips.append(dst)
            if clips:
                return clips, f"manim rendered {len(clips)} scene clips (720p)"
    except Exception:
        pass
    clips, log = render_code(job_dir, scenes, options)
    return clips, "manim render failed — fell back to code. " + log


def make_thumbnail(job_dir: Path, topic: str, angle: dict,
                   options: JobOptions) -> Path | None:
    """Clean thumbnail card (Pillow): topic + angle, no baked-in logos.

    The 2-4 overlay words go on in CapCut (see prompts/thumbnail.md);
    this card is the clean image the library stores.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except ImportError:
        return None
    job_dir = Path(job_dir)
    width, height = options.width, options.height
    bg, accent = PALETTE[1]
    img = Image.new("RGB", (width, height), bg)
    d = ImageDraw.Draw(img)
    d.rectangle([0, int(height * 0.72), width, height], fill=accent)
    try:
        font_big = ImageFont.truetype("DejaVuSans-Bold.ttf", int(height * 0.06))
        font_small = ImageFont.truetype("DejaVuSans.ttf", int(height * 0.032))
    except Exception:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()
    wrap = max(8, width // (int(height * 0.06) // 2 + 1))
    lines = textwrap.wrap(topic, width=wrap)[:4]
    y = int(height * 0.12)
    for line in lines:
        d.text((width * 0.07, y), line, font=font_big, fill=(255, 255, 255))
        y += int(height * 0.08)
    angle_line = (angle or {}).get("thumbnail_angle", "") or (angle or {}).get("angle", "")
    for line in textwrap.wrap(angle_line, width=wrap + 10)[:2]:
        d.text((width * 0.07, y), line, font=font_small, fill=(255, 255, 255))
        y += int(height * 0.05)
    out = job_dir / "thumbnail.jpg"
    img.save(out)
    return out


def render_visuals(job_dir: Path, scenes: list[dict], options: JobOptions,
                   ) -> tuple[list[Path], str, str]:
    """Return (scene clips, backend_actually_used, log line)."""
    want = options.video_backend
    if want == "flow-manual":
        return [], "", ("flow-manual chosen: Flow has no public API, so visuals "
                        "cannot be auto-rendered. Paste prompts/flow-prompts.txt "
                        "into Flow by hand, then run assemble.")
    order = ([want] if want != "auto" else ["motion-canvas", "manim", "code"])
    # "auto" tries the richest backend first, but code is the reliable one:
    # if neither motion-canvas nor manim is installed, code runs immediately.
    for backend in order:
        if backend == "code":
            clips, log = render_code(job_dir, scenes, options)
            return clips, "code", log
        if backend == "motion-canvas":
            clips, log = render_motion_canvas(job_dir, scenes, options)
            if clips:
                return clips, "motion-canvas" if "fell back" not in log else "code", log
        if backend == "manim":
            clips, log = render_manim(job_dir, scenes, options)
            if clips:
                return clips, "manim" if "fell back" not in log else "code", log
    return [], "", "No video backend could render (install Pillow + FFmpeg: pip install pillow)."
