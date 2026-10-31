"""
backend/nlu/intents.py

Single source of truth for all 7 banking intent labels.

Every file in the NLU module that needs intent labels — the keyword
baseline, the DistilBERT classifier, the training script, and the
evaluation script — imports from HERE.  No intent string is hardcoded
anywhere else.  This eliminates the class-of-bug where the baseline and
fine-tuned model silently evaluate against different label sets due to
a typo or ordering difference in a per-file copy of the list.

Downstream usage
----------------
    from backend.nlu.intents import INTENTS, LABEL2ID, ID2LABEL, NUM_CLASSES

    # Keyword baseline: iterate INTENTS to build KEYWORD_MAP keys
    # DistilBERT:       pass id2label=ID2LABEL, label2id=LABEL2ID to from_pretrained
    # Training loop:    use NUM_CLASSES as the num_labels argument
    # Evaluation:       use INTENTS as confusion matrix axis labels
"""

# ---------------------------------------------------------------------------
# Intent registry — the ONE place intent labels are defined
# ---------------------------------------------------------------------------
# Order is fixed and matters: DistilBERT's id2label mapping uses this order,
# and sklearn's confusion matrix rows/columns follow it.
# Do not reorder without regenerating the trained checkpoint.

INTENTS: list[str] = [
    "open_account",
    "check_balance",
    "apply_loan",
    "deposit_money",
    "withdraw_money",
    "account_info_query",
    "interest_rate_query",
]

# Derived constants — computed once, imported everywhere
LABEL2ID: dict[str, int] = {label: i for i, label in enumerate(INTENTS)}
ID2LABEL: dict[int, str] = {i: label for i, label in enumerate(INTENTS)}
NUM_CLASSES: int = len(INTENTS)

# ---------------------------------------------------------------------------
# Validation helper — used by dataset.py and train.py to catch bad labels
# early, before they corrupt training or evaluation silently
# ---------------------------------------------------------------------------
VALID_INTENT_SET: frozenset[str] = frozenset(INTENTS)


def validate_intent(label: str) -> None:
    """
    Raise ``ValueError`` if *label* is not a recognised intent.

    Call this when loading training data so a typo in the JSON is caught
    at load time, not during training where it would produce a confusing
    index-out-of-range error.

    Parameters
    ----------
    label:
        Intent label string to check.

    Raises
    ------
    ValueError
        If *label* is not in :data:`VALID_INTENT_SET`.
    """
    if label not in VALID_INTENT_SET:
        raise ValueError(
            f"Unknown intent label '{label}'. "
            f"Valid labels are: {sorted(VALID_INTENT_SET)}"
        )
