# Skill (repo copy) — used by the pipeline, not by chat

This file is a skill the auto-runner follows for a job. The job picks it
in the dashboard (or with --skill). The pipeline reads this file and
applies its rules to the script, scenes, voice and style. To change how
videos are made, edit this file — no code change needed. To add a skill,
drop another .md file in skills/ and pick it per job.

# Origin Loop Shorts

## When to use this skill

- Use this skill when the user gives a topic for a new Origin Loop Short and asks for the production package.

- Use this skill only for Shorts. Do not use it for long form video. Origin Loop is Shorts only. Long-form content belongs on Tiny Timeline Lab, under the `tiny_timeline_longform` skill.

- The pipeline makes the video file when the user presses Run on a job.
  This skill only sets the rules the pipeline follows.

- Read `references/origin-loop-shorts-prompt.md` before you start work on a topic. That file is the master v2 prompt and it sets the rules for the whole package.

## Channel pattern — Origin Loop (keep this look every time)

- **Channel:** Origin Loop (@originloopofficial) — Shorts ONLY, never long-form.
- **Length:** 30-60 seconds, 85-100 word script, 8-10 scenes of 3-4 seconds.
- **Form / style (default):** cinematic realistic — real-looking machines,
  incidents and places; Flow / Omni Flash clips when made by hand, code
  scene cards (Pillow + FFmpeg Ken Burns) when auto-rendered. 9:16, 720x1280.
  Do NOT default to stick figures or flat cartoon — that is not this channel.
- **Topics:** engineering, science, technology, history, inventions, how
  machines work. Proven, searched stories (real incidents, high stakes,
  visible machines, a specific number in the title). Sequence guide, flexible:
  3 engineering, 3 history, 3 technology, then incidents — never rigid.
- **Angle:** one person facing one impossible problem; hook in the first line;
  a question every ~60 seconds; end with a curiosity/surprise left open.
- **Voice:** Charon (Google AI Studio / Gemini TTS), masculine low-pitched,
  same voice on every video. Captions via ElevenLabs only.
- **Thumbnail:** Nano Banana clean image (no text); words added in CapCut.
- **What works here (verified):** Tonga anchor incident, Excavators, Roman
  Aqueduct — real incident + stakes + machine + number. What flops: abstract
  physics explainers with no incident and no machine.

## Shared storytelling identity

- Do not chase a totally new or unknown topic. Use a proven and searched story that others already told and win by telling it from a different angle, in a different style, with better and more meaningful visuals.

- Start every story in the middle of an impossible problem, not with a history lesson.

- Tell every story through one person's eyes.

- Leave a question about every 60 seconds that the viewer cannot answer yet.

- Make every visual explain the story, not decorate it. If you remove the visual and the story stays clear, the visual is wrong.

- End with curiosity or surprise left open, not with a summary.

- Do not produce generic textbook wording. First generate 5 different angles, pick the one that big channels did not use, then write only that angle and use only facts that support it.

- Use the Origin Loop angle lens called The Engineer in the Story. Find one problem, one impossible constraint, one clever machine or trick, and one cost or consequence.

- Apply this identity to Shorts and to long form alike. It is shared with the `tiny_timeline_longform` skill.

## Run the demand check first

- Run Step 0 from the reference file before any research or scripting.

- Check search interest with `browser.search` and check 3 to 5 existing Shorts or videos on the topic.

- State the missing angle in one sentence.

- Give a verdict of PROCEED or REFRAME or DROP.

- Stop the whole package when the verdict is DROP. Offer one stronger replacement topic instead.

- Choose topics on public demand only. Do not choose a topic from the user's background or qualifications.

## Produce the package

- Follow the reference file in order and return exactly its 10 output blocks in order.

- Verify every date, name, number and technical claim with `browser.search` before you write the script.

- Keep the script to 85 to 100 words for a 35 to 45 second Short.

- Keep the storyboard to 8 to 10 scenes of 3 to 4 seconds each.

- End the script with one loop back line only. Do not add a spoken subscribe, like, comment or share request.

- Keep the voice direction fixed to Google AI Studio Charon, masculine and low pitched, brisk and energetic.

- Give 5 title options, score each briefly, then pick one best title.

- Give a clean thumbnail image prompt with no text in the image. Put the 2 to 4 thumbnail words in the CapCut overlay plan only.

## Check before delivering

- Inspect every visual idea for text that an AI model could add on its own.

- Reject any visual with misspelled or wrong text and say how to regenerate it.

- Check numbers and units in every CapCut overlay against the verified facts.

- Check the title grammar by hand before you deliver it.

- Present the 10 blocks in chat in order. Offer a Word document only when the user asks for a file.



## Alternatives for better results

- When a topic fails the demand check, reframe it around a real event, a visible machine or a question the viewer can imagine themselves in.

- When the user has no topic yet, propose 3 demand led topics with a one line reason for each and let the user choose one.
