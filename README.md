# YT Production Factory — Origin Loop + Tiny Timeline Lab

Python backend + dashboard for making YouTube videos on a low-end laptop.
CPU-first, no GPU required. Toshiba Portégé A30-D (16 GB RAM, 256 GB SSD) par chalta hai.

**Channels (locked split):**
- **Origin Loop** — Shorts ONLY, 35–45 sec, cinematic/realistic, daily
- **Tiny Timeline Lab** — Long-form 8–10 min, weekly, 2.5D cartoon (+ Shorts there as trailers)

**Stack (user-confirmed):**
- Video: **Omni Flash ONLY** — 3 credits/sec at 720p. Veo NOT used (100 credits / 8 sec, leaves 5 Dec).
- Voice: **Google AI Studio, Charon** — masculine, low-pitched, same voice every video.
- Captions: **ElevenLabs ONLY** (captions, never voice). Default local: faster-whisper (CPU).
- Thumbnails: **Nano Banana** — clean image, text added in CapCut only.
- Editing: **CapCut free tier**. Animation: Motion Canvas / Manim (720p).
- Credits: 2 Google AI Pro accounts × 1000 + 50/day each = 2000 + 100/day.
  One 40s Short ≈ 120 credits. One 9-min long-form ≈ 450 + 144 reserve = 594 max.

## Honest limits — please read this first

**Google Flow / Veo 3 / Nano Banana have NO public API.** This app does NOT
fake an API call to them. For those steps it generates the exact prompts +
a job folder, and you paste the prompts into Flow / Nano Banana in your
browser. The dashboard Tools page shows each tool as `manual` for this reason.
The app never auto-uploads to YouTube either — you upload the approved
final video in YouTube Studio yourself.

**What ONE CLICK does (v2.3 — real stills):** press **Run** on a job in the dashboard
(or `python -m factory.cli auto --job <slug>`). **Muse is the supervisor**
(the project manager) — and Muse works through the **Google Gen AI SDK
agent** (`google-genai`, API key): the agent calls seven Python tools in
order — plan_angle, write_script, make_voice, make_visuals, make_captions,
assemble_video, run_qc — one video at a time. The model decides the
content (the one angle, the script); the tools do the work. If the SDK
or the key is missing, the same seven steps run sequentially instead —
nothing is left half-done because the model stopped talking. The finished
video lands in `jobs/<slug>/output-<short|long>.mp4` and in the channel
library (`output/origin-loop/Origin Loop N.mp4` or
`output/tiny-timeline-lab/Tiny Timeline Lab N.mp4`, auto-numbered, never
overwritten). Auto visuals cost **0** Omni Flash credits (one real
still per scene + FFmpeg Ken Burns, or Motion Canvas / Manim if
installed). Voice is Gemini TTS
Charon if `GEMINI_API_KEY` is set, else local Kokoro / Piper (draft
voices), else voice mp3s you already recorded. Full architecture:
`docs/AUTO-RUN.md`.

**Supervisor = Gen AI SDK, not the CLIs.** The Gemini CLI / AntiGravity
CLI are manual fallback only — they have session-time and authentication
problems, so they never drive a run. The SDK agent is the default.
Models (real Gen AI SDK names only): planning/script =
`gemini-2.5-flash` (or `gemini-2.5-pro` via `GEMINI_MODEL` in .env);
voice = `gemini-2.5-flash-preview-tts` (Charon). Omni Flash / Neon are
video models inside Google Flow with NO public API — manual-only (the
app prepares exact prompts, you paste them in Flow). "Carbon" /
"Hydrogen" are NOT Gen AI SDK models and are never used here.

**Version 2.3 — real-stills renderer (2026-11-23).** No batch mode, no queue, no factory scale: while
one video is running, a second Run waits. Each job follows one skill from
`skills/` (Origin Loop Shorts or Tiny Timeline Lab long-form by default,
or one you add) plus that job's own custom instructions, so two jobs
never produce the same script or visuals. Per-job options (type,
duration, aspect, style, video/audio/caption/supervisor backends, voice,
captions on/off, skill, custom instructions, assembler) are all dropdowns
in the dashboard — nothing is hard-coded to Short or long-form.

