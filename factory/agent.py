"""Muse supervisor agent — Google Gen AI SDK, proper tool-calling.

Muse is the supervisor (the project manager). The agent works through
the Google Gen AI SDK (`google-genai`, `from google import genai`)
with an API key — NOT through the Gemini CLI or the AntiGravity CLI.
Those CLIs are a manual fallback only: they have session-time and
authentication problems, so they are never the default and never the
supervisor.

How it works (the same shape as OpenAI's Agents SDK):
  1. Seven Python tools are defined — one per production step. The
     tools do the real work (they are the pipeline functions in
     factory/audio.py, visuals.py, captions.py, video.py, qc.py and
     supervisor.py); the model never renders anything itself.
  2. The tools are declared to the model as FunctionDeclarations.
  3. The agent loop sends the job to the model, the model calls tools
     in order (one video at a time), this file executes each call and
     feeds the result back, until the QC tool has run.
  4. Order is enforced: a tool called out of order is NOT executed —
     the model gets an error result telling it which tool is next.
  5. If the model stalls, errors, or the loop runs out of turns, the
     deterministic runner (factory/auto.py) finishes the remaining
     steps sequentially with the same tools. Nothing is left half-done
     because the model stopped talking.

No SDK installed or no API key is a normal setup state: sdk_ready()
is False, the loop is skipped, and the sequential runner uses the
job's own script.md. Nothing here invents a model: planning uses
cfg.gemini_model (default gemini-2.5-flash).
"""
from __future__ import annotations

from .config import Config
from .genai_client import sdk_ready

TOOL_ORDER = ["plan_angle", "write_script", "make_voice", "make_visuals",
              "make_captions", "assemble_video", "run_qc"]

MAX_TURNS = 16

TOOL_DECLARATIONS = [
    {
        "name": "plan_angle",
        "description": (
            "STEP 1 — pick the ONE angle for this video, BEFORE any script "
            "is written. Give the angle big channels did NOT use: one "
            "person, one decision, one machine, or one impossible problem. "
            "Also give the demand verdict: PROCEED (real demand), REFRAME "
            "(demand exists but the angle must change) or DROP (no demand — "
            "the job stops). The hook and the thumbnail angle must follow "
            "this one angle."),
        "parameters": {
            "type": "object",
            "properties": {
                "angle": {"type": "string", "description": "The one chosen angle, one sentence."},
                "person": {"type": "string", "description": "The one person whose eyes the story is told through."},
                "problem": {"type": "string", "description": "The impossible problem at the heart of the story."},
                "hook": {"type": "string", "description": "The opening line (first sentence of the script)."},
                "thumbnail_angle": {"type": "string", "description": "The one moment the thumbnail shows."},
                "why_different": {"type": "string", "description": "Why no big channel used this angle."},
                "existing_angles": {"type": "array", "items": {"type": "string"},
                                    "description": "Angles existing videos on this topic already used."},
                "demand_verdict": {"type": "string", "enum": ["PROCEED", "REFRAME", "DROP"]},
            },
            "required": ["angle", "person", "problem", "hook", "thumbnail_angle",
                         "why_different", "demand_verdict"],
        },
    },
    {
        "name": "write_script",
        "description": (
            "STEP 2 — write the full narration script, following the chosen "
            "angle exactly: start with the hook, tell it through the one "
            "person, leave a question every ~60 seconds, end with a "
            "curiosity/surprise left open (not a summary). Narration only — "
            "no headings, no scene labels, no stage directions. Short: "
            "85-100 words. Long-form: 1150-1350 words. Never generic "
            "textbook wording."),
        "parameters": {
            "type": "object",
            "properties": {
                "script": {"type": "string",
                           "description": "The complete narration, ready to read aloud."},
            },
            "required": ["script"],
        },
    },
    {
        "name": "make_voice",
        "description": (
            "STEP 3 — render the voiceover (Charon) from the script. "
            "No arguments: the tool reads the saved script."),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "make_visuals",
        "description": (
            "STEP 4 — render the scene visuals. Every scene's visual must "
            "explain its own narration, not decorate it. No arguments: "
            "the tool reads the saved script and scenes."),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "make_captions",
        "description": (
            "STEP 5 — make the captions (SRT) for the video. No arguments: "
            "the tool reads the saved script and voiceover."),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "assemble_video",
        "description": (
            "STEP 6 — assemble the scene clips + voiceover + captions into "
            "the finished mp4, and make the thumbnail (same angle as the "
            "script). No arguments."),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "run_qc",
        "description": (
            "STEP 7 (LAST) — run the pre-publish QC gate: repetitive script "
            "vs previous jobs, angle reused, generic visuals, missing facts, "
            "custom instructions not reflected, pronunciation. Report the "
            "result honestly; do NOT mark the job done yourself — the "
            "runner decides done vs needs-review from this result. "
            "No arguments."),
        "parameters": {"type": "object", "properties": {}},
    },
]


