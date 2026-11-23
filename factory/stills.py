"""Real-stills visuals — one real image per scene, Ken Burns motion.

This module replaces the old Pillow scene-card renderer (deleted in
v2.3). That renderer made solid-colour cards, burned the whole
narration on them as big text, and added a "Scene N • style" debug
label — the 40-second Constantinople test video was rated 2/10 for
exactly that, and it must never be produced again.

Rules of this module (non-negotiable):
  * Every scene uses ONE real still image, supplied by the human in
    jobs/<slug>/stills/scene-NN.jpg (or .png / .webp). The stills are
    generated in Nano Banana from the prompts this module writes
    (Nano Banana has no public API — manual, prompts only).
  * If a scene still is missing, the job FAILS here, clearly, naming
    the exact missing filename and the Nano Banana prompt for that
    scene. No coloured card, no gradient, no text card is ever
    rendered as a substitute.
  * No text is ever burned into a still or a scene clip. No scene
    number, no style label, no script text. Captions are a separate,
    single bottom layer handled by factory/captions.py + factory/video.py.
  * A still that is (near-)uniform in colour is treated as a
    placeholder, not a real image, and fails the same way as missing.
  * Motion is a slow Ken Burns pan/zoom, alternating per scene, never
    a static frame.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

STILL_EXTS = (".jpg", ".jpeg", ".png", ".webp")


class MissingStillsError(Exception):
    """Raised when one or more scene stills are missing / placeholders.

    Carries ``missing`` — a list of dicts {scene, filename, prompt,
    reason} — so the caller can report exactly what the human must
    generate in Nano Banana and drop into jobs/<slug>/stills/.
    """

    def __init__(self, missing: list[dict], guide_path: str = ""):
        self.missing = missing
        self.guide_path = guide_path
        names = ", ".join(m["filename"] for m in missing)
        super().__init__(
            f"Missing stills ({len(missing)}): {names}. "
            "Generate each one in Nano Banana from prompts/stills-prompts.md, "
            f"save it as jobs/<slug>/stills/<filename>, then press Run again. "
            f"Guide: {guide_path or 'prompts/stills-prompts.md'}")


def still_filename(scene_index: int) -> str:
    """Canonical filename for a scene: scene-01.jpg, scene-02.jpg, ..."""
    return f"scene-{scene_index + 1:02d}.jpg"


def find_still(job_dir: Path, scene_index: int) -> Path | None:
    """Find the real still for a scene, or None.

    Looks only in jobs/<slug>/stills/ (top level). The old
    stills/auto/ folder — where the deleted card renderer wrote its
    Pillow cards — is deliberately NOT searched: those were not real
    images and must never be reused as visuals.
    """
    stills_dir = Path(job_dir) / "stills"
    stem = f"scene-{scene_index + 1:02d}"
    for ext in STILL_EXTS:
        p = stills_dir / (stem + ext)
        if p.is_file() and p.stat().st_size > 0:
            return p
    # Tolerate scene-1.jpg (no zero-pad) — same scene, same rule.
    for ext in STILL_EXTS:
        p = stills_dir / f"scene-{scene_index + 1}{ext}"
        if p.is_file() and p.stat().st_size > 0:
            return p
    return None


def is_real_image(path: Path) -> bool:
    """True only for a real, non-uniform image.

    A solid-colour card has (near-)zero colour variance; a real photo
    or illustration does not. Pillow is already a required dependency.
    Returns False for unreadable / tiny / uniform files.
    """
    try:
        from PIL import Image, ImageStat  # type: ignore
        with Image.open(path) as img:
            img = img.convert("RGB")
            if img.width < 200 or img.height < 200:
                return False
            small = img.resize((64, 64))
            stat = ImageStat.Stat(small)
            # A real still has real variance in at least one channel.
            # Solid colours (and flat gradients) sit below ~8.
            if max(stat.stddev) < 8:
                return False
            colours = small.getcolors(maxcolors=4096)
            if colours is not None and len(colours) < 20:
                return False
            return True
    except Exception:
        return False


def still_prompt(scene: dict, scene_index: int, options=None,
                 angle: dict | None = None) -> str:
    """Nano Banana prompt for one scene's still (manual generation).

    The prompt describes the visual moment the narration needs — the
    subject, the action, the setting — and ends with the no-text rule
    from the skills: AI-generated text inside an image is never
    allowed; all text goes in captions / CapCut.
    """
    style = (getattr(options, "style", "") or "auto") if options else "auto"
    kind = (getattr(options, "kind", "") or "short") if options else "short"
    aspect = "vertical 9:16" if kind == "short" else "horizontal 16:9"
    if style in ("2.5d-cartoon", "diagram", "map"):
        look = ("2.5D cartoon illustration, bright colours, big clear shapes, "
                "shaded relief, one subject in the centre")
    elif style == "diagram":
        look = "clear diagram-style illustration, one mechanism, labelled by composition only"
    else:  # cinematic-realistic (default, Origin Loop Shorts)
        look = "Photorealistic cinematic still, natural light, shallow depth of field"
    narration = str(scene.get("narration", "") or "").strip()
    visual = str(scene.get("visual", "") or "").strip()
    # The visual line in old jobs is just the narration again; use the
    # narration itself as the moment to show, not as text to print.
    moment = (visual if visual and visual != narration else narration).strip()
    if moment and moment[-1] not in ".!?":
        moment += "."
    person = ((angle or {}).get("person") or "").strip()
    person_line = f"Seen through the eyes of {person}. " if person else ""
    return (
        f"{look}, {aspect}. {person_line}"
        f"Show this exact moment: {moment}. "
        "One clear subject, one visible action, the setting must explain "
        "what is happening — if you remove the image, the story must get "
        "harder to follow. No text, no letters, no words, no numbers, "
        "no logos, no watermarks, no captions, no subtitles in the image."
    )


def check_stills(job_dir: Path, scenes: list[dict], options=None,
                 angle: dict | None = None) -> dict:
    """Check every scene has a real still. Returns a status dict.

    {expected, present_count, present: [{scene, filename}],
     missing: [{scene, filename, prompt, reason}]}
    reason is "missing" or "placeholder" (uniform-colour file).
    """
    job_dir = Path(job_dir)
    present, missing = [], []
    for i, scene in enumerate(scenes):
        fname = still_filename(i)
        found = find_still(job_dir, i)
        if found is None:
            missing.append({"scene": i + 1, "filename": fname,
                            "prompt": still_prompt(scene, i, options, angle),
                            "reason": "missing"})
        elif not is_real_image(found):
            missing.append({"scene": i + 1, "filename": found.name,
                            "prompt": still_prompt(scene, i, options, angle),
                            "reason": ("placeholder — file is a near-uniform "
                                       "colour, not a real image; replace it")})
        else:
            present.append({"scene": i + 1, "filename": found.name})
    return {"expected": len(scenes), "present_count": len(present),
            "present": present, "missing": missing}


def write_stills_guide(job_dir: Path, scenes: list[dict], options=None,
                       angle: dict | None = None) -> tuple[Path, dict]:
    """Write prompts/stills-prompts.md + stills/README.md. Returns (path, check)."""
    job_dir = Path(job_dir)
    check = check_stills(job_dir, scenes, options, angle)
    (job_dir / "stills").mkdir(parents=True, exist_ok=True)
    (job_dir / "prompts").mkdir(parents=True, exist_ok=True)
    lines = [
        "# Stills — one real image per scene (Nano Banana, manual)",
        "",
        "Nano Banana has NO public API. Generate each still by hand:",
        "paste ONE prompt below into Nano Banana, save the image as the",
        "filename shown, and drop it into jobs/<slug>/stills/. Then press",
        "Run again — the run resumes from the visuals step.",
        "",
        "Rules: one image per scene, no text in the image (no letters,",
        "no words, no logos), the image must show the moment the",
        "narration describes. A solid-colour card is NOT a still — the",
        "job will fail rather than render one.",
        "",
        f"Stills present: {check['present_count']}/{check['expected']}",
        "",
    ]
    for i, scene in enumerate(scenes):
        fname = still_filename(i)
        status = next((p["filename"] for p in check["present"]
                       if p["scene"] == i + 1), None)
        lines.append(f"## Scene {i + 1} — `{fname}` — "
                     f"{'READY' if status else 'MISSING'}")
        lines.append("")
        lines.append(still_prompt(scene, i, options, angle))
        lines.append("")
    guide = job_dir / "prompts" / "stills-prompts.md"
    guide.write_text("\n".join(lines), encoding="utf-8")
    (job_dir / "stills" / "README.md").write_text(
        "# Stills — drop real images here\n\n"
        "One file per scene, named scene-01.jpg, scene-02.jpg, ...\n"
        "(jpg, png or webp). Generate each one in Nano Banana from\n"
        "prompts/stills-prompts.md — that file has one prompt per scene.\n\n"
        "Do NOT put files in stills/auto/ — that folder held the old\n"
        "Pillow text cards and is ignored. Do NOT render a coloured\n"
        "card as a substitute: a missing still stops the run with the\n"
        "exact filename, so you can generate it and resume.\n",
        encoding="utf-8")
    return guide, check


def scenes_from_job(job_dir: Path, options=None) -> list[dict]:
    """Re-derive scenes from the job's clean script (for status views)."""
    from .scriptgen import clean_script_text, split_into_scenes
    from .config import Config
    job_dir = Path(job_dir)
    script = clean_script_text(job_dir)
    if not script:
        return []
    cfg = Config()
    kind = (getattr(options, "kind", "") or "short") if options else "short"
    n = 9 if kind == "short" else 44
    duration = float(getattr(options, "duration_sec", 40) or 40) if options else 40.0
    return split_into_scenes(script, n, duration, cfg.voice_wpm)


