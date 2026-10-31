"""What a returning customer is shown at the kiosk (and the sentence the kiosk reads out)."""

from __future__ import annotations

from typing import Any

from backend.db import ledger
from backend.forms.summary_kn import amount_speak_kn, digits_to_kannada_words

STATUS_KN = {"submitted": "ಪರಿಶೀಲನೆಯಲ್ಲಿದೆ", "approved": "ಅನುಮೋದಿಸಲಾಗಿದೆ", "rejected": "ತಿರಸ್ಕರಿಸಲಾಗಿದೆ", "needs_info": "ಹೆಚ್ಚಿನ ಮಾಹಿತಿ ಬೇಕು"}


def _rupees(value: float) -> str:
    return amount_speak_kn(str(int(round(float(value or 0)))))


def _message(name: str, accounts: list[dict], loans: list[dict], deposits: list[dict], pending: int) -> str:
    parts = [f"ನಮಸ್ಕಾರ {name}."]
    for a in accounts:
        parts.append(f"ಕೊನೆಯ ನಾಲ್ಕು ಅಂಕಿಗಳು {digits_to_kannada_words(a['last4'])} ಇರುವ ಖಾತೆಯ ಶಿಲ್ಕು {_rupees(a['balance_inr'])}.")
    if loans:
        total = sum(float(x.get("outstanding_inr") or 0) for x in loans)
        parts.append(f"ನಿಮ್ಮ ಸಾಲದ ಬಾಕಿ {_rupees(total)}.")
    if deposits:
        parts.append(f"ನಿಮಗೆ {len(deposits)} ಸ್ಥಿರ ಠೇವಣಿ ಇದೆ.")
    if pending:
        parts.append(f"{pending} ಅರ್ಜಿ ಪರಿಶೀಲನೆಯಲ್ಲಿದೆ.")
    return " ".join(parts)


def summary(account_last4: str, mobile_last4: str) -> dict[str, Any] | None:
    """The customer's own picture, or None when the two sets of digits do not match one customer."""
    try:
        customer = ledger.identify(account_last4, mobile_last4)
        if customer is None:
            return None
        detail = ledger.customer_detail(customer["id"], transactions=6)
    except ledger.LedgerError:
        return None

    accounts = [
        {
            "last4": a["account_number"][-4:],
            "account_type": a.get("account_type") or "Savings",
            "balance_inr": round(float(a.get("balance_inr") or 0), 2),
        }
        for a in detail["accounts"]
    ]
    loans = [
        {"loan_type": x.get("loan_type"), "principal_inr": x.get("principal_inr"), "outstanding_inr": x.get("outstanding_inr"),
         "emi_inr": x.get("emi_inr"), "status": x.get("status")}
        for x in detail["loans"]
        if x.get("status") == "active"
    ]
    deposits = [
        {"principal_inr": d["principal_inr"], "maturity_inr": d["maturity_inr"], "matures_on": d["matures_on"], "annual_rate_pct": d["annual_rate_pct"]}
        for d in detail["deposits"]
        if d.get("status") == "active"
    ]
    transactions = [
        {"kind": t["kind"], "amount": t["amount"], "balance_after": t["balance_after"], "at": t["at"], "last4": t["account_number"][-4:]}
        for t in detail["transactions"]
    ]
    apps = [
        {"ref": a["ref"], "title_kn": a["title_kn"], "title_en": a["title_en"], "status": a["status"], "status_kn": STATUS_KN.get(a["status"], "")}
        for a in detail["applications"]
    ]
    name = detail["customer"].get("full_name_kn") or detail["customer"].get("full_name") or ""
    pending = sum(1 for a in apps if a["status"] == "submitted")
    return {
        "name": name,
        "accounts": accounts,
        "loans": loans,
        "deposits": deposits,
        "transactions": transactions,
        "applications": apps,
        "message_kn": _message(name, accounts, loans, deposits, pending),
    }
