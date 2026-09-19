"""One model-selected fixture action, with an explicit response schema.

Guided lessons do not depend on a model's native tool-call parser. The model
chooses whether to call the single declared tool and supplies its arguments;
only the scoped executor performs the action and produces completion evidence.
"""
import asyncio
import json

import httpx

from .chat import ModelError, OLLAMA_HOST, OLLAMA_MODEL


async def call_guided_action(persona, history, *, tool_executor):
    if len(persona.tools) != 1:
        raise ModelError("The guided lesson requires one declared tool.")
    tool = persona.tools[0]["function"]
    schema = {
        "type": "object",
        "properties": {
            "call_tool": {"type": "boolean"},
            "arguments": {"anyOf": [tool["parameters"], {"type": "null"}]},
            "reply": {"type": "string"},
        },
        "required": ["call_tool", "arguments", "reply"],
        "additionalProperties": False,
    }
    system = (
        persona.system_prompt + "\nYou have one tool: " + json.dumps(tool)
        + ".\nRequest that tool with a JSON decision matching this schema: "
        + json.dumps(schema)
        + ". Set call_tool false and arguments null if no tool is needed. "
        "The reply is a brief user-facing message about the action you request, "
        "not a claim that it has already succeeded."
    )
    payload = {"model": OLLAMA_MODEL, "messages": [{"role": "system", "content": system}, *history],
               "format": schema, "stream": False, "options": persona.options}
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(OLLAMA_HOST + "/api/chat", json=payload)
            response.raise_for_status()
            body = response.json()
        if not isinstance(body, dict) or not isinstance(body.get("message"), dict):
            raise ValueError("invalid envelope")
        message = body["message"]
        if message.get("tool_calls") or not isinstance(message.get("content"), str):
            raise ValueError("unexpected response format")
        decision = json.loads(message["content"])
        if (not isinstance(decision, dict)
                or set(decision) != {"call_tool", "arguments", "reply"}
                or type(decision["call_tool"]) is not bool
                or not isinstance(decision["reply"], str) or not decision["reply"].strip()
                or (decision["call_tool"] and not isinstance(decision["arguments"], dict))
                or (not decision["call_tool"] and decision["arguments"] is not None)):
            raise ValueError("invalid decision")
    except (httpx.HTTPError, ValueError) as exc:
        raise ModelError("The AI service did not return a valid guided action.") from exc
    if decision["call_tool"]:
        await asyncio.to_thread(tool_executor, tool["name"], decision["arguments"])
    # This is the model's message about its requested action, not proof of success.
    # The executor's separately recorded result is the authoritative evidence.
    return decision["reply"]
