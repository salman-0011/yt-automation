# AUTO-RUN — how one click makes ONE video (v2.2)

## The idea in one paragraph

Muse is the supervisor — the central Project Manager. Muse works
through the **Google Gen AI SDK agent** (`factory/agent.py`): the
agent calls seven Python tools in order, and Python scripts do the
actual work, synchronised by `factory/auto.py`. One video at a time,
no batch, no queue. The supervisor never renders anything itself, and
no step is faked: if a backend is missing, the run says so and falls
back (or stops) instead of pretending. If the SDK or the API key is
missing, the same seven steps run sequentially — the agent is the
driver, not a single point of failure.

Design patterns used (from modern workflow automation — supervisor +
tool-use agents, job state machines, durable execution):
- **Typed state, graph decides control flow.** One `job.json` holds the
  whole run state. The runner (this file's code) decides which step
  runs next; the LLM decides content only. That split is what makes the
  workflow testable — the set of possible paths is finite and known.
- **Checkpoint after every step.** `job.json` records step, progress
  and `completed_steps`, so a re-run resumes from the first incomplete
  step instead of starting over.
- **Idempotent steps.** A step whose output already exists and is valid
  is skipped on resume (script, narration.mp3, scene clips, SRT,
  output mp4). Re-running never double-spends or double-renders.
  Steps are keyed by run + step name; if the job's options changed,
  the checkpoints are cleared and the job re-runs from the start.
- **Capped retries.** Transient failures (network / API) retry at most
  twice with backoff, with the error logged; deterministic failures
  fail fast into `failed`. No uncapped loops.
- **Human-in-the-loop QC gate.** The automated QC gate must pass
  before a job is marked done. If it blocks, the job goes to
  `needs-review` and a human approves (dashboard Approve / CLI
  `approve`) after reviewing the output and `qc-report.md`.
- **Audit log.** `run-log.md` records every step, the real backend
  used, and every QC decision. Nothing here is a multi-agent swarm:
  one supervisor, one job, one step at a time.

```
Topic + skill + custom instructions (dashboard / CLI)
        |
        v
  MUSE SUPERVISOR AGENT (Google Gen AI SDK, gemini-2.5-flash)
    tools, in order — the model calls them, Python executes them:
    1. plan_angle    — ONE angle the big channels did NOT use
                        + demand PROCEED / REFRAME / DROP (DROP stops all)
    2. write_script  — hook + script + thumbnail follow that one angle
    3. make_voice    — Charon (Gemini TTS) / Kokoro / Piper / existing mp3
    4. make_visuals  — motion-canvas -> manim -> code (Pillow + FFmpeg)
    5. make_captions — faster-whisper (CPU) / script SRT
    6. assemble_video— FFmpeg (default) or MoviePy + thumbnail (same angle)
    7. run_qc        — pre-publish gate (factory/qc.py)
  If the agent loop ends early, the sequential runner (below) finishes
  the remaining steps with the same tools. The graph decides order;
  the model decides content.
        |
        v
  SEQUENTIAL RUNNER (factory/auto.py _Runner) — same seven steps, same
  order, used when the SDK/key is missing or the agent stopped early.
  Skill rules (skills/*.md) + the job's custom instructions apply in
  both drivers. Auto visuals cost 0 Omni Flash credits.
        |
        v
  QC GATE: repetitive script vs previous jobs, angle reused, generic
  visuals, demand DROP, missing facts, custom instructions not
  reflected, missing pronunciations, media checks.
  Pass -> done + publish. Blockers -> needs-review (human approves).
        |
        v
  PUBLISH: output/<channel>/, auto-numbered, never overwritten
    output/origin-loop/Origin Loop 1.mp4 (+ thumbnails/Origin Loop 1.jpg)
    output/tiny-timeline-lab/Tiny Timeline Lab 1.mp4 (+ thumbnails/...)
```

## The agent's tools (factory/agent.py)

| Tool | What the MODEL decides | What the TOOL does |
|---|---|---|
| plan_angle | The one angle, person, problem, hook, thumbnail angle, demand verdict | Validates + saves angle.md / angle.json / prompts/thumbnail.md |
| write_script | The full narration | Validates word count, saves script.md, splits scenes, writes storyboard |
| make_voice | — (no content args) | Renders Charon / Kokoro / Piper / existing mp3 |
| make_visuals | — | Renders scene clips (motion-canvas -> manim -> code) |
| make_captions | — | faster-whisper (CPU) or script-timed SRT |
| assemble_video | — | FFmpeg (default) or MoviePy + thumbnail |
| run_qc | — | Runs the QC gate, returns pass/blockers/warnings |

Order is enforced: a tool called out of order is not executed — the
model gets an error telling it which tool is next. A tool that fails
twice stops the agent loop; the sequential runner finishes the rest.

## Models (real Gen AI SDK names only)

| Use | Model |
|---|---|
| Planning / script / supervision | `gemini-2.5-flash` (default; `GEMINI_MODEL` can set `gemini-2.5-pro`) |
| Voice (Charon TTS) | `gemini-2.5-flash-preview-tts` |
| Video (Omni Flash / Neon) | NO public API — manual-only in Flow; the app prepares prompts |
| "Carbon" / "Hydrogen" | NOT Gen AI SDK models — never used here |

## Style defaults (channel pattern, in each skill)

Style is a per-job dropdown, but the default keeps each channel
consistent: Origin Loop Shorts = cinematic realistic; Tiny Timeline
Lab long-form = 2.5D cartoon map animation. Stick figures are never
the default. Each skill file has a "Channel pattern" section (topics,
angle, visual style, voice, length) that the supervisor follows so
new jobs stay consistent with the channel. There is no separate
channel-analysis service — the skill IS the record.

## Job states

`created -> planning -> scripting -> voice -> visuals -> captions
-> assembling -> qc -> done | needs-review | failed`

`needs-review` is not done: no library copy until the issues are fixed
(re-run resumes from the failed step) or a human approves it.

## Skills

A job follows one skill from `skills/*.md` (see `skills/README.md`).
Defaults: `origin-loop-shorts` for Shorts, `tiny-timeline-longform`
for long-form. The skill text is copied into
`jobs/<slug>/prompts/skill.md`, and the job's custom instructions into
`jobs/<slug>/custom-instructions.md`, so every job records exactly
what it followed. The supervisor's script prompt includes the skill,
the chosen angle and the custom instructions — and QC checks the custom
instructions actually show up in the script or angle.

## Backends (pluggable)

| Step | Backends | Needs | Fallback |
|---|---|---|---|
| Supervisor | Muse via genai-sdk (agent), gemini-cli / antigravity (manual fallback only), none | GEMINI_API_KEY + google-genai for genai-sdk | none (use script.md) |
| Script | job script.md, Muse via gemini-api | key for gemini-api | stops with a clear error, never a generic script |
| Audio | gemini-tts, kokoro, piper, existing | key / `kokoro` / `piper` / voice/*.mp3 | next backend in order |
| Video | code, motion-canvas, manim, flow-manual | Pillow+FFmpeg / Node / manim | code (always, if Pillow+FFmpeg exist) |
| Captions | faster-whisper, script-srt, off | faster-whisper installed | script-srt |
| Assemble | FFmpeg (default) or MoviePy | FFmpeg on PATH; MoviePy if chosen | FFmpeg (MoviePy fails -> FFmpeg; captions on -> FFmpeg) |

Pick per job in the dashboard (every option is a dropdown) or on the
CLI: `python -m factory.cli auto --job <slug> --video-backend code
--audio-backend gemini-tts --duration 40 --aspect 9:16
--skill origin-loop-shorts --custom "focus on the engineer who built it"`.
`--fresh` re-does every step instead of resuming.
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

- `jobs/<slug>/job.json` — options + skill + angle + live run progress
- `jobs/<slug>/angle.md`, `angle.json` — the one chosen angle
- `jobs/<slug>/custom-instructions.md`, `prompts/skill.md` — what the job followed
- `jobs/<slug>/run-log.md` — one line per step, with the real backend used
- `jobs/<slug>/qc-report.md` — QC blockers / warnings / details
- `jobs/<slug>/usage.json` — supervisor, backends, Flow credits (0 for auto)
- `jobs/<slug>/voice/narration.mp3`, `captions.srt`, `thumbnail.jpg`
- `jobs/<slug>/clips/auto-scene-NN.mp4`, `stills/auto/scene-NN.png`
- `jobs/<slug>/output-short.mp4` or `output-long.mp4`
- `output/<channel>/…` — the published library copy (see above)

## Troubleshooting

- Run fails at plan: no script in script.md and no GEMINI_API_KEY.
  Write the script (or let Muse write it) into script.md, or set the key.
  With a key but no `google-genai` package, the agent loop is skipped
  and the sequential runner writes the script instead — install it with
  `pip install google-genai` to get the agent.
- Agent loop ended early (see run-log.md): the sequential runner
  finished the remaining steps with the same tools. The video is still
  complete; only the model-driven planning was cut short.
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
- Job is needs-review: read qc-report.md, fix the issue, press Run
  again (it resumes from the failed step) — or Approve it in the
  dashboard after reviewing the video yourself.
- Two jobs look alike: that is what the QC gate is for. Give the new
  job different custom instructions and a different skill angle, and
  check angle.md — the angle must differ from the previous job's.
