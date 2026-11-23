# AUTO-RUN — how one click makes a video (v2.0)

## The idea in one paragraph

One central Project Manager — the LLM supervisor — plans the job.
Python scripts do the actual work, in order, synchronised by
`factory/auto.py`. The supervisor never renders anything itself, and
no step is faked: if a backend is missing, the run says so and falls
back (or stops) instead of pretending.

```
Topic + options (dashboard / CLI)
        |
        v
  SUPERVISOR  (Gemini API if GEMINI_API_KEY is set, else CLI / none)
    - writes the script (only if script.md has no real script yet)
    - splits it into scenes with durations (5 storytelling rules)
        |
        v
  AUDIO backends, in order (auto): gemini-tts (Charon) -> kokoro -> piper -> existing
    - "existing" = voice/*.mp3 already in the job folder (Charon from AI Studio)
    - ElevenLabs is captions ONLY — it is never a voice backend
        |
        v
  VIDEO backends, in order (auto): motion-canvas -> manim -> code
    - code = Pillow scene cards + kinetic text, FFmpeg zoompan Ken Burns
    - motion-canvas / manim fall back to code if their render fails
    - flow-manual = NOT a render backend (Flow has no public API)
        |
        v
  CAPTIONS: faster-whisper (CPU) if installed, else SRT timed from the script
        |
        v
  ASSEMBLE: FFmpeg (Quick Sync if present, else libx264 veryfast), 720p,
            loudness -14 LUFS, subtitles burned in if captions are on
        |
        v
  QC: file exists, has video + audio streams, duration near target.
      Result in jobs/<slug>/job.json ("run"), full log in run-log.md,
      usage in usage.json. Output: jobs/<slug>/output-<short|long>.mp4
```

## Backends (pluggable)

| Step | Backends | Needs | Fallback |
|---|---|---|---|
| Supervisor | gemini-api, gemini-cli, antigravity, none | GEMINI_API_KEY for gemini-api | none (use script.md) |
| Script | job script.md, gemini-api | key for gemini-api | stops with a clear error, never a generic script |
| Audio | gemini-tts, kokoro, piper, existing | key / `kokoro` / `piper` / voice/*.mp3 | next backend in order |
| Video | code, motion-canvas, manim, flow-manual | Pillow+FFmpeg / Node / manim | code (always, if Pillow+FFmpeg exist) |
| Captions | faster-whisper, script-srt, off | faster-whisper installed | script-srt |
| Assemble | FFmpeg | FFmpeg on PATH | stops with "install FFmpeg" |

Pick per job in the dashboard (every option is a dropdown) or on the
CLI: `python -m factory.cli auto --job <slug> --video-backend code
--audio-backend gemini-tts --duration 40 --aspect 9:16`.
`python -m factory.cli options` prints what is installed on this machine.
`GET /api/options` does the same for the dashboard.

## What one click does NOT do

- **Google Flow / Omni Flash / Nano Banana clips.** No public API
  exists. The job folder still gets Flow prompts; paste them by hand
  if you want cinematic clips, then run the old `assemble` command.
  Auto visuals cost **0** Omni Flash credits.
- **YouTube upload.** Upload the finished mp4 in YouTube Studio
  yourself, after watching it and ticking the AI disclosure.
- **Guarantee views or monetization.** It makes the video; the audience
  still decides.

## Files a run writes

- `jobs/<slug>/job.json` — options + live run progress (step, %, message)
- `jobs/<slug>/run-log.md` — one line per step, with the real backend used
- `jobs/<slug>/usage.json` — supervisor, backends, Flow credits (0 for auto)
- `jobs/<slug>/voice/narration.mp3`, `captions.srt`
- `jobs/<slug>/clips/auto-scene-NN.mp4`, `stills/auto/scene-NN.png`
- `jobs/<slug>/output-short.mp4` or `output-long.mp4`

## Troubleshooting

- Run fails at plan: no script in script.md and no GEMINI_API_KEY.
  Write the script (or let Muse write it) into script.md, or set the key.
- Run fails at voice: no key and no Kokoro/Piper and no voice/*.mp3.
  Record Charon in AI Studio into voice/act-01.mp3 and pick audio
  backend "existing", or set GEMINI_API_KEY.
- Run fails at visuals: Pillow or FFmpeg missing. `pip install pillow`
  and install FFmpeg (https://ffmpeg.org/download.html, add to PATH).
- Output is shorter than the target: the narration was faster than
  152 wpm. QC tolerates ±25%; re-run with a longer script or a
  bigger --duration.
- Motion Canvas / Manim render failed: check run-log.md — the run
  fell back to the code backend automatically and still finished.