def stills_status(job_dir: Path) -> dict:
    """Status for the dashboard: present X/Y, missing list, prompts.

    Works even before a script exists (then expected is unknown and
    only the files actually present are listed).
    """
    job_dir = Path(job_dir)
    scenes = []
    try:
        import json
        job_json = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
        from .options import JobOptions
        opts = JobOptions.from_dict(job_json.get("options"), job_json.get("kind", "short"))
        scenes = scenes_from_job(job_dir, opts)
        angle = job_json.get("angle") or {}
    except Exception:
        opts, angle = None, {}
    if not scenes:
        present = []
        stills_dir = job_dir / "stills"
        if stills_dir.exists():
            for p in sorted(stills_dir.glob("scene-*.*")):
                if p.suffix.lower() in STILL_EXTS and p.is_file():
                    present.append({"scene": p.stem, "filename": p.name})
        return {"expected": 0, "present_count": len(present),
                "present": present, "missing": [],
                "note": "No script yet — scenes (and the stills list) appear once the script is written."}
    check = check_stills(job_dir, scenes, opts, angle)
    # Keep the guide fresh so the dashboard always shows current prompts.
    try:
        write_stills_guide(job_dir, scenes, opts, angle)
    except Exception:
        pass
    return {**check,
            "guide": "prompts/stills-prompts.md",
            "note": ("Generate missing stills in Nano Banana from "
                     "prompts/stills-prompts.md, save as jobs/<slug>/stills/<filename>, then Run again.")}