def build_system_instruction(context: dict) -> str:
    """System instruction: Muse, supervisor of ONE video, tools in order."""
    return (
        "You are Muse, the supervisor (project manager) of a one-video-at-a-time "
        "YouTube production pipeline. You plan and coordinate; Python tools do "
        "the actual work. You never render video or audio yourself.\n\n"
        "JOB\n"
        f"Topic: {context.get('topic', '')}\n"
        f"Type: {context.get('kind', 'short')} ({context.get('duration_sec', 40)}s, "
        f"{context.get('aspect', '')}, style: {context.get('style', '')})\n"
        f"Skill to follow (this job's rules):\n{context.get('skill_text', '')}\n\n"
        f"Custom instructions for THIS job (must be honoured — they are the "
        f"job's own directions, not a template):\n{context.get('custom_instructions', '(none)')}\n\n"
        "FIVE STORYTELLING RULES (every script must follow all five):\n"
        "1. Start from an impossible problem, not a history lesson.\n"
        "2. Tell it through one person's eyes.\n"
        "3. Leave a question every ~60 seconds.\n"
        "4. Visuals must explain, not just decorate.\n"
        "5. End with a curiosity/surprise left open, not a summary.\n\n"
        "CALL THE TOOLS IN THIS EXACT ORDER, one video at a time:\n"
        "plan_angle -> write_script -> make_voice -> make_visuals -> "
        "make_captions -> assemble_video -> run_qc.\n"
        "Call each tool once. If a tool returns ok=false, fix the input and "
        "retry that tool once; if it fails again, stop and say what failed. "
        "If plan_angle returns demand DROP, stop immediately — do not write "
        "a script. After run_qc, stop and summarise the video in one short "
        "paragraph (angle, backends used, QC result). Never invent a result "
        "a tool did not return."
    )


