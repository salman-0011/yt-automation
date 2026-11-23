# Skill (repo copy) — used by the pipeline, not by chat

This file is a skill the auto-runner follows for a job. The job picks it
in the dashboard (or with --skill). The pipeline reads this file and
applies its rules to the script, scenes, voice and style. To change how
videos are made, edit this file — no code change needed. To add a skill,
drop another .md file in skills/ and pick it per job.

# Tiny Timeline Lab Long-Form

## When to use this skill

- Use this skill when the user gives a topic for a new Tiny Timeline Lab long-form video and asks for the production package.

- Use this skill only for long form. Do not use it for Shorts. Use `origin_loop_shorts` for Origin Loop Shorts.

- Use this skill for Tiny Timeline Lab only. Tiny Timeline Lab is the long-form channel. It also posts Shorts there as trailers and teasers for its own long-form videos, but this skill covers long form only.

- Origin Loop is Shorts only. Do not plan long-form content for Origin Loop.

- The pipeline makes the video file when the user presses Run on a job.
  This skill only sets the rules the pipeline follows.

- The pipeline generates the video from this skill when the user presses Run.

- Read `references/tiny-timeline-longform-prompt.md` before you start work on a topic. That file is the long-form master prompt adapted from the Denmark Production Bible.

## Channel pattern — Tiny Timeline Lab (keep this look every time)

- **Channel:** Tiny Timeline Lab (@TINYTIMELINELAB) — long-form FIRST
  (8-10 minutes, weekly, over 8 min for mid-roll ads), plus Shorts only as
  trailers/teasers for its own long-form videos.
- **Length:** 8-10 minutes, 1150-1350 word script, ~40 scenes.
- **Form / style (default):** 2.5D cartoon map animation — cartoon
  characters over shaded topographic relief maps, big arrows and banners,
  bright colours; map animation only where a route / battle / history map
  is needed, ground dioramas for the rest. 16:9, 720p. Do NOT default to
  stick figures — the channel look is 2.5D cartoon, not stick-figure.
- **Topics:** history first — ancient civilisations, battles, engineering
  marvels, empires, inventions. Proven, searched stories told from one
  narrow, fresh angle (one person, one decision, one machine), never the
  generic retelling (e.g. WWII as a whole — too broad; one decision inside
  it instead).
- **Angle:** one person facing one impossible problem; hook in the first
  line; a question every ~60 seconds; end with a curiosity/surprise left
  open, not a summary.
- **Voice:** Charon (Google AI Studio / Gemini TTS), masculine low-pitched,
  same voice on every video. Captions via ElevenLabs only.
- **Thumbnail:** Nano Banana clean image (no text); words added in CapCut.
- **What works here (verified):** the Constantinople Short (70 warships over
  dry land, 249 views on day one) — one impossible problem, one narrow
  angle. What flops: a broad topic retold generically (WWII in 9 minutes).

## Shared storytelling identity

- Do not chase a totally new or unknown topic. Use a proven and searched story that others already told and win by telling it from a different angle, in a different style, with better and more meaningful visuals.

- Start every story in the middle of an impossible problem, not with a history lesson.

- Tell every story through one person's eyes.

- Leave a question about every 60 seconds that the viewer cannot answer yet.

- Make every visual explain the story, not decorate it. If you remove the visual and the story stays clear, the visual is wrong.

- End with curiosity or surprise left open, not with a summary.

- Do not produce generic textbook wording. First generate 5 different angles, pick the one that big channels did not use, then write only that angle and use only facts that support it.

- Use the Origin Loop angle lens called The Engineer in the Story. Find one problem, one impossible constraint, one clever machine or trick, and one cost or consequence.

- Apply this identity to Shorts and to long form alike. It is shared with the `origin_loop_shorts` skill.

## Run the demand check first

- Run the demand check before any research or scripting.

- Check search interest with `browser.search` and check 3 to 5 existing long-form videos on the topic.

- Note each existing video angle and, where visible, its view count. Do not invent view counts or search volumes. If a number cannot be seen, say so.

- State the missing angle in one sentence.

- Give a verdict of PROCEED or REFRAME or DROP.

- Stop the whole package when the verdict is DROP. Offer one stronger replacement topic instead.

- Choose topics on public demand only. Do not choose a topic from the user's background or qualifications.

- Use Constantinople as the proven example of a PROCEED verdict. Kings and Generals has 4.0 million views on its Fall of Constantinople documentary. The user's own Tiny Timeline Lab Short on 70 warships sailed over dry land reached 249 views in 20 hours. The broad angle is crowded. The narrow angle is the gap. Tell only the 70 ships over land in one night, as an engineering puzzle, not the whole 53 day siege.

