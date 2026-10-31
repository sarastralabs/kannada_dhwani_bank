"""Demo money: deposits, withdrawals, transfers, loans, fixed deposits and service requests.

Everything here is simulated bank data held in MongoDB (``BANK_CUSTOMER_STORE=mongo``):

    accounts        balance_inr is the live balance
    transactions    one row per movement (the ledger / audit trail)
    loans           principal, rate, tenure, EMI, outstanding
    loan_payments   each repayment, split into interest and principal
    deposits        fixed deposits
    service_requests  cheque books, ATM cards, stopped cheques

Balances only change through ``credit`` and ``debit``, which are single atomic updates, so two
approvals can never overdraw an account.
"""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.db import customers

DEFAULT_LOAN_RATE = 10.5  # % per year
DEFAULT_LOAN_MONTHS = 36
DEFAULT_FD_RATE = 6.5
DEFAULT_FD_MONTHS = 12


class LedgerError(ValueError):
    """A money operation cannot be done (unknown account, not enough balance, bad amount…)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _db():
    db = customers._mongo()  # noqa: SLF001
    if db is None or customers.store_mode() != "mongo":
        raise LedgerError("Money movements need the MongoDB customer store (BANK_CUSTOMER_STORE=mongo).")
    return db


def money(value: Any) -> float:
    """Parse a form amount ("5,000", "5000.50", "₹ 5000", "೫೦೦೦") into rupees; must be positive.

    Anything that is not a plain number (a minus sign, two dots, words) is refused rather than guessed at.
    """
    text = str(value or "").translate(str.maketrans("೦೧೨೩೪೫೬೭೮೯", "0123456789"))
    text = re.sub(r"[,\s₹]|rs\.?|inr", "", text, flags=re.IGNORECASE)
    if not re.fullmatch(r"\d+(\.\d{1,2})?", text):
        raise LedgerError("The amount is missing or not a valid number.")
    amount = round(float(text), 2)
    if amount <= 0:
        raise LedgerError("The amount must be more than zero.")
    return amount


def inr(amount: float) -> str:
    return f"₹{int(amount):,}" if float(amount).is_integer() else f"₹{amount:,.2f}"


# ── Accounts ─────────────────────────────────────────────────────────────────

def resolve_account(raw: Any) -> dict[str, Any]:
    """Active account from a full 10-digit number or a unique last 4 digits."""
    db = _db()
    digits = _digits(raw)
    if len(digits) == 10:
        account = db.accounts.find_one({"account_number": digits, "status": "active"})
        if account:
            return account
        raise LedgerError(f"No active account {digits}.")
    if len(digits) == 4:
        found = list(db.accounts.find({"account_number": {"$regex": f"{digits}$"}, "status": "active"}))
        if len(found) == 1:
            return found[0]
        if not found:
            raise LedgerError(f"No account ends in {digits}.")
        raise LedgerError(f"More than one account ends in {digits} — ask the customer for the full number.")
    raise LedgerError("The account number should be 10 digits (or the last 4).")


def primary_account(customer_id: str) -> dict[str, Any]:
    account = _db().accounts.find_one({"customer_id": customer_id, "status": "active"}, sort=[("created_at", 1)])
    if not account:
        raise LedgerError("This customer has no active account to receive the money.")
    return account


def _entry(db, account: dict, kind: str, amount: float, balance_after: float, *, ref: str, by: str, note: str, counterparty: str = "") -> dict:
    row = {
        "id": str(uuid.uuid4()),
        "account_number": account["account_number"],
        "customer_id": account.get("customer_id"),
        "kind": kind,
        "amount": round(amount, 2),
        "balance_after": round(balance_after, 2),
        "ref": ref,
        "by": by,
        "note": note,
        "counterparty": counterparty,
        "at": _now(),
    }
    db.transactions.insert_one(dict(row))
    return row


def credit(account_number: str, amount: float, kind: str, *, ref: str = "", by: str = "", note: str = "", counterparty: str = "") -> dict:
    db = _db()
    after = db.accounts.find_one_and_update(
        {"account_number": account_number, "status": "active"},
        {"$inc": {"balance_inr": amount}, "$set": {"balance_updated_at": _now()}},
        return_document=_after(),
    )
    if not after:
        raise LedgerError(f"No active account {account_number}.")
    return _entry(db, after, kind, amount, float(after["balance_inr"]), ref=ref, by=by, note=note, counterparty=counterparty)


def debit(account_number: str, amount: float, kind: str, *, ref: str = "", by: str = "", note: str = "", counterparty: str = "") -> dict:
    db = _db()
    after = db.accounts.find_one_and_update(
        {"account_number": account_number, "status": "active", "balance_inr": {"$gte": amount}},
        {"$inc": {"balance_inr": -amount}, "$set": {"balance_updated_at": _now()}},
        return_document=_after(),
    )
    if not after:
        current = db.accounts.find_one({"account_number": account_number, "status": "active"})
        if not current:
            raise LedgerError(f"No active account {account_number}.")
        raise LedgerError(f"Not enough balance: {inr(float(current['balance_inr']))} available, {inr(amount)} needed.")
    return _entry(db, after, kind, amount, float(after["balance_inr"]), ref=ref, by=by, note=note, counterparty=counterparty)


def _after():
    from pymongo import ReturnDocument

    return ReturnDocument.AFTER


def transfer(from_raw: Any, to_raw: Any, amount: float, *, ref: str = "", by: str = "", note: str = "") -> dict:
    """Move money between two of our accounts, or out of one (to_raw=None / not ours)."""
    source = resolve_account(from_raw)
    target = None
    if to_raw:
        try:
            target = resolve_account(to_raw)
        except LedgerError:
            target = None  # another bank — only the debit side exists here
    if target and target["account_number"] == source["account_number"]:
        raise LedgerError("The two accounts are the same.")
    out = debit(source["account_number"], amount, "transfer_out", ref=ref, by=by, note=note,
                counterparty=(target or {}).get("account_number") or _digits(to_raw))
    if target:
        try:
            credit(target["account_number"], amount, "transfer_in", ref=ref, by=by, note=note, counterparty=source["account_number"])
        except LedgerError:
            credit(source["account_number"], amount, "reversal", ref=ref, by=by, note="credit failed — transfer reversed")
            raise
    return {"from": source["account_number"], "to": (target or {}).get("account_number"), "external": target is None,
            "amount": amount, "balance_after": out["balance_after"]}


def list_transactions(account_numbers: list[str], limit: int = 20) -> list[dict[str, Any]]:
    if not account_numbers:
        return []
    rows = _db().transactions.find({"account_number": {"$in": account_numbers}}).sort("at", -1).limit(limit)
    return [{k: v for k, v in r.items() if k != "_id"} for r in rows]


# ── Loans ────────────────────────────────────────────────────────────────────

def emi(principal: float, annual_rate_pct: float, months: int) -> float:
    if months <= 0:
        raise LedgerError("The loan term must be at least one month.")
    r = annual_rate_pct / 1200
    if r == 0:
        return round(principal / months, 2)
    factor = (1 + r) ** months
    return round(principal * r * factor / (factor - 1), 2)


def create_loan(customer_id: str, *, loan_type: str, principal: float, annual_rate_pct: float, tenure_months: int,
                ref: str = "", by: str = "") -> dict[str, Any]:
    """Create an active loan and pay it into the customer's first account."""
    db = _db()
    account = primary_account(customer_id)
    loan = {
        "id": str(uuid.uuid4()),
        "customer_id": customer_id,
        "account_number": account["account_number"],
        "loan_type": loan_type or "personal",
        "principal_inr": principal,
        "annual_rate_pct": annual_rate_pct,
        "tenure_months": tenure_months,
        "emi_inr": emi(principal, annual_rate_pct, tenure_months),
        "outstanding_inr": principal,
        "status": "active",
        "application_ref": ref,
        "created_at": _now(),
    }
    credit(account["account_number"], principal, "loan_disbursal", ref=ref, by=by, note=f"{loan['loan_type']} loan")
    db.loans.insert_one(dict(loan))
    return loan