def run_agent_loop(tools: dict, context: dict, config: Config | None = None,
                   log_fn=None) -> dict:
    """Run the Muse supervisor agent loop.

    tools: {tool_name: callable(args_dict) -> dict} — the real pipeline
    steps, provided by the caller (factory/auto.py). context: job info
    for the system instruction. log_fn(text): audit logging.

    Returns {"used": bool, "completed": [tool names in order],
    "turns": int, "notes": str, "reason": str}. If the SDK/key is
    missing, used=False and the caller runs sequentially instead.
    """
    cfg = config or Config()
    log = log_fn or (lambda text: None)
    if not sdk_ready(cfg):
        return {"used": False, "completed": [], "turns": 0, "notes": "",
                "reason": ("Gen AI SDK not ready (pip install google-genai "
                           "and set GEMINI_API_KEY) — sequential runner used.")}
    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
    except ImportError:
        return {"used": False, "completed": [], "turns": 0, "notes": "",
                "reason": "google-genai package not installed."}

    client = genai.Client(api_key=cfg.gemini_api_key)
    declarations = [types.FunctionDeclaration(
        name=d["name"], description=d["description"],
        parameters=d["parameters"]) for d in TOOL_DECLARATIONS]
    cfg_gen = types.GenerateContentConfig(
        system_instruction=build_system_instruction(context),
        tools=[types.Tool(function_declarations=declarations)],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True),
        temperature=0.7,
    )
    first = (
        f"Make this ONE video: {context.get('topic', '')} "
        f"({context.get('kind', 'short')}, {context.get('duration_sec', 40)} seconds). "
        "Start with plan_angle."
    )
    contents = [types.Content(role="user",
                              parts=[types.Part.from_text(text=first)])]
    completed: list[str] = []
    notes = ""
    last_failed: dict[str, int] = {}
    try:
        for turn in range(1, MAX_TURNS + 1):
            resp = client.models.generate_content(
                model=cfg.gemini_model or "gemini-2.5-flash",
                contents=contents, config=cfg_gen)
            cand = (resp.candidates or [None])[0]
            if cand is None or not getattr(cand, "content", None):
                break
            contents.append(cand.content)
            parts = cand.content.parts or []
            calls = [p.function_call for p in parts
                     if getattr(p, "function_call", None)]
            if not calls:
                notes = resp.text or ""
                break
            response_parts = []
            for call in calls:
                name = call.name
                args = dict(call.args or {})
                expected = (TOOL_ORDER[len(completed)]
                            if len(completed) < len(TOOL_ORDER) else None)
                if name not in TOOL_ORDER:
                    result = {"ok": False,
                              "error": f"Unknown tool: {name}."}
                elif name in completed and last_failed.get(name, 0) == 0:
                    result = {"ok": False,
                              "error": f"{name} is already done — call {expected} next."}
                elif name != expected:
                    result = {"ok": False,
                              "error": (f"Wrong order — call {expected} next, "
                                        f"not {name}.")}
                else:
                    log(f"Agent tool: {name}({list(args)})")
                    try:
                        result = tools[name](args) or {}
                    except Exception as e:  # noqa: BLE001 - tool errors go back to the model
                        result = {"ok": False, "error": str(e)}
                    if not isinstance(result, dict):
                        result = {"ok": bool(result), "result": str(result)}
                    log(f"Agent tool {name} -> ok={result.get('ok')}")
                    if result.get("ok"):
                        completed.append(name)
                        last_failed.pop(name, None)
                    else:
                        last_failed[name] = last_failed.get(name, 0) + 1
                        if last_failed[name] >= 2:
                            log(f"Agent tool {name} failed twice — stopping agent loop.")
                            contents.append(types.Content(
                                role="user",
                                parts=[types.Part.from_function_response(
                                    name=name, response=result)]))
                            return {"used": True, "completed": completed,
                                    "turns": turn, "notes": notes,
                                    "reason": f"Tool {name} failed twice."}
                    if name == "plan_angle" and result.get("demand_verdict") == "DROP":
                        contents.append(types.Content(
                            role="user",
                            parts=[types.Part.from_function_response(
                                name=name, response=result)]))
                        return {"used": True, "completed": completed,
                                "turns": turn, "notes": notes,
                                "reason": "Demand DROP — job stopped."}
                response_parts.append(types.Part.from_function_response(
                    name=name, response=result))
            contents.append(types.Content(role="user", parts=response_parts))
            if len(completed) == len(TOOL_ORDER):
                break
    except Exception as e:  # noqa: BLE001 - agent errors never crash a run
        log(f"Agent loop error: {e}")
        return {"used": True, "completed": completed, "turns": 0,
                "notes": notes, "reason": f"Agent loop error: {e}"}
    return {"used": True, "completed": completed, "turns": MAX_TURNS,
            "notes": notes,
            "reason": ("Agent loop finished." if len(completed) == len(TOOL_ORDER)
                       else "Agent loop ended early — runner completes the rest.")}
