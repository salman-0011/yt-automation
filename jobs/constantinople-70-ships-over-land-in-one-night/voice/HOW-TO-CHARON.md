CHARON VOICE — MANUAL STEPS (Google AI Studio, no API key needed)
  1. Open Google AI Studio -> Generate speech / TTS.
  2. Voice: Charon. Same voice on every video, never change it.
  3. Paste ONE act file at a time from jobs/<job>/voice/ (act-01.txt ...).
  4. Speed: brisk for Shorts (~145-165 wpm feel), natural ~152 wpm for long-form.
  5. Check EVERY difficult name against jobs/<job>/pronunciation.md before
     recording. If a name sounds wrong, re-record that line only.
  6. Save as act-01.mp3 ... into jobs/<job>/voice/ and run:
       python -m factory.cli captions --job <job>
       python -m factory.cli assemble --job <job>
Local fallback (voice will NOT match Charon — use only as a draft):
  Piper (CPU, offline): pip install piper-tts — pick an English male voice.
  Kokoro-82M (CPU): see README. Draft only; final must be Charon.