def repay_loan(loan_id: str, amount: float, *, by: str = "") -> dict[str, Any]:
    """Record a payment received at the counter: interest for the month first, the rest reduces the loan."""
    db = _db()
    loan = db.loans.find_one({"id": loan_id})
    if not loan or loan.get("status") != "active":
        raise LedgerError("No active loan with this id.")
    outstanding = float(loan["outstanding_inr"])
    interest = round(outstanding * float(loan.get("annual_rate_pct") or 0) / 1200, 2)
    principal_part = round(min(max(0.0, amount - interest), outstanding), 2)
    after = round(outstanding - principal_part, 2)
    closed = after <= 0.009
    db.loans.update_one({"id": loan_id}, {"$set": {"outstanding_inr": 0.0 if closed else after, "status": "closed" if closed else "active"}})
    payment = {"id": str(uuid.uuid4()), "loan_id": loan_id, "customer_id": loan["customer_id"], "amount": amount,
               "interest_part": min(interest, amount), "principal_part": principal_part,
               "outstanding_after": 0.0 if closed else after, "by": by, "at": _now()}
    db.loan_payments.insert_one(dict(payment))
    return {**payment, "closed": closed}


def list_loans(customer_id: str) -> list[dict[str, Any]]:
    rows = _db().loans.find({"customer_id": customer_id}).sort("created_at", -1)
    return [{k: v for k, v in r.items() if k != "_id"} for r in rows]


# ── Fixed deposits ───────────────────────────────────────────────────────────

def maturity_amount(principal: float, annual_rate_pct: float, months: int) -> float:
    """Quarterly compounding, the usual rule for term deposits."""
    return round(principal * (1 + annual_rate_pct / 400) ** (months / 3), 2)


