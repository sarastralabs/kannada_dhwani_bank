"""Conversation repair: clarification intent resolution."""

from backend.nlu.clarification import build_clarification, resolve_clarified_intent


def test_build_clarification_progressive():
    top = [("check_balance", 0.3), ("withdraw_money", 0.28)]
    en0, _ = build_clarification(top, attempt=0)
    en1, _ = build_clarification(top, attempt=1)
    en2, _ = build_clarification(top, attempt=2)
    assert "Did you mean" in en0
    assert "one choice" in en1
    assert "one service clearly" in en2


def test_resolve_clarified_intent_picks_balance():
    picked = resolve_clarified_intent(
        ["check_balance", "withdraw_money"],
        "",
        "yes check my balance",
    )
    assert picked is not None
    assert picked[0] == "check_balance"


def test_resolve_clarified_intent_picks_loan():
    picked = resolve_clarified_intent(
        ["apply_loan", "open_account"],
        "",
        "I want a home loan",
    )
    assert picked is not None
    assert picked[0] == "apply_loan"
