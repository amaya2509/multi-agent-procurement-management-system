"""
Unit tests for all 4 procurement tools.

Tests focus on:
- Structural correctness of returned dicts (required keys present)
- Business logic correctness (scoring, budget math, PO totals)
- Error handling (empty inputs, missing files, invalid data)

LLM calls are mocked for parse_request_tool — all other tools are
deterministic and do not require mocking.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.supplier_lookup import supplier_lookup_tool, _normalise, _score_suppliers
from tools.generate_po import generate_po_tool, _generate_po_number
from tools.validate_budget import validate_budget_tool, _find_department


# ═══════════════════════════════════════════════════════════════════════════════
# parse_request_tool tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseRequestTool:
    """Unit tests for parse_request_tool (LLM mocked)."""

    def test_returns_required_fields_on_success(self):
        """Parsed result must contain all required fields."""
        mock_llm_response = {
            "item": "laptop",
            "quantity": 10,
            "department": "IT",
            "budget_limit": 15000.0,
            "urgency": "medium",
            "additional_requirements": "",
            "confidence_score": 0.95,
        }
        with patch("tools.parse_request.query_llm", return_value=mock_llm_response):
            from tools.parse_request import parse_request_tool
            result = parse_request_tool("Need 10 laptops for IT with budget 15000")

        required_keys = {"item", "quantity", "department", "budget_limit", "urgency"}
        assert required_keys.issubset(result.keys()), (
            f"Missing keys: {required_keys - result.keys()}"
        )

    def test_item_is_normalised_to_lowercase(self):
        """Item names should always be returned in lowercase."""
        mock_llm_response = {
            "item": "Laptop",
            "quantity": 5,
            "department": "IT",
            "budget_limit": 8000.0,
            "urgency": "high",
            "additional_requirements": "",
            "confidence_score": 0.9,
        }
        with patch("tools.parse_request.query_llm", return_value=mock_llm_response):
            from tools.parse_request import parse_request_tool
            result = parse_request_tool("Need 5 Laptops for IT urgently")
        assert result["item"] == "laptop"

    def test_urgency_normalisation(self):
        """Invalid urgency values should default to 'medium'."""
        mock_llm_response = {
            "item": "monitor",
            "quantity": 3,
            "department": "HR",
            "budget_limit": 1500.0,
            "urgency": "CRITICAL",  # Invalid value
            "additional_requirements": "",
            "confidence_score": 0.7,
        }
        with patch("tools.parse_request.query_llm", return_value=mock_llm_response):
            from tools.parse_request import parse_request_tool
            result = parse_request_tool("Need 3 monitors for HR")
        assert result["urgency"] == "medium"

    def test_returns_error_on_empty_request(self):
        """Empty input should return an error dict, not raise."""
        with patch("tools.parse_request.query_llm", return_value={}):
            from tools.parse_request import parse_request_tool
            result = parse_request_tool("")
        assert "error" in result

    def test_returns_error_on_llm_failure(self):
        """LLM failure should propagate as an error dict."""
        with patch(
            "tools.parse_request.query_llm",
            return_value={"error": "Ollama not running"},
        ):
            from tools.parse_request import parse_request_tool
            result = parse_request_tool("Need 5 chairs")
        assert "error" in result

    def test_confidence_score_is_float_between_0_and_1(self):
        """confidence_score must be within valid range."""
        mock_llm_response = {
            "item": "printer",
            "quantity": 2,
            "department": "Finance",
            "budget_limit": 900.0,
            "urgency": "low",
            "additional_requirements": "",
            "confidence_score": 0.88,
        }
        with patch("tools.parse_request.query_llm", return_value=mock_llm_response):
            from tools.parse_request import parse_request_tool
            result = parse_request_tool("Need 2 printers for Finance")
        assert isinstance(result["confidence_score"], float)
        assert 0.0 <= result["confidence_score"] <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# supplier_lookup_tool tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSupplierLookupTool:
    """Unit tests for supplier_lookup_tool (fully deterministic — no mocks)."""

    def test_returns_suppliers_for_known_item(self, suppliers_json: Path):
        """Should return at least one supplier for 'laptop'."""
        result = supplier_lookup_tool(item="laptop", quantity=5,
                                      suppliers_file=suppliers_json)
        assert "suppliers" in result
        assert len(result["suppliers"]) > 0

    def test_result_structure_has_required_keys(self, suppliers_json: Path):
        """Each returned supplier must have scoring and identification fields."""
        result = supplier_lookup_tool(item="laptop", quantity=1,
                                      suppliers_file=suppliers_json)
        required = {"supplier_name", "unit_price", "rating", "stock", "composite_score"}
        for supplier in result["suppliers"]:
            assert required.issubset(supplier.keys()), (
                f"Supplier missing keys: {required - supplier.keys()}"
            )

    def test_suppliers_sorted_by_composite_score_descending(self, suppliers_json: Path):
        """Suppliers must be returned in descending composite score order."""
        result = supplier_lookup_tool(item="laptop", quantity=1,
                                      suppliers_file=suppliers_json)
        scores = [s["composite_score"] for s in result["suppliers"]]
        assert scores == sorted(scores, reverse=True)

    def test_filters_by_item_case_insensitive(self, suppliers_json: Path):
        """Lookup should work regardless of input case."""
        lower = supplier_lookup_tool(item="laptop", quantity=1,
                                     suppliers_file=suppliers_json)
        upper = supplier_lookup_tool(item="LAPTOP", quantity=1,
                                     suppliers_file=suppliers_json)
        assert len(lower["suppliers"]) == len(upper["suppliers"])

    def test_returns_empty_for_unknown_item(self, suppliers_json: Path):
        """Unknown items should return empty suppliers list, not an error."""
        result = supplier_lookup_tool(item="spaceship", quantity=1,
                                      suppliers_file=suppliers_json)
        assert result["suppliers"] == []
        assert result["total_found"] == 0
        assert "error" not in result

    def test_error_on_invalid_quantity(self, suppliers_json: Path):
        """Quantity < 1 should return an error dict."""
        result = supplier_lookup_tool(item="laptop", quantity=0,
                                      suppliers_file=suppliers_json)
        assert "error" in result

    def test_error_on_missing_file(self, tmp_path: Path):
        """Missing suppliers file should return an error dict, not raise."""
        result = supplier_lookup_tool(item="laptop", quantity=1,
                                      suppliers_file=tmp_path / "missing.json")
        assert "error" in result

    def test_budget_filter_soft_fallback(self, suppliers_json: Path):
        """Budget filter too strict should fall back to all suppliers."""
        result = supplier_lookup_tool(item="laptop", quantity=1,
                                      budget_per_unit=0.01,  # Impossibly low
                                      suppliers_file=suppliers_json)
        # Should still return suppliers (soft fallback)
        assert len(result["suppliers"]) > 0

    def test_normalise_equal_values_returns_half(self):
        """When all values are equal, normalise should return 0.5 for each."""
        result = _normalise([5.0, 5.0, 5.0])
        assert all(v == 0.5 for v in result)

    def test_normalise_invert(self):
        """Inverted normalise should give highest value the lowest score."""
        result = _normalise([1.0, 2.0, 3.0], invert=True)
        assert result[0] > result[2], "Lowest value should have highest inverted score"

    def test_composite_score_is_between_0_and_1(self, suppliers_json: Path):
        """Composite scores must always be in [0, 1]."""
        result = supplier_lookup_tool(item="laptop", quantity=1,
                                      suppliers_file=suppliers_json)
        for s in result["suppliers"]:
            assert 0.0 <= s["composite_score"] <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# generate_po_tool tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestGeneratePOTool:
    """Unit tests for generate_po_tool (fully deterministic — no mocks)."""

    def test_po_has_required_structure(
        self, sample_parsed_request: dict, sample_selected_supplier: dict
    ):
        """Generated PO must contain all required top-level keys."""
        po = generate_po_tool(sample_parsed_request, sample_selected_supplier)
        required = {
            "po_number", "issue_date", "requester_department",
            "supplier_name", "line_items", "subtotal", "tax_rate",
            "tax_amount", "total", "currency", "payment_terms",
            "expected_delivery_date",
        }
        assert required.issubset(po.keys()), f"Missing keys: {required - po.keys()}"

    def test_po_total_equals_subtotal_plus_tax(
        self, sample_parsed_request: dict, sample_selected_supplier: dict
    ):
        """PO total must equal subtotal + tax_amount (financial integrity)."""
        po = generate_po_tool(sample_parsed_request, sample_selected_supplier)
        assert "error" not in po
        expected_total = round(po["subtotal"] + po["tax_amount"], 2)
        assert po["total"] == expected_total

    def test_subtotal_equals_qty_times_unit_price(
        self, sample_parsed_request: dict, sample_selected_supplier: dict
    ):
        """Subtotal must equal quantity × unit price."""
        po = generate_po_tool(sample_parsed_request, sample_selected_supplier)
        qty = sample_parsed_request["quantity"]
        unit = sample_selected_supplier["unit_price"]
        assert po["subtotal"] == round(qty * unit, 2)

    def test_po_number_has_correct_prefix(
        self, sample_parsed_request: dict, sample_selected_supplier: dict
    ):
        """PO number must start with the configured prefix."""
        po = generate_po_tool(sample_parsed_request, sample_selected_supplier)
        assert po["po_number"].startswith("PO-")

    def test_po_number_uniqueness(
        self, sample_parsed_request: dict, sample_selected_supplier: dict
    ):
        """Two consecutive PO generations should yield different PO numbers."""
        po1 = generate_po_tool(sample_parsed_request, sample_selected_supplier)
        po2 = generate_po_tool(sample_parsed_request, sample_selected_supplier)
        assert po1["po_number"] != po2["po_number"]

    def test_delivery_date_after_issue_date(
        self, sample_parsed_request: dict, sample_selected_supplier: dict
    ):
        """Expected delivery date must be after or equal to issue date."""
        from datetime import date
        po = generate_po_tool(sample_parsed_request, sample_selected_supplier)
        issue = date.fromisoformat(po["issue_date"])
        delivery = date.fromisoformat(po["expected_delivery_date"])
        assert delivery >= issue

    def test_error_on_zero_quantity(self, sample_selected_supplier: dict):
        """Zero quantity must return an error dict."""
        bad_request = {
            "item": "laptop",
            "quantity": 0,  # invalid
            "department": "IT",
            "budget_limit": 5000.0,
        }
        result = generate_po_tool(bad_request, sample_selected_supplier)
        assert "error" in result

    def test_line_items_is_list(
        self, sample_parsed_request: dict, sample_selected_supplier: dict
    ):
        """line_items must be a non-empty list."""
        po = generate_po_tool(sample_parsed_request, sample_selected_supplier)
        assert isinstance(po["line_items"], list)
        assert len(po["line_items"]) > 0

    def test_generate_po_number_format(self):
        """PO number must match expected pattern PO-YYYYMMDD-XXXXXXXX."""
        import re
        po_num = _generate_po_number()
        assert re.match(r"PO-\d{8}-[A-F0-9]{8}", po_num), (
            f"PO number '{po_num}' does not match expected pattern"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# validate_budget_tool tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateBudgetTool:
    """Unit tests for validate_budget_tool (fully deterministic — no mocks)."""

    def test_approved_when_within_limit(
        self, sample_purchase_order: dict, budgets_json: Path
    ):
        """PO within budget limit must be approved."""
        # IT limit = 20000, PO total = 12960
        result = validate_budget_tool(
            purchase_order=sample_purchase_order,
            department="IT",
            budgets_file=budgets_json,
        )
        assert result["approved"] is True

    def test_rejected_when_over_limit(
        self, budgets_json: Path
    ):
        """PO exceeding budget limit must be rejected."""
        oversized_po = {
            "po_number": "PO-TEST",
            "total": 50000.00,  # Way over IT's 20000 limit
            "currency": "USD",
        }
        result = validate_budget_tool(
            purchase_order=oversized_po,
            department="IT",
            budgets_file=budgets_json,
        )
        assert result["approved"] is False

    def test_result_has_required_keys(
        self, sample_purchase_order: dict, budgets_json: Path
    ):
        """Result must contain all required audit fields."""
        result = validate_budget_tool(
            purchase_order=sample_purchase_order,
            department="IT",
            budgets_file=budgets_json,
        )
        required = {
            "approved", "reason", "approved_by", "department",
            "department_budget_limit", "po_total",
            "remaining_budget", "requires_dual_approval", "timestamp",
        }
        assert required.issubset(result.keys())

    def test_dual_approval_flagged_above_threshold(
        self, budgets_json: Path
    ):
        """PO above dual-approval threshold must set requires_dual_approval=True."""
        # IT dual threshold = 10000, use PO total = 15000 (within 20000 limit)
        large_po = {
            "po_number": "PO-TEST-LARGE",
            "total": 15000.00,
            "currency": "USD",
        }
        result = validate_budget_tool(
            purchase_order=large_po,
            department="IT",
            budgets_file=budgets_json,
        )
        assert result["requires_dual_approval"] is True

    def test_fallback_to_general_for_unknown_dept(
        self, sample_purchase_order: dict, budgets_json: Path
    ):
        """Unknown department should fall back to 'General' limits."""
        result = validate_budget_tool(
            purchase_order=sample_purchase_order,
            department="UnknownDept",
            budgets_file=budgets_json,
        )
        assert result["department"] == "General"

    def test_case_insensitive_department_lookup(
        self, sample_purchase_order: dict, budgets_json: Path
    ):
        """Department lookup should be case-insensitive."""
        result_lower = validate_budget_tool(
            purchase_order=sample_purchase_order,
            department="it",
            budgets_file=budgets_json,
        )
        result_upper = validate_budget_tool(
            purchase_order=sample_purchase_order,
            department="IT",
            budgets_file=budgets_json,
        )
        assert result_lower["approved"] == result_upper["approved"]

    def test_error_on_missing_budgets_file(self, sample_purchase_order: dict, tmp_path: Path):
        """Missing budgets file should return error dict, not raise."""
        result = validate_budget_tool(
            purchase_order=sample_purchase_order,
            department="IT",
            budgets_file=tmp_path / "no_such_file.json",
        )
        assert "error" in result

    def test_hr_department_lower_limit(self, budgets_json: Path):
        """HR department has a lower per-order limit and should reject larger POs."""
        # HR limit = 5000
        large_po = {"po_number": "PO-HR-TEST", "total": 8000.00, "currency": "USD"}
        result = validate_budget_tool(
            purchase_order=large_po,
            department="HR",
            budgets_file=budgets_json,
        )
        assert result["approved"] is False

    def test_find_department_returns_none_for_unknown(self):
        """_find_department should return None for non-existent department."""
        depts = {"IT": {}, "HR": {}}
        assert _find_department(depts, "XYZ") is None

    def test_find_department_case_insensitive(self):
        """_find_department should match regardless of case."""
        depts = {"IT": {}, "HR": {}}
        assert _find_department(depts, "it") == "IT"
        assert _find_department(depts, "hR") == "HR"
