"""
Customer / account / loan repository.

Modes (BANK_CUSTOMER_STORE):
  json     — current demo file data/demo_accounts.json (default, no break)
  sqlite   — local production-shaped DB at data/customer_banking.db
  postgres — BANK_CUSTOMER_DB_URL (optional; falls back to json if unavailable)

Balance lookup always goes through get_account_balance() so the API surface stays stable.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEMO_PATH = _PROJECT_ROOT / "data" / "demo_accounts.json"
_SCHEMA_PATH = Path(__file__).with_name("customer_schema.sql")
_DEFAULT_SQLITE = _PROJECT_ROOT / "data" / "customer_banking.db"

_demo_cache: dict[str, dict] | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def store_mode() -> str:
    mode = os.environ.get("BANK_CUSTOMER_STORE", "json").strip().lower()
    if mode in {"sqlite", "postgres", "postgresql", "pg"}:
        return "postgres" if mode in {"postgres", "postgresql", "pg"} else "sqlite"
    return "json"


def _sqlite_path() -> Path:
    raw = os.environ.get("BANK_CUSTOMER_DB_PATH", "").strip()
    if raw:
        path = Path(raw)
        return path if path.is_absolute() else _PROJECT_ROOT / path
    return _DEFAULT_SQLITE


def _load_demo() -> dict[str, dict]:
    global _demo_cache
    if _demo_cache is None:
        with open(_DEMO_PATH, encoding="utf-8") as handle:
            _demo_cache = json.load(handle)
    return _demo_cache


def _connect_sqlite() -> sqlite3.Connection:
    path = _sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_customer_db() -> str:
    """Create schema for sqlite mode. Returns active mode."""
    mode = store_mode()
    if mode != "sqlite":
        return mode
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    with _connect_sqlite() as conn:
        conn.executescript(schema)
        conn.commit()
    return mode


def seed_from_demo(*, force: bool = False) -> dict[str, int]:
    """
    Seed customers/accounts/balances from demo_accounts.json into sqlite store.
    Safe to call repeatedly: without force=True, only demo accounts missing from
    the DB are inserted (existing rows and balances are left untouched), so
    accounts added to demo_accounts.json later still reach an existing DB.
    """
    init_customer_db()
    if store_mode() != "sqlite":
        return {"customers": 0, "accounts": 0, "skipped": 1}

    demo = _load_demo()
    with _connect_sqlite() as conn:
        if force:
            conn.execute("DELETE FROM balance_audit")
            conn.execute("DELETE FROM account_balances")
            conn.execute("DELETE FROM loans")
            conn.execute("DELETE FROM accounts")
            conn.execute("DELETE FROM customers")
            present: set[str] = set()
        else:
            present = {
                r["account_number"]
                for r in conn.execute("SELECT account_number FROM accounts")
            }

        pending = {num: row for num, row in demo.items() if num not in present}
        if not pending:
            return {"customers": 0, "accounts": len(present), "skipped": 1}

        customers = 0
        accounts = 0
        for account_number, row in pending.items():
            customer_id = str(uuid.uuid4())
            account_id = str(uuid.uuid4())
            created = _now()
            conn.execute(
                """
                INSERT INTO customers (id, full_name, full_name_kn, mobile, status, created_at)
                VALUES (?, ?, ?, ?, 'active', ?)
                """,
                (
                    customer_id,
                    row.get("holder_name") or "",
                    row.get("holder_name_kn") or "",
                    (str(row.get("mobile") or "").strip() or None),
                    created,
                ),
            )
            customers += 1
            conn.execute(
                """
                INSERT INTO accounts (
                    id, customer_id, account_number, account_type, status, created_at
                ) VALUES (?, ?, ?, ?, 'active', ?)
                """,
                (
                    account_id,
                    customer_id,
                    account_number,
                    row.get("account_type") or "Savings",
                    created,
                ),
            )
            accounts += 1
            conn.execute(
                """
                INSERT INTO account_balances (account_id, available_inr, updated_at)
                VALUES (?, ?, ?)
                """,
                (account_id, float(row.get("balance_inr") or 0), created),
            )
            # Sample linked loan for the first demo savings account only.
            if account_number == "1234567890":
                conn.execute(
                    """
                    INSERT INTO loans (
                        id, customer_id, loan_type, principal_inr, outstanding_inr,
                        status, created_at
                    ) VALUES (?, ?, ?, ?, ?, 'active', ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        customer_id,
                        "personal",
                        200000.0,
                        125000.0,
                        created,
                    ),
                )
        conn.commit()
    return {"customers": customers, "accounts": accounts, "skipped": 0}


