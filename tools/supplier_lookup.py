"""
supplier_lookup_tool — Supplier Intelligence Tool

Searches the local supplier catalogue (data/suppliers.json) for suppliers that
carry the requested item, scores them using a configurable weighted composite
formula, and returns the top N candidates sorted by score descending.

Scoring formula (weights from config):
  score = (normalised_rating   × RATING_WEIGHT)
        + (price_competitiveness × PRICE_WEIGHT)
        + (stock_availability   × STOCK_WEIGHT)
        + (lead_time_score      × LEAD_TIME_WEIGHT)

Each component is normalised to [0, 1] relative to the candidate set, so
the formula always produces a fair comparison regardless of absolute values.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import (
    SUPPLIERS_FILE,
    MAX_SUPPLIER_CANDIDATES,
    SUPPLIER_WEIGHT_RATING,
    SUPPLIER_WEIGHT_PRICE,
    SUPPLIER_WEIGHT_STOCK,
    SUPPLIER_WEIGHT_LEAD_TIME,
)
from src.logger import get_logger

logger = get_logger("tools.supplier_lookup")


def _load_suppliers(suppliers_file: Path = SUPPLIERS_FILE) -> list[dict[str, Any]]:
    """Load and return the supplier catalogue from disk."""
    if not suppliers_file.exists():
        raise FileNotFoundError(f"Supplier file not found: {suppliers_file}")
    with suppliers_file.open(encoding="utf-8") as fh:
        return json.load(fh)


def _normalise(values: list[float], invert: bool = False) -> list[float]:
    """
    Min-max normalise a list of floats to [0, 1].

    Args:
        values: Raw numeric values.
        invert: If True, the highest raw value maps to 0 (used for metrics
                where lower is better, e.g. unit price, lead time).

    Returns:
        Normalised list of the same length.
    """
    if not values:
        return values
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.5] * len(values)  # All equal — neutral score
    normalised = [(v - lo) / (hi - lo) for v in values]
    return [1 - n for n in normalised] if invert else normalised


def _score_suppliers(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Compute and attach a composite_score to each supplier candidate.

    Args:
        candidates: List of supplier dicts that match the requested item.

    Returns:
        Same list with 'composite_score' field added, sorted descending.
    """
    if not candidates:
        return candidates

    ratings = [c.get("rating", 0.0) for c in candidates]
    prices = [c.get("unit_price", float("inf")) for c in candidates]
    stocks = [c.get("stock", 0) for c in candidates]
    leads = [c.get("lead_time_days", 999) for c in candidates]

    norm_ratings = _normalise(ratings)
    norm_prices = _normalise(prices, invert=True)   # Lower price → higher score
    norm_stocks = _normalise(stocks)
    norm_leads = _normalise(leads, invert=True)      # Shorter lead → higher score

    for i, supplier in enumerate(candidates):
        supplier["composite_score"] = round(
            norm_ratings[i] * SUPPLIER_WEIGHT_RATING
            + norm_prices[i] * SUPPLIER_WEIGHT_PRICE
            + norm_stocks[i] * SUPPLIER_WEIGHT_STOCK
            + norm_leads[i] * SUPPLIER_WEIGHT_LEAD_TIME,
            4,
        )

    return sorted(candidates, key=lambda s: s["composite_score"], reverse=True)


def supplier_lookup_tool(
    item: str,
    quantity: int,
    budget_per_unit: float | None = None,
    suppliers_file: Path = SUPPLIERS_FILE,
    max_results: int = MAX_SUPPLIER_CANDIDATES,
) -> dict[str, Any]:
    """
    Find and rank suppliers for the requested item from the local catalogue.

    The tool performs:
      1. Case-insensitive exact + partial item name matching.
      2. Stock sufficiency filtering (stock >= quantity).
      3. Optional budget-per-unit ceiling filtering.
      4. Weighted composite scoring and top-N selection.

    Args:
        item:            The item to procure (e.g. "laptop"). Case-insensitive.
        quantity:        Number of units needed (used for stock check).
        budget_per_unit: Optional price ceiling per unit. Suppliers above this
                         are excluded unless no suppliers remain.
        suppliers_file:  Path to the JSON catalogue (injectable for testing).
        max_results:     Maximum number of ranked suppliers to return.

    Returns:
        {
          "suppliers": [<ranked supplier dicts>],
          "total_found": <int>,
          "item_searched": <str>,
          "quantity_requested": <int>
        }
        Or on error:
        {"error": "<reason>", "item": "<str>", "quantity": <int>}
    """
    logger.info(
        "supplier_lookup_tool | item=%s qty=%d budget_unit=%s",
        item,
        quantity,
        budget_per_unit,
    )

    if not item or not item.strip():
        return {"error": "Item name cannot be empty", "item": item, "quantity": quantity}
    if quantity < 1:
        return {"error": "Quantity must be at least 1", "item": item, "quantity": quantity}

    try:
        all_suppliers = _load_suppliers(suppliers_file)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.error("supplier_lookup_tool | Failed to load catalogue: %s", exc)
        return {"error": str(exc), "item": item, "quantity": quantity}

    item_lower = item.lower().strip()

    # ── Step 1: Item matching (exact or partial) ──────────────────────────────
    matches = [
        s for s in all_suppliers
        if item_lower in s.get("item", "").lower()
        or s.get("item", "").lower() in item_lower
    ]

    if not matches:
        logger.warning("supplier_lookup_tool | No suppliers found for item='%s'", item)
        return {
            "suppliers": [],
            "total_found": 0,
            "item_searched": item,
            "quantity_requested": quantity,
        }

    # ── Step 2: Stock availability filter ────────────────────────────────────
    in_stock = [s for s in matches if s.get("stock", 0) >= quantity]
    if not in_stock:
        logger.warning(
            "supplier_lookup_tool | No suppliers with sufficient stock (%d units)", quantity
        )
        in_stock = matches  # Fallback: include all even if under-stocked

    # ── Step 3: Budget ceiling filter (soft — fallback to all if too strict) ──
    if budget_per_unit and budget_per_unit > 0:
        affordable = [s for s in in_stock if s.get("unit_price", 0) <= budget_per_unit]
        if affordable:
            in_stock = affordable
        else:
            logger.warning(
                "supplier_lookup_tool | No suppliers within budget %.2f/unit; "
                "including all as fallback.",
                budget_per_unit,
            )

    # ── Step 4: Score and rank ────────────────────────────────────────────────
    ranked = _score_suppliers(in_stock)
    top_n = ranked[:max_results]

    logger.info(
        "supplier_lookup_tool | found=%d ranked=%d returning=%d",
        len(matches),
        len(ranked),
        len(top_n),
    )

    return {
        "suppliers": top_n,
        "total_found": len(matches),
        "item_searched": item,
        "quantity_requested": quantity,
    }