**Video form / style.** Style is a per-job dropdown, but the DEFAULT
keeps each channel consistent (recorded in each skill's "Channel
pattern" section, which the supervisor follows): Origin Loop Shorts =
cinematic realistic; Tiny Timeline Lab long-form = 2.5D cartoon map
animation. Stick figures are never the default on either channel.
Assemble with FFmpeg by default (fast, burned-in subtitles); MoviePy
is a slower optional timeline assembler (CPU, no GPU — see below).

What the app ALSO still does locally: demand-check + research templates,
script / storyboard templates with the 5 storytelling rules, Charon voice
files (Gemini TTS API if you set a key, else AI Studio steps), captions
(faster-whisper, CPU), FFmpeg assembly (Intel Quick Sync if present, else
libx264 veryfast), credit tracking, and the pre-publish QC gate.

## v2.3 — how visuals work now (read this — the old renderer is gone)

The v2.2 auto renderer made solid-colour Pillow cards with the whole
narration burned on as big text plus a "Scene N • style" label. A
40-second Constantinople test video made that way was rated **2/10**
and must never be uploaded. v2.3 deletes that renderer completely:

- **One real still per scene.** Each scene uses one real image in
  `jobs/<slug>/stills/scene-NN.jpg` (jpg/png/webp), generated by hand
  in **Nano Banana** from `prompts/stills-prompts.md` — the app writes
  one prompt per scene when the script is ready. Nano Banana has no
  public API, so this step is manual (prompts only), like Flow.
- **Missing still = the job stops.** Run fails at the visuals step
  naming every missing filename and its prompt. No coloured card, no
  gradient, no text card is ever rendered as a substitute, and a
  near-uniform-colour file is treated as a placeholder and fails too.
  Generate the stills, drop them in `stills/`, press Run again — the
  run resumes from the visuals step.
- **Motion is Ken Burns, never static.** Each scene clip pans/zooms
  slowly (zoom-in, zoom-out, pan-right, pan-left, alternating).
- **No text is ever burned into a scene clip.** No scene number, no
  style label, no script text. The thumbnail is a real still,
  centre-cropped, with no text added (overlay words go in CapCut).
- **Captions are one layer only, bottom, max 2 lines.** Only real
  faster-whisper ASR timing is burned in. Without ASR, the app writes
  `captions-estimated.srt` for hand-correction in CapCut and renders
  **no captions at all** rather than guessing overlapping ones.
- **Dashboard shows stills.** Jobs list shows `Stills X/Y`; Job detail
  shows the missing stills and a "Generate stills prompts" view with
  the exact Nano Banana prompt per scene (`GET /api/jobs/<slug>/stills`).
- **QC blocks placeholder visuals.** A missing still, a placeholder
  still, or the same still reused across scenes sends the job to
  `needs-review`.

Flow / Omni Flash clips remain the manual upgrade: paste scene prompts
from `prompts/flow-prompts.txt` into Flow, save clips as
`clips/scene-NN.mp4`, then run assemble. The app never claims Flow,
Omni Flash or Nano Banana are automated.

## Install — exact steps (Windows / Linux / macOS, same)

```bash
git clone https://github.com/salman-0011/yt-automation.git
cd yt-automation
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env ONLY if you have API keys. No key = manual Flow / AI Studio steps, app still works.
```

You also need (free): **FFmpeg** (https://ffmpeg.org/download.html, add to PATH),
and optionally Node.js (Motion Canvas) + Manim. No GPU, no Blender, no local
Stable Diffusion — those will not run well on this laptop. Free GPU fallback
(Google Colab / Hugging Face) is documented in `docs/GPU-FALLBACK.md` — only
if a CPU step cannot do the job.

## Run

### 1. Dashboard (easiest)
```bash
python -m factory.server
```
Then open **http://localhost:8000** in your browser.

Dashboard sections:
- **New job** — topic name + EVERY option: type (Short / Long-form),
  duration in seconds, aspect (9:16 / 16:9), style, video backend, audio
  backend, voice, captions on/off + caption backend, supervisor. Channel
  is set automatically from the type. Creates `jobs/<slug>/` with
  demand-check, master prompt, script + storyboard templates, Flow
  prompts and the pre-publish checklist, plus `options.json`.
- **Stats** — total jobs, videos produced, Shorts vs long-form, credits used /
  remaining per account (1000 + 50/day each).
- **Jobs** — all jobs, status, type, topic, live run progress, whether the
  output video exists. Each row has a green **▶ Run** button (one click).
  Auto-refreshes every 3 seconds (simple polling of `/api/jobs` — reliable on
  a low-end laptop, no websockets).
- **Job detail** — click Detail: options, live run progress bar, output file,
  step-by-step pipeline (demand → research →
  script → storyboard → voice → visuals → captions → assemble → QC gate),
  files produced, and credits used for that job. Plus a **Stills**
  section: present X/Y, the missing still filenames, and the Nano
  Banana prompt for each missing still.
- **Tools** — supervisor (Gemini API / CLI / AntiGravity), Google Flow,
  Omni Flash, Nano Banana, auto visuals (real stills / Motion Canvas / Manim),
  Charon TTS, Kokoro, Piper, ElevenLabs captions, faster-whisper, FFmpeg —
  each showing installed / configured / manual, with what to do next.

### 2. CLI (same backend, no browser needed)
```bash
python -m factory.cli --help
python -m factory.cli options
python -m factory.cli new --type short --topic "How 70 warships sailed over dry land"
python -m factory.cli new --type long --topic "Constantinople: 70 ships over land in one night"
python -m factory.cli auto --job how-70-warships-sailed-over-dry-land
python -m factory.cli auto --job constantinople-70-ships-over-land-in-one-night --duration 540 --video-backend stills --audio-backend gemini-tts
python -m factory.cli status
python -m factory.cli credits
python -m factory.cli voice --job constantinople-70-ships-over-land-in-one-night
python -m factory.cli captions --job <slug>
python -m factory.cli assemble --job <slug> --type short
python -m factory.cli review --job <slug>     # Gemini CLI / AntiGravity CLI, if installed
python -m factory.cli serve                   # same as python -m factory.server
```

## Workflow per video (9 steps)
1. **Demand check** — `jobs/<slug>/prompts/demand-check.md`, verdict PROCEED / REFRAME / DROP.
   DROP = stop, spend nothing.
2. **Research** — verify every date/name/number, keep sources. Do-not-say list.
3. **Script** — `script.md`. Short: 85–100 words. Long: 1150–1350 words, 5 acts.
4. **Storyboard** — Short: 8–10 scenes. Long: 40–48 scenes (Tier 1 / 2 / 3).
5. **Voice** — Charon. API if `GEMINI_API_KEY` set, else local Kokoro/Piper
   (draft), else voice mp3s you recorded in AI Studio (backend "existing").
   One click (`auto`) does this for you; the old `voice` command is manual.
6. **Visuals** — first generate the stills: open
   `prompts/stills-prompts.md`, paste each prompt into Nano Banana,
   save as `stills/scene-NN.jpg`. Then one click: the stills backend
   (Ken Burns per scene) or Motion Canvas / Manim, chosen per job.
   A missing still stops the run — nothing is faked. Manual upgrade
   only: paste scene prompts from `prompts/flow-prompts.txt` into
   Flow, Omni Flash, 720p, one generation per scene. Check Flow cost
   screen first. Inspect every clip for AI-generated text — reject
   misspelled text.
7. **Captions** — faster-whisper (real timing only), then hand-correct
   in CapCut. Without faster-whisper, no captions are burned in.
8. **Assemble** — `assemble` command (FFmpeg) or CapCut free tier.
9. **QC gate** — `checklist.md`, all items must pass or do not upload.

## The 5 storytelling rules (every script)
1. Start from an impossible problem, not a history lesson.
2. Tell it through one person's eyes.
3. Leave a question every ~60 seconds.
4. Visuals must explain, not just decorate.
5. End with a curiosity/surprise left open, not a summary.
Plus: "The Engineer in the Story" — one problem, one impossible constraint,
one clever machine/trick, one cost/consequence. Do NOT chase a totally new
topic — take a proven, searched story and win on angle, style and better,
more meaningful visuals.

## Monetisation safety — read this before you upload

YouTube's Partner Program pays for original, authentic content. Since
July 2025 its policy calls mass-produced, generic or repetitive uploads
"inauthentic content" and they are ineligible for monetization — even
when everything in them is your own. The test YouTube applies: would a
viewer instantly recognise this as your original work, or is it
indistinguishable from 50 other channels doing the same thing? Templated
slideshows with minimal variation and unedited prompt-to-upload AI
pipelines are the examples YouTube names as not monetizable.

This pipeline is built to stay on the right side of that line:
- **One angle per job, angle first.** Muse picks a different angle from
  existing videos before writing anything; the hook, script and
  thumbnail all follow that one angle.
- **Original research + original script + original angle per job.**
  The demand check stays (PROCEED / REFRAME / DROP), and every job
  records its own topic, research, skill and custom instructions.
- **Meaningful visuals.** Every scene's visual must explain its own
  narration — a slideshow of generic images fails the QC gate.
- **Real voiceover, correct pronunciation.** Charon via Gemini TTS, or
  mp3s you recorded; every difficult name needs a respelling in
  `pronunciation.md` before the voice is final.
- **Pre-publish QC gate (`factory/qc.py`).** Before a job is marked
  done, code checks: script similarity vs all previous jobs, angle
  similarity, generic visuals, missing facts, custom instructions not
  reflected, missing pronunciations. Blockers send the job to
  `needs-review` — it is NOT marked done and is NOT published to the
  library until you fix it and re-run (it resumes from the failed step)
  or review and Approve it yourself in the dashboard.
- **Version 2.3 — real-stills renderer (2026-11-23).** No mass production by design.

This does not guarantee monetization — nobody can promise that. It
keeps every video defensibly original, which is the bar YouTube states.

## What runs on the Toshiba A30-D (16 GB RAM, no GPU) — checked 2026-11-23

| Tool | Runs on CPU? | Verdict in this app |
|---|---|---|
| FFmpeg | Yes — libx264 / Quick Sync | Default assembler. Fast. |
| Pillow | Yes | Still validation + thumbnail crop (no text cards since v2.3). |
| MoviePy 2.x | Yes — no GPU targets; needs 2+ CPU cores, 4 GB RAM | Optional assembler only. MUCH slower than FFmpeg (frames are built in Python — ~8 min for a 15 s slideshow on one CPU in published tests), no burned-in subtitles, so captions fall back to FFmpeg. |
| Manim | Yes — Cairo CPU renderer | Pluggable video backend. |
| Motion Canvas | Yes — browser canvas, Node | Pluggable video backend. |
| faster-whisper | Yes — CPU (int8), GPU optional | Captions backend. |
| Remotion | Yes, via Chrome Headless Shell — but needs Node + a ~177 MB Chrome download and is slower on CPU | NOT added: Motion Canvas already covers programmatic video, and Remotion adds that weight for no new capability here. |
| Blender / local AI image gen | No — needs a GPU | Dropped. Will not run on this laptop. |

## Storage (256 GB SSD)
Keep only 1–2 jobs' clips on the laptop at a time (30–50 GB free).
Archive finished videos to Google Drive (5–10 TB available on Google AI Pro)
and delete local clips. See `docs/STORAGE.md` if added later.

## Project layout
```
factory/            Python package (config, credits, pipeline, voice, captions,
                    video, animation, prompts, supervisor, agent (Gen AI SDK
                    supervisor), genai_client (SDK calls), cli, server,
                    static/, options, scriptgen, audio, visuals, auto, qc,
                    library, skills)
skills/             Skill files a job follows (origin-loop-shorts,
                    tiny-timeline-longform — add your own .md here)
output/             Finished library, by channel, auto-numbered:
                    output/origin-loop/Origin Loop N.mp4 (+ thumbnails/)
                    output/tiny-timeline-lab/Tiny Timeline Lab N.mp4
factory/static/     Dashboard (plain HTML/CSS/JS, no Node build)
jobs/               One folder per video (job.json, script.md, storyboard.md,
                    prompts/, clips/, voice/, stills/, animation/, checklist.md)
scripts/            run.sh / run.bat — start the dashboard in one click
data/               credits.json ledger (local only, git-ignored)
```

## Roman Urdu — mukhtasar
Ye app aapke laptop par local chalti hai, GPU zaroori nahi. Flow / Nano Banana
ka koi API nahi hai, is liye wo steps manual hain — app prompts bana kar deti
hai, aap Flow mein paste karte hain. Dashboard `http://localhost:8000` par
khulta hai, jobs, credits aur tools sab wahin dikhte hain.
