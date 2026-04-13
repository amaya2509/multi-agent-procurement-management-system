"""
Shared pytest fixtures for the Multi-Agent Procurement Management System tests.

Fixtures are designed to be self-contained — they do not depend on file I/O
or external services. Data files are injected as temporary JSON files where
needed, making tests fast and deterministic.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


# ─── Supplier Data Fixtures ───────────────────────────────────────────────────

SAMPLE_SUPPLIERS = [
    {
        "id": "TEST-001",
        "item": "laptop",
        "supplier_name": "Alpha Tech",
        "unit_price": 1200.00,
        "currency": "USD",
        "lead_time_days": 5,
        "rating": 4.8,
        "stock": 100,
        "min_order_qty": 1,
        "payment_terms": "Net 30",
        "warranty_months": 24,
        "certifications": ["ISO 9001"],
        "contact_email": "alpha@test.example.com",
    },
    {
        "id": "TEST-002",
        "item": "laptop",
        "supplier_name": "Beta Supplies",
        "unit_price": 950.00,
        "currency": "USD",
        "lead_time_days": 10,
        "rating": 4.0,
        "stock": 50,
        "min_order_qty": 5,
        "payment_terms": "Net 15",
        "warranty_months": 12,
        "certifications": [],
        "contact_email": "beta@test.example.com",
    },
    {
        "id": "TEST-003",
        "item": "monitor",
        "supplier_name": "Gamma Screens",
        "unit_price": 300.00,
        "currency": "USD",
        "lead_time_days": 7,
        "rating": 4.5,
        "stock": 200,
        "min_order_qty": 1,
        "payment_terms": "Net 30",
        "warranty_months": 36,
        "certifications": ["CE"],
        "contact_email": "gamma@test.example.com",
    },
]

SAMPLE_BUDGETS = {
    "departments": {
        "IT": {
            "annual_budget": 150000.00,
            "quarterly_budget": 37500.00,
            "per_order_limit": 20000.00,
            "currency": "USD",
            "approver": "CTO",
            "requires_dual_approval_above": 10000.00,
        },
        "HR": {
            "annual_budget": 50000.00,
            "quarterly_budget": 12500.00,
            "per_order_limit": 5000.00,
            "currency": "USD",
            "approver": "HR Director",
            "requires_dual_approval_above": 3000.00,
        },
        "General": {
            "annual_budget": 30000.00,
            "quarterly_budget": 7500.00,
            "per_order_limit": 5000.00,
            "currency": "USD",
            "approver": "Department Head",
            "requires_dual_approval_above": 3000.00,
        },
    },
    "global_rules": {
        "minimum_quotes_required": 3,
        "emergency_purchase_limit": 2000.00,
        "preferred_payment_terms": ["Net 30", "Net 45"],
        "tax_rate": 0.08,
        "currency": "USD",
    },
}


@pytest.fixture
def suppliers_json(tmp_path: Path) -> Path:
    """Write sample supplier data to a temp JSON file and return its path."""
    path = tmp_path / "suppliers.json"
    path.write_text(json.dumps(SAMPLE_SUPPLIERS), encoding="utf-8")
    return path


@pytest.fixture
def budgets_json(tmp_path: Path) -> Path:
    """Write sample budget data to a temp JSON file and return its path."""
    path = tmp_path / "budgets.json"
    path.write_text(json.dumps(SAMPLE_BUDGETS), encoding="utf-8")
    return path


# ─── Parsed Request Fixture ───────────────────────────────────────────────────

@pytest.fixture
def sample_parsed_request() -> dict:
    """A valid ParsedRequest dict for use in tool and agent tests."""
    return {
        "item": "laptop",
        "quantity": 10,
        "department": "IT",
        "budget_limit": 15000.0,
        "urgency": "medium",
        "additional_requirements": "Need SSD storage",
        "confidence_score": 0.95,
    }


@pytest.fixture
def sample_selected_supplier() -> dict:
    """A valid SupplierRecord dict for use in PO generation tests."""
    return {
        "id": "TEST-001",
        "item": "laptop",
        "supplier_name": "Alpha Tech",
        "unit_price": 1200.00,
        "currency": "USD",
        "lead_time_days": 5,
        "rating": 4.8,
        "stock": 100,
        "min_order_qty": 1,
        "payment_terms": "Net 30",
        "warranty_months": 24,
        "certifications": ["ISO 9001"],
        "contact_email": "alpha@test.example.com",
        "composite_score": 0.8750,
    }


@pytest.fixture
def sample_purchase_order() -> dict:
    """A valid PurchaseOrder dict for use in approval tests."""
    return {
        "po_number": "PO-20250101-ABCD1234",
        "issue_date": "2025-01-01",
        "requester_department": "IT",
        "supplier_name": "Alpha Tech",
        "supplier_contact": "alpha@test.example.com",
        "line_items": [
            {
                "line_number": 1,
                "description": "Laptop",
                "quantity": 10,
                "unit_price": 1200.00,
                "unit": "each",
                "line_total": 12000.00,
                "notes": "",
            }
        ],
        "subtotal": 12000.00,
        "tax_rate": 0.08,
        "tax_amount": 960.00,
        "total": 12960.00,
        "currency": "USD",
        "payment_terms": "Net 30",
        "expected_delivery_date": "2025-01-06",
        "notes": "Standard specification.",
    }


# ─── State Fixture ────────────────────────────────────────────────────────────

@pytest.fixture
def sample_initial_state() -> dict:
    """A valid initial ProcurementState for workflow tests."""
    return {
        "user_request": "Need 10 laptops for IT department with budget 15000",
        "parsed_request": None,
        "supplier_options": [],
        "selected_supplier": None,
        "purchase_order": None,
        "approval_status": None,
        "logs": [],
        "error": None,
    }
