# Multi-Agent Procurement Management System

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-green)
![Ollama](https://img.shields.io/badge/LLM-Ollama%20(Local)-orange)
![License](https://img.shields.io/badge/License-MIT-lightgrey)
![Tests](https://img.shields.io/badge/Tests-pytest-yellow)

**A production-grade, locally-hosted Multi-Agent System (MAS) for end-to-end Procurement Automation**

*Coordinator-Worker Design (CWD Model) · LangGraph Orchestration · Zero External APIs*

</div>

---

## Overview

This system automates the entire procurement lifecycle — from a natural-language request to a validated, budget-approved Purchase Order — using five collaborating AI agents orchestrated by LangGraph.

Every agent has a single responsibility, communicates through a shared typed state, and uses dedicated tools for all business logic. No logic is embedded directly in agents. No external APIs are used.

---

## Architecture

```
User Request (CLI)
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│                   LangGraph StateGraph                   │
│                                                         │
│  ┌──────────────┐     ┌────────────────────────────┐    │
│  │  Coordinator │────▶│    Request Analyzer         │    │
│  │  Agent       │     │    (parse_request_tool)     │    │
│  └──────────────┘     └────────────┬───────────────┘    │
│        🎯                          │                     │
│                                    ▼                     │
│                        ┌──────────────────────────┐     │
│                        │  Supplier Intelligence    │     │
│                        │  (supplier_lookup_tool)  │     │
│                        └──────────┬───────────────┘     │
│                                   │                     │
│                                   ▼                     │
│                        ┌──────────────────────────┐     │
│                        │  Procurement Generator   │     │
│                        │  (generate_po_tool)      │     │
│                        └──────────┬───────────────┘     │
│                                   │                     │
│                                   ▼                     │
│                        ┌──────────────────────────┐     │
│                        │  Approval Agent           │     │
│                        │  (validate_budget_tool)  │     │
│                        └──────────────────────────┘     │
└─────────────────────────────────────────────────────────┘
       │
       ▼
Final State → CLI Output + logs/execution.log
```

### Agent Responsibilities

| Agent | Role | Tool Used |
|---|---|---|
| **Coordinator** | Initialise workflow, validate input, set state defaults | None (pure orchestration) |
| **Request Analyzer** | Parse natural-language request into structured JSON | `parse_request_tool` |
| **Supplier Intelligence** | Search catalogue, score and rank suppliers | `supplier_lookup_tool` |
| **Procurement Generator** | Generate complete PO with financial calculations | `generate_po_tool` |
| **Approval Agent** | Validate PO against department budget, issue formal notice | `validate_budget_tool` |

### State Design

All agents share a single `ProcurementState` TypedDict that flows through the entire graph:

```python
class ProcurementState(TypedDict):
    user_request: str
    parsed_request: Optional[ParsedRequest]
    supplier_options: list[SupplierRecord]
    selected_supplier: Optional[SupplierRecord]
    purchase_order: Optional[PurchaseOrder]
    approval_status: Optional[ApprovalStatus]
    logs: list[dict]
    error: Optional[str]
```

### Supplier Scoring Formula

```
composite_score = rating        × 0.40
                + price_score   × 0.35   (inverted: lower price → higher score)
                + stock_score   × 0.15
                + lead_score    × 0.10   (inverted: shorter lead → higher score)
```
All components are min-max normalised to [0, 1] relative to the candidate set.

---

## Project Structure

```
multi-agent-procurement-management-system/
├── agents/                     # 5 LangGraph agent nodes
│   ├── coordinator.py          # Orchestration entry point
│   ├── request_analyzer.py     # NLP → structured request
│   ├── supplier_intelligence.py # Catalogue search + ranking
│   ├── procurement_generator.py # PO creation
│   └── approval.py             # Budget validation + formal notice
│
├── tools/                      # 4 tool modules (pure functions)
│   ├── parse_request.py        # parse_request_tool
│   ├── supplier_lookup.py      # supplier_lookup_tool
│   ├── generate_po.py          # generate_po_tool
│   └── validate_budget.py      # validate_budget_tool
│
├── src/                        # Core infrastructure
│   ├── config.py               # All config (env-var driven)
│   ├── logger.py               # Rotating file + console logger
│   ├── state.py                # ProcurementState TypedDict schema
│   ├── llm_client.py           # Ollama wrapper (retry + JSON extraction)
│   └── graph.py                # LangGraph StateGraph definition
│
├── data/
│   ├── suppliers.json          # Local supplier catalogue (15 suppliers)
│   └── budgets.json            # Department budget limits (7 departments)
│
├── tests/
│   ├── conftest.py             # Shared fixtures
│   ├── test_tools.py           # 30+ unit tests for all 4 tools
│   ├── test_agents.py          # 20+ agent behavior tests
│   └── test_e2e.py             # 9 end-to-end integration tests
│
├── logs/                       # Auto-created; execution.log written here
├── main.py                     # CLI entry point (rich output)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com/) installed and running locally

### 1. Clone the Repository

```bash
git clone <repo-url>
cd multi-agent-procurement-management-system
git checkout dev
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate       # macOS / Linux
# OR
.venv\Scripts\activate          # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Pull an Ollama Model

```bash
# Recommended (best quality/speed trade-off)
ollama pull llama3:8b

# Lighter alternative for low-resource machines
ollama pull phi3
```

### 5. Configure (Optional)

Copy the example env file and edit if needed:

```bash
cp .env.example .env
```

Key variables:

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_MODEL` | `llama3:8b` | Ollama model tag |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `LLM_TEMPERATURE` | `0.1` | LLM temperature (low = deterministic) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Usage

### Basic Request

```bash
python main.py --request "Need 10 laptops for IT with budget 15000"
```

### With Model Override

```bash
python main.py --request "5 office chairs for HR department" --model phi3
```

### Verbose Mode (shows raw state)

```bash
python main.py --request "20 monitors for Engineering team" --verbose
```

### Help

```bash
python main.py --help
```

---

## Example Output

```
╔══════════════════════════════════════════════════════════╗
║      MULTI-AGENT PROCUREMENT MANAGEMENT SYSTEM           ║
║      CWD Model  ·  Powered by LangGraph + Ollama         ║
╚══════════════════════════════════════════════════════════╝

╭──────────────── 📥 Procurement Request ────────────────╮
│  Need 10 laptops for IT with budget 15000               │
╰─────────────────────────────────────────────────────────╯

🚀 Initiating multi-agent workflow...

📋 Agent Execution Trace
┌──────────────────────────────┬──────────────────────┬────────────────────────────────────────────┐
│ Agent                        │ Event                │ Message                                    │
├──────────────────────────────┼──────────────────────┼────────────────────────────────────────────┤
│ 🎯 CoordinatorAgent          │ workflow_start        │ Workflow started for request: 'Need 10...' │
│ 🔍 RequestAnalyzerAgent      │ request_parsed        │ 10x laptop for IT dept, budget $15000       │
│ 🏭 SupplierIntelligenceAgent │ supplier_selected     │ Selected: TechPro Solutions (score=0.8312) │
│ 📄 ProcurementGeneratorAgent │ po_generated          │ PO PO-20250414-A3F1B2C9 | Total: $12,960  │
│ ✅ ApprovalAgent             │ approval_decision    │ ✅ APPROVED | Within budget limit $20,000   │
└──────────────────────────────┴──────────────────────┴────────────────────────────────────────────┘

🔍 Parsed Request
  Item          laptop
  Quantity      10
  Department    IT
  Budget Limit  15000.00
  Urgency       medium

🏭 Supplier Selection
┌──────┬───────────────────────┬────────────┬────────┬───────┬────────────┬────────┐
│ Rank │ Supplier              │ Price/Unit │ Rating │ Stock │ Lead (days)│ Score  │
├──────┼───────────────────────┼────────────┼────────┼───────┼────────────┼────────┤
│ ★ 1  │ TechPro Solutions     │ $1200.00   │ 4.8    │ 150   │ 5          │ 0.8312 │
│ 2    │ DigiVendor Inc.       │ $1050.00   │ 4.2    │ 75    │ 10         │ 0.5521 │
│ 3    │ GlobalTech Supplies   │ $980.00    │ 3.9    │ 200   │ 14         │ 0.4180 │
└──────┴───────────────────────┴────────────┴────────┴───────┴────────────┴────────┘

📄 Purchase Order
  PO Number         PO-20250414-A3F1B2C9
  Issue Date        2025-04-14
  Supplier          TechPro Solutions
  Department        IT
  Payment Terms     Net 30
  Expected Delivery 2025-04-19
  Subtotal          $12000.00
  Tax               $960.00 (8%)
  TOTAL             $12960.00 USD

╭─────────────── Procurement Decision ──────────────────╮
│ ✅ APPROVED                                            │
│ PO total of 12960.00 is within the IT department's    │
│ per-order limit of 20000.00.                           │
│ Approved by: CTO                                       │
│ Budget limit: $20000.00 | PO total: $12960.00          │
│ Remaining: $7040.00                                    │
│ ⚠️  Dual Approval Required                             │
╰─────────────────────────────────────────────────────────╯

📁 Full execution log saved to: logs/execution.log
```

---

## Running Tests

```bash
# All tests with coverage report
pytest tests/ -v --cov=. --cov-report=term-missing

# Unit tests only (tools)
pytest tests/test_tools.py -v

# Agent behavior tests
pytest tests/test_agents.py -v

# End-to-end tests
pytest tests/test_e2e.py -v
```

> **Note**: Tests mock `query_llm` calls — **Ollama is not required to run tests**.

---

## Design Decisions

| Decision | Rationale |
|---|---|
| **LangGraph** for orchestration | Native stateful graph execution, conditional edges, streaming |
| **TypedDict state** | LangGraph-native; clean serialisation without runtime overhead |
| **Pydantic for tool I/O** | Validates LLM output, normalises data, provides clear error messages |
| **Tools as pure functions** | Independently testable; no coupling between agents |
| **Algorithmic supplier ranking** | LLM cannot reliably do math; scoring is deterministic |
| **LLM for explanation only** | Keeps the system auditable; LLM adds value without controlling decisions |
| **Structured JSON prompting** | Forces deterministic output shape; prevents hallucination |
| **Error short-circuit edges** | Prevents cascading failures; each agent checks for upstream errors |
| **Rotating log handler** | Prevents unbounded disk growth in production |

---

## Enhancements Beyond Requirements

1. **Composite supplier scoring** — 4-dimension min-max normalised scoring (not just basic filtering)
2. **LLM retry with back-off** — 3 retries, exponential back-off, 3-strategy JSON extraction fallback
3. **Dual approval flagging** — automatically detects orders requiring secondary sign-off
4. **Rich CLI output** — colour-coded tables, panels, agent trace, and verbose mode
5. **Conditional error edges** — graph short-circuits on any agent failure without crashing
6. **Configurable via env vars** — zero hardcoded values; all settings overridable
7. **Rotating file handler** — log files capped at 5 MB × 3 backups
8. **Soft budget/stock filter** — fallback logic prevents empty supplier results
9. **Pydantic input validation** — all tool inputs validated before LLM or file I/O
10. **15 suppliers across 8 categories** — realistic sample catalogue for demo variety

---

## Contributing

1. Fork the repo and create a feature branch from `dev`
2. Write tests for any new functionality
3. Ensure `pytest tests/ -v` passes before opening a PR
4. Follow the existing module docstring and type-hint conventions

---

## License

MIT License — see [LICENSE](LICENSE) for details.