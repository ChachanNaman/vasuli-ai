"""LLM client with Groq primary / Gemini automatic fallback (PRD §8, §10).

Both providers are wired for tool-calling against the same JSON schema
(app/agents/prompts.py::DIAGNOSE_TOOL_SCHEMA) so the caller gets one
consistent structured dict back regardless of which provider answered.

Every fallback event (Groq erroring or rate-limiting, so we drop to Gemini)
is logged via the `on_fallback` hook so it shows up in the audit trail —
this doubles as PRD §10's built-in resilience feature.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger("vasuli.llm_client")


@dataclass
class LLMResult:
    data: dict
    provider: str  # 'groq' | 'gemini'
    fallback_used: bool


class LLMClientError(Exception):
    """Raised when both Groq and Gemini fail to produce a usable structured result."""


GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")


def _groq_client():
    from groq import Groq

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise LLMClientError("GROQ_API_KEY is not set")
    # max_retries=0: on free-tier rate limits, fail fast into our own
    # Groq -> Gemini fallback (see call_diagnosis_llm) instead of sitting
    # through the SDK's internal exponential backoff (which can eat 30s+
    # per call across a batch, since it happens before our fallback logic
    # ever runs). timeout=20: without an explicit cap a hung request blocks
    # the whole (sequential) batch indefinitely.
    return Groq(api_key=api_key, max_retries=0, timeout=20.0)


def _call_groq(system_prompt: str, user_prompt: str, tool_schema: dict) -> dict:
    client = _groq_client()
    tool = {"type": "function", "function": tool_schema}

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        tools=[tool],
        tool_choice={"type": "function", "function": {"name": tool_schema["name"]}},
        temperature=0.2,
    )

    message = response.choices[0].message
    tool_calls = getattr(message, "tool_calls", None)
    if not tool_calls:
        raise LLMClientError("Groq response contained no tool call")

    args_raw = tool_calls[0].function.arguments
    return json.loads(args_raw)


# ---------------------------------------------------------------------------
# Gemini fallback. google-generativeai's function-calling schema uses its own
# protobuf Schema type rather than raw JSON-schema dicts, so we translate the
# shared DIAGNOSE_TOOL_SCHEMA into it here.
# ---------------------------------------------------------------------------


def _json_schema_to_gemini_schema(schema: dict):
    import google.generativeai as genai

    type_map = {
        "string": genai.protos.Type.STRING,
        "number": genai.protos.Type.NUMBER,
        "integer": genai.protos.Type.INTEGER,
        "boolean": genai.protos.Type.BOOLEAN,
        "object": genai.protos.Type.OBJECT,
        "array": genai.protos.Type.ARRAY,
    }

    json_type = schema.get("type", "string")
    # Handle ["string", "null"] style nullable unions — Gemini has no null
    # type, so fall back to the first non-null type and mark nullable.
    nullable = False
    if isinstance(json_type, list):
        nullable = "null" in json_type
        non_null = [t for t in json_type if t != "null"]
        json_type = non_null[0] if non_null else "string"

    kwargs: dict[str, Any] = {
        "type": type_map.get(json_type, genai.protos.Type.STRING),
        "description": schema.get("description", ""),
        "nullable": nullable,
    }

    if json_type == "object" and "properties" in schema:
        kwargs["properties"] = {
            k: _json_schema_to_gemini_schema(v) for k, v in schema["properties"].items()
        }
        if "required" in schema:
            kwargs["required"] = schema["required"]

    if json_type == "array" and "items" in schema:
        kwargs["items"] = _json_schema_to_gemini_schema(schema["items"])

    if "enum" in schema:
        kwargs["enum"] = schema["enum"]
        kwargs["format"] = "enum"

    return genai.protos.Schema(**kwargs)


def _gemini_client(tool_schema: dict):
    import google.generativeai as genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise LLMClientError("GEMINI_API_KEY is not set")
    genai.configure(api_key=api_key)

    function_declaration = genai.protos.FunctionDeclaration(
        name=tool_schema["name"],
        description=tool_schema["description"],
        parameters=_json_schema_to_gemini_schema(tool_schema["parameters"]),
    )
    tool = genai.protos.Tool(function_declarations=[function_declaration])

    return genai.GenerativeModel(
        GEMINI_MODEL,
        tools=[tool],
        tool_config={"function_calling_config": {"mode": "ANY"}},
    )


def _proto_to_python(value):
    """Recursively convert proto-plus MapComposite/RepeatedComposite values
    to plain dict/list. `dict(function_call.args)` only converts the top
    level — nested object/array fields (e.g. action_params) are left as
    MapComposite/RepeatedComposite, which fails `isinstance(x, dict)`
    downstream in diagnosis_agent's contract validation."""
    if hasattr(value, "items"):
        return {k: _proto_to_python(v) for k, v in value.items()}
    if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
        return [_proto_to_python(v) for v in value]
    return value


def _call_gemini(system_prompt: str, user_prompt: str, tool_schema: dict) -> dict:
    model = _gemini_client(tool_schema)
    # request_options timeout: same reasoning as Groq's timeout above — a
    # hung call here would otherwise block the whole sequential batch.
    response = model.generate_content(
        [f"{system_prompt}\n\n{user_prompt}"],
        generation_config={"temperature": 0.2},
        request_options={"timeout": 20},
    )

    candidates = response.candidates or []
    if not candidates:
        raise LLMClientError("Gemini response had no candidates")

    for part in candidates[0].content.parts:
        function_call = getattr(part, "function_call", None)
        if function_call and function_call.name == tool_schema["name"]:
            return _proto_to_python(function_call.args)

    raise LLMClientError("Gemini response contained no matching function call")


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def call_diagnosis_llm(
    system_prompt: str,
    user_prompt: str,
    tool_schema: dict,
    on_fallback: Optional[Callable[[str, str], None]] = None,
) -> LLMResult:
    """Try Groq first; on any error or rate-limit, fall back to Gemini.

    `on_fallback(reason, from_provider)` is called exactly once if and only
    if the fallback path is taken, so the caller can write a fallback event
    to the audit trail (PRD §10).
    """
    try:
        data = _call_groq(system_prompt, user_prompt, tool_schema)
        return LLMResult(data=data, provider="groq", fallback_used=False)
    except Exception as groq_error:  # noqa: BLE001 - any Groq failure triggers fallback
        logger.warning("Groq call failed, falling back to Gemini: %s", groq_error)
        if on_fallback:
            on_fallback(str(groq_error), "groq")

        try:
            data = _call_gemini(system_prompt, user_prompt, tool_schema)
            return LLMResult(data=data, provider="gemini", fallback_used=True)
        except Exception as gemini_error:  # noqa: BLE001
            logger.error("Gemini fallback also failed: %s", gemini_error)
            raise LLMClientError(
                f"Both Groq and Gemini failed. Groq: {groq_error}. Gemini: {gemini_error}"
            ) from gemini_error
