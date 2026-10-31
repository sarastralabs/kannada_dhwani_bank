"""Application workflow: a customer submits a form at the kiosk, staff decide, the customer
comes back and sees the outcome.

    submitted ──approve──▶ approved   (open_account: the account now exists)
        │      ──reject───▶ rejected  (with a message for the customer)
        └──────needs_info─▶ needs_info (customer is asked to visit / resubmit)

Approving carries out the form's effect: open the account, credit or debit it, transfer, create
a loan or a fixed deposit, issue a cheque book or card, stop a cheque, change a mobile number.
Everything here works on demo money (see backend/db/ledger.py).
"""

from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from typing import Any

from backend.db import store

STATUSES = ("submitted", "approved", "rejected", "needs_info")
OPEN = ("submitted", "needs_info")  # states a decision can still be made from

STATUS_KN = {
    "submitted": "ನಿಮ್ಮ ಅರ್ಜಿ ಪರಿಶೀಲನೆಯಲ್ಲಿದೆ",
    "approved": "ನಿಮ್ಮ ಅರ್ಜಿಯನ್ನು ಅನುಮೋದಿಸಲಾಗಿದೆ",
    "rejected": "ನಿಮ್ಮ ಅರ್ಜಿಯನ್ನು ತಿರಸ್ಕರಿಸಲಾಗಿದೆ",
    "needs_info": "ನಿಮ್ಮ ಅರ್ಜಿಗೆ ಹೆಚ್ಚಿನ ಮಾಹಿತಿ ಬೇಕು, ದಯವಿಟ್ಟು ಶಾಖೆಗೆ ಭೇಟಿ ನೀಡಿ",
}

_ACTION_STATUS = {"approve": "approved", "reject": "rejected", "needs_info": "needs_info"}
_MOBILE_FIELDS = ("mobile_number", "new_mobile", "old_mobile")
_decide_lock = threading.Lock()


