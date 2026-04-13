"""
Global state schema for the Multi-Agent Procurement Management System.

The ProcurementState TypedDict is the single source of truth that flows
through every node in the LangGraph StateGraph. Each agent reads from and
writes back to a subset of this state — never bypassing it.

Design rationale:
- TypedDict keeps LangGraph compatibility (it serialises cleanly).
- Optional fields default to None / empty so the graph can be initialised
  with just a user_request and progressively enriched.
"""

from __future__ import annotations

from typing import Any, Optional
from typing_extensions import TypedDict


class ParsedRequest(TypedDict, total=False):
    """Structured representation of the user's procurement request."""

    item: str                    # What is being procured
    quantity: int                # How many units
    department: str              # Requesting department
    budget_limit: float          # Max spend the requester expects
    urgency: str                 # "low" | "medium" | "high"
    additional_requirements: str # Free-text constraints
    confidence_score: float      # LLM confidence in extraction (0–1)


class SupplierRecord(TypedDict, total=False):
    """A single supplier entry from the catalogue."""

    id: str
    item: str
    supplier_name: str
    unit_price: float
    currency: str
    lead_time_days: int
    rating: float
    stock: int
    min_order_qty: int
    payment_terms: str
    warranty_months: int
    certifications: list[str]
    contact_email: str
    composite_score: float       # Computed scoring value


class PurchaseOrder(TypedDict, total=False):
    """A complete Purchase Order document."""

    po_number: str
    issue_date: str              # ISO-8601 date
    requester_department: str
    supplier_name: str
    supplier_contact: str
    line_items: list[dict[str, Any]]
    subtotal: float
    tax_rate: float
    tax_amount: float
    total: float
    currency: str
    payment_terms: str
    expected_delivery_date: str  # ISO-8601 date
    notes: str


class ApprovalStatus(TypedDict, total=False):
    """Result of the budget validation and approval check."""

    approved: bool
    reason: str
    approved_by: str
    department_budget_limit: float
    po_total: float
    remaining_budget: float
    requires_dual_approval: bool
    timestamp: str               # ISO-8601 datetime


class ProcurementState(TypedDict, total=False):
    """
    Master state object shared across all agents in the procurement workflow.

    Lifecycle:
      1. Initialised by the Coordinator with user_request.
      2. Populated by Request Analyzer (parsed_request).
      3. Populated by Supplier Intelligence (supplier_options, selected_supplier).
      4. Populated by Procurement Generator (purchase_order).
      5. Populated by Approval Agent (approval_status).

    The `logs` field accumulates structured log entries from every agent;
    the `error` field is set by any agent that encounters an unrecoverable
    error (which causes the graph to exit early).
    """

    # ── Input ────────────────────────────────────────────────────────────────
    user_request: str

    # ── Agent Outputs ────────────────────────────────────────────────────────
    parsed_request: Optional[ParsedRequest]
    supplier_options: list[SupplierRecord]
    selected_supplier: Optional[SupplierRecord]
    purchase_order: Optional[PurchaseOrder]
    approval_status: Optional[ApprovalStatus]

    # ── Observability ────────────────────────────────────────────────────────
    logs: list[dict[str, Any]]   # Structured agent-level log entries
    error: Optional[str]          # Set on unrecoverable failures
