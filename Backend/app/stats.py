"""Aggregate negotiation metrics.

telemetry.py already writes every message and tool call to ClickHouse, but
nothing ever read it back, so the data was write-only and the UI had no way to
show how negotiations were actually going. These aggregates are computed from
the persisted negotiations in app.store, which needs no ClickHouse to be
running and is accurate for the single-host deployment this service targets.
"""

from typing import Any

from app import store

_TERMINAL = {"FULFILLED", "TERMINATED"}


def _agreed_total(state: dict[str, Any]) -> float | None:
    invoice = state.get("invoice") or {}
    total = invoice.get("total_amount")
    return float(total) if isinstance(total, (int, float)) else None


def summary() -> dict[str, Any]:
    """Counts, convergence rate, and price/turn averages across all runs."""
    rows = store.list_negotiations(limit=10_000)
    total = len(rows)

    by_status: dict[str, int] = {}
    for row in rows:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1

    settled = by_status.get("FULFILLED", 0)
    finished = sum(count for status, count in by_status.items() if status in _TERMINAL)

    turns: list[int] = []
    totals: list[float] = []
    unit_prices: list[float] = []

    for row in rows:
        state = store.get_negotiation(row["transaction_id"])
        if not state:
            continue
        if state.get("status") == "FULFILLED":
            turns.append(int(state.get("turn", 0)))
            amount = _agreed_total(state)
            if amount is not None:
                totals.append(amount)
            price = state.get("current_price")
            if isinstance(price, (int, float)):
                unit_prices.append(float(price))

    def mean(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 4) if values else None

    return {
        "total_negotiations": total,
        "by_status": by_status,
        # Share of *finished* negotiations that closed a deal. Runs still in
        # flight are excluded so the rate is not diluted by pending work.
        "convergence_rate": round(settled / finished, 4) if finished else None,
        "settled": settled,
        "finished": finished,
        "in_flight": total - finished,
        "avg_turns_to_settle": mean([float(t) for t in turns]),
        "avg_agreed_unit_price": mean(unit_prices),
        "avg_deal_value": mean(totals),
        "total_settled_value": round(sum(totals), 2) if totals else 0.0,
    }


def recent(limit: int = 20) -> list[dict[str, Any]]:
    return store.list_negotiations(limit=limit)
