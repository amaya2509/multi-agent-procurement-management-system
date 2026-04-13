"""
parse_request_tool — Request Parsing Tool

Converts a natural-language procurement request into a structured dict by
calling the local LLM. The tool provides a detailed system prompt to guide
the model into producing deterministic JSON output and validates the result
with Pydantic before returning it.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.llm_client import query_llm
from src.logger import get_logger

logger = get_logger("tools.parse_request")

# ─── Response Validation Schema ───────────────────────────────────────────────


class ParsedRequestSchema(BaseModel):
    """Pydantic model that validates the LLM's structured response."""

    item: str = Field(..., description="The item to procure (e.g. 'laptop')")
    quantity: int = Field(..., ge=1, description="Number of units requested")
    department: str = Field(..., description="Requesting department")
    budget_limit: float = Field(..., ge=0, description="Maximum budget in USD")
    urgency: str = Field(
        default="medium",
        description="Priority level: low | medium | high",
    )
    additional_requirements: str = Field(
        default="",
        description="Any extra specs or constraints",
    )
    confidence_score: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Model confidence in extraction (0–1)",
    )

    @field_validator("urgency")
    @classmethod
    def validate_urgency(cls, v: str) -> str:
        allowed = {"low", "medium", "high"}
        normalised = v.lower().strip()
        return normalised if normalised in allowed else "medium"

    @field_validator("item")
    @classmethod
    def normalise_item(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator("department")
    @classmethod
    def normalise_department(cls, v: str) -> str:
        return v.strip().title()


# ─── System Prompt ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a procurement request parser. Your ONLY job is to extract 
structured information from a natural-language procurement request and return it as JSON.

RULES:
1. Respond ONLY with a valid JSON object — no markdown, no explanation.
2. Extract these fields exactly:
   - item: the product/service name (singular, lowercase)
   - quantity: integer number of units
   - department: which department is requesting (title case)
   - budget_limit: total budget in USD as a float (extract from text or estimate)
   - urgency: "low" | "medium" | "high"
   - additional_requirements: any extra specs (empty string if none)
   - confidence_score: your confidence in extraction from 0.0 to 1.0

3. If budget is missing, infer from context or set to 0.
4. If department is missing, use "General".
5. Never hallucinate values not present or inferable from the request.

Example output:
{
  "item": "laptop",
  "quantity": 10,
  "department": "IT",
  "budget_limit": 15000.0,
  "urgency": "medium",
  "additional_requirements": "",
  "confidence_score": 0.95
}"""


# ─── Tool Function ────────────────────────────────────────────────────────────


def parse_request_tool(user_request: str) -> dict[str, Any]:
    """
    Parse a natural-language procurement request into a structured dict.

    This tool calls the local LLM with a structured system prompt and validates
    the raw JSON response against a Pydantic schema. If any step fails, it
    returns an error dict so the calling agent can handle it gracefully.

    Args:
        user_request: The raw natural-language procurement request string from
                      the end user (e.g. "Need 10 laptops for IT budget 15000").

    Returns:
        A dict matching ParsedRequestSchema fields on success, or a dict with:
          {"error": "<reason>", "raw_input": "<user_request>"}  on failure.

    Example:
        >>> result = parse_request_tool("Need 10 laptops for IT with budget 15000")
        >>> result["item"]
        'laptop'
        >>> result["quantity"]
        10
    """
    logger.info("parse_request_tool | input_chars=%d", len(user_request))

    if not user_request or not user_request.strip():
        logger.error("parse_request_tool | Empty input received")
        return {"error": "Empty request provided", "raw_input": user_request}

    prompt = f"""Parse the following procurement request into the required JSON structure:

REQUEST: "{user_request}"

Remember: respond ONLY with valid JSON."""

    try:
        raw_result = query_llm(prompt=prompt, system_prompt=_SYSTEM_PROMPT)

        if "error" in raw_result:
            logger.error("parse_request_tool | LLM error: %s", raw_result["error"])
            return {"error": raw_result["error"], "raw_input": user_request}

        # Validate and normalise with Pydantic
        validated = ParsedRequestSchema(**raw_result)
        result = validated.model_dump()
        logger.info(
            "parse_request_tool | parsed: item=%s qty=%d dept=%s budget=%.2f",
            result["item"],
            result["quantity"],
            result["department"],
            result["budget_limit"],
        )
        return result

    except Exception as exc:  # noqa: BLE001
        logger.exception("parse_request_tool | Unexpected error: %s", exc)
        return {"error": str(exc), "raw_input": user_request}
