"""Choice answers map to an allowed option — or are re-asked, never saved as junk."""
from __future__ import annotations

import pytest

from backend.forms.extract import CHOICE_OPTIONS, extract_field_value
from backend.forms.validation import CHOICE_RETRY_KN, validate_captured_value


@pytest.mark.parametrize(
    ("english", "kannada", "fid", "want"),
    [
        # Live kiosk case: "ಉಳಿತಾಯ" misheard as "ಉಳಿದಾಯ", translated "Remaining"
        ("Remaining", "ಉಳಿದಾಯ", "account_type", "Savings"),
        ("Savings", "ಉಳಿತಾಯ ಖಾತೆ", "account_type", "Savings"),
        ("Salary", "ವೇತನ", "account_type", "Salary"),
        ("current account", "ಚಾಲ್ತಿ ಖಾತೆ", "account_type", "Current"),
        ("Home Loan", "ಗೃಹ ಸಾಲ", "loan_type", "Home Loan"),
        ("a loan for the vehicle", "ವಾಹನ ಸಾಲ", "loan_type", "Car Loan"),
        ("Cash", "ನಗದು", "deposit_mode", "Cash"),
        ("check", "ಚೆಕ್", "deposit_mode", "Cheque"),
        ("quarterly", "ತ್ರೈಮಾಸಿಕ", "interest_payout", "Quarterly"),
        ("monthly", "ಮಾಸಿಕ", "interest_payout", "Monthly"),
        # Kannada word wins even when the translation drifts
        ("Wages", "ವೇತನ", "account_type", "Salary"),
    ],
)
def test_choice_maps_to_option(english, kannada, fid, want) -> None:
    value = extract_field_value(english, field_type="text", field_id=fid, kannada_text=kannada)
    assert value == want
    assert validate_captured_value(value, field_type="text", field_id=fid) is None


@pytest.mark.parametrize("fid", sorted(CHOICE_RETRY_KN))
def test_unrecognised_choice_is_reasked_not_saved(fid) -> None:
    value = extract_field_value("Remaining", field_type="text", field_id=fid, kannada_text="ಏನೋ ಬೇರೆ")
    assert value == ""
    assert validate_captured_value(value, field_type="text", field_id=fid) == CHOICE_RETRY_KN[fid]


def test_every_extractable_value_passes_validation() -> None:
    # Extraction and validation share one option table — they cannot drift apart.
    from backend.forms import extract as ex

    maps = {"account_type": ex._ACCOUNT_TYPES, "loan_type": ex._LOAN_TYPES,
            "deposit_mode": ex._DEPOSIT_MODES, "interest_payout": ex._INTEREST_PAYOUT}
    for fid, m in maps.items():
        for value in list(m.values()) + list(ex._KN_CHOICES[fid].values()):
            assert value in CHOICE_OPTIONS[fid], (fid, value)


def test_other_fields_unchanged() -> None:
    assert extract_field_value("my name is Ramesh Kumar", field_id="full_name") == "Ramesh Kumar"
    assert extract_field_value("five thousand rupees", field_type="amount", field_id="amount") == "5000"