def _record_from_demo(account_number: str) -> dict[str, Any] | None:
    row = _load_demo().get(account_number)
    if not row:
        return None
    return {
        "account_number": account_number,
        "holder_name": row.get("holder_name") or "",
        "holder_name_kn": row.get("holder_name_kn") or row.get("holder_name") or "",
        "account_type": row.get("account_type") or "Savings",
        "balance_inr": float(row.get("balance_inr") or 0),
        "customer_id": None,
        "source": "json",
    }


def _record_from_sqlite(account_number: str) -> dict[str, Any] | None:
    init_customer_db()
    # Auto-seed empty DB so first sqlite boot still works (separate connection).
    with _connect_sqlite() as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM accounts").fetchone()["n"]
    if count == 0:
        seed_from_demo()
    with _connect_sqlite() as conn:
        row = conn.execute(
            """
            SELECT
                a.account_number AS account_number,
                a.account_type AS account_type,
                a.customer_id AS customer_id,
                c.full_name AS holder_name,
                c.full_name_kn AS holder_name_kn,
                b.available_inr AS balance_inr
            FROM accounts a
            JOIN customers c ON c.id = a.customer_id
            JOIN account_balances b ON b.account_id = a.id
            WHERE a.account_number = ?
              AND a.status = 'active'
              AND c.status = 'active'
            """,
            (account_number,),
        ).fetchone()
        if not row:
            return None
        return {
            "account_number": row["account_number"],
            "holder_name": row["holder_name"],
            "holder_name_kn": row["holder_name_kn"] or row["holder_name"],
            "account_type": row["account_type"],
            "balance_inr": float(row["balance_inr"]),
            "customer_id": row["customer_id"],
            "source": "sqlite",
        }


def get_account_balance(account_number: str) -> dict[str, Any] | None:
    """Return normalized account+balance record or None if not found."""
    acct = "".join(ch for ch in (account_number or "") if ch.isdigit())
    if not acct:
        return None
    mode = store_mode()
    if mode == "sqlite":
        try:
            return _record_from_sqlite(acct)
        except Exception as exc:
            print(f"[customers] sqlite lookup failed, falling back to json: {exc}", flush=True)
            return _record_from_demo(acct)
    if mode == "postgres":
        # Postgres driver optional — fall back safely so demos never break.
        print(
            "[customers] postgres mode requested but driver/wiring uses json fallback "
            "until BANK_CUSTOMER_DB_URL adapter is provisioned",
            flush=True,
        )
        return _record_from_demo(acct)
    return _record_from_demo(acct)


