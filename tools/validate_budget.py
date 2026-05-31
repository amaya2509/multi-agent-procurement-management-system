"""
validate_budget_tool — Budget Validation Tool

Compares a generated Purchase Order total against the approved department
budget limits loaded from data/budgets.json. Returns a structured approval
decision with full audit trail information.

Business rules enforced:
- PO total must not exceed department's per_order_limit.
- If total exceeds requires_dual_approval_above threshold, the response
  flags dual_approval_required = True.
- If department is not found, falls back to "General" department limits.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import BUDGETS_FILE, DEFAULT_DEPARTMENT
from src.logger import get_logger

logger = get_logger("tools.validate_budget")


def _load_budgets(budgets_file: Path = BUDGETS_FILE) -> dict[str, Any]:
    """Load the budgets configuration from disk."""
    if not budgets_file.exists():
        raise FileNotFoundError(f"Budgets file not found: {budgets_file}")
    with budgets_file.open(encoding="utf-8") as fh:
        return json.load(fh)


def validate_budget_tool(
    purchase_order: dict[str, Any],
    department: str,
    budgets_file: Path = BUDGETS_FILE,
) -> dict[str, Any]:
    """
    Validate a Purchase Order against the department's approved budget limits.

    The tool checks:
    1. Whether the PO total is within the department's per_order_limit.
    2. Whether dual approval is required (if total > requires_dual_approval_above).
    3. Provides a clear reason for approval or rejection.

    Args:
        purchase_order: A PO dict as produced by generate_po_tool. Must contain
                        'total' (float) and 'currency' (str) keys.
        department:     The requesting department name (e.g. "IT"). Case-insensitive
                        lookup — falls back to DEFAULT_DEPARTMENT if not found.
        budgets_file:   Path to budgets.json (injectable for testing).

    Returns:
        A dict with the following structure on success::

            {
              "approved": bool,
              "reason": str,
              "approved_by": str,
              "department": str,
              "department_budget_limit": float,
              "po_total": float,
              "remaining_budget": float,
              "requires_dual_approval": bool,
              "timestamp": str   # ISO-8601 UTC
            }

        Or on error::

            {"error": "<reason>", "purchase_order_total": <float>}

    Raises:
        Never raises — all exceptions are caught and returned as error dicts.
    """
    po_total = purchase_order.get("total", 0.0)
    logger.info(
        "validate_budget_tool | dept=%s po_total=%.2f %s",
        department,
        po_total,
        purchase_order.get("currency", "USD"),
    )

    try:
        budget_data = _load_budgets(budgets_file)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.error("validate_budget_tool | Failed to load budgets: %s", exc)
        return {"error": str(exc), "purchase_order_total": po_total}

    # ── Department lookup (case-insensitive, fallback to General) ─────────────
    departments: dict[str, Any] = budget_data.get("departments", {})
    dept_key = _find_department(departments, department)

    if dept_key:
        dept_config = departments[dept_key]
        resolved_dept = dept_key
    else:
        logger.warning(
            "validate_budget_tool | Department '%s' not found; using '%s'",
            department,
            DEFAULT_DEPARTMENT,
        )
        dept_config = departments.get(DEFAULT_DEPARTMENT, {})
        resolved_dept = DEFAULT_DEPARTMENT

    per_order_limit: float = dept_config.get("per_order_limit", 5000.0)
    dual_approval_threshold: float = dept_config.get("requires_dual_approval_above", 3000.0)
    approver: str = dept_config.get("approver", "Department Head")

    # ── Business rule evaluation ──────────────────────────────────────────────
    approved = po_total <= per_order_limit
    requires_dual = po_total > dual_approval_threshold
    remaining = round(per_order_limit - po_total, 2)

    if approved:
        reason = (
            f"PO total of {po_total:.2f} is within the {resolved_dept} "
            f"department's per-order limit of {per_order_limit:.2f}."
        )
    else:
        reason = (
            f"PO total of {po_total:.2f} exceeds the {resolved_dept} "
            f"department's per-order limit of {per_order_limit:.2f} "
            f"by {abs(remaining):.2f}."
        )

    result = {
        "approved": approved,
        "reason": reason,
        "approved_by": approver if approved else "REJECTED",
        "department": resolved_dept,
        "department_budget_limit": per_order_limit,
        "po_total": po_total,
        "remaining_budget": remaining,
        "requires_dual_approval": requires_dual,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }

    logger.info(
        "validate_budget_tool | approved=%s dept=%s limit=%.2f total=%.2f",
        approved,
        resolved_dept,
        per_order_limit,
        po_total,
    )
    return result


def _find_department(
    departments: dict[str, Any], target: str
) -> str | None:
    """
    Case-insensitive department lookup.

    Args:
        departments: Dict of department name → config.
        target:      Department name to search for.

    Returns:
        The matching key in the departments dict, or None.
    """
    target_lower = target.lower().strip()
    for key in departments:
        if key.lower() == target_lower:
            return key
    return None