- Do not pick a broad whole war or whole era as a first long-form topic. A broad topic competes with channels that already have millions of views. A narrow incident with a number, a date and a visible trick can win.

## Research and fact-check

- Verify every date, name, number and technical claim with `browser.search` before you write the script.

- Keep a fact register with two lists. Verified means a source was opened and confirmed. Confirm means two or more named sources agree but the page was not reopened here, so check it before upload.

- Keep a do-not-say list for the topic. Put every unsettled number, disputed claim and common myth on it and keep those claims out of the spoken script.

- Never invent statistics, quotations, incidents or mechanisms. If a claim cannot be verified, leave it out or keep it only in the research list, clearly labelled uncertain, and out of the spoken script.

- Keep the research short. List only the claims the script actually uses, each with a clickable source link.

- Check numbers that vary by source. Give a range or name the source, never a single exact number presented as settled fact when sources disagree.

## Script structure for 8 to 10 minutes

- Lock the format before scripting. 16 to 9 horizontal, 8 to 10 minutes, English narration, Google AI Studio Charon voice, 2.5D cartoon style.

- Stay over 8 minutes so mid-roll ads are possible. Aim for 8 minutes 30 seconds to 9 minutes 30 seconds in the plan, so a real voice render still lands over 8 minutes.

- Target 1150 to 1350 spoken words at about 152 words per minute. Add planned pauses of 0.3 to 0.6 seconds before reveals and at act breaks. Reconcile words plus pauses plus visual holds to the target runtime by calculation, never by guess.

- Structure the script in 5 acts. Act 1 is the hook and the impossible problem. Act 2 is the person and the constraint. Act 3 is the clever machine or trick explained step by step. Act 4 is the cost and the turning point. Act 5 is the aftermath and the open ending.

- Start Act 1 in medias res at a climax, then rewind once to the start of the story. Use the cold open and rewind trick at most twice in the whole video.

- Keep the timeline broadly chronological after the opening rewind. Do not jump back and forth between years without a clear date banner on screen.

- Give every act a date banner and a chapter title. Chapters must match the timestamps in the storyboard.

- End with a 20 second outro. Give a one sentence recap, a subscribe prompt and a next video prompt. Never end cold with no outro, or autoplay takes the viewer away.

- Write in natural conversational American English. Use short punchy sentences. Avoid textbook language and generic openings.

- Give the clean script again on its own, copy ready, with no production notes, timestamps or stage directions mixed in.

## Storyboard and visuals

- Keep the storyboard to 40 to 48 scenes for 8 to 10 minutes. Each scene carries one narration beat and one visual that explains that beat.

- Use three tiers counted from the storyboard. Tier 1 is a hero AI clip of 6 seconds, one subject, one camera move and one physical action. Tier 2 is a verified map or still scene with a slow pan or zoom. Tier 3 is a CapCut graphic or recut of an earlier clip.

- Plan 22 to 28 Tier 1 hero clips. Keep the rest as Tier 2 and Tier 3 scenes. This tier mix stretches the credit budget and keeps maps accurate.

- Use 2.5D cartoon style for the whole video. Use bright colours, big arrows, cartoon figures and large date and title banners where they explain the story.

- Use map animation only where a route, a battle, a border or a location carries the story. Build every map from verified base data and animate it in CapCut. Never ask an AI model for accurate geography, borders or routes.

- Embed facts in every visual prompt. Give dates, numbers, what must be shown and what must not be shown, in the prompt itself. Repeat the shape, size, colour, material and lighting of a recurring object word for word in every prompt that shows it.

- Keep captions, tanks, arrows and graphics off country labels and on-screen titles. Keep all CapCut callouts inside X 8 percent to 92 percent and Y 10 percent to 72 percent of the frame. Keep the bottom band clear for captions and YouTube controls.

- Use one consistent map style with a scale and a legend, so a viewer can track where places are relative to each other.

- Give one sound effect per scene only where it lands on a visible action. Add light background music low under the voice.

- Check every visual for AI generated text. Never ask for words, numbers, labels, logos, ship names, signs or subtitles inside a generated image or clip. Add all text in CapCut.

- Reject any visual with misspelled or wrong text and say how to regenerate it.

## Voice and pronunciation

- Keep the voice fixed to Google AI Studio Charon, masculine and low pitched, brisk and natural at about 152 words per minute. Never change the voice between videos.

- Give a pronunciation guide for every difficult name in the script, with a plain respelling for each one.

- Learn from the WWII video review. The AI voice slurred proper nouns and YouTube's own transcript rendered them wrong. Check and re-record Barbarossa, Volga, Rhine, Elbe, Iwo Jima, Doolittle, Bagration, Coral Sea and Maginot before you deliver a package that uses any of them.