def get_account_by_last4(last4: str) -> list[dict[str, Any]]:
    """
    Find accounts whose account_number ends with the given 4 digits.
    Returns a list — empty = not found, 1 = unique match, 2+ = ambiguous.
    """
    digits = re.sub(r"\D", "", last4 or "")
    if len(digits) != 4:
        return []
    mode = store_mode()
    if mode == "sqlite":
        try:
            init_customer_db()
            with _connect_sqlite() as conn:
                count = conn.execute("SELECT COUNT(*) AS n FROM accounts").fetchone()["n"]
            if count == 0:
                seed_from_demo()
            with _connect_sqlite() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        a.account_number, a.account_type, a.customer_id,
                        c.full_name AS holder_name,
                        c.full_name_kn AS holder_name_kn,
                        b.available_inr AS balance_inr
                    FROM accounts a
                    JOIN customers c ON c.id = a.customer_id
                    JOIN account_balances b ON b.account_id = a.id
                    WHERE a.account_number LIKE ? AND a.status = 'active' AND c.status = 'active'
                    """,
                    (f"%{digits}",),
                ).fetchall()
            return [
                {
                    "account_number": r["account_number"],
                    "holder_name": r["holder_name"],
                    "holder_name_kn": r["holder_name_kn"] or r["holder_name"],
                    "account_type": r["account_type"],
                    "balance_inr": float(r["balance_inr"]),
                    "customer_id": r["customer_id"],
                    "source": "sqlite",
                }
                for r in rows
            ]
        except Exception as exc:
            print(f"[customers] last4 sqlite lookup failed: {exc}", flush=True)

    # JSON fallback
    demo = _load_demo()
    return [
        {
            "account_number": acct,
            "holder_name": row.get("holder_name") or "",
            "holder_name_kn": row.get("holder_name_kn") or row.get("holder_name") or "",
            "account_type": row.get("account_type") or "Savings",
            "balance_inr": float(row.get("balance_inr") or 0),
            "customer_id": None,
            "source": "json",
        }
        for acct, row in demo.items()
        if acct.endswith(digits)
    ]


def list_customer_loans(customer_id: str) -> list[dict[str, Any]]:
    if store_mode() != "sqlite" or not customer_id:
        return []
    init_customer_db()
    with _connect_sqlite() as conn:
        rows = conn.execute(
            """
            SELECT id, loan_type, principal_inr, outstanding_inr, status, created_at
            FROM loans
            WHERE customer_id = ? AND status = 'active'
            ORDER BY created_at DESC
            """,
            (customer_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def write_balance_audit(
    *,
    account_number: str,
    found: bool,
    customer_id: str | None = None,
    kiosk_session_id: str = "",
    source: str = "",
) -> None:
    """Best-effort audit trail (sqlite mode only)."""
    if store_mode() != "sqlite":
        return
    try:
        init_customer_db()
        with _connect_sqlite() as conn:
            conn.execute(
                """
                INSERT INTO balance_audit (
                    account_number, customer_id, found, source, kiosk_session_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    account_number,
                    customer_id,
                    1 if found else 0,
                    source or store_mode(),
                    kiosk_session_id or "",
                    _now(),
                ),
            )
            conn.commit()
    except Exception as exc:
        print(f"[customers] audit write skipped: {exc}", flush=True)


def list_customers(*, limit: int = 100) -> list[dict[str, Any]]:
    """Admin-facing customer + account + balance rows."""
    limit = max(1, min(int(limit), 500))
    mode = store_mode()
    if mode == "sqlite":
        try:
            init_customer_db()
            with _connect_sqlite() as conn:
                count = conn.execute("SELECT COUNT(*) AS n FROM accounts").fetchone()["n"]
                if count == 0:
                    seed_from_demo()
                rows = conn.execute(
                    """
                    SELECT
                        c.id AS customer_id,
                        c.full_name AS holder_name,
                        c.full_name_kn AS holder_name_kn,
                        c.mobile AS mobile,
                        c.status AS customer_status,
                        a.account_number AS account_number,
                        a.account_type AS account_type,
                        a.status AS account_status,
                        b.available_inr AS balance_inr,
                        b.updated_at AS balance_updated_at
                    FROM accounts a
                    JOIN customers c ON c.id = a.customer_id
                    JOIN account_balances b ON b.account_id = a.id
                    ORDER BY a.account_number
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            out = []
            for row in rows:
                item = dict(row)
                item["source"] = "sqlite"
                item["loans"] = list_customer_loans(item["customer_id"])
                out.append(item)
            return out
        except Exception as exc:
            print(f"[customers] list sqlite failed, falling back to json: {exc}", flush=True)

    demo = _load_demo()
    items: list[dict[str, Any]] = []
    for account_number, row in list(demo.items())[:limit]:
        items.append(
            {
                "customer_id": None,
                "holder_name": row.get("holder_name") or "",
                "holder_name_kn": row.get("holder_name_kn") or "",
                "mobile": row.get("mobile"),
                "customer_status": "active",
                "account_number": account_number,
                "account_type": row.get("account_type") or "Savings",
                "account_status": "active",
                "balance_inr": float(row.get("balance_inr") or 0),
                "balance_updated_at": None,
                "source": "json",
                "loans": [],
            }
        )
    return items


def list_balance_audit(*, limit: int = 50) -> list[dict[str, Any]]:
    """Recent balance lookup attempts (sqlite audit table)."""
    if store_mode() != "sqlite":
        return []
    limit = max(1, min(int(limit), 200))
    try:
        init_customer_db()
        with _connect_sqlite() as conn:
            rows = conn.execute(
                """
                SELECT
                    id, account_number, customer_id, found, source,
                    kiosk_session_id, created_at
                FROM balance_audit
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:
        print(f"[customers] audit list skipped: {exc}", flush=True)
        return []
