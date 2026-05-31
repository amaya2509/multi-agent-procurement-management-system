"""
End-to-end test for the Multi-Agent Procurement Management System.

Tests the full workflow from user_request to approval_status by running the
complete LangGraph graph with mocked LLM calls. All tool logic executes
against real temp JSON fixtures (no mocked tools), verifying true integration
of the data flow across all 5 agents.

Strategy:
- Mock only query_llm (requires Ollama) and parse_request_tool (calls LLM).
- All data-processing tools (supplier_lookup, generate_po, validate_budget)
  run against real fixture data files.
- Assertions focus on state structure and key business invariants, NOT on
  exact string content (non-deterministic system principle).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.graph import run_procurement_workflow, build_graph
from src.state import ProcurementState


# ─── Shared mock responses ────────────────────────────────────────────────────

MOCK_PARSED_REQUEST = {
    "item": "laptop",
    "quantity": 10,
    "department": "IT",
    "budget_limit": 15000.0,
    "urgency": "medium",
    "additional_requirements": "SSD storage preferred",
    "confidence_score": 0.95,
}

MOCK_LLM_JUSTIFICATION = {
    "selected_supplier_name": "TechPro Solutions",
    "justification": (
        "TechPro Solutions was selected based on the highest composite score "
        "across all evaluation criteria."
    ),
    "key_advantages": ["High rating", "Adequate stock", "Competitive pricing"],
}

MOCK_LLM_FORMAL_NOTICE = {
    "formal_notice": (
        "This Purchase Order has been reviewed and approved in accordance "
        "with departmental procurement policy."
    ),
    "action_required": "Proceed with issuing PO to supplier.",
    "compliance_notes": "Dual approval may be required for orders above threshold.",
}


# ─── E2E Test Suite ───────────────────────────────────────────────────────────

class TestEndToEnd:
    """Full workflow integration tests."""

    def _mock_llm_side_effect(self, prompt: str, system_prompt: str, **kwargs):
        """
        Route LLM mock responses based on system prompt content.
        This simulates each agent getting its appropriate response.
        """
        if "procurement analyst" in system_prompt.lower() or "parse" in system_prompt.lower():
            return MOCK_PARSED_REQUEST
        elif "supplier intelligence" in system_prompt.lower():
            return MOCK_LLM_JUSTIFICATION
        elif "financial controller" in system_prompt.lower():
            return MOCK_LLM_FORMAL_NOTICE
        else:
            return MOCK_LLM_JUSTIFICATION  # Default fallback

    def test_full_workflow_completes_without_error(
        self,
        suppliers_json: Path,
        budgets_json: Path,
    ):
        """Complete workflow must not set error in final state."""
        with (
            patch("tools.parse_request.query_llm", return_value=MOCK_PARSED_REQUEST),
            patch("agents.supplier_intelligence.query_llm", return_value=MOCK_LLM_JUSTIFICATION),
            patch("agents.approval.query_llm", return_value=MOCK_LLM_FORMAL_NOTICE),
            patch("tools.supplier_lookup.SUPPLIERS_FILE", suppliers_json),
            patch("tools.validate_budget.BUDGETS_FILE", budgets_json),
        ):
            final_state = run_procurement_workflow(
                "Need 10 laptops for IT department with budget 15000"
            )

        assert final_state.get("error") is None, (
            f"Workflow returned error: {final_state.get('error')}"
        )

    def test_all_state_fields_populated(
        self,
        suppliers_json: Path,
        budgets_json: Path,
    ):
        """Every agent's output field must be populated in the final state."""
        with (
            patch("tools.parse_request.query_llm", return_value=MOCK_PARSED_REQUEST),
            patch("agents.supplier_intelligence.query_llm", return_value=MOCK_LLM_JUSTIFICATION),
            patch("agents.approval.query_llm", return_value=MOCK_LLM_FORMAL_NOTICE),
            patch("tools.supplier_lookup.SUPPLIERS_FILE", suppliers_json),
            patch("tools.validate_budget.BUDGETS_FILE", budgets_json),
        ):
            final_state = run_procurement_workflow(
                "Need 10 laptops for IT department with budget 15000"
            )

        # Each agent must have populated its field
        assert final_state.get("parsed_request") is not None, "Analyzer did not produce output"
        assert final_state.get("supplier_options") is not None, "Supplier agent did not run"
        assert final_state.get("selected_supplier") is not None, "No supplier selected"
        assert final_state.get("purchase_order") is not None, "No PO generated"
        assert final_state.get("approval_status") is not None, "No approval decision"

    def test_approval_status_has_approved_key(
        self,
        suppliers_json: Path,
        budgets_json: Path,
    ):
        """Final approval_status must have an 'approved' boolean field."""
        with (
            patch("tools.parse_request.query_llm", return_value=MOCK_PARSED_REQUEST),
            patch("agents.supplier_intelligence.query_llm", return_value=MOCK_LLM_JUSTIFICATION),
            patch("agents.approval.query_llm", return_value=MOCK_LLM_FORMAL_NOTICE),
            patch("tools.supplier_lookup.SUPPLIERS_FILE", suppliers_json),
            patch("tools.validate_budget.BUDGETS_FILE", budgets_json),
        ):
            final_state = run_procurement_workflow(
                "Need 10 laptops for IT department with budget 15000"
            )

        approval = final_state.get("approval_status", {})
        assert "approved" in approval
        assert isinstance(approval["approved"], bool)

    def test_purchase_order_financial_integrity(
        self,
        suppliers_json: Path,
        budgets_json: Path,
    ):
        """PO total must equal subtotal + tax_amount (financial integrity)."""
        with (
            patch("tools.parse_request.query_llm", return_value=MOCK_PARSED_REQUEST),
            patch("agents.supplier_intelligence.query_llm", return_value=MOCK_LLM_JUSTIFICATION),
            patch("agents.approval.query_llm", return_value=MOCK_LLM_FORMAL_NOTICE),
            patch("tools.supplier_lookup.SUPPLIERS_FILE", suppliers_json),
            patch("tools.validate_budget.BUDGETS_FILE", budgets_json),
        ):
            final_state = run_procurement_workflow(
                "Need 10 laptops for IT department with budget 15000"
            )

        po = final_state["purchase_order"]
        expected_total = round(po["subtotal"] + po["tax_amount"], 2)
        assert po["total"] == expected_total, (
            f"PO total {po['total']} != subtotal {po['subtotal']} + "
            f"tax {po['tax_amount']} = {expected_total}"
        )

    def test_workflow_logs_contain_all_agents(
        self,
        suppliers_json: Path,
        budgets_json: Path,
    ):
        """All 5 agents must appear in the workflow logs."""
        with (
            patch("tools.parse_request.query_llm", return_value=MOCK_PARSED_REQUEST),
            patch("agents.supplier_intelligence.query_llm", return_value=MOCK_LLM_JUSTIFICATION),
            patch("agents.approval.query_llm", return_value=MOCK_LLM_FORMAL_NOTICE),
            patch("tools.supplier_lookup.SUPPLIERS_FILE", suppliers_json),
            patch("tools.validate_budget.BUDGETS_FILE", budgets_json),
        ):
            final_state = run_procurement_workflow(
                "Need 10 laptops for IT department with budget 15000"
            )

        logs = final_state.get("logs", [])
        agent_names = {entry["agent"] for entry in logs}
        expected_agents = {
            "CoordinatorAgent",
            "RequestAnalyzerAgent",
            "SupplierIntelligenceAgent",
            "ProcurementGeneratorAgent",
            "ApprovalAgent",
        }
        assert expected_agents.issubset(agent_names), (
            f"Missing agents in logs: {expected_agents - agent_names}"
        )

    def test_workflow_halts_on_empty_request(self):
        """Empty user_request must cause workflow to halt with error, not crash."""
        final_state = run_procurement_workflow("")
        assert final_state.get("error") is not None

    def test_po_number_format(
        self,
        suppliers_json: Path,
        budgets_json: Path,
    ):
        """PO number must follow the PO-YYYYMMDD-XXXXXXXX format."""
        import re
        with (
            patch("tools.parse_request.query_llm", return_value=MOCK_PARSED_REQUEST),
            patch("agents.supplier_intelligence.query_llm", return_value=MOCK_LLM_JUSTIFICATION),
            patch("agents.approval.query_llm", return_value=MOCK_LLM_FORMAL_NOTICE),
            patch("tools.supplier_lookup.SUPPLIERS_FILE", suppliers_json),
            patch("tools.validate_budget.BUDGETS_FILE", budgets_json),
        ):
            final_state = run_procurement_workflow(
                "Need 10 laptops for IT department with budget 15000"
            )

        po_number = final_state["purchase_order"]["po_number"]
        assert re.match(r"PO-\d{8}-[A-F0-9]{8}", po_number), (
            f"PO number '{po_number}' does not match expected pattern"
        )

    def test_supplier_options_sorted_by_score(
        self,
        suppliers_json: Path,
        budgets_json: Path,
    ):
        """supplier_options in final state must be sorted by composite_score descending."""
        with (
            patch("tools.parse_request.query_llm", return_value=MOCK_PARSED_REQUEST),
            patch("agents.supplier_intelligence.query_llm", return_value=MOCK_LLM_JUSTIFICATION),
            patch("agents.approval.query_llm", return_value=MOCK_LLM_FORMAL_NOTICE),
            patch("tools.supplier_lookup.SUPPLIERS_FILE", suppliers_json),
            patch("tools.validate_budget.BUDGETS_FILE", budgets_json),
        ):
            final_state = run_procurement_workflow(
                "Need 10 laptops for IT department with budget 15000"
            )

        options = final_state.get("supplier_options", [])
        if len(options) > 1:
            scores = [s.get("composite_score", 0) for s in options]
            assert scores == sorted(scores, reverse=True), (
                "supplier_options are not sorted by composite_score descending"
            )

    def test_graph_builds_successfully(self):
        """build_graph() must not raise and must return a callable compiled graph."""
        graph = build_graph()
        assert graph is not None
        # Compiled LangGraph graphs expose an invoke() method
        assert callable(getattr(graph, "invoke", None)), (
            "Compiled graph must have an invoke() method"
        )
