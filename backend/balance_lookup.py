"""Demo / production-shaped account balance lookup for the kiosk.

Supports two modes:
  - Full account number (10 digits) — exact match
  - Last 4 digits — partial match with disambiguation if multiple accounts match
"""

from __future__ import annotations

import os
import re

from backend.db.customers import get_account_balance, get_account_by_last4, write_balance_audit
from backend.forms.summary_kn import amount_speak_kn, digits_to_kannada_words


def _normalize_account(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")


def lookup_balance(account_number: str, *, kiosk_session_id: str = "") -> dict:
    acct = _normalize_account(account_number)

    try:
        expected_length = max(4, int(os.environ.get("BANK_DEMO_ACCOUNT_LENGTH", "10")))
    except ValueError:
        expected_length = 10

    # ── Last-4-digit shortcut ─────────────────────────────────────────────────
    if len(acct) == 4:
        matches = get_account_by_last4(acct)

        if not matches:
            spoken_acct = digits_to_kannada_words(acct)
            write_balance_audit(
                account_number=acct,
                found=False,
                kiosk_session_id=kiosk_session_id,
                source="last4_not_found",
            )
            return {
                "found": False,
                "account_number": acct,
                "message_en": (
                    f"No account ending in {acct} was found. "
                    "Please check and try again."
                ),
                "message_kn": (
                    f"ಕೊನೆಯ ನಾಲ್ಕು ಅಂಕಿಗಳು {spoken_acct} ಇರುವ ಖಾತೆ ಕಂಡುಬಂದಿಲ್ಲ. "
                    "ದಯವಿಟ್ಟು ಮತ್ತೆ ಪರಿಶೀಲಿಸಿ."
                ),
            }

        if len(matches) > 1:
            # Multiple accounts share the same last 4 — ask for one more digit
            write_balance_audit(
                account_number=acct,
                found=False,
                kiosk_session_id=kiosk_session_id,
                source="last4_ambiguous",
            )
            return {
                "found": False,
                "account_number": acct,
                "ambiguous": True,
                "match_count": len(matches),
                "message_en": (
                    f"Multiple accounts end in {acct}. "
                    "Please say the last 6 digits of your account number."
                ),
                "message_kn": (
                    f"ಕೊನೆಯ ನಾಲ್ಕು ಅಂಕಿಗಳು {digits_to_kannada_words(acct)} ಇರುವ "
                    "ಹಲವು ಖಾತೆಗಳಿವೆ. ದಯವಿಟ್ಟು ನಿಮ್ಮ ಖಾತೆ ಸಂಖ್ಯೆಯ ಕೊನೆಯ ಆರು ಅಂಕಿಗಳನ್ನು ಹೇಳಿ."
                ),
            }

        # Unique match — use it
        row = matches[0]
        return _build_found_response(row, kiosk_session_id=kiosk_session_id)

    # ── Last-6-digit shortcut (disambiguation) ────────────────────────────────
    if len(acct) == 6:
        matches = get_account_by_last4(acct[-4:])
        matches = [m for m in matches if m["account_number"].endswith(acct)]
        if len(matches) == 1:
            return _build_found_response(matches[0], kiosk_session_id=kiosk_session_id)
        # Fall through to full-number path

    # ── Full account number ───────────────────────────────────────────────────
    if len(acct) != expected_length:
        expected_length_kn = (
            "ಹತ್ತು" if expected_length == 10
            else digits_to_kannada_words(str(expected_length))
        )
        write_balance_audit(
            account_number=acct,
            found=False,
            kiosk_session_id=kiosk_session_id,
            source="length_reject",
        )
        return {
            "found": False,
            "account_number": acct,
            "message_en": (
                f"Please say the last 4 digits of your account number, "
                f"or the full {expected_length}-digit number."
            ),
            "message_kn": (
                "ದಯವಿಟ್ಟು ನಿಮ್ಮ ಖಾತೆ ಸಂಖ್ಯೆಯ ಕೊನೆಯ ನಾಲ್ಕು ಅಂಕಿಗಳನ್ನು ಹೇಳಿ, "
                f"ಅಥವಾ ಪೂರ್ತಿ {expected_length_kn} ಅಂಕಿಗಳ ಸಂಖ್ಯೆ ಹೇಳಿ."
            ),
        }

    row = get_account_balance(acct)
    if not row:
        spoken_acct = digits_to_kannada_words(acct)
        write_balance_audit(
            account_number=acct,
            found=False,
            kiosk_session_id=kiosk_session_id,
            source="not_found",
        )
        return {
            "found": False,
            "account_number": acct,
            "message_en": (
                f"Account number {acct} was not found. "
                "Please check the number and try again."
            ),
            "message_kn": (
                f"ಖಾತೆ ಸಂಖ್ಯೆ {spoken_acct} ನಮ್ಮ ದಾಖಲೆಗಳಲ್ಲಿ ಕಂಡುಬಂದಿಲ್ಲ. "
                "ದಯವಿಟ್ಟು ಸಂಖ್ಯೆಯನ್ನು ಪರಿಶೀಲಿಸಿ ಮತ್ತೆ ಹೇಳಿ."
            ),
        }

    return _build_found_response(row, kiosk_session_id=kiosk_session_id)


def _build_found_response(row: dict, *, kiosk_session_id: str = "") -> dict:
    """Build the success response from a DB row dict."""
    acct = row["account_number"]
    bal = float(row["balance_inr"])
    bal_str = f"{bal:,.2f}"
    name_kn = row.get("holder_name_kn") or row.get("holder_name", "")
    name_en = row.get("holder_name", "")
    spoken_acct = digits_to_kannada_words(acct)
    spoken_balance = amount_speak_kn(str(bal))

    write_balance_audit(
        account_number=acct,
        found=True,
        customer_id=row.get("customer_id"),
        kiosk_session_id=kiosk_session_id,
        source=str(row.get("source") or "lookup"),
    )

    return {
        "found": True,
        "account_number": acct,
        "balance_inr": bal,
        "holder_name": name_en,
        "holder_name_kn": name_kn,
        "account_type": row.get("account_type", "Savings"),
        "customer_id": row.get("customer_id"),
        "source": row.get("source"),
        "message_en": (
            f"Account {acct} in the name of {name_en}. "
            f"Your available balance is {bal_str} rupees."
        ),
        "message_kn": (
            f"ಖಾತೆ ಸಂಖ್ಯೆ {spoken_acct}. {name_kn} ಅವರ ಖಾತೆಯಲ್ಲಿ "
            f"ಪ್ರಸ್ತುತ ಲಭ್ಯವಿರುವ ಶಿಲ್ಕು {spoken_balance}."
        ),
    }
