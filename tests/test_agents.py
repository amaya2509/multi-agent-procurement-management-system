"""
Agent behavior tests for the Multi-Agent Procurement Management System.

Tests verify:
- Each agent mutates the correct state fields
- Agents skip processing when upstream error is detected
- Agents handle tool failures gracefully
- Logs are correctly populated by each agent

LLM calls are mocked throughout — these tests do NOT require Ollama.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agents.coordinator import coordinator_agent
from agents.request_analyzer import request_analyzer_agent
from agents.supplier_intelligence import supplier_intelligence_agent
from agents.procurement_generator import procurement_generator_agent
from agents.approval import approval_agent


# ═══════════════════════════════════════════════════════════════════════════════
# Coordinator Agent Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoordinatorAgent:
    """Tests for the Coordinator agent node."""

    def test_initialises_state_fields(self):
        """Coordinator should return all required initial state fields."""
        state = {"user_request": "Need 5 laptops for IT"}
        result = coordinator_agent(state)
        assert "logs" in result
        assert isinstance(result["logs"], list)
        assert len(result["logs"]) > 0
        assert result.get("error") is None

    def test_sets_error_on_empty_request(self):
        """Empty user_request must set error and not proceed."""
        result = coordinator_agent({"user_request": ""})
        assert result.get("error") is not None
        assert "logs" in result

    def test_sets_error_on_missing_request(self):
        """Missing user_request key must set error."""
        result = coordinator_agent({})
        assert result.get("error") is not None

    def test_log_entry_has_required_fields(self):
        """First log entry should have agent, event, message, timestamp fields."""
        state = {"user_request": "Need 3 monitors"}
        result = coordinator_agent(state)
        log = result["logs"][0]
        assert "agent" in log
        assert "event" in log
        assert "message" in log
        assert "timestamp" in log

    def test_initialises_supplier_options_as_list(self):
        """supplier_options must be initialised as an empty list."""
        state = {"user_request": "Need 2 printers"}
        result = coordinator_agent(state)
        assert result.get("supplier_options") == []


# ═══════════════════════════════════════════════════════════════════════════════
# Request Analyzer Agent Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestRequestAnalyzerAgent:
    """Tests for the Request Analyzer agent node."""

    def test_populates_parsed_request_on_success(self):
        """Successful parse should set parsed_request in state update."""
        mock_result = {
            "item": "laptop",
            "quantity": 10,
            "department": "IT",
            "budget_limit": 15000.0,
            "urgency": "medium",
            "additional_requirements": "",
            "confidence_score": 0.9,
        }
        with patch("agents.request_analyzer.parse_request_tool", return_value=mock_result):
            state = {
                "user_request": "Need 10 laptops for IT with budget 15000",
                "logs": [],
                "error": None,
            }
            result = request_analyzer_agent(state)
        assert "parsed_request" in result
        assert result["parsed_request"]["item"] == "laptop"
        assert result["parsed_request"]["quantity"] == 10

    def test_skips_when_upstream_error(self):
        """Agent must return empty dict when upstream error exists."""
        state = {"error": "upstream failure", "logs": []}
        result = request_analyzer_agent(state)
        assert result == {}

    def test_sets_error_on_tool_failure(self):
        """Tool failure must propagate as state error."""
        with patch(
            "agents.request_analyzer.parse_request_tool",
            return_value={"error": "LLM offline"},
        ):
            state = {"user_request": "Need chairs", "logs": [], "error": None}
            result = request_analyzer_agent(state)
        assert "error" in result
        assert result["error"] is not None

    def test_appends_log_entry(self):
        """Agent must append exactly one log entry on success."""
        mock_result = {
            "item": "mouse",
            "quantity": 5,
            "department": "HR",
            "budget_limit": 300.0,
            "urgency": "low",
            "additional_requirements": "",
            "confidence_score": 0.85,
        }
        with patch("agents.request_analyzer.parse_request_tool", return_value=mock_result):
            state = {"user_request": "Need 5 mice for HR", "logs": [], "error": None}
            result = request_analyzer_agent(state)
        assert len(result["logs"]) == 1
        assert result["logs"][0]["agent"] == "RequestAnalyzerAgent"

    def test_preserves_existing_logs(self):
        """Agent must preserve existing log entries (append, not overwrite)."""
        existing_log = {"agent": "CoordinatorAgent", "event": "start", "message": "...", "timestamp": "t"}
        mock_result = {
            "item": "keyboard",
            "quantity": 2,
            "department": "Finance",
            "budget_limit": 200.0,
            "urgency": "low",
            "additional_requirements": "",
            "confidence_score": 0.9,
        }
        with patch("agents.request_analyzer.parse_request_tool", return_value=mock_result):
            state = {
                "user_request": "Need 2 keyboards for Finance",
                "logs": [existing_log],
                "error": None,
            }
            result = request_analyzer_agent(state)
        assert len(result["logs"]) == 2
        assert result["logs"][0] == existing_log


# ═══════════════════════════════════════════════════════════════════════════════
# Supplier Intelligence Agent Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSupplierIntelligenceAgent:
    """Tests for the Supplier Intelligence agent node."""

    def test_populates_supplier_fields_on_success(
        self, sample_parsed_request: dict, suppliers_json: Path
    ):
        """Agent must populate both supplier_options and selected_supplier."""
        mock_lookup = {
            "suppliers": [
                {
                    "supplier_name": "Alpha Tech",
                    "unit_price": 1200.0,
                    "rating": 4.8,
                    "stock": 100,
                    "lead_time_days": 5,
                    "item": "laptop",
                    "composite_score": 0.875,
                    "currency": "USD",
                    "payment_terms": "Net 30",
                    "contact_email": "a@test.com",
                    "warranty_months": 24,
                    "id": "T001",
                    "min_order_qty": 1,
                    "certifications": [],
                }
            ],
            "total_found": 2,
            "item_searched": "laptop",
            "quantity_requested": 10,
        }
        mock_llm = {
            "selected_supplier_name": "Alpha Tech",
            "justification": "Best rating and reasonable price.",
            "key_advantages": ["High rating", "Good stock"],
        }
        with patch("agents.supplier_intelligence.supplier_lookup_tool", return_value=mock_lookup):
            with patch("agents.supplier_intelligence.query_llm", return_value=mock_llm):
                state = {
                    "parsed_request": sample_parsed_request,
                    "logs": [],
                    "error": None,
                }
                result = supplier_intelligence_agent(state)
        assert "supplier_options" in result
        assert "selected_supplier" in result
        assert len(result["supplier_options"]) > 0
        assert result["selected_supplier"]["supplier_name"] == "Alpha Tech"

    def test_skips_when_upstream_error(self):
        """Agent must return empty dict when upstream error exists."""
        result = supplier_intelligence_agent({"error": "upstream", "logs": []})
        assert result == {}

    def test_sets_error_when_no_suppliers_found(self, sample_parsed_request: dict):
        """Empty supplier list must set error."""
        mock_lookup = {
            "suppliers": [],
            "total_found": 0,
            "item_searched": "laptop",
            "quantity_requested": 10,
        }
        with patch("agents.supplier_intelligence.supplier_lookup_tool", return_value=mock_lookup):
            state = {"parsed_request": sample_parsed_request, "logs": [], "error": None}
            result = supplier_intelligence_agent(state)
        assert "error" in result

    def test_selection_includes_justification(
        self, sample_parsed_request: dict
    ):
        """Selected supplier must include selection_justification field."""
        mock_lookup = {
            "suppliers": [
                {
                    "supplier_name": "TestCo",
                    "unit_price": 1000.0,
                    "rating": 4.5,
                    "stock": 50,
                    "lead_time_days": 7,
                    "item": "laptop",
                    "composite_score": 0.72,
                    "currency": "USD",
                    "payment_terms": "Net 30",
                    "contact_email": "t@co.com",
                    "warranty_months": 12,
                    "id": "T999",
                    "min_order_qty": 1,
                    "certifications": [],
                }
            ],
            "total_found": 1,
            "item_searched": "laptop",
            "quantity_requested": 10,
        }
        mock_llm = {
            "selected_supplier_name": "TestCo",
            "justification": "Only available supplier.",
            "key_advantages": ["Available"],
        }
        with patch("agents.supplier_intelligence.supplier_lookup_tool", return_value=mock_lookup):
            with patch("agents.supplier_intelligence.query_llm", return_value=mock_llm):
                state = {"parsed_request": sample_parsed_request, "logs": [], "error": None}
                result = supplier_intelligence_agent(state)
        assert "selection_justification" in result["selected_supplier"]


# ═══════════════════════════════════════════════════════════════════════════════
# Procurement Generator Agent Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestProcurementGeneratorAgent:
    """Tests for the Procurement Generator agent node."""

    def test_populates_purchase_order(
        self, sample_parsed_request: dict, sample_selected_supplier: dict
    ):
        """Agent must set purchase_order in state update."""
        state = {
            "parsed_request": sample_parsed_request,
            "selected_supplier": sample_selected_supplier,
            "logs": [],
            "error": None,
        }
        result = procurement_generator_agent(state)
        assert "purchase_order" in result
        assert "po_number" in result["purchase_order"]
        assert "total" in result["purchase_order"]

    def test_skips_when_upstream_error(self):
        """Agent must return empty dict when upstream error exists."""
        result = procurement_generator_agent({"error": "upstream", "logs": []})
        assert result == {}

    def test_sets_error_when_parsed_request_missing(self, sample_selected_supplier: dict):
        """Missing parsed_request must set error."""
        state = {
            "parsed_request": None,
            "selected_supplier": sample_selected_supplier,
            "logs": [],
            "error": None,
        }
        result = procurement_generator_agent(state)
        assert "error" in result

    def test_sets_error_when_supplier_missing(self, sample_parsed_request: dict):
        """Missing selected_supplier must set error."""
        state = {
            "parsed_request": sample_parsed_request,
            "selected_supplier": None,
            "logs": [],
            "error": None,
        }
        result = procurement_generator_agent(state)
        assert "error" in result

    def test_po_total_is_positive(
        self, sample_parsed_request: dict, sample_selected_supplier: dict
    ):
        """Generated PO total must always be positive."""
        state = {
            "parsed_request": sample_parsed_request,
            "selected_supplier": sample_selected_supplier,
            "logs": [],
            "error": None,
        }
        result = procurement_generator_agent(state)
        assert result["purchase_order"]["total"] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Approval Agent Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestApprovalAgent:
    """Tests for the Approval agent node."""

    def test_approval_status_has_approved_key(
        self,
        sample_purchase_order: dict,
        sample_parsed_request: dict,
        budgets_json: Path,
    ):
        """approval_status must have an 'approved' boolean key."""
        mock_validation = {
            "approved": True,
            "reason": "Within budget.",
            "approved_by": "CTO",
            "department": "IT",
            "department_budget_limit": 20000.0,
            "po_total": 12960.0,
            "remaining_budget": 7040.0,
            "requires_dual_approval": True,
            "timestamp": "2025-01-01T00:00:00+00:00",
        }
        mock_llm = {
            "formal_notice": "PO approved by CTO.",
            "action_required": "Proceed with procurement.",
            "compliance_notes": "Dual approval required.",
        }
        with patch("agents.approval.validate_budget_tool", return_value=mock_validation):
            with patch("agents.approval.query_llm", return_value=mock_llm):
                state = {
                    "purchase_order": sample_purchase_order,
                    "parsed_request": sample_parsed_request,
                    "logs": [],
                    "error": None,
                }
                result = approval_agent(state)
        assert "approval_status" in result
        assert "approved" in result["approval_status"]
        assert isinstance(result["approval_status"]["approved"], bool)

    def test_skips_when_upstream_error(self):
        """Agent must return empty dict when upstream error exists."""
        result = approval_agent({"error": "upstream", "logs": []})
        assert result == {}

    def test_sets_error_when_po_missing(self, sample_parsed_request: dict):
        """Missing purchase_order must set error."""
        state = {
            "purchase_order": None,
            "parsed_request": sample_parsed_request,
            "logs": [],
            "error": None,
        }
        result = approval_agent(state)
        assert "error" in result

    def test_approval_status_includes_formal_notice(
        self, sample_purchase_order: dict, sample_parsed_request: dict
    ):
        """approval_status must include a formal_notice string."""
        mock_validation = {
            "approved": True,
            "reason": "OK",
            "approved_by": "CTO",
            "department": "IT",
            "department_budget_limit": 20000.0,
            "po_total": 12960.0,
            "remaining_budget": 7040.0,
            "requires_dual_approval": False,
            "timestamp": "2025-01-01T00:00:00+00:00",
        }
        mock_llm = {
            "formal_notice": "This PO is hereby approved.",
            "action_required": "Dispatch PO.",
            "compliance_notes": "",
        }
        with patch("agents.approval.validate_budget_tool", return_value=mock_validation):
            with patch("agents.approval.query_llm", return_value=mock_llm):
                state = {
                    "purchase_order": sample_purchase_order,
                    "parsed_request": sample_parsed_request,
                    "logs": [],
                    "error": None,
                }
                result = approval_agent(state)
        assert "formal_notice" in result["approval_status"]
        assert isinstance(result["approval_status"]["formal_notice"], str)
