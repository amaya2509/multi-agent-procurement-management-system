"""
Supplier Intelligence Agent

Role:
  Find and select the best supplier for the requested item using a two-step
  approach:
    1. supplier_lookup_tool — deterministic catalogue search + scoring.
    2. LLM reasoning layer — provides a human-readable justification for the
       top-ranked supplier selection (does NOT change the algorithmic ranking).

System Prompt:
  "You are a supplier intelligence analyst. Given a list of ranked suppliers,
  confirm the selection of the top-ranked supplier and provide a concise
  business justification in JSON."

Constraints:
  - MUST use supplier_lookup_tool for discovery and ranking.
  - LLM is used ONLY for explanation — the composite_score determines the winner.
  - MUST update state["supplier_options"] and state["selected_supplier"].
  - MUST NOT modify parsed_request, purchase_order, or approval_status.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.llm_client import query_llm
from src.logger import get_logger
from src.state import ProcurementState
from tools.supplier_lookup import supplier_lookup_tool

logger = get_logger("agents.supplier_intelligence")

AGENT_NAME = "SupplierIntelligenceAgent"

_SYSTEM_PROMPT = """You are a supplier intelligence analyst for a procurement system.
You are given a list of pre-ranked suppliers (sorted by composite score: rating, price, stock, lead time).
Your job is to confirm the top-ranked supplier as the selection and write a concise business justification.

RULES:
1. Respond ONLY with valid JSON — no markdown, no explanation outside JSON.
2. Do NOT change the ranking — the algorithm has already made the optimal selection.
3. Your response structure must be exactly:
{
  "selected_supplier_name": "<name of the top-ranked supplier>",
  "justification": "<2-3 sentence business rationale>",
  "key_advantages": ["<advantage 1>", "<advantage 2>", "<advantage 3>"]
}"""


def supplier_intelligence_agent(state: ProcurementState) -> dict[str, Any]:
    """
    Discover, rank and select the best supplier for the procurement request.

    Step 1: Calls supplier_lookup_tool with item/quantity/budget from parsed_request.
    Step 2: Asks the LLM to justify the top-scored supplier selection.
    Step 3: Attaches selection metadata and justification to the selected_supplier.

    Args:
        state: Current ProcurementState. Must have 'parsed_request' populated.

    Returns:
        Partial state update with 'supplier_options' and 'selected_supplier'.
        Sets 'error' if no suppliers found or tool fails critically.
    """
    logger.info("[%s] Starting supplier discovery...", AGENT_NAME)

    if state.get("error"):
        logger.warning("[%s] Upstream error detected — skipping.", AGENT_NAME)
        return {}

    parsed = state.get("parsed_request", {})
    if not parsed:
        error_msg = "parsed_request is empty — cannot perform supplier lookup."
        logger.error("[%s] %s", AGENT_NAME, error_msg)
        return {"error": error_msg, "logs": list(state.get("logs", []))}

    existing_logs: list = list(state.get("logs", []))

    item: str = parsed.get("item", "")
    quantity: int = parsed.get("quantity", 1)
    budget_limit: float = parsed.get("budget_limit", 0.0)
    budget_per_unit = (budget_limit / quantity) if (budget_limit > 0 and quantity > 0) else None

    # ── Step 1: Tool call — catalogue lookup ──────────────────────────────────
    logger.info("[%s] Calling supplier_lookup_tool for '%s'...", AGENT_NAME, item)
    tool_start = datetime.now(tz=timezone.utc)
    lookup_result = supplier_lookup_tool(
        item=item, quantity=quantity, budget_per_unit=budget_per_unit
    )
    tool_duration_ms = int(
        (datetime.now(tz=timezone.utc) - tool_start).total_seconds() * 1000
    )

    if "error" in lookup_result:
        error_msg = f"supplier_lookup_tool failed: {lookup_result['error']}"
        logger.error("[%s] %s", AGENT_NAME, error_msg)
        log_entry = _log_entry(AGENT_NAME, "tool_error", error_msg,
                               {"tool": "supplier_lookup_tool", "duration_ms": tool_duration_ms})
        return {"error": error_msg, "logs": existing_logs + [log_entry]}

    suppliers: list[dict[str, Any]] = lookup_result.get("suppliers", [])
    if not suppliers:
        error_msg = f"No suppliers found for item='{item}'."
        logger.warning("[%s] %s", AGENT_NAME, error_msg)
        log_entry = _log_entry(AGENT_NAME, "no_suppliers", error_msg,
                               {"item": item, "duration_ms": tool_duration_ms})
        return {"error": error_msg, "supplier_options": [], "logs": existing_logs + [log_entry]}

    logger.info("[%s] Found %d suppliers. Top: %s (score=%.4f)",
                AGENT_NAME, len(suppliers), suppliers[0].get("supplier_name"),
                suppliers[0].get("composite_score", 0))

    # ── Step 2: LLM justification ─────────────────────────────────────────────
    top_supplier = suppliers[0]
    llm_prompt = (
        f"Item requested: {quantity}x {item}\n"
        f"Budget limit: ${budget_limit:.2f}\n\n"
        f"Ranked suppliers (top {len(suppliers)}):\n"
        + "\n".join(
            f"  {i+1}. {s['supplier_name']} | price=${s['unit_price']:.2f} "
            f"| rating={s['rating']} | stock={s['stock']} "
            f"| lead={s['lead_time_days']}d | score={s.get('composite_score', 0):.4f}"
            for i, s in enumerate(suppliers)
        )
    )

    logger.info("[%s] Calling LLM for supplier justification...", AGENT_NAME)
    llm_result = query_llm(prompt=llm_prompt, system_prompt=_SYSTEM_PROMPT)

    justification = "Selected based on highest composite score (rating, price, stock, lead time)."
    key_advantages: list[str] = []

    if "error" not in llm_result:
        justification = llm_result.get("justification", justification)
        key_advantages = llm_result.get("key_advantages", [])
        logger.info("[%s] LLM justification received.", AGENT_NAME)
    else:
        logger.warning("[%s] LLM justification failed — using default.", AGENT_NAME)

    # ── Step 3: Enrich selected_supplier with selection metadata ─────────────
    selected = {
        **top_supplier,
        "selection_justification": justification,
        "key_advantages": key_advantages,
        "selection_rank": 1,
        "alternatives_considered": len(suppliers),
    }

    log_entry = _log_entry(
        AGENT_NAME,
        "supplier_selected",
        f"Selected supplier: {top_supplier['supplier_name']} "
        f"(score={top_supplier.get('composite_score', 0):.4f}, "
        f"price=${top_supplier['unit_price']:.2f}/unit)",
        {
            "tool": "supplier_lookup_tool",
            "duration_ms": tool_duration_ms,
            "selected_supplier": top_supplier.get("supplier_name"),
            "composite_score": top_supplier.get("composite_score"),
            "total_candidates": lookup_result.get("total_found", len(suppliers)),
        },
    )

    return {
        "supplier_options": suppliers,
        "selected_supplier": selected,
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
