import json
import os
from typing import Any

import httpx

from .db import db
from .personas import Persona, get_persona
from .tools import TOOL_REGISTRY

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")

# Trim history to this many turns to keep prompts in context window.
MAX_HISTORY = 20

# Cap on tool-call rounds within a single user turn (prevents infinite loops).
MAX_TOOL_ITERATIONS = 6


def get_history(user_id: int, persona_slug: str) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            "SELECT role, content FROM chat_messages "
            "WHERE user_id = ? AND persona = ? "
            "ORDER BY created_at ASC, id ASC",
            (user_id, persona_slug),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def save_message(user_id: int, persona_slug: str, role: str, content: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO chat_messages (user_id, persona, role, content) VALUES (?, ?, ?, ?)",
            (user_id, persona_slug, role, content),
        )


def _coerce_args(raw: Any) -> dict:
    """Ollama may return tool args as a dict or a JSON-encoded string."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}
    return {}


def _execute_tool(name: str, args_raw: Any) -> str:
    args = _coerce_args(args_raw)
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return json.dumps({"error": f"unknown tool: {name}"})
    try:
        result = fn(**args)
    except TypeError as e:
        return json.dumps({
            "error": "invalid_arguments",
            "detail": str(e),
            "args_seen": args,
        })
    except Exception as e:
        return json.dumps({"error": type(e).__name__, "detail": str(e)})
    if isinstance(result, str):
        return result
    return json.dumps(result, default=str)


async def call_ollama(persona: Persona, history: list[dict]) -> str:
    messages: list[dict] = [{"role": "system", "content": persona.system_prompt}]
    messages.extend(history[-MAX_HISTORY:])

    async with httpx.AsyncClient(timeout=180) as client:
        for _ in range(MAX_TOOL_ITERATIONS):
            payload: dict = {
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
            }
            if persona.tools:
                payload["tools"] = persona.tools

            try:
                resp = await client.post(f"{OLLAMA_HOST}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as e:
                return (
                    f"[Backend error: the AI service is unreachable or slow. "
                    f"Try again in a moment. ({type(e).__name__})]"
                )

            msg = data.get("message", {}) or {}
            tool_calls = msg.get("tool_calls") or []

            if not tool_calls:
                return msg.get("content", "(no response)")

            # Append the assistant message (with tool_calls) so the model
            # retains its own request when we feed back the tool results.
            messages.append({
                "role": "assistant",
                "content": msg.get("content", ""),
                "tool_calls": tool_calls,
            })

            for call in tool_calls:
                fn_data = call.get("function", {}) or {}
                name = fn_data.get("name", "")
                args_raw = fn_data.get("arguments", {})
                result = _execute_tool(name, args_raw)
                messages.append({
                    "role": "tool",
                    "content": result,
                })

    return "[Tool-call loop exceeded; please rephrase your request.]"


async def send_message(
    user_id: int, persona_slug: str, user_message: str
) -> str:
    persona = get_persona(persona_slug)
    if not persona:
        raise ValueError(f"Unknown persona: {persona_slug}")
    save_message(user_id, persona_slug, "user", user_message)
    history = get_history(user_id, persona_slug)
    bot_response = await call_ollama(persona, history)
    save_message(user_id, persona_slug, "assistant", bot_response)
    return bot_response
