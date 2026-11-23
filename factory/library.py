"""Output library — finished videos, filed by channel, numbered.

Working folder: jobs/<slug>/ (everything the pipeline made).
Clean library: output/<channel>/ — one numbered file per finished video:
  output/origin-loop/Origin Loop 1.mp4, Origin Loop 2.mp4, ...
  output/tiny-timeline-lab/Tiny Timeline Lab 1.mp4, ...
Thumbnails: output/<channel>/thumbnails/<Name> 1.jpg, same numbering.
Numbering is auto: next number = highest existing number + 1.
A file is NEVER overwritten — if the target name somehow exists, the
number is bumped again.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

CHANNELS = {
    "short": ("origin-loop", "Origin Loop"),
    "long": ("tiny-timeline-lab", "Tiny Timeline Lab"),
}


def channel_info(kind: str) -> tuple[str, str]:
    return CHANNELS.get(kind, CHANNELS["short"])


def library_dir(root: Path, kind: str) -> Path:
    sub, _ = channel_info(kind)
    return Path(root) / "output" / sub


def _next_number(directory: Path, prefix: str, suffix: str) -> int:
    n = 0
    if directory.exists():
        for p in directory.glob(f"{prefix} *{suffix}"):
            m = re.match(rf"^{re.escape(prefix)} (\d+){re.escape(suffix)}$", p.name)
            if m:
                n = max(n, int(m.group(1)))
    return n + 1


def publish(root: Path, kind: str, output_mp4: Path,
            thumbnail_jpg: Path | None = None) -> dict:
    """Copy a finished video (+ thumbnail) into the library. Never overwrites.

    ONE number for the video and its thumbnail: the number comes from the
    videos in the folder only. If a thumbnail with that number already
    exists, it is stale (its video was deleted and the number reused), so
    it is replaced by this video's thumbnail — the thumbnail always
    belongs to the video with the same number. Videos themselves are
    never overwritten.
    """
    root = Path(root)
    sub, display = channel_info(kind)
    video_dir = root / "output" / sub
    thumb_dir = video_dir / "thumbnails"
    video_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir.mkdir(parents=True, exist_ok=True)
    n = _next_number(video_dir, display, ".mp4")
    while (video_dir / f"{display} {n}.mp4").exists():
        n += 1
    video_dest = video_dir / f"{display} {n}.mp4"
    shutil.copy2(output_mp4, video_dest)
    thumb_dest = None
    if thumbnail_jpg and Path(thumbnail_jpg).exists():
        thumb_dest = thumb_dir / f"{display} {n}.jpg"
        shutil.copy2(thumbnail_jpg, thumb_dest)
    return {"number": n, "video": str(video_dest),
            "thumbnail": str(thumb_dest) if thumb_dest else None}
