"""
LangGraph StateGraph construction for the Multi-Agent Procurement System.

Graph topology (sequential CWD Model):
  coordinator → request_analyzer → supplier_intelligence
              → procurement_generator → approval → END

Each node is a pure function (agent) that accepts ProcurementState and
returns a partial state dict. LangGraph merges the returned dict into
the current state before calling the next node.

Conditional routing:
  After each non-terminal node, a routing function checks for state["error"].
  If an error is set, the graph routes directly to END to prevent cascading
  failures. Otherwise, it proceeds to the next node in sequence.
"""

from __future__ import annotations

from typing import Literal

from langgraph.graph import StateGraph, END

from agents.coordinator import coordinator_agent
from agents.request_analyzer import request_analyzer_agent
from agents.supplier_intelligence import supplier_intelligence_agent
from agents.procurement_generator import procurement_generator_agent
from agents.approval import approval_agent
from src.logger import get_logger
from src.state import ProcurementState

logger = get_logger("graph")

# ─── Node names (constants for readability and typo-prevention) ───────────────
NODE_COORDINATOR = "coordinator"
NODE_ANALYZER = "request_analyzer"
NODE_SUPPLIER = "supplier_intelligence"
NODE_GENERATOR = "procurement_generator"
NODE_APPROVAL = "approval"


def _route_or_error(
    state: ProcurementState,
    next_node: str,
) -> Literal["__end__"] | str:
    """
    Conditional edge router.

    If the state contains an error key set to a non-None value, route to END
    immediately. Otherwise proceed to next_node.

    Args:
        state:     Current ProcurementState.
        next_node: The node to route to if no error is present.

    Returns:
        "__end__" on error, or next_node on success.
    """
    if state.get("error"):
        logger.warning(
            "[graph] Error detected after node — routing to END. error=%s",
            state["error"],
        )
        return END
    return next_node


def build_graph() -> StateGraph:
    """
    Construct and compile the procurement multi-agent StateGraph.

    Returns:
        A compiled LangGraph StateGraph ready for invocation.
    """
    graph = StateGraph(ProcurementState)

    # ── Register nodes ────────────────────────────────────────────────────────
    graph.add_node(NODE_COORDINATOR, coordinator_agent)
    graph.add_node(NODE_ANALYZER, request_analyzer_agent)
    graph.add_node(NODE_SUPPLIER, supplier_intelligence_agent)
    graph.add_node(NODE_GENERATOR, procurement_generator_agent)
    graph.add_node(NODE_APPROVAL, approval_agent)

    # ── Set entry point ───────────────────────────────────────────────────────
    graph.set_entry_point(NODE_COORDINATOR)

    # ── Conditional edges with error short-circuit ────────────────────────────
    graph.add_conditional_edges(
        NODE_COORDINATOR,
        lambda s: _route_or_error(s, NODE_ANALYZER),
        {NODE_ANALYZER: NODE_ANALYZER, END: END},
    )
    graph.add_conditional_edges(
        NODE_ANALYZER,
        lambda s: _route_or_error(s, NODE_SUPPLIER),
        {NODE_SUPPLIER: NODE_SUPPLIER, END: END},
    )
    graph.add_conditional_edges(
        NODE_SUPPLIER,
        lambda s: _route_or_error(s, NODE_GENERATOR),
        {NODE_GENERATOR: NODE_GENERATOR, END: END},
    )
    graph.add_conditional_edges(
        NODE_GENERATOR,
        lambda s: _route_or_error(s, NODE_APPROVAL),
        {NODE_APPROVAL: NODE_APPROVAL, END: END},
    )
    graph.add_edge(NODE_APPROVAL, END)

    compiled = graph.compile()
    logger.info("[graph] Procurement StateGraph compiled successfully.")
    return compiled


def run_procurement_workflow(user_request: str) -> ProcurementState:
    """
    Execute the full procurement workflow for a given user request.

    Args:
        user_request: The natural-language procurement request.

    Returns:
        The final ProcurementState after all agents have executed.
    """
    graph = build_graph()
    initial_state: ProcurementState = {
        "user_request": user_request,
        "parsed_request": None,
        "supplier_options": [],
        "selected_supplier": None,
        "purchase_order": None,
        "approval_status": None,
        "logs": [],
        "error": None,
    }
    logger.info("[graph] Invoking procurement workflow...")
    final_state = graph.invoke(initial_state)
    logger.info("[graph] Workflow complete.")
    return final_state
