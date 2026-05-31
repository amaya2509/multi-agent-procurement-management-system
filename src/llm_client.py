"""
LLM client wrapper for Ollama integration.

Provides a clean interface for interacting with a locally-hosted Ollama model.
Key features:
- Automatic retry with exponential back-off
- JSON extraction fallback for imperfect model responses
- Full request/response logging for observability
- Structured error handling — never crashes the calling agent
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Optional

import ollama

from src.config import OLLAMA_MODEL, LLM_MAX_RETRIES, LLM_TIMEOUT_SECONDS, LLM_TEMPERATURE
from src.logger import get_logger

logger = get_logger("llm_client")


def _extract_json(text: str) -> Optional[dict[str, Any]]:
    """
    Attempt to extract the first JSON object or array from a text string.

    LLMs sometimes embed JSON inside markdown code fences or prose. This
    function tries three strategies in order:
      1. Direct parse of the whole string.
      2. Extract from a ```json ... ``` code fence.
      3. Find the first {...} or [...] substring and parse it.

    Args:
        text: Raw text from the LLM response.

    Returns:
        Parsed dict/list, or None if extraction fails.
    """
    # Strategy 1: direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Strategy 2: markdown code fence
    fence_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3: first {...} block
    brace_match = re.search(r"(\{[\s\S]*\})", text)
    if brace_match:
        try:
            return json.loads(brace_match.group(1))
        except json.JSONDecodeError:
            pass

    return None


def query_llm(
    prompt: str,
    system_prompt: str,
    model: str = OLLAMA_MODEL,
    expect_json: bool = True,
) -> dict[str, Any]:
    """
    Send a prompt to the local Ollama model and return a parsed response.

    Args:
        prompt:        User-facing prompt / instruction.
        system_prompt: System role definition injected as a system message.
        model:         Ollama model tag (default from config).
        expect_json:   If True, the response will be parsed as JSON. If the
                       model does not return valid JSON the function retries
                       up to LLM_MAX_RETRIES times before returning an error
                       dict.

    Returns:
        A dict with at least one of:
          - The parsed JSON from the model.
          - {"error": "<reason>", "raw_response": "<text>"} on failure.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    logger.debug("LLM query | model=%s | prompt_chars=%d", model, len(prompt))

    last_error: str = "Unknown error"
    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            response = ollama.chat(
                model=model,
                messages=messages,
                options={
                    "temperature": LLM_TEMPERATURE,
                    "num_predict": 2048,
                },
            )
            raw_text: str = response["message"]["content"]
            logger.debug(
                "LLM response | attempt=%d | chars=%d", attempt, len(raw_text)
            )

            if not expect_json:
                return {"content": raw_text}

            parsed = _extract_json(raw_text)
            if parsed is not None:
                logger.debug("LLM JSON parsed successfully on attempt %d", attempt)
                return parsed  # type: ignore[return-value]

            last_error = f"Could not parse JSON from response: {raw_text[:200]}"
            logger.warning(
                "LLM attempt %d/%d failed JSON parse. Retrying...",
                attempt,
                LLM_MAX_RETRIES,
            )

            # Give the model a hint on the next retry
            messages.append({"role": "assistant", "content": raw_text})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your response was not valid JSON. "
                        "Please respond ONLY with a valid JSON object, "
                        "no markdown, no explanation."
                    ),
                }
            )

        except ollama.ResponseError as exc:
            last_error = f"Ollama ResponseError: {exc}"
            logger.error("LLM attempt %d/%d | %s", attempt, LLM_MAX_RETRIES, last_error)
        except Exception as exc:  # noqa: BLE001
            last_error = f"Unexpected LLM error: {exc}"
            logger.exception("LLM call failed on attempt %d", attempt)

        if attempt < LLM_MAX_RETRIES:
            backoff = 2 ** (attempt - 1)
            logger.info("Backing off %ds before retry...", backoff)
            time.sleep(backoff)

    logger.error("LLM failed after %d attempts. Last error: %s", LLM_MAX_RETRIES, last_error)
    return {"error": last_error, "raw_response": ""}
