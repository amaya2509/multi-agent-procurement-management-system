"""
Coordinator Agent — Workflow Orchestration

Role:
  The Coordinator is the entry point of the multi-agent workflow. It does NOT
  call the LLM or any tools. Its responsibilities are:
    1. Validate that a user_request exists in the state.
    2. Initialise the logs list and other optional state fields.
    3. Log the workflow start event with metadata.
    4. Pass control to the next agent (Request Analyzer) by returning state.

Design principle:
  Pure orchestration only. All business logic belongs in downstream agents
  and their associated tools.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.logger import get_logger
from src.state import ProcurementState

logger = get_logger("agents.coordinator")

AGENT_NAME = "CoordinatorAgent"


def coordinator_agent(state: ProcurementState) -> dict[str, Any]:
    """
    Initialise the procurement workflow and validate the input state.

    This node:
    - Ensures the user_request field is present and non-empty.
    - Initialises all list/optional fields to safe defaults.
    - Records the workflow_start log entry.

    Args:
        state: The incoming ProcurementState (must have 'user_request').

    Returns:
        A partial state dict to be merged by LangGraph containing:
        - logs: initialised log list with a workflow_start entry.
        - supplier_options, parsed_request, selected_supplier,
          purchase_order, approval_status: all set to safe defaults.
        - error: set if user_request is missing.
    """
    logger.info("=" * 70)
    logger.info("[%s] Workflow initialising...", AGENT_NAME)

    user_request = state.get("user_request", "").strip()

    # ── Guard: must have a request ────────────────────────────────────────────
    if not user_request:
        error_msg = "No user_request provided. Cannot start the procurement workflow."
        logger.error("[%s] %s", AGENT_NAME, error_msg)
        return {
            "error": error_msg,
            "logs": [_log_entry(AGENT_NAME, "error", error_msg)],
        }

    logger.info("[%s] User request received: %s", AGENT_NAME, user_request)

    start_log = _log_entry(
        AGENT_NAME,
        "workflow_start",
        f"Workflow started for request: '{user_request}'",
        metadata={
            "request_length": len(user_request),
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        },
    )

    logger.info("[%s] Handing off to Request Analyzer Agent.", AGENT_NAME)

    return {
        "error": None,
        "parsed_request": None,
        "supplier_options": [],
        "selected_supplier": None,
        "purchase_order": None,
        "approval_status": None,
        "logs": [start_log],
    }


def _log_entry(
    agent: str,
    event: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a structured log entry dict in the required format.
    """
    return {
        "agent": agent,
        "step": message,
        "output": metadata,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
