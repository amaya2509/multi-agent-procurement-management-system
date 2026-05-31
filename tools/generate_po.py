"""
generate_po_tool — Purchase Order Generation Tool

Creates a complete, structured Purchase Order (PO) document from a validated
parsed request and a selected supplier. The PO includes:
- Auto-generated PO number (prefix + date + UUID fragment)
- Line item breakdown with unit prices
- Subtotal, tax calculation, and grand total
- Payment and delivery terms from the supplier record
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.config import PO_PREFIX
from src.logger import get_logger

logger = get_logger("tools.generate_po")


# ─── Validation Schemas ───────────────────────────────────────────────────────


class GeneratePOInput(BaseModel):
    """Validates inputs to generate_po_tool."""

    item: str
    quantity: int = Field(..., ge=1)
    department: str
    supplier_name: str
    unit_price: float = Field(..., ge=0)
    tax_rate: float = Field(default=0.08, ge=0.0, le=1.0)
    additional_requirements: str = ""
    payment_terms: str = "Net 30"
    lead_time_days: int = Field(default=7, ge=0)
    supplier_contact: str = ""
    currency: str = "USD"

    @field_validator("item")
    @classmethod
    def normalise_item(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("department")
    @classmethod
    def normalise_department(cls, v: str) -> str:
        return v.strip().title()


def _generate_po_number() -> str:
    """
    Generate a unique Purchase Order number.

    Format: PO-YYYYMMDD-XXXXXXXX
    where XXXXXXXX is the first 8 characters of a UUID4.
    """
    today = date.today().strftime("%Y%m%d")
    uid_fragment = uuid.uuid4().hex[:8].upper()
    return f"{PO_PREFIX}-{today}-{uid_fragment}"


# ─── Tool Function ────────────────────────────────────────────────────────────


def generate_po_tool(
    parsed_request: dict[str, Any],
    selected_supplier: dict[str, Any],
    tax_rate: float = 0.08,
) -> dict[str, Any]:
    """
    Generate a complete Purchase Order document from request and supplier data.

    This tool is purely deterministic — it does not call the LLM. All values
    are computed from the validated inputs, guaranteeing consistent, auditable
    POs regardless of model behaviour.

    Args:
        parsed_request:    Output of parse_request_tool containing at minimum:
                           item, quantity, department, additional_requirements.
        selected_supplier: Output of supplier_lookup_tool / selection step
                           containing: supplier_name, unit_price, lead_time_days,
                           payment_terms, contact_email, currency.
        tax_rate:          Decimal tax rate to apply (default 8% from global rules).

    Returns:
        A complete PO dict with all financial details, or:
        {"error": "<reason>", "parsed_request": {...}, "selected_supplier": {...}}

    Raises:
        Never raises — all exceptions are caught and returned as error dicts.
    """
    logger.info(
        "generate_po_tool | item=%s qty=%s supplier=%s",
        parsed_request.get("item"),
        parsed_request.get("quantity"),
        selected_supplier.get("supplier_name"),
    )

    try:
        # ── Validate inputs ───────────────────────────────────────────────────
        inp = GeneratePOInput(
            item=parsed_request.get("item", ""),
            quantity=parsed_request.get("quantity", 1),
            department=parsed_request.get("department", "General"),
            supplier_name=selected_supplier.get("supplier_name", ""),
            unit_price=selected_supplier.get("unit_price", 0.0),
            tax_rate=tax_rate,
            additional_requirements=parsed_request.get("additional_requirements", ""),
            payment_terms=selected_supplier.get("payment_terms", "Net 30"),
            lead_time_days=selected_supplier.get("lead_time_days", 7),
            supplier_contact=selected_supplier.get("contact_email", ""),
            currency=selected_supplier.get("currency", "USD"),
        )

        # ── Financial calculations ────────────────────────────────────────────
        subtotal = round(inp.unit_price * inp.quantity, 2)
        tax_amount = round(subtotal * inp.tax_rate, 2)
        total = round(subtotal + tax_amount, 2)

        # ── Dates ─────────────────────────────────────────────────────────────
        issue_date = date.today()
        delivery_date = issue_date + timedelta(days=inp.lead_time_days)

        # ── Build PO ──────────────────────────────────────────────────────────
        po = {
            "po_number": _generate_po_number(),
            "issue_date": issue_date.isoformat(),
            "requester_department": inp.department,
            "supplier_name": inp.supplier_name,
            "supplier_contact": inp.supplier_contact,
            "line_items": [
                {
                    "line_number": 1,
                    "description": inp.item.title(),
                    "quantity": inp.quantity,
                    "unit_price": inp.unit_price,
                    "unit": "each",
                    "line_total": subtotal,
                    "notes": inp.additional_requirements,
                }
            ],
            "subtotal": subtotal,
            "tax_rate": inp.tax_rate,
            "tax_amount": tax_amount,
            "total": total,
            "currency": inp.currency,
            "payment_terms": inp.payment_terms,
            "expected_delivery_date": delivery_date.isoformat(),
            "notes": (
                f"Purchase Order generated by Procurement MAS. "
                f"Requirements: {inp.additional_requirements or 'Standard specification.'}"
            ),
        }

        logger.info(
            "generate_po_tool | po_number=%s total=%.2f %s",
            po["po_number"],
            po["total"],
            po["currency"],
        )
        return po

    except Exception as exc:  # noqa: BLE001
        logger.exception("generate_po_tool | Failed: %s", exc)
        return {
            "error": str(exc),
            "parsed_request": parsed_request,
            "selected_supplier": selected_supplier,
        }
