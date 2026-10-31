"""Tests for Kannada form read-back summaries."""

from __future__ import annotations

from backend.forms.summary_kn import (
    amount_speak_kn,
    build_form_summary_kn,
    digits_to_kannada_words,
    mask_account,
)


def _withdrawal_form() -> dict:
    return {
        "id": "cash_withdrawal",
        "title_kn": "ನಗದು ಹಿಂಪಡೆಯುವ ಚೀಟಿ",
        "fields": [
            {
                "id": "full_name",
                "label_kn": "ಖಾತೆದಾರರ ಹೆಸರು",
                "type": "text",
                "required": True,
            },
            {
                "id": "account_number",
                "label_kn": "ಖಾತೆ ಸಂಖ್ಯೆ",
                "type": "digits",
                "required": True,
            },
            {
                "id": "amount",
                "label_kn": "ಮೊತ್ತ",
                "type": "amount",
                "required": True,
            },
            {
                "id": "date",
                "label_kn": "ದಿನಾಂಕ",
                "type": "date",
                "required": True,
                "auto": "today",
            },
        ],
    }


def test_mask_account():
    assert mask_account("1234567890") == "••••••7890"
    assert mask_account("1234") == "1234"


def test_digits_to_kannada_words():
    spoken = digits_to_kannada_words("1234")
    assert "ಒಂದು" in spoken
    assert "ಎರಡು" in spoken


def test_amount_speak_kn():
    assert "ಸಾವಿರ" in amount_speak_kn("5000")
    assert "ರೂಪಾಯಿ" in amount_speak_kn("5000")
    assert amount_speak_kn("11") == "ಹನ್ನೊಂದು ರೂಪಾಯಿ"
    assert amount_speak_kn("18") == "ಹದಿನೆಂಟು ರೂಪಾಯಿ"
    assert amount_speak_kn("25") == "ಇಪ್ಪತ್ತೈದು ರೂಪಾಯಿ"
    assert amount_speak_kn("80") == "ಎಂಬತ್ತು ರೂಪಾಯಿ"
    assert amount_speak_kn("125") == "ನೂರ ಇಪ್ಪತ್ತೈದು ರೂಪಾಯಿ"
    assert amount_speak_kn("125000") == "ಒಂದು ಲಕ್ಷ ಇಪ್ಪತ್ತೈದು ಸಾವಿರ ರೂಪಾಯಿ"


def test_build_form_summary_kn():
    payload = build_form_summary_kn(
        _withdrawal_form(),
        {
            "full_name": "ರಾಮೇಶ್ ಕುಮಾರ್",
            "account_number": "1234567890",
            "amount": "5000",
            "date": "01/09/2026",
        },
    )
    assert payload["form_id"] == "cash_withdrawal"
    assert "ನಿಮ್ಮ ಅರ್ಜಿಯ ಸಾರಾಂಶ" in payload["summary_kn"]
    assert "ವಿವರಗಳು ಸರಿಯಾಗಿವೆಯೇ" in payload["summary_kn"]
    assert payload["confirm_prompt_kn"]
    assert len(payload["lines"]) == 3
    acct_line = next(l for l in payload["lines"] if l["field_id"] == "account_number")
    assert acct_line["display_kn"].endswith("7890")
    assert "ಒಂದು" in acct_line["speak_kn"]


def test_summary_truncates_very_long_forms():
    from backend.forms.summary_kn import _truncate_summary_kn

    long_text = "word " * 400
    out = _truncate_summary_kn(long_text)
    assert len(out) <= 1300
    assert "ಹೆಚ್ಚಿನ ವಿವರಗಳು" in out
