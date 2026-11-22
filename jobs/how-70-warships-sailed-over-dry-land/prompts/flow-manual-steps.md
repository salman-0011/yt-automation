GOOGLE FLOW / OMNI FLASH — MANUAL STEPS (no public API exists)
This backend does NOT call Flow. For each scene in prompts/flow-prompts.txt:
  1. Open Google Flow in your browser (AI Pro account A (or B — track it in credits)).
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
