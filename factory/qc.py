"""Pre-publish QC gate — monetisation safety, checked by code.

YouTube's Partner Program requires original, authentic content. Since
July 2025 its policy calls mass-produced, generic or repetitive uploads
"inauthentic content" and they are ineligible for monetization — even
when everything in them is the creator's own. The test YouTube applies:
would a viewer instantly recognise this as your original work, or is it
indistinguishable from 50 other channels doing the same thing?

This gate checks, before a job may be marked done:
  BLOCKERS (job goes to needs-review, no library copy, not done):
    - repetitive_script: script too similar to an earlier job's script
    - angle_reused:     chosen angle too similar to an earlier job's angle
    - generic_visuals:  scene visuals are (near-)identical across scenes
    - missing_still / placeholder_still: a scene has no real still, or
      its still is a solid-colour placeholder (v2.3 — the 2/10 video)
    - demand_drop:      demand verdict was DROP
    - no_audio / no_video / duration far off target
  WARNINGS also include:
    - captions_estimated: captions are timed from the script, not ASR
      (they are never burned in — see factory/captions.py)
  WARNINGS (job may finish, but the warning is logged + shown):
    - pronunciation:    a difficult name in the script has no entry in
                        pronunciation.md (learn from the WWII review)
    - no_specific_fact: script has no number/date/name — thin original value
    - custom_instructions_not_reflected: the job's own instructions do
                        not show up in the script or angle
    - captions_estimated: captions are timed from the script, not ASR
"""
from __future__ import annotations

import json
import re
from pathlib import Path

STOPWORDS = set(
    "the a an and or of to in on for with is was are were it its this that "
    "there here from by at as be been has have had will would can could "
    "you your we our they their he she his her not no do does did so if then "
    "when what how why who which one two".split())

