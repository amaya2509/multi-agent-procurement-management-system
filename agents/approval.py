"""
Approval Agent

Role:
  Final validation gate of the procurement workflow. Uses validate_budget_tool
  to compare the generated PO total against the department's approved limits,
  and uses the LLM to produce a formal approval/rejection notice with an
  audit-ready explanation.

System Prompt:
  "You are a financial controller. Based on the budget validation result,
  generate a formal procurement approval or rejection notice in JSON."

Constraints:
  - MUST use validate_budget_tool for the actual financial decision.
  - LLM is used ONLY for composing the formal notice text.
  - MUST update state["approval_status"].
  - MUST NOT modify any other state field except logs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.llm_client import query_llm
from src.logger import get_logger
from src.state import ProcurementState
from tools.validate_budget import validate_budget_tool

logger = get_logger("agents.approval")

AGENT_NAME = "ApprovalAgent"

_SYSTEM_PROMPT = """You are a financial controller in a procurement department.
You have received a budget validation result for a Purchase Order. Write a formal
procurement approval or rejection notice.

RULES:
1. Respond ONLY with valid JSON — no markdown, no extra text.
2. Base your decision STRICTLY on the 'approved' field in the validation result.
3. Your response must be exactly:
{
  "formal_notice": "<2-3 sentence formal approval or rejection statement>",
  "action_required": "<next steps for the requester>",
  "compliance_notes": "<any compliance or audit observations>"
}"""


def approval_agent(state: ProcurementState) -> dict[str, Any]:
    """
    Validate the Purchase Order budget and produce a formal approval decision.

    Step 1: Calls validate_budget_tool with the PO and department.
    Step 2: Asks the LLM to compose a formal notice based on the validation.
    Step 3: Merges tool result and LLM notice into a complete approval_status.

    Args:
        state: Current ProcurementState. Must have 'purchase_order' and
               'parsed_request' (for the department name).

    Returns:
        Partial state update with 'approval_status' set and logs updated.
        On tool error, sets 'error' and stops the workflow.
    """
    logger.info("[%s] Starting budget validation and approval...", AGENT_NAME)

    if state.get("error"):
        logger.warning("[%s] Upstream error detected — skipping.", AGENT_NAME)
        return {}

    purchase_order = state.get("purchase_order")
    parsed = state.get("parsed_request", {})
    existing_logs: list = list(state.get("logs", []))

    if not purchase_order:
        error_msg = "purchase_order is empty — cannot validate budget."
        logger.error("[%s] %s", AGENT_NAME, error_msg)
        return {"error": error_msg, "logs": existing_logs}

    department = (parsed or {}).get("department", "General")

    # ── Step 1: Tool call — budget validation ─────────────────────────────────
    logger.info("[%s] Calling validate_budget_tool | dept=%s po_total=%.2f",
                AGENT_NAME, department, purchase_order.get("total", 0))
    tool_start = datetime.now(tz=timezone.utc)
    validation = validate_budget_tool(purchase_order=purchase_order, department=department)
    tool_duration_ms = int(
        (datetime.now(tz=timezone.utc) - tool_start).total_seconds() * 1000
    )

    if "error" in validation:
        error_msg = f"validate_budget_tool failed: {validation['error']}"
        logger.error("[%s] %s", AGENT_NAME, error_msg)
        log_entry = _log_entry(AGENT_NAME, "tool_error", error_msg,
                               {"tool": "validate_budget_tool", "duration_ms": tool_duration_ms})
        return {"error": error_msg, "logs": existing_logs + [log_entry]}

    approved: bool = validation.get("approved", False)
    logger.info("[%s] Budget validation result: approved=%s", AGENT_NAME, approved)

    # ── Step 2: LLM formal notice ─────────────────────────────────────────────
    llm_prompt = (
        f"Purchase Order: {purchase_order.get('po_number')}\n"
        f"Department: {department}\n"
        f"PO Total: ${purchase_order.get('total', 0):.2f} {purchase_order.get('currency', 'USD')}\n"
        f"Budget Limit: ${validation.get('department_budget_limit', 0):.2f}\n"
        f"Approved: {approved}\n"
        f"Reason: {validation.get('reason', '')}\n"
        f"Requires Dual Approval: {validation.get('requires_dual_approval', False)}\n"
        f"Approved By: {validation.get('approved_by', 'N/A')}\n\n"
        f"Write the formal procurement notice."
    )

    formal_notice = ""
    action_required = ""
    compliance_notes = ""

    llm_result = query_llm(prompt=llm_prompt, system_prompt=_SYSTEM_PROMPT)
    if "error" not in llm_result:
        formal_notice = llm_result.get("formal_notice", "")
        action_required = llm_result.get("action_required", "")
        compliance_notes = llm_result.get("compliance_notes", "")
        logger.info("[%s] LLM formal notice generated.", AGENT_NAME)
    else:
        formal_notice = (
            f"APPROVED: {purchase_order.get('po_number')}" if approved
            else f"REJECTED: {purchase_order.get('po_number')}"
        )
        logger.warning("[%s] LLM notice generation failed — using default.", AGENT_NAME)

    # ── Step 3: Compose final approval_status ─────────────────────────────────
    approval_status = {
        **validation,
        "formal_notice": formal_notice,
        "action_required": action_required,
        "compliance_notes": compliance_notes,
        "po_number": purchase_order.get("po_number"),
    }

    status_str = "✅ APPROVED" if approved else "❌ REJECTED"
    log_entry = _log_entry(
        AGENT_NAME,
        "approval_decision",
        f"{status_str} | PO {purchase_order.get('po_number')} | "
        f"Total: {purchase_order.get('currency')} {purchase_order.get('total'):.2f} | "
        f"Limit: {validation.get('department_budget_limit'):.2f} | "
        f"By: {validation.get('approved_by')}",
        {
            "tool": "validate_budget_tool",
            "duration_ms": tool_duration_ms,
            "approved": approved,
            "po_number": purchase_order.get("po_number"),
            "po_total": purchase_order.get("total"),
            "budget_limit": validation.get("department_budget_limit"),
            "requires_dual_approval": validation.get("requires_dual_approval"),
        },
    )

    logger.info("[%s] Workflow complete. %s", AGENT_NAME, status_str)
    logger.info("=" * 70)

    return {
        "approval_status": approval_status,
        "logs": existing_logs + [log_entry],
    }


def _log_entry(
    agent: str, event: str, message: str, metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "agent": agent,
        "event": event,
        "message": message,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        **(metadata or {}),
    }