- Do not let a name appear in the script unless its pronunciation is written down in the guide.

- Render the voiceover in act files with the same style prompt, model and temperature, so pitch and pace do not drift between acts.

- Set loudness to minus 14 LUFS integrated, plus or minus 1, with true peak at or below minus 1 dBTP.

## Thumbnail, titles and publishing package

- Give 5 title options. Score each briefly on curiosity, search relevance and accuracy, then pick one best title and say why in one line.

- Prefer question-led titles where they stay accurate. Check title grammar by hand before you deliver it.

- Give a clean thumbnail image prompt with no text in the image. Put the 2 to 4 thumbnail words in the CapCut overlay plan only.

- Use one dominant subject, strong contrast, cinematic lighting and a dark teal or other high-contrast background, horizontal 16 to 9. End the image prompt with no text, no letters, no words, no logos.

- Write a description of 2 to 3 natural sentences with the main keyword, what the viewer learns, the sources and a line disclosing that visuals are AI-generated reconstructions where that applies.

- Give relevant comma-separated tags with no keyword stuffing, and 3 to 5 hashtags only.

- Give one pinned comment question that invites a real answer and ties to the open ending. This is the only engagement ask.

- Give chapters with timestamps that match the storyboard acts.

## CapCut checklist and pre-publish gate

- Use CapCut free tier only. Never require a Pro feature.

- Create a 16 to 9 project. Import scenes in storyboard order and place the Charon voiceover first. Cut visuals to the voice, not the other way round.

- Sync each scene change to its sentence. Add auto-captions, then correct them by hand. Check caption timing and spelling, never trust auto-captions.

- Add kinetic text callouts only where the plan calls for them. Keep them in the safe zone and in US spelling.

- Export at 1920 by 1080 at 24 frames per second. Watch the full export once before uploading. Check captions, text, pacing, the loop of the ending and the outro.

- Run a binary pre-publish gate. Every item must pass or the video does not upload. Check facts against the register, check the do-not-say list, check every visual for wrong AI text, check captions against the script, check that the AI disclosure is ticked at upload, check that reconstructions are labelled illustrative and never presented as real footage, and check that music and sound effects are licensed or from CapCut's usable library.

## Monetization and repetitive content safety

- Confirm the video adds original educational value and is not repetitive or mass-produced filler. Flag any remaining risk in one line. Never guarantee monetization approval.

- Keep the same niche across videos. The same niche is safe. The same story, the same template, the same visuals or the same script structure repeated is not safe.

- Follow the YouTube July 2026 inauthentic content policy. Generic, repetitive or template-based content with little variation from video to video can lose monetization, even when the topic changes.

- Make every long-form video new in research, in visuals and in structure. Change the angle, change the person at the centre, change the visual plan and change the ending question for every video.

- Never reuse a hero clip, a map build or a script block from an earlier video without saying so in the package and rebuilding it for the new angle.

- Never upload the same video to both channels. One video belongs to one channel only.

- Do not promise a monetization date. State the current bar honestly. Full ad revenue needs 1000 subscribers plus either 4000 qualified long-form watch hours in 12 months or 10 million qualified Shorts views in 90 days, and that bar doubles for new applicants from 1 February 2027.

## Production stack and credit plan

- Use Omni Flash only for video generation. Do not use Veo. Veo leaves on 5 December and charges 100 credits for an 8 second video, against Omni Flash at 3 credits per second at 720p.

- Use Google AI Studio Charon for voice. Use ElevenLabs for captions only. Use Nano Banana for thumbnails and stills. Edit in CapCut free tier.

- Track credits per account separately. The user has 2 Google AI Pro accounts with 1000 credits each plus 50 credits per day on each account, so 2000 credits to start plus 100 per day in total.

- Budget a 9 minute long-form video at 25 Tier 1 clips of 6 seconds at 3 credits per second, which is 450 credits for the primary pass. Hold a retake reserve of up to 8 clips at 18 credits each, which is 144 credits. Plan a maximum of 594 credits for one long-form video and warn the user before spending past it.

- Read the Flow cost screen before every run. The number shown there is the only authority on price.

- Generate one output per scene first. Regenerate only a failed scene, not the whole set.



## Alternatives for better results

- When a topic fails the demand check, reframe it around one incident, one visible machine or one question the viewer can imagine themselves in.

- When a broad topic fails, narrow it to one night, one decision or one trick inside that topic, as with the 70 ships over land inside Constantinople.

- When the user has no topic yet, propose 3 demand-led topics with a one line reason for each and let the user choose one.
