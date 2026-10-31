"""Kannada keyword hints: repayment questions must not route to apply_loan."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from backend.nlu.kannada_keywords import match_kannada_intent  # noqa: E402


@pytest.mark.parametrize(
    ("kannada", "english"),
    [
        ("ಸಾಲದ ಮರುಪಾವತಿ ಮೊತ್ತ ಎಷ್ಟು?", "How much is the loan repayment amount?"),
        # Real STT output for clip_014 (trailing word half-heard)
        ("ಲೋನ್ ಮರುಪಾವತಿ ಎಸ್", "Loan repayment S"),
        ("", "How do I repay my home loan"),
    ],
)
def test_repayment_routes_to_interest_rate_query(kannada: str, english: str) -> None:
    hit = match_kannada_intent(kannada, english)
    assert hit is not None
    assert hit[0] == "interest_rate_query"


@pytest.mark.parametrize(
    ("kannada", "english"),
    [
        ("ಸಾಲ ಬೇಕು", "I want a loan"),
        ("ಸಾಲ ಅರ್ಜಿ ಹೇಗೆ ಮಾಡಬೇಕು", "How to apply for a loan"),
        ("", "I want a home loan"),
    ],
)
def test_loan_requests_still_route_to_apply_loan(kannada: str, english: str) -> None:
    hit = match_kannada_intent(kannada, english)
    assert hit is not None
    assert hit[0] == "apply_loan"


def test_repayment_answer_is_repayment_info_not_full_rate_list() -> None:
    from backend.decision_router import route

    out = route(
        "interest_rate_query",
        "Loan repayment S",
        kannada_text="ಲೋನ್ ಮರುಪಾವತಿ ಎಸ್",
    )
    assert out["route"] == "informational"
    assert out["response_text"].startswith("Loan repayment amount")
    assert "ಮರುಪಾವತಿ" in out["response_text_kn"]

    # Plain rate question still gets the full list.
    rates = route("interest_rate_query", "What are your interest rates?")
    assert rates["response_text"].startswith("Here are our current interest rates")


@pytest.mark.parametrize(
    "kannada",
    [
        "ನನ್ನ ಖಾತೆ ಎಷ್ಟಿದೆ",  # live misroute: was opening the account form
        "ಖಾತೆಯಲ್ಲಿ ಎಷ್ಟು ಹಣ ಇದೆ",
        "ನನ್ನ ಖಾತೆಯ ಬಾಕಿ ಎಷ್ಟಿದೆ",
        "ಬಾಕಿ ಎಷ್ಟು",
    ],
)
def test_balance_questions_are_not_account_opening(kannada: str) -> None:
    hit = match_kannada_intent(kannada, "")
    assert hit is not None
    assert hit[0] == "check_balance"


@pytest.mark.parametrize(
    "kannada",
    [
        "ನಾನು ಹೊಸ ಖಾತೆ ತೆರೆಯಬೇಕು",
        "ನನ್ನ ಖಾತೆ ತೆರೆಯಬ",  # STT-truncated form seen in logs
        "ಸೇವಿಂಗ್ಸ್ ಖಾತೆ ಬೇಕು",
        "ಖಾತೆ ತೆಗೆಯಬೇಕು",
    ],
)
def test_open_account_phrases_still_open_account(kannada: str) -> None:
    hit = match_kannada_intent(kannada, "")
    assert hit is not None
    assert hit[0] == "open_account"


def test_bare_account_word_no_longer_forces_open_account() -> None:
    # Left to the trained model instead of a 0.71 keyword override.
    hit = match_kannada_intent("ನನ್ನ ಖಾತೆ", "")
    assert hit is None or hit[0] != "open_account"


def test_interest_how_much_is_not_balance() -> None:
    hit = match_kannada_intent("ಬಡ್ಡಿ ದರ ಎಷ್ಟಿದೆ", "")
    assert hit is not None
    assert hit[0] == "interest_rate_query"