NAME_BLOCKLIST = set("January February March April May June July August September "
                     "October November December Monday Tuesday Wednesday Thursday "
                     "Friday Saturday Sunday".split()) | set(
    "water ship canal locks world history time day year war river sea ocean "
    "mountain city people man woman boy girl country empire king queen".split())


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", text.lower())
            if w not in STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _previous_jobs(root: Path, self_slug: str) -> list[dict]:
    out = []
    for jf in sorted((root / "jobs").glob("*/job.json")):
        if jf.parent.name == self_slug:
            continue
        try:
            out.append(json.loads(jf.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def _names_in_script(script: str) -> list[str]:
    """Capitalised words that look like proper names (not sentence starts)."""
    names = []
    for m in re.finditer(r"\b([A-Z][a-z]{3,}(?:\s+[A-Z][a-z]{3,})?)\b", script):
        name = m.group(1)
        if name.split()[0].lower() in {b.lower() for b in NAME_BLOCKLIST}:
            continue
        if name not in names:
            names.append(name)
    return names[:20]


def run_qc(job_dir: Path, script: str, angle: dict, scenes: list[dict],
           clips: list, audio_path, output_path, duration_target: float,
           custom_instructions: str = "") -> dict:
    """Return {passed, blockers[], warnings[], details{}}."""
    job_dir = Path(job_dir)
    blockers, warnings, details = [], [], {}

    # --- repetitive script vs previous jobs ---------------------------
    words = _words(script)
    worst, worst_slug = 0.0, ""
    # Repo root: jobs/<slug> -> root is two levels up.
    root = job_dir.parent.parent
    for prev in _previous_jobs(root, job_dir.name):
        prev_script = ""
        sp = root / "jobs" / prev.get("slug", "") / "script.md"
        if sp.exists():
            prev_script = sp.read_text(encoding="utf-8")
        sim = _jaccard(words, _words(prev_script))
        if sim > worst:
            worst, worst_slug = sim, prev.get("slug", "?")
    details["script_similarity_vs_previous"] = round(worst, 2)
    details["most_similar_previous_job"] = worst_slug
    if worst > 0.45:
        blockers.append(f"repetitive_script: script is {worst:.0%} similar to "
                        f"job '{worst_slug}' — rewrite with a new angle, new "
                        "research and new wording before this can be marked done.")
    elif worst > 0.30:
        warnings.append(f"script is {worst:.0%} similar to job '{worst_slug}' — "
                        "check the angle really is different.")

    # --- angle reused ---------------------------------------------------
    angle_text = (angle or {}).get("angle", "")
    worst_a = 0.0
    for prev in _previous_jobs(root, job_dir.name):
        prev_angle = ""
        ap = root / "jobs" / prev.get("slug", "") / "angle.md"
        if ap.exists():
            prev_angle = ap.read_text(encoding="utf-8")
        worst_a = max(worst_a, _jaccard(_words(angle_text), _words(prev_angle)))
    details["angle_similarity_vs_previous"] = round(worst_a, 2)
    if worst_a > 0.60 and angle_text:
        blockers.append("angle_reused: this angle is too close to an earlier "
                        "job's angle — pick a different angle first.")

    # --- demand verdict -------------------------------------------------
    if (angle or {}).get("demand_verdict") == "DROP":
        blockers.append("demand_drop: the demand check said DROP — do not make this video.")

    # --- real stills (v2.3) ----------------------------------------------
    try:
        from .stills import check_stills, find_still
        import hashlib as _hashlib
        _check = check_stills(job_dir, scenes)
        details["stills_present"] = (f"{_check['present_count']}/"
                                     f"{_check['expected']}")
        for m in _check["missing"]:
            blockers.append(
                f"{'placeholder_still' if m['reason'] != 'missing' else 'missing_still'}: "
                f"scene {m['scene']} has no real still ({m['filename']}, "
                f"{m['reason']}) — generate it in Nano Banana from "
                f"prompts/stills-prompts.md and re-run.")
        _hashes = []
        for i in range(len(scenes)):
            _f = find_still(job_dir, i)
            if _f:
                _hashes.append(_hashlib.sha256(_f.read_bytes()).hexdigest())
        details["distinct_stills"] = f"{len(set(_hashes))}/{len(_hashes)}"
        if _hashes and len(set(_hashes)) < len(_hashes):
            blockers.append("generic_visuals: two or more scenes reuse the "
                            "same still image — every scene needs its own visual.")
    except Exception as e:  # noqa: BLE001 - a stills check must never crash QC
        warnings.append(f"stills check could not run ({e}) — check stills by hand.")

    # --- generic visuals -------------------------------------------------
    visuals = [str(s.get("visual", "")).strip().lower() for s in scenes]
    distinct = len(set(visuals))
    details["distinct_scene_visuals"] = f"{distinct}/{len(visuals)}"
    if scenes and distinct < max(2, len(visuals) // 2):
        blockers.append("generic_visuals: most scenes use the same visual — "
                        "every scene needs a visual that explains its own narration.")
    clip_sizes = [Path(c).stat().st_size for c in clips if Path(c).exists()]
    if clips and clip_sizes and len(set(clip_sizes)) < 2 and len(clips) > 2:
        warnings.append("scene clips are all the same size — check the visuals "
                        "really differ per scene.")

    # --- original value --------------------------------------------------
    has_fact = bool(re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b|\b\d+(\.\d+)?\s*(km|m|kg|tons?|seconds?|minutes?|ships?|%)", script))
    details["has_specific_fact"] = has_fact
    if not has_fact:
        warnings.append("no_specific_fact: script has no number, date or "
                        "measurement — add verified facts or the video adds "
                        "little original value.")

    # --- custom instructions reflected ------------------------------------
    if custom_instructions.strip():
        keys = [w for w in re.findall(r"[a-z]{5,}", custom_instructions.lower())
                if w not in STOPWORDS][:8]
        hay = (script + " " + angle_text).lower()
        hit = sum(1 for k in keys if k in hay)
        details["custom_instructions_keywords_matched"] = f"{hit}/{len(keys)}"
        if keys and hit == 0:
            warnings.append("custom_instructions_not_reflected: none of the "
                            "job's own instruction keywords appear in the "
                            "script or angle — check the instructions were honoured.")

    # --- captions are real timing, not estimates -------------------------
    if (job_dir / "captions-note.txt").exists():
        warnings.append("captions_estimated: captions are timed from the "
                        "script, not ASR — they were NOT burned in. Install "
                        "faster-whisper and re-run for real captions, or "
                        "hand-correct captions-estimated.srt in CapCut.")

    # --- pronunciation -----------------------------------------------------
    pron = (job_dir / "pronunciation.md").read_text(encoding="utf-8", errors="ignore") \
        if (job_dir / "pronunciation.md").exists() else ""
    missing = [n for n in _names_in_script(script) if n.lower() not in pron.lower()]
    details["names_missing_pronunciation"] = missing
    if missing:
        warnings.append("pronunciation: add a respelling for "
                        + ", ".join(missing[:6]) +
                        " in pronunciation.md and re-check the voiceover.")

    # --- media presence ------------------------------------------------------
    out = Path(output_path) if output_path else None
    if not out or not out.exists() or out.stat().st_size == 0:
        blockers.append("no_video: no finished output file.")
    if not audio_path or not Path(audio_path).exists():
        blockers.append("no_audio: no narration audio — a video with no real voiceover is low-effort content.")
    if out and out.exists():
        import subprocess
        try:
            r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                "format=duration", "-of", "csv=p=0", str(out)],
                               capture_output=True, text=True, timeout=60)
            dur = float(r.stdout.strip() or 0)
            details["output_duration_sec"] = round(dur, 1)
            if abs(dur - duration_target) > max(10, duration_target * 0.25):
                blockers.append(f"duration_off: output is {dur:.0f}s but the target "
                                f"is {duration_target:.0f}s.")
        except Exception:
            warnings.append("could not probe output duration (ffprobe missing).")

    return {"passed": not blockers, "blockers": blockers,
            "warnings": warnings, "details": details}
