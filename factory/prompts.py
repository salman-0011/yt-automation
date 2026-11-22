"""Prompt library — the channel's fixed storytelling identity.

These are TEXT templates embedded in code. Nothing here calls an LLM
by default. The supervisor (supervisor.py) may hand a template to
Gemini CLI / AntiGravity CLI, but only when the user asks for it.

THE 5 STORYTELLING RULES (shared by Origin Loop Shorts + TTL long-form):
  1. Start from an impossible problem, not a history lesson.
  2. Tell it through one person's eyes.
  3. Leave a question every ~60 seconds.
  4. Visuals must explain, not just decorate.
  5. End with a curiosity/surprise left open, not a summary.
Plus the angle lens "The Engineer in the Story": one problem, one
impossible constraint, one clever machine/trick, one cost/consequence.
And the core rule: do NOT chase a totally new topic — take a proven,
searched story others already told and win on angle, style, better and
more meaningful visuals, with life in the telling.
"""
from __future__ import annotations

FIVE_RULES = """THE 5 STORYTELLING RULES (apply to every script, Short or long-form):
1. Start from an impossible problem, not a history lesson.
2. Tell it through one person's eyes.
3. Leave a question every ~60 seconds that the viewer cannot answer yet.
4. Visuals must explain, not just decorate. If you remove the visual and
   the story stays clear, the visual is wrong.
5. End with a curiosity/surprise left open, not a summary.
ANGLE LENS — "The Engineer in the Story": one problem, one impossible
constraint, one clever machine or trick, one cost or consequence.
IDENTITY RULE: do NOT chase a totally new/unknown topic. Use a proven,
searched story others already told and win by telling it from a different
angle, in a different style, with better/more meaningful visuals, with
life in the telling. First generate 5 different angles, pick the one big
channels did NOT use, then write only that angle, using only facts that
support it. Never write generic textbook wording.
"""

SHORTS_V2_PROMPT = """ORIGIN LOOP — SHORTS v2 (condensed master prompt)
Channel: Origin Loop — Shorts ONLY. Vertical 9:16, 35-45s (hard limit 50s).
Audience: US/UK/Canada/Australia, natural conversational American English.
Voice: Google AI Studio Charon, masculine low-pitched, brisk, ~145-165 wpm.
Step 0 — DEMAND CHECK first (5 lines max): search interest, 3-5 existing
Shorts + their angle, missing angle in one sentence, viewer-in-the-story
check, verdict PROCEED / REFRAME / DROP. DROP stops everything.
1. One central idea only. 2-3 lines: what is it, why care, most surprising thing.
2. Research: verify every date/name/number. Verified facts (with source link)
   + Uncertain claims list. Never invent stats, quotes or mechanisms.
3. Script 85-100 words (hard limit 115): HOOK -> CURIOSITY -> EXPLANATION ->
   SURPRISING DETAIL -> LOOP-BACK ENDING. One ending only: the loop-back line.
   No spoken subscribe/like/comment/share, no "send to a friend", no closing question.
4. Storyboard: 8-10 scenes max, 3-4s each. Scene | Time | Narration | Visual |
   Omni Flash prompt | Kinetic text. Every sentence in exactly one scene.
5. Visual rules: maps only for geography/routes (accurate, labels in CapCut);
   machines shown working (full -> cutaway -> mechanism -> real use); science
   as accurate simulation; history as labelled reconstruction.
   Omni Flash prompts: subject, action, camera, lighting, 9:16, what must NOT appear.
   Continuity: repeat a recurring object's shape/size/colour/material/lighting
   word-for-word in every prompt. One generation per scene first.
   AI TEXT CHECK (mandatory): never ask for words/numbers/labels/logos/ship names
   in a generated visual. Reject any visual with misspelled/garbled text
   (e.g. "EVER GLOBE" for "EVER GIVEN"). All text is added in CapCut.
6. Thumbnail: Nano Banana CLEAN image, no text. 2-4 thumbnail words are a
   CapCut overlay plan only. Prompt ends: "no text, no letters, no words, no logos".
7. Titles: 5 options, scored, pick ONE best. Description 2-3 sentences +
   sources + AI-reconstruction disclosure. Tags, 3-5 hashtags incl. #shorts.
   Pinned comment: one real question (the only engagement ask).
8. CapCut free tier only: 1080x1920, voiceover first, cut visuals to voice,
   hand-corrected auto-captions, music low under voice. Monetization check:
   original educational value, licensed music, AI disclosure ticked, flag risk.
   Quality scores /10: demand, hook, script+loop, research, visual accuracy,
   AI text check, thumbnail, overall. Fix anything under 7.
"""

