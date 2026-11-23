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

**What ONE CLICK does (v2.0):** press **Run** on a job in the dashboard
(or `python -m factory.cli auto --job <slug>`). The LLM supervisor plans
the job, then Python backends do the work in order — script, voice,
visuals, captions, FFmpeg assembly, QC — and the finished video lands in
`jobs/<slug>/output-<short|long>.mp4`. Auto visuals cost **0** Omni Flash
credits (Pillow + FFmpeg, or Motion Canvas / Manim if installed). Voice is
Gemini TTS Charon if `GEMINI_API_KEY` is set, else local Kokoro / Piper
(draft voices), else voice mp3s you already recorded. Full architecture:
`docs/AUTO-RUN.md`. Per-job options (type, duration, aspect, style,
video/audio/caption/supervisor backends, voice, captions on/off) are all
dropdowns in the dashboard — nothing is hard-coded to Short or long-form.

What the app ALSO still does locally: demand-check + research templates,
script / storyboard templates with the 5 storytelling rules, Charon voice
files (Gemini TTS API if you set a key, else AI Studio steps), captions
(faster-whisper, CPU), FFmpeg assembly (Intel Quick Sync if present, else
libx264 veryfast), credit tracking, and the pre-publish QC gate.

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
  files produced, and credits used for that job.
- **Tools** — supervisor (Gemini API / CLI / AntiGravity), Google Flow,
  Omni Flash, Nano Banana, auto visuals (code / Motion Canvas / Manim),
  Charon TTS, Kokoro, Piper, ElevenLabs captions, faster-whisper, FFmpeg —
  each showing installed / configured / manual, with what to do next.

### 2. CLI (same backend, no browser needed)
```bash
python -m factory.cli --help
python -m factory.cli options
python -m factory.cli new --type short --topic "How 70 warships sailed over dry land"
python -m factory.cli new --type long --topic "Constantinople: 70 ships over land in one night"
python -m factory.cli auto --job how-70-warships-sailed-over-dry-land
python -m factory.cli auto --job constantinople-70-ships-over-land-in-one-night --duration 540 --video-backend code --audio-backend gemini-tts
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
6. **Visuals** — one click: code (Pillow + FFmpeg zoompan), Motion Canvas
   or Manim, chosen per job. Manual upgrade only: paste scene prompts from
   `prompts/flow-prompts.txt` into Flow, Omni Flash, 720p, one generation
   per scene. Check Flow cost screen first. Inspect every clip for
   AI-generated text — reject misspelled text.
7. **Captions** — faster-whisper, then hand-correct in CapCut.
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

## Storage (256 GB SSD)
Keep only 1–2 jobs' clips on the laptop at a time (30–50 GB free).
Archive finished videos to Google Drive (5–10 TB available on Google AI Pro)
and delete local clips. See `docs/STORAGE.md` if added later.

## Project layout
```
factory/            Python package (config, credits, pipeline, voice, captions,
                    video, animation, prompts, supervisor, cli, server, static/,
                    options, scriptgen, audio, visuals, auto)
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
