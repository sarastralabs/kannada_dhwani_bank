"""
backend/nlu/keyword_classifier.py

Keyword-matching baseline classifier for banking intent classification.

This is the ZERO-TRAINING baseline used in the project's baseline vs
fine-tuned comparison.  It requires no model download, no GPU, and no
training data — demonstrating what is achievable with pure rule-based
matching before any machine learning is applied.

Design decisions
----------------
Keywords are hand-written domain terms, NOT derived from the training
data.  Deriving keywords automatically (e.g. most frequent words per
class in the 294 training sentences) would let the baseline implicitly
learn from training data, contaminating the comparison.  A human writing
"balance", "loan", "withdraw" with zero knowledge of specific sentences
is the methodologically honest approach — it makes the DistilBERT
improvement look earned, not inflated.

The keyword map is intentionally small and simple: 3–5 high-signal phrases
per intent.  A baroque keyword system with 50 rules per intent would
undermine the comparison story — the baseline should be "dumb" enough to
be clearly worse than a trained model on this domain.

All keywords are imported from this single file.  No intent keyword
appears in any other file in the module.
"""

from __future__ import annotations

from backend.nlu.intents import INTENTS

# ---------------------------------------------------------------------------
# Keyword map
# ---------------------------------------------------------------------------
# Keys MUST be a subset of INTENTS (validated in __init__ below).
# Order within a list does not matter — all are checked for substring match.
# Order of intents in KEYWORD_MAP does not matter — ties are broken by
# position in INTENTS (the shared ordering from intents.py).
#
# Design notes on potential ambiguities:
# - "credit" (deposit_money): rare in deposit context but could appear in
#   interest-rate phrasing ("credit card rate"). Kept because deposit
#   phrasing ("credit my account") is common; the risk is noted.
# - "name" (account_info_query): broad term but in banking context "change
#   my name / update name" is a clear account-info request. Kept as-is.
# - "rate" (interest_rate_query): could theoretically appear in other
#   contexts but banking queries are sufficiently constrained.
# - "apply" is intentionally NOT in open_account to avoid matching
#   "apply for a loan" hitting both apply_loan and open_account.

KEYWORD_MAP: dict[str, list[str]] = {
    "open_account": [
        "open account",
        "new account",
        "create account",
        "start account",
        "savings account",
        "current account",
    ],
    "check_balance": [
        "balance",
        "how much",
        "account balance",
        "funds",
        "available amount",
    ],
    "apply_loan": [
        "loan",
        "apply loan",
        "loan application",
        "borrow",
        "home loan",
        "personal loan",
        "car loan",
        "education loan",
    ],
    "deposit_money": [
        "i want to deposit",
        "deposit cash",
        "deposit money",
        "deposit rupees",
        "deposit amount",
        "put money",
        "add money",
        "credit my account",
        "add funds",
        "cash deposit",
    ],
    "withdraw_money": [
        "withdraw",
        "take out",
        "cash out",
        "debit",
        "cash withdrawal",
        "take money",
    ],
    "account_info_query": [
        "statement",
        "atm",
        "atm card",
        "pin",
        "mobile number",
        "cheque",
        "checkbook",
        "internet banking",
        "update my name",
        "change my name",
        "account number",
        "branch",
        "ifsc",
        "passbook",
    ],
    "interest_rate_query": [
        "interest",
        "interest rate",
        "repayment",
        "emi",
        "fixed deposit",
        "fd rate",
        "loan rate",
    ],
}


class KeywordClassifier:
    """
    Classify a banking query into one of 7 intents using keyword matching.

    No model, no training, no network calls.  Instant inference.

    The classifier is stateless — it holds no mutable state and is safe
    to reuse across calls without re-instantiation.  The singleton cache
    in ``__init__.py`` keeps one instance for the process lifetime.

    Classification logic
    --------------------
    1. Lowercase the input text.
    2. Count how many keywords from each intent's list appear as
       substrings in the lowercased text.
    3. The intent with the **most matches** wins.
    4. Ties are broken by the order intents appear in ``INTENTS``
       (the shared ordering from intents.py) — deterministic, never random.
    5. Confidence = ``match_count / len(keyword_list_for_winner)``
       (fraction of the winner's keywords that fired).
    6. If no keyword matches at all, return ``("account_info_query", 0.0)``
       as the safe fallback (AC-1.2: no crash, no None).

    Notes
    -----
    ``account_info_query`` is the fallback — pipeline treats zero-confidence
    intents as "please clarify" instead of opening a transactional form.
    """

    # INTENTS ordering defines tie-breaking — import from shared registry
    _INTENT_ORDER: list[str] = INTENTS
    _FALLBACK_INTENT: str = "account_info_query"

    def __init__(self) -> None:
        # Validate at construction time that KEYWORD_MAP keys are all
        # recognised intents — catches any drift between the two files.
        unknown = set(KEYWORD_MAP.keys()) - set(INTENTS)
        if unknown:
            raise ValueError(
                f"KEYWORD_MAP contains unknown intents: {unknown}. "
                f"Update intents.py or fix KEYWORD_MAP."
            )

    def classify(self, text: str) -> tuple[str, float]:
        """
        Classify *text* and return ``(intent_label, confidence)``.

        Parameters
        ----------
        text:
            English input string.  May be empty — returns the fallback.

        Returns
        -------
        tuple[str, float]
            ``(intent_label, confidence)`` where confidence is in [0, 1].
            Never returns ``None`` for either element.
        """
        lowered = text.lower()

        # Count keyword matches per intent
        match_counts: dict[str, int] = {}
        for intent, keywords in KEYWORD_MAP.items():
            count = sum(1 for kw in keywords if kw in lowered)
            if count > 0:
                match_counts[intent] = count

        # No matches → safe fallback with zero confidence
        if not match_counts:
            return (self._FALLBACK_INTENT, 0.0)

        # Find the maximum match count
        max_count = max(match_counts.values())

        # Among all intents with max_count matches, pick the one that
        # appears earliest in INTENTS — deterministic tie-breaking
        winner = next(
            intent for intent in self._INTENT_ORDER
            if match_counts.get(intent, 0) == max_count
        )

        confidence = round(max_count / len(KEYWORD_MAP[winner]), 4)
        return (winner, confidence)
