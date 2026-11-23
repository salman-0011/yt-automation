# Skills — how to add one

A skill is a plain Markdown instruction file that a job follows. The
pipeline reads the chosen skill and applies its rules to the script,
scenes, voice and style. No code change is needed to change how videos
are made — edit the skill file.

## Shipped skills (defaults)

- `origin-loop-shorts.md` — Origin Loop Shorts. Shorts only, 35–45s,
  85–100 words, 8–10 scenes, loop-back ending, Charon voice.
- `tiny-timeline-longform.md` — Tiny Timeline Lab long-form. 8–10 min,
  1150–1350 words, 5 acts, 40–48 scenes, 2.5D cartoon, 20s outro.

The dashboard picks `auto` by default: Short jobs use
`origin-loop-shorts`, long-form jobs use `tiny-timeline-longform`.
Pick a different skill per job in the dashboard, or with
`--skill <name>` on the CLI.

## Adding your own skill

1. Copy one of the shipped files to `skills/<your-name>.md`.
2. Edit the rules: format, word count, scene count, voice, style,
   thumbnail rules, pre-publish gate. Keep the shared storytelling
   identity (the 5 rules) unless you mean to change it.
3. Restart the dashboard (or re-run `python -m factory.cli options`)
   — skills are listed from this folder at startup.
4. Pick it for a job. The pipeline copies the skill into
   `jobs/<slug>/prompts/skill.md` so every job records exactly which
   skill it followed.

## Rules for skills

- A skill sets rules. It never calls tools, never uploads, never
  invents facts. The supervisor (Muse) plans the job; Python renders it.
- Keep the demand check in the skill: PROCEED / REFRAME / DROP, and
  DROP stops the job before anything is spent.
- Keep the angle rule: first generate 5 different angles, pick the one
  big channels did not use, then write only that angle.
- Keep the monetisation guardrails: original research, original script,
  original angle per job; meaningful visuals; real voiceover with a
  pronunciation guide; a pre-publish gate.
