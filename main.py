#!/usr/bin/env python3
"""
Multi-Agent Procurement Management System — CLI Entry Point

Usage:
    python main.py --request "Need 10 laptops for IT with budget 15000"
    python main.py --request "Order 5 office chairs for HR" --model phi3
    python main.py --request "20 monitors for Engineering team" --verbose

Features:
    - Full agent trace with rich terminal formatting
    - Configurable Ollama model via --model flag
    - Verbose mode exposes raw state output
    - All execution logged to logs/execution.log
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure the project root is in PYTHONPATH regardless of where main.py is called from
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from src.graph import run_procurement_workflow
from src.logger import get_logger

logger = get_logger("main")
console = Console()

# ─── ASCII Banner ──────────────────────────────────────────────────────────────

BANNER = """
[bold cyan]╔══════════════════════════════════════════════════════════╗[/bold cyan]
[bold cyan]║      MULTI-AGENT PROCUREMENT MANAGEMENT SYSTEM           ║[/bold cyan]
[bold cyan]║      CWD Model  ·  Powered by LangGraph + Ollama         ║[/bold cyan]
[bold cyan]╚══════════════════════════════════════════════════════════╝[/bold cyan]
"""

# ─── Agent icons for display ──────────────────────────────────────────────────

AGENT_ICONS = {
    "CoordinatorAgent":          "🎯",
    "RequestAnalyzerAgent":      "🔍",
    "SupplierIntelligenceAgent": "🏭",
    "ProcurementGeneratorAgent": "📄",
    "ApprovalAgent":             "✅",
}


# ─── CLI Argument Parsing ─────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="procurement-mas",
        description="Multi-Agent Procurement Automation System (local, Ollama-powered)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --request "Need 10 laptops for IT with budget 15000"
  python main.py --request "5 office chairs for HR department" --model phi3
  python main.py --request "20 monitors for Engineering" --verbose
        """,
    )
    parser.add_argument(
        "--request", "-r",
        type=str,
        required=True,
        help="Natural-language procurement request (e.g. 'Need 10 laptops for IT')",
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default=None,
        help="Ollama model to use (default: from config/OLLAMA_MODEL env var)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print the full raw state dict after workflow completes",
    )
    return parser.parse_args()


# ─── Rich Output Helpers ───────────────────────────────────────────────────────

def print_banner() -> None:
    console.print(BANNER)


def print_agent_log(logs: list[dict]) -> None:
    """Render the agent execution trace as a rich table."""
    console.print("\n[bold white]📋 Agent Execution Trace[/bold white]")
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
        border_style="dim",
        show_lines=True,
        expand=True,
    )
    table.add_column("Agent", style="cyan", min_width=28)
    table.add_column("Event", style="yellow", min_width=20)
    table.add_column("Message", style="white")

    for entry in logs:
        agent_name = entry.get("agent", "Unknown")
        icon = AGENT_ICONS.get(agent_name, "🤖")
        table.add_row(
            f"{icon} {agent_name}",
            entry.get("event", ""),
            entry.get("message", ""),
        )
    console.print(table)


def print_parsed_request(parsed: dict) -> None:
    """Display the structured request extracted by the Analyzer agent."""
    console.print("\n[bold white]🔍 Parsed Request[/bold white]")
    table = Table(box=box.SIMPLE, show_header=False, border_style="dim")
    table.add_column("Field", style="cyan", min_width=22)
    table.add_column("Value", style="white")
    for key, val in parsed.items():
        table.add_row(key.replace("_", " ").title(), str(val))
    console.print(table)


def print_supplier_selection(selected: dict, options: list[dict]) -> None:
    """Display the selected supplier and the candidate comparison table."""
    console.print("\n[bold white]🏭 Supplier Selection[/bold white]")

    if options:
        table = Table(
            box=box.ROUNDED,
            show_header=True,
            header_style="bold blue",
            border_style="dim",
        )
        table.add_column("Rank", style="dim", justify="center")
        table.add_column("Supplier", style="cyan")
        table.add_column("Price/Unit", style="yellow", justify="right")
        table.add_column("Rating", justify="center")
        table.add_column("Stock", justify="center")
        table.add_column("Lead (days)", justify="center")
        table.add_column("Score", style="green", justify="right")

        for i, s in enumerate(options, 1):
            rank_str = f"[bold green]★ {i}[/bold green]" if i == 1 else str(i)
            table.add_row(
                rank_str,
                s.get("supplier_name", ""),
                f"${s.get('unit_price', 0):.2f}",
                str(s.get("rating", "")),
                str(s.get("stock", "")),
                str(s.get("lead_time_days", "")),
                f"{s.get('composite_score', 0):.4f}",
            )
        console.print(table)

    justification = selected.get("selection_justification", "")
    if justification:
        console.print(
            Panel(
                f"[italic]{justification}[/italic]",
                title="[bold]Selection Rationale[/bold]",
                border_style="green",
            )
        )