class DecisionError(ValueError):
    """The decision cannot be made (already decided, missing message, bad action)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def application_mobile(values: dict[str, str]) -> str:
    """Mobile number on the form, if there is one (digits only)."""
    for key in _MOBILE_FIELDS:
        digits = _digits(values.get(key))
        if len(digits) >= 4:
            return digits
    return ""


def _account_type(text: str) -> str:
    t = (text or "").lower()
    if "ಚಾಲ್ತಿ" in t or "current" in t:
        return "Current"
    return "Savings"


def _open_account(app: dict[str, Any]) -> dict[str, Any]:
    from backend.db import customers

    v = app["values"]
    name = (v.get("full_name") or "").strip()
    if not name:
        raise DecisionError("The application has no name, so an account cannot be opened.")
    mobile = _digits(v.get("mobile_number"))
    existing = customers.find_customer_by_mobile(mobile) if len(mobile) >= 10 else None
    kannada = bool(re.search(r"[ಀ-೿]", name))
    opened = customers.create_customer_with_account(
        name,
        full_name_kn=name if kannada else "",
        mobile=mobile or None,
        account_type=_account_type(v.get("account_type", "")),
        customer_id=existing["customer_id"] if existing else None,
    )
    return {
        "account_number": opened["account_number"],
        "account_type": opened["account_type"],
        "customer_id": opened["customer_id"],
        "existing_customer": bool(existing),
    }


def _months(text: str, default: int) -> int:
    """"2 years" / "24 months" / "೨ ವರ್ಷ" -> months; anything unclear -> the default."""
    m = re.search(r"\d+", (text or "").translate(str.maketrans("೦೧೨೩೪೫೬೭೮೯", "0123456789")))
    if not m:
        return default
    n = int(m.group())
    return n * 12 if re.search(r"year|yr|ವರ್ಷ", (text or "").lower()) else n


def _terms_number(terms: dict[str, Any], key: str, default: float) -> float:
    raw = terms.get(key)
    if raw in (None, ""):
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise DecisionError(f"'{key}' must be a number.") from None
    if value < 0:
        raise DecisionError(f"'{key}' cannot be negative.")
    return value


def _customer_of(account: dict[str, Any]) -> dict[str, Any]:
    from backend.db import customers

    customers_db = customers._mongo()  # noqa: SLF001
    found = customers_db.customers.find_one({"id": account["customer_id"]}) if customers_db is not None else None
    return found or {}


def _holder(account: dict[str, Any]) -> str:
    c = _customer_of(account)
    return c.get("full_name") or c.get("full_name_kn") or account["account_number"]


# Each effect: (app, terms, admin, dry) -> details. With dry=True nothing is changed: it only checks
# that approving would work and says what it would do (the admin sees this before deciding).

def _fx_open_account(app, terms, admin, dry):
    v = app["values"]
    name = (v.get("full_name") or "").strip()
    if not name:
        raise DecisionError("The application has no name, so an account cannot be opened.")
    from backend.db import customers

    mobile = _digits(v.get("mobile_number"))
    existing = customers.find_customer_by_mobile(mobile) if len(mobile) >= 10 else None
    kind = _account_type(v.get("account_type", ""))
    if dry:
        who = "an existing customer" if existing else "a new customer"
        return {"summary": f"Opens a {kind} account for {name} ({who})."}
    return _open_account(app)


def _fx_cash_deposit(app, terms, admin, dry):
    from backend.db import ledger

    v = app["values"]
    account, amount = ledger.resolve_account(v.get("account_number")), ledger.money(v.get("amount"))
    info = {"account_number": account["account_number"], "amount": amount,
            "summary": f"Credits {ledger.inr(amount)} to {_holder(account)} ({account['account_number']})."}
    if dry:
        return info
    row = ledger.credit(account["account_number"], amount, "deposit", ref=app["ref"], by=admin, note=v.get("deposit_mode", ""))
    return {**info, "balance_after": row["balance_after"]}


def _fx_cash_withdrawal(app, terms, admin, dry):
    from backend.db import ledger

    v = app["values"]
    account, amount = ledger.resolve_account(v.get("account_number")), ledger.money(v.get("amount"))
    if float(account["balance_inr"]) < amount:
        raise DecisionError(f"Not enough balance: {ledger.inr(float(account['balance_inr']))} available, {ledger.inr(amount)} requested.")
    info = {"account_number": account["account_number"], "amount": amount,
            "summary": f"Pays out {ledger.inr(amount)} from {_holder(account)} ({account['account_number']})."}
    if dry:
        return info
    row = ledger.debit(account["account_number"], amount, "withdrawal", ref=app["ref"], by=admin, note=v.get("purpose", ""))
    return {**info, "balance_after": row["balance_after"]}


def _fx_rtgs_neft(app, terms, admin, dry):
    from backend.db import ledger

    v = app["values"]
    source, amount = ledger.resolve_account(v.get("remitter_account")), ledger.money(v.get("amount"))
    if float(source["balance_inr"]) < amount:
        raise DecisionError(f"Not enough balance: {ledger.inr(float(source['balance_inr']))} available, {ledger.inr(amount)} requested.")
    info = {"account_number": source["account_number"], "amount": amount,
            "summary": f"Transfers {ledger.inr(amount)} from {source['account_number']} to {_digits(v.get('beneficiary_account')) or 'the beneficiary'}."}
    if dry:
        return info
    moved = ledger.transfer(source["account_number"], v.get("beneficiary_account"), amount, ref=app["ref"], by=admin, note=v.get("remarks", ""))
    return {**info, "to": moved["to"], "external": moved["external"], "balance_after": moved["balance_after"]}


def _fx_apply_loan(app, terms, admin, dry):
    from backend.db import customers, ledger

    v = app["values"]
    mobile = _digits(v.get("mobile_number"))
    customer = customers.find_customer_by_mobile(mobile) if len(mobile) >= 10 else None
    if not customer:
        raise DecisionError("No customer has this mobile number. Open an account for them first, then approve the loan.")
    principal = _terms_number(terms, "amount", 0) or ledger.money(v.get("loan_amount"))
    rate = _terms_number(terms, "annual_rate_pct", ledger.DEFAULT_LOAN_RATE)
    months = int(_terms_number(terms, "tenure_months", ledger.DEFAULT_LOAN_MONTHS))
    account = ledger.primary_account(customer["customer_id"])
    payment = ledger.emi(principal, rate, months)
    info = {"amount": principal, "annual_rate_pct": rate, "tenure_months": months, "emi_inr": payment,
            "account_number": account["account_number"],
            "summary": f"Lends {ledger.inr(principal)} to {customer['full_name']} at {rate}% for {months} months "
                       f"(EMI {ledger.inr(payment)}), paid into {account['account_number']}."}
    if dry:
        return info
    loan = ledger.create_loan(customer["customer_id"], loan_type=v.get("loan_type") or "personal", principal=principal,
                              annual_rate_pct=rate, tenure_months=months, ref=app["ref"], by=admin)
    return {**info, "loan_id": loan["id"]}


def _fx_fixed_deposit(app, terms, admin, dry):
    from backend.db import ledger

    v = app["values"]
    account, amount = ledger.resolve_account(v.get("account_number")), ledger.money(v.get("fd_amount"))
    rate = _terms_number(terms, "annual_rate_pct", ledger.DEFAULT_FD_RATE)
    months = int(_terms_number(terms, "tenure_months", _months(v.get("tenure", ""), ledger.DEFAULT_FD_MONTHS)))
    if float(account["balance_inr"]) < amount:
        raise DecisionError(f"Not enough balance: {ledger.inr(float(account['balance_inr']))} available, {ledger.inr(amount)} needed.")
    maturity = ledger.maturity_amount(amount, rate, months)
    info = {"amount": amount, "annual_rate_pct": rate, "tenure_months": months, "maturity_inr": maturity,
            "account_number": account["account_number"],
            "summary": f"Locks {ledger.inr(amount)} from {account['account_number']} for {months} months at {rate}% "
                       f"(matures at {ledger.inr(maturity)})."}
    if dry:
        return info
    deposit = ledger.create_deposit(account["account_number"], amount, tenure_months=months, annual_rate_pct=rate, ref=app["ref"], by=admin)
    return {**info, "deposit_id": deposit["id"], "matures_on": deposit["matures_on"]}


def _fx_cheque_book(app, terms, admin, dry):
    from backend.db import ledger

    v = app["values"]
    account = ledger.resolve_account(v.get("account_number"))
    leaves = int(_digits(v.get("number_of_leaves")) or 25)
    info = {"account_number": account["account_number"], "leaves": leaves,
            "summary": f"Issues a {leaves}-leaf cheque book to {_holder(account)} ({account['account_number']})."}
    if dry:
        return info
    ledger.record_service("cheque_book", account, {"leaves": leaves}, ref=app["ref"], by=admin)
    return info


def _fx_atm_card(app, terms, admin, dry):
    from backend.db import ledger

    v = app["values"]
    account = ledger.resolve_account(v.get("account_number"))
    card_type = v.get("card_type") or "Debit"
    info = {"account_number": account["account_number"], "card_type": card_type,
            "summary": f"Issues a {card_type} card to {_holder(account)} ({account['account_number']})."}
    if dry:
        return info
    card = ledger.issue_card(account, card_type, ref=app["ref"], by=admin)
    return {**info, "card_last4": card["details"]["last4"]}


def _fx_stop_cheque(app, terms, admin, dry):
    from backend.db import ledger

    v = app["values"]
    account = ledger.resolve_account(v.get("account_number"))
    number = _digits(v.get("cheque_number"))
    if not number:
        raise DecisionError("The cheque number is missing.")
    info = {"account_number": account["account_number"], "cheque_number": number,
            "summary": f"Stops payment of cheque {number} on {account['account_number']}."}
    if dry:
        return info
    ledger.stop_cheque(account, number, v.get("reason", ""), ref=app["ref"], by=admin)
    return info


def _fx_mobile_update(app, terms, admin, dry):
    from backend.db import ledger

    v = app["values"]
    account = ledger.resolve_account(v.get("account_number"))
    customer = _customer_of(account)
    current = _digits(customer.get("mobile"))
    if current and _digits(v.get("old_mobile"))[-4:] != current[-4:]:
        raise DecisionError("The old mobile number does not match the one on record.")
    new = _digits(v.get("new_mobile"))[-10:]
    if len(new) < 10:
        raise DecisionError("The new mobile number should have 10 digits.")
    info = {"account_number": account["account_number"], "summary": f"Changes {_holder(account)}'s mobile to ••••••{new[-4:]}."}
    if dry:
        return info
    ledger.update_mobile(account["customer_id"], v.get("old_mobile", ""), new)
    return info


_EFFECTS = {
    "open_account": _fx_open_account,
    "cash_deposit": _fx_cash_deposit,
    "cash_withdrawal": _fx_cash_withdrawal,
    "rtgs_neft": _fx_rtgs_neft,
    "apply_loan": _fx_apply_loan,
    "fixed_deposit": _fx_fixed_deposit,
    "cheque_book_request": _fx_cheque_book,
    "atm_debit_card": _fx_atm_card,
    "stop_cheque": _fx_stop_cheque,
    "mobile_update": _fx_mobile_update,
}


def _run_effect(app: dict[str, Any], terms: dict[str, Any] | None, admin: str, dry: bool) -> dict[str, Any]:
    from backend.db import ledger

    effect = _EFFECTS.get(app["form_id"])
    if effect is None:
        return {}
    try:
        return effect(app, terms or {}, admin, dry)
    except ledger.LedgerError as exc:
        raise DecisionError(str(exc)) from exc


def preview(app_id: str) -> dict[str, Any]:
    """What approving would do, without doing it — so staff see problems before they press the button."""
    app = store.get_application(app_id)
    if app is None:
        raise LookupError("Application not found")
    if app["status"] not in OPEN:
        return {"ok": False, "problems": [f"Already {app['status']}."], "summary": "", "details": {}}
    try:
        details = _run_effect(app, {}, "preview", dry=True)
    except DecisionError as exc:
        return {"ok": False, "problems": [str(exc)], "summary": "", "details": {}}
    return {"ok": True, "problems": [], "summary": details.get("summary", "Nothing is changed automatically; staff handle the rest."),
            "details": details}


def decide(app_id: str, action: str, *, admin: str, note: str = "", terms: dict[str, Any] | None = None) -> dict[str, Any]:
    """Approve, reject or ask for more information. Returns the updated application.

    Approving carries out the form's effect (open the account, move the money, create the loan…).
    ``terms`` lets staff set the amount, rate and tenure of a loan or fixed deposit.
    """
    if action not in _ACTION_STATUS:
        raise DecisionError(f"Unknown action {action!r}.")
    note = (note or "").strip()
    with _decide_lock:  # one decision at a time, so an account can never be opened twice
        app = store.get_application(app_id)
        if app is None:
            raise LookupError("Application not found")
        if app["status"] not in OPEN:
            raise DecisionError(f"This application is already {app['status']}.")
        if action in ("reject", "needs_info") and not note:
            raise DecisionError("Write a short message for the customer.")
        result: dict[str, Any] = {}
        if action == "approve":
            result = _run_effect(app, terms, admin, dry=False)
        decision = {"action": action, "by": admin, "at": _now(), "note": note, "result": result}
        updated = store.decide_application(app["id"], status=_ACTION_STATUS[action], decision=decision)
    if updated is None:
        raise LookupError("Application not found")
    return updated


def normalize_ref(ref: str) -> str:
    """DH-26-000123, dh-26-000123 or just the spoken digits 26000123 -> DH-26-000123."""
    text = (ref or "").strip().upper()
    digits = _digits(text)
    if len(digits) == 8 and not text.startswith("DH"):
        return f"DH-{digits[:2]}-{digits[2:]}"
    return text


def _spoken(digits: str) -> str:
    return " ".join(digits)


def public_status(ref: str, mobile_last4: str = "") -> dict[str, Any] | None:
    """What a customer may see when they come back with their application number.

    If the form carried a mobile number, its last 4 digits must match; a wrong or missing
    answer looks exactly like an unknown number (nothing to guess from).
    """
    app = store.get_application(normalize_ref(ref))
    if app is None or not app.get("ref"):
        return None
    mobile = application_mobile(app["values"])
    if mobile and _digits(mobile_last4)[-4:] != mobile[-4:]:
        return None
    decision = app.get("decision") or {}
    out: dict[str, Any] = {
        "ref": app["ref"],
        "form_id": app["form_id"],
        "title_kn": app["title_kn"],
        "title_en": app["title_en"],
        "status": app["status"],
        "status_kn": STATUS_KN.get(app["status"], ""),
        "submitted_at": app["created_at"],
        "decided_at": decision.get("at"),
        "message": decision.get("note") or "",
    }
    if app["status"] == "approved" and app["form_id"] == "open_account":
        out["account_number"] = (decision.get("result") or {}).get("account_number")
    out["message_kn"] = _message_kn(out)
    return out


def _message_kn(info: dict[str, Any]) -> str:
    """The sentence the kiosk reads to the customer."""
    text = f"{STATUS_KN.get(info['status'], '')}."
    if info.get("account_number"):
        text += f" ನಿಮ್ಮ ಹೊಸ ಖಾತೆ ಸಂಖ್ಯೆ {_spoken(info['account_number'])}."
    if info.get("message"):
        text += f" {info['message']}."
    return text
