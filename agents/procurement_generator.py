"""
Procurement Generator Agent

Role:
  Generate a complete, compliant Purchase Order (PO) document from the
  selected supplier and structured parsed request using generate_po_tool.

System Prompt:
  "You are a senior procurement officer. Review the generated PO for
  completeness and add any missing business context."

Constraints:
  - MUST use generate_po_tool — no inline PO construction.
  - MUST update state["purchase_order"].
  - MUST NOT modify parsed_request, supplier_options, or approval_status.
  - On tool error, set state["error"] to halt the workflow.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.logger import get_logger
from src.state import ProcurementState
from tools.generate_po import generate_po_tool

logger = get_logger("agents.procurement_generator")

AGENT_NAME = "ProcurementGeneratorAgent"


def procurement_generator_agent(state: ProcurementState) -> dict[str, Any]:
    """
    Generate a complete Purchase Order from the selected supplier and request data.

    Uses generate_po_tool to build the PO deterministically. The tax rate is
    read from the global budget rules when available; otherwise a default of
    8% is applied.

    Args:
        state: Current ProcurementState. Must have 'parsed_request' and
               'selected_supplier' populated.

    Returns:
        Partial state update with 'purchase_order' populated and a new log
        entry. Sets 'error' on failure.
    """
    logger.info("[%s] Generating Purchase Order...", AGENT_NAME)

    if state.get("error"):
        logger.warning("[%s] Upstream error detected — skipping.", AGENT_NAME)
        return {}

    parsed = state.get("parsed_request")
    selected = state.get("selected_supplier")
    existing_logs: list = list(state.get("logs", []))

    if not parsed:
        error_msg = "parsed_request is empty — cannot generate PO."
        logger.error("[%s] %s", AGENT_NAME, error_msg)
        return {"error": error_msg, "logs": existing_logs}

    if not selected:
        error_msg = "selected_supplier is empty — cannot generate PO."
        logger.error("[%s] %s", AGENT_NAME, error_msg)
        return {"error": error_msg, "logs": existing_logs}

    # ── Call tool ─────────────────────────────────────────────────────────────
    logger.info(
        "[%s] Calling generate_po_tool | item=%s qty=%d supplier=%s",
        AGENT_NAME, parsed.get("item"), parsed.get("quantity"), selected.get("supplier_name"),
    )
    tool_start = datetime.now(tz=timezone.utc)
    po = generate_po_tool(parsed_request=parsed, selected_supplier=selected)
    tool_duration_ms = int(
        (datetime.now(tz=timezone.utc) - tool_start).total_seconds() * 1000
    )

    if "error" in po:
        error_msg = f"generate_po_tool failed: {po['error']}"
        logger.error("[%s] %s", AGENT_NAME, error_msg)
        log_entry = _log_entry(AGENT_NAME, "tool_error", error_msg,
                               {"tool": "generate_po_tool", "duration_ms": tool_duration_ms})
        return {"error": error_msg, "logs": existing_logs + [log_entry]}

    # ── Success ───────────────────────────────────────────────────────────────
    logger.info(
        "[%s] PO generated: %s | total=%.2f %s",
        AGENT_NAME, po.get("po_number"), po.get("total", 0), po.get("currency", "USD"),
    )

    log_entry = _log_entry(
        AGENT_NAME,
        "po_generated",
        f"PO {po['po_number']} generated | "
        f"{parsed.get('quantity')}x {parsed.get('item')} | "
        f"Total: {po.get('currency')} {po.get('total'):.2f} | "
        f"Expected delivery: {po.get('expected_delivery_date')}",
        {
            "tool": "generate_po_tool",
            "duration_ms": tool_duration_ms,
            "po_number": po.get("po_number"),
            "subtotal": po.get("subtotal"),
            "tax_amount": po.get("tax_amount"),
            "total": po.get("total"),
            "currency": po.get("currency"),
            "delivery_date": po.get("expected_delivery_date"),
        },
    )

    return {
        "purchase_order": po,
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
