"""Map NLU intents to voice-fill form ids in data/forms.json.

Kept in sync with data/forms.json intent_map. Extra forms (RTGS, cheque book,
ATM card, FD, mobile update, stop cheque) are selected from the Forms tab —
they are real branch forms but not yet separate NLU intents.
"""

from __future__ import annotations

FORM_ID_FOR_INTENT: dict[str, str] = {
    "check_balance": "balance_inquiry",
    "withdraw_money": "cash_withdrawal",
    "deposit_money": "cash_deposit",
    "open_account": "open_account",
    "apply_loan": "apply_loan",
}


def form_id_for_intent(intent: str) -> str | None:
    """Return form id for a transactional intent, or None if none mapped."""
    return FORM_ID_FOR_INTENT.get(intent)
