# GPU fallback — only if a CPU step cannot do the job

CPU-first is the default. Use free GPU ONLY as a fallback:

- Google Colab (free tier): upload the job's script/animation notebook,
  run the heavy step, download the result, delete the Colab runtime.
  Session limits apply; do not rely on it for daily production.
- Hugging Face Spaces / Inference: for a single image/model step that
  will not run on CPU. Keep prompts and outputs in the job folder.

Never put API keys in a notebook you share. Never treat Colab as the
main pipeline — the laptop pipeline (this repo) is the main one.
Local AI image generation (Stable Diffusion / ComfyUI) will NOT run
well on the Toshiba A30-D — that is why it is not in the core pipeline.
