"""
Request Analyzer Agent

Role:
  Transform the raw natural-language user_request into a structured
  parsed_request dict using the parse_request_tool. This agent is the
  first LLM-calling node in the workflow.

System Prompt:
  "You are a senior procurement analyst. Extract structured data from
  procurement requests — strictly as JSON, no hallucination."

Constraints:
  - MUST use parse_request_tool (no inline logic).
  - MUST update state["parsed_request"].
  - MUST NOT modify supplier_options, purchase_order, or approval_status.
  - On tool error, sets state["error"] to halt the workflow.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.logger import get_logger
from src.state import ProcurementState
from tools.parse_request import parse_request_tool

logger = get_logger("agents.request_analyzer")

AGENT_NAME = "RequestAnalyzerAgent"


def request_analyzer_agent(state: ProcurementState) -> dict[str, Any]:
    """
    Analyse the user request and extract structured procurement data.

    Uses parse_request_tool to convert the freeform user_request string
    into a structured ParsedRequest dict. Validates the result before
    updating state.

    Args:
        state: Current ProcurementState. Must have 'user_request'.

    Returns:
        Partial state update with 'parsed_request' populated and a new
        log entry appended. Sets 'error' if parsing fails.
    """
    logger.info("[%s] Starting request analysis...", AGENT_NAME)

    # ── Early exit on upstream error ─────────────────────────────────────────
    if state.get("error"):
        logger.warning("[%s] Upstream error detected — skipping.", AGENT_NAME)
        return {}

    user_request: str = state.get("user_request", "")
    existing_logs: list = list(state.get("logs", []))

    # ── Call tool ─────────────────────────────────────────────────────────────
    logger.info("[%s] Calling parse_request_tool...", AGENT_NAME)
    tool_start = datetime.now(tz=timezone.utc)
    result = parse_request_tool(user_request)
    tool_duration_ms = int(
        (datetime.now(tz=timezone.utc) - tool_start).total_seconds() * 1000
    )

    # ── Handle tool error ─────────────────────────────────────────────────────
    if "error" in result:
        error_msg = f"parse_request_tool failed: {result['error']}"
        logger.error("[%s] %s", AGENT_NAME, error_msg)
        log_entry = _log_entry(
            AGENT_NAME,
            "tool_error",
            error_msg,
            {"tool": "parse_request_tool", "duration_ms": tool_duration_ms},
        )
        return {"error": error_msg, "logs": existing_logs + [log_entry]}

    # ── Success ───────────────────────────────────────────────────────────────
    logger.info(
        "[%s] Parsed: item=%s qty=%d dept=%s budget=%.2f urgency=%s",
        AGENT_NAME,
        result.get("item"),
        result.get("quantity", 0),
        result.get("department"),
        result.get("budget_limit", 0.0),
        result.get("urgency"),
    )

    log_entry = _log_entry(
        AGENT_NAME,
        "request_parsed",
        f"Request parsed: {result.get('quantity')}x {result.get('item')} "
        f"for {result.get('department')} dept, budget ${result.get('budget_limit', 0):.0f}",
        {
            "tool": "parse_request_tool",
            "duration_ms": tool_duration_ms,
            "parsed_item": result.get("item"),
            "parsed_quantity": result.get("quantity"),
            "parsed_department": result.get("department"),
            "parsed_budget": result.get("budget_limit"),
            "confidence": result.get("confidence_score"),
        },
    )

    return {
        "parsed_request": result,
        "logs": existing_logs + [log_entry],
    }


def _log_entry(
    agent: str, event: str, message: str, metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "agent": agent,
        "step": message,
        "output": metadata,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
