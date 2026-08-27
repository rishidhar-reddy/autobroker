"""SQLite-backed persistence for negotiations and payment intents.

Both used to live in module-level dicts, which meant every negotiation was lost
on restart and a second uvicorn worker saw none of the first worker's state --
so `GET /negotiations/{id}` would 404 at random behind any real deployment.

SQLite keeps the dependency footprint at stdlib while giving durability and a
single shared view across workers on one host. The state itself is stored as a
JSON blob: it is a document, it is always read whole, and nothing queries inside
it except the aggregate stats, which are cheap at this scale.

Set NEGOTIATION_DB to relocate the file, or to ":memory:" for ephemeral runs.
"""

import json
import os
import sqlite3
import threading
from typing import Any, Optional

_DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "negotiations.db")
_DB_PATH = os.getenv("NEGOTIATION_DB", _DEFAULT_DB)

# FastAPI runs sync endpoints and BackgroundTasks on a threadpool, so the
# connection is shared across threads and every write is serialised behind this
# lock. check_same_thread=False is safe only in combination with it.
_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS negotiations (
    transaction_id TEXT PRIMARY KEY,
    product_id     TEXT,
    status         TEXT NOT NULL,
    turn           INTEGER NOT NULL DEFAULT 0,
    state          TEXT NOT NULL,
    created_at     REAL NOT NULL DEFAULT (strftime('%s','now')),
    updated_at     REAL NOT NULL DEFAULT (strftime('%s','now'))
);
CREATE INDEX IF NOT EXISTS idx_negotiations_status ON negotiations(status);

CREATE TABLE IF NOT EXISTS payment_intents (
    payment_intent_id TEXT PRIMARY KEY,
    transaction_id    TEXT,
    payload           TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        # WAL lets readers proceed during a write; harmless for :memory:.
        try:
            _conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError:
            pass
        _conn.executescript(_SCHEMA)
        _conn.commit()
    return _conn


# ── negotiations ──────────────────────────────────────────────────────────────

def save_negotiation(state: dict[str, Any]) -> None:
    """Insert or update a negotiation by transaction_id."""
    transaction_id = state["transaction_id"]
    product_id = (state.get("vendor_config") or {}).get("Product_ID")
    with _lock:
        conn = _connect()
        conn.execute(
            """
            INSERT INTO negotiations (transaction_id, product_id, status, turn, state)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(transaction_id) DO UPDATE SET
                status     = excluded.status,
                turn       = excluded.turn,
                state      = excluded.state,
                updated_at = strftime('%s','now')
            """,
            (
                transaction_id,
                product_id,
                state.get("status", "NEGOTIATING"),
                int(state.get("turn", 0)),
                json.dumps(state),
            ),
        )
        conn.commit()


def get_negotiation(transaction_id: str) -> Optional[dict[str, Any]]:
    with _lock:
        row = _connect().execute(
            "SELECT state FROM negotiations WHERE transaction_id = ?", (transaction_id,)
        ).fetchone()
    return json.loads(row["state"]) if row else None


def list_negotiations(limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    """Most recently updated first."""
    with _lock:
        rows = _connect().execute(
            """
            SELECT transaction_id, product_id, status, turn, created_at, updated_at
            FROM negotiations ORDER BY updated_at DESC LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    return [dict(row) for row in rows]


def count_negotiations() -> int:
    with _lock:
        return _connect().execute("SELECT COUNT(*) AS n FROM negotiations").fetchone()["n"]


# ── payment intents ───────────────────────────────────────────────────────────

def save_payment_intent(payment_intent: dict[str, Any]) -> None:
    with _lock:
        conn = _connect()
        conn.execute(
            """
            INSERT INTO payment_intents (payment_intent_id, transaction_id, payload)
            VALUES (?, ?, ?)
            ON CONFLICT(payment_intent_id) DO UPDATE SET payload = excluded.payload
            """,
            (
                payment_intent["id"],
                (payment_intent.get("metadata") or {}).get("transaction_id"),
                json.dumps(payment_intent),
            ),
        )
        conn.commit()


def get_payment_intent(payment_intent_id: str) -> Optional[dict[str, Any]]:
    with _lock:
        row = _connect().execute(
            "SELECT payload FROM payment_intents WHERE payment_intent_id = ?",
            (payment_intent_id,),
        ).fetchone()
    return json.loads(row["payload"]) if row else None


# ── test / maintenance helpers ────────────────────────────────────────────────

def reset() -> None:
    """Drop all rows. Used by tests; never called by the application."""
    with _lock:
        conn = _connect()
        conn.execute("DELETE FROM negotiations")
        conn.execute("DELETE FROM payment_intents")
        conn.commit()