def create_deposit(account_number: str, amount: float, *, tenure_months: int, annual_rate_pct: float, ref: str = "", by: str = "") -> dict:
    db = _db()
    if tenure_months <= 0:
        raise LedgerError("The deposit term must be at least one month.")
    account = db.accounts.find_one({"account_number": account_number, "status": "active"})
    if not account:
        raise LedgerError(f"No active account {account_number}.")
    debit(account_number, amount, "fd_open", ref=ref, by=by, note=f"{tenure_months}-month fixed deposit")
    opened = datetime.now(timezone.utc)
    deposit = {
        "id": str(uuid.uuid4()),
        "customer_id": account["customer_id"],
        "account_number": account_number,
        "principal_inr": amount,
        "annual_rate_pct": annual_rate_pct,
        "tenure_months": tenure_months,
        "maturity_inr": maturity_amount(amount, annual_rate_pct, tenure_months),
        "opened_at": opened.isoformat(),
        "matures_on": (opened + timedelta(days=round(tenure_months * 30.4375))).date().isoformat(),
        "status": "active",
        "application_ref": ref,
    }
    db.deposits.insert_one(dict(deposit))
    return deposit


def list_deposits(customer_id: str) -> list[dict[str, Any]]:
    rows = _db().deposits.find({"customer_id": customer_id}).sort("opened_at", -1)
    return [{k: v for k, v in r.items() if k != "_id"} for r in rows]


# ── Service requests (cheque book, ATM card, stop cheque) ────────────────────

def record_service(kind: str, account: dict, details: dict[str, Any], *, ref: str = "", by: str = "") -> dict[str, Any]:
    row = {"id": str(uuid.uuid4()), "kind": kind, "customer_id": account.get("customer_id"),
           "account_number": account["account_number"], "details": details, "status": "fulfilled",
           "application_ref": ref, "by": by, "at": _now()}
    _db().service_requests.insert_one(dict(row))
    return {k: v for k, v in row.items() if k != "_id"}


def issue_card(account: dict, card_type: str, *, ref: str = "", by: str = "") -> dict[str, Any]:
    """Demo card: only a random 4-digit tail is generated — no real card numbers exist."""
    tail = "".join(secrets.choice("0123456789") for _ in range(4))
    return record_service("atm_card", account, {"card_type": card_type, "last4": tail}, ref=ref, by=by)


def stop_cheque(account: dict, cheque_number: str, reason: str, *, ref: str = "", by: str = "") -> dict[str, Any]:
    number = _digits(cheque_number)
    if not number:
        raise LedgerError("The cheque number is missing.")
    db = _db()
    if db.service_requests.find_one({"kind": "stop_cheque", "account_number": account["account_number"], "details.cheque_number": number}):
        raise LedgerError(f"Cheque {number} is already stopped.")
    return record_service("stop_cheque", account, {"cheque_number": number, "reason": reason}, ref=ref, by=by)


def update_mobile(customer_id: str, old_mobile: str, new_mobile: str) -> dict[str, Any]:
    db = _db()
    customer = db.customers.find_one({"id": customer_id})
    if not customer:
        raise LedgerError("Customer not found.")
    new = _digits(new_mobile)[-10:]
    if len(new) < 10:
        raise LedgerError("The new mobile number should have 10 digits.")
    current = _digits(customer.get("mobile"))
    if current and _digits(old_mobile)[-4:] != current[-4:]:
        raise LedgerError("The old mobile number does not match the one on record.")
    db.customers.update_one({"id": customer_id}, {"$set": {"mobile": new}})
    return {"customer_id": customer_id, "mobile_last4": new[-4:]}


# ── Returning customers ──────────────────────────────────────────────────────

def identify(account_last4: Any, mobile_last4: Any) -> dict[str, Any] | None:
    """Customer who has an account ending in these 4 digits AND a mobile ending in these 4."""
    a, m = _digits(account_last4)[-4:], _digits(mobile_last4)[-4:]
    if len(a) != 4 or len(m) != 4:
        return None
    db = _db()
    for account in db.accounts.find({"account_number": {"$regex": f"{a}$"}, "status": "active"}):
        customer = db.customers.find_one({"id": account["customer_id"], "status": "active"})
        if customer and _digits(customer.get("mobile")).endswith(m):
            return customer
    return None


def customer_detail(customer_id: str, *, transactions: int = 15) -> dict[str, Any]:
    """Everything about one customer: accounts, loans, deposits, recent movements, applications."""
    db = _db()
    customer = db.customers.find_one({"id": customer_id})
    if not customer:
        raise LedgerError("Customer not found.")
    accounts = [{k: v for k, v in a.items() if k != "_id"} for a in db.accounts.find({"customer_id": customer_id}).sort("created_at", 1)]
    numbers = [a["account_number"] for a in accounts]
    mobile = _digits(customer.get("mobile"))
    from backend.db import store

    return {
        "customer": {k: v for k, v in customer.items() if k != "_id"},
        "accounts": accounts,
        "loans": list_loans(customer_id),
        "deposits": list_deposits(customer_id),
        "transactions": list_transactions(numbers, transactions),
        "applications": store.applications_for(mobile[-10:], numbers, limit=8),
    }