LONGFORM_PROMPT = """TINY TIMELINE LAB — LONG-FORM (condensed master prompt)
Channel: Tiny Timeline Lab — long-form ONLY here. Horizontal 16:9, 8-10 min
(aim 8:30-9:30 so a real render still lands over 8 min for mid-roll ads).
Audience: US/UK/Canada/Australia, natural conversational American English.
Voice: Google AI Studio Charon, masculine low-pitched, ~152 wpm.
Style: 2.5D cartoon throughout. Map animation ONLY where a route/battle/
border/location carries the story; maps from verified base data, animated
in CapCut — never ask AI for accurate geography.
Step 0 — DEMAND CHECK first (5 lines max), verdict PROCEED / REFRAME / DROP.
  Narrow beats broad: never a whole war/era as a first topic. One night, one
  decision, one trick. Example PROCEED: Constantinople — NOT the whole 53-day
  siege, only "70 ships over land in one night" as an engineering puzzle.
1. One central idea. The Engineer in the Story lens.
2. Research: verified facts + source links, uncertain list, DO-NOT-SAY list.
   Never invent stats/quotes/mechanisms.
3. Script 1150-1350 words, 5 acts: (1) hook + impossible problem, in medias
   res then ONE rewind; (2) person + constraint; (3) clever machine/trick step
   by step; (4) cost + turning point; (5) aftermath + open ending + 20s outro
   (1-line recap, subscribe, next video). Cold-open/rewind trick max 2x total.
   A question every ~60s. Date banner + chapter title per act.
   Pronunciation guide for EVERY difficult name (learn from the WWII review:
   Barbarossa, Volga, Rhine, Elbe, Iwo Jima, Doolittle, Bagration, Maginot —
   check before recording, never let a name in without its respelling).
4. Storyboard 40-48 scenes: Tier 1 hero AI clip 6s (22-28 clips, one subject/
   one camera move/one action), Tier 2 verified map/still (slow pan/zoom),
   Tier 3 CapCut graphic/recut (0 credits). Facts embedded in every visual
   prompt: dates, numbers, must-show / must-not-show. Safe zone X 8-92%,
   Y 10-72%. AI TEXT CHECK mandatory (see Shorts prompt).
5. Thumbnail: Nano Banana clean image, no text; 2-4 words = CapCut overlay.
6. Titles: 5 options, scored, pick ONE. Description + sources + AI disclosure.
   Tags, 3-5 hashtags. Pinned comment: one real question. Chapters with
   timestamps matching the storyboard acts.
7. CapCut free tier: 1920x1080 24fps, voiceover first, hand-corrected captions.
   Loudness -14 LUFS +/-1, true peak <= -1 dBTP. PRE-PUBLISH GATE (binary,
   all must pass): facts vs register, do-not-say checked, every visual checked
   for wrong AI text, captions vs script, AI disclosure ticked, reconstructions
   labelled illustrative, music licensed, outro present, chapters match.
8. Credits (Omni Flash only, never Veo): 25 Tier-1 clips x 6s x 3 = 450 primary
   + 8 retakes x 18 = 144 reserve = 594 max per long-form. Warn before spending
   past it. Read the Flow cost screen before every run — it is the authority.
9. Repetitive-content safety: same niche is safe; same story/template/visuals/
   script structure repeated is NOT. Every video: new research, new visuals,
   new angle, new person, new ending question. Never upload the same video to
   both channels. Never guarantee monetization.
"""

DEMAND_CHECK_TEMPLATE = """STEP 0 — DEMAND CHECK (topic: {topic})
Interest: [what exact phrases would viewers type/say?]
Existing: [3-5 videos, their angle, view count if visible — never invent]
Missing angle: [one sentence — what they did NOT cover / got wrong]
Viewer in the story: [can the viewer imagine themselves in it? yes/no + why]
Verdict: PROCEED / REFRAME (new angle: ...) / DROP (why + 1 stronger topic)
If DROP, stop here. Do not script, do not generate, do not spend credits.
"""

FLOW_MANUAL_STEPS = """GOOGLE FLOW / OMNI FLASH — MANUAL STEPS (no public API exists)
This backend does NOT call Flow. For each scene in prompts/flow-prompts.txt:
  1. Open Google Flow in your browser (AI Pro account {account}).
  2. Paste ONE scene prompt. Model: Omni Flash, 720p, 9:16 (Short) / 16:9 (long).
  3. Check the Flow cost screen BEFORE generating (3 credits/sec is the
     expected rate; the screen is the only authority).
  4. Generate once per scene. Regenerate ONLY a failed scene.
  5. Download the clip into jobs/<job>/clips/ as scene-01.mp4, scene-02.mp4, ...
  6. Inspect every clip for AI-generated text. Reject misspelled text and
     regenerate with "no text, no letters, no logos" added.
  7. Run: python -m factory.cli assemble --job <job>   (FFmpeg, local, CPU)
Nano Banana thumbnail: paste the clean thumbnail prompt from prompts.md,
download the image, add text ONLY in CapCut. Never bake text into the image.
Charon voice: generate in Google AI Studio (Charon), or run:
  python -m factory.cli voice --job <job>   (Gemini TTS API, if GEMINI_API_KEY set)
"""

__all__ = ["FIVE_RULES", "SHORTS_V2_PROMPT", "LONGFORM_PROMPT",
           "DEMAND_CHECK_TEMPLATE", "FLOW_MANUAL_STEPS"]
