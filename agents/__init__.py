"""
Agents package for Multi-Agent Procurement Management System.

Each agent is a LangGraph node function:
  - Accepts ProcurementState as input
  - Returns a partial ProcurementState dict (LangGraph merges it)
  - Uses tools for all logic (never embeds business logic directly)
  - Appends structured entries to state["logs"]
"""