def print_purchase_order(po: dict) -> None:
    """Display the generated Purchase Order."""
    console.print("\n[bold white]📄 Purchase Order[/bold white]")
    table = Table(box=box.SIMPLE, show_header=False, border_style="dim")
    table.add_column("Field", style="cyan", min_width=25)
    table.add_column("Value", style="white")

    fields = [
        ("PO Number",          po.get("po_number", "")),
        ("Issue Date",         po.get("issue_date", "")),
        ("Supplier",           po.get("supplier_name", "")),
        ("Department",         po.get("requester_department", "")),
        ("Payment Terms",      po.get("payment_terms", "")),
        ("Expected Delivery",  po.get("expected_delivery_date", "")),
        ("Subtotal",           f"${po.get('subtotal', 0):.2f}"),
        ("Tax",                f"${po.get('tax_amount', 0):.2f} ({po.get('tax_rate', 0)*100:.0f}%)"),
        ("TOTAL",              f"[bold green]${po.get('total', 0):.2f} {po.get('currency', 'USD')}[/bold green]"),
    ]
    for field, value in fields:
        table.add_row(field, value)
    console.print(table)


def print_approval(approval: dict) -> None:
    """Display the final approval decision."""
    approved = approval.get("approved", False)
    status_color = "green" if approved else "red"
    status_icon = "✅ APPROVED" if approved else "❌ REJECTED"

    console.print(f"\n[bold white]🏛️  Approval Decision[/bold white]")
    console.print(
        Panel(
            f"[bold {status_color}]{status_icon}[/bold {status_color}]\n\n"
            f"[white]{approval.get('reason', '')}[/white]\n\n"
            f"[dim]Approved by: {approval.get('approved_by', 'N/A')}[/dim]\n"
            f"[dim]Budget limit: ${approval.get('department_budget_limit', 0):.2f}  |  "
            f"PO total: ${approval.get('po_total', 0):.2f}  |  "
            f"Remaining: ${approval.get('remaining_budget', 0):.2f}[/dim]\n"
            + (
                f"\n[bold yellow]⚠️  Dual Approval Required[/bold yellow]"
                if approval.get("requires_dual_approval") else ""
            ),
            title=f"[bold {status_color}]Procurement Decision[/bold {status_color}]",
            border_style=status_color,
        )
    )

    notice = approval.get("formal_notice", "")
    if notice:
        console.print(
            Panel(
                f"[italic]{notice}[/italic]",
                title="[bold]Formal Notice[/bold]",
                border_style="dim",
            )
        )

    action = approval.get("action_required", "")
    if action:
        console.print(f"\n[bold yellow]→ Action Required:[/bold yellow] {action}")


# ─── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    """Run the procurement MAS workflow from CLI."""
    args = parse_args()

    # Override model via CLI flag
    if args.model:
        os.environ["OLLAMA_MODEL"] = args.model

    print_banner()
    console.print(
        Panel(
            f"[bold white]{args.request}[/bold white]",
            title="[bold cyan]📥 Procurement Request[/bold cyan]",
            border_style="cyan",
        )
    )

    # ── Run the multi-agent workflow ──────────────────────────────────────────
    console.print("\n[dim]🚀 Initiating multi-agent workflow...[/dim]\n")
    logger.info("CLI invocation | request='%s'", args.request)

    try:
        with console.status("[bold cyan]Agents processing...[/bold cyan]", spinner="dots"):
            final_state = run_procurement_workflow(args.request)
    except KeyboardInterrupt:
        console.print("\n[bold red]Workflow interrupted by user.[/bold red]")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        console.print(f"\n[bold red]Workflow failed: {exc}[/bold red]")
        logger.exception("Unhandled workflow error: %s", exc)
        sys.exit(1)

    # ── Check for workflow-level error ────────────────────────────────────────
    if final_state.get("error"):
        console.print(
            Panel(
                f"[bold red]{final_state['error']}[/bold red]",
                title="[bold red]❌ Workflow Error[/bold red]",
                border_style="red",
            )
        )
        sys.exit(1)

    # ── Render agent trace ────────────────────────────────────────────────────
    logs = final_state.get("logs", [])
    if logs:
        print_agent_log(logs)

    # ── Render structured outputs ─────────────────────────────────────────────
    if final_state.get("parsed_request"):
        print_parsed_request(final_state["parsed_request"])

    if final_state.get("selected_supplier"):
        print_supplier_selection(
            final_state["selected_supplier"],
            final_state.get("supplier_options", []),
        )

    if final_state.get("purchase_order"):
        print_purchase_order(final_state["purchase_order"])

    if final_state.get("approval_status"):
        print_approval(final_state["approval_status"])

    # ── Verbose dump ──────────────────────────────────────────────────────────
    if args.verbose:
        console.print("\n[bold dim]── Raw State (verbose) ──[/bold dim]")
        console.print_json(json.dumps(final_state, indent=2, default=str))

    console.print(
        f"\n[dim]📁 Full execution log saved to: logs/execution.log[/dim]"
    )


if __name__ == "__main__":
    main()
