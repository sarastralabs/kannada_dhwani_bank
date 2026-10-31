"""Model-independent tests for spoken numeric capture and validation."""

import pytest

from backend.forms.date_kn import extract_date_from_kannada
from backend.forms.extract import extract_field_value
from backend.forms.kannada_digits import extract_digits_from_kannada
from backend.forms.validation import validate_captured_value
from backend.forms.stt_tuning import plausible_digit_capture


def test_extracts_native_and_spoken_digits() -> None:
    assert extract_digits_from_kannada("೧೨೩೪೫೬೭೮೯೦") == "1234567890"
    assert (
        extract_digits_from_kannada(
            "ಒಂದು ಎರಡು ಮೂರು ನಾಲ್ಕು ಐದು ಆರು ಏಳು ಎಂಟು ಒಂಬತ್ತು ಸೊನ್ನೆ"
        )
        == "1234567890"
    )


def test_extracts_spoken_number_groups() -> None:
    assert extract_digits_from_kannada("ಹನ್ನೆರಡು ಮೂವತ್ತನಾಲ್ಕು") == "1234"
    assert extract_digits_from_kannada("twenty five ten") == "2510"


def test_mobile_and_account_validation() -> None:
    assert (
        validate_captured_value(
            "9876543210",
            field_type="digits",
            field_id="mobile_number",
        )
        is None
    )
    assert validate_captured_value(
        "98765",
        field_type="digits",
        field_id="mobile_number",
    )
    assert (
        validate_captured_value(
            "1234567890",
            field_type="digits",
            field_id="account_number",
        )
        is None
    )
    assert validate_captured_value(
        "12345678",
        field_type="digits",
        field_id="account_number",
    )
    assert validate_captured_value(
        "12345",
        field_type="digits",
        field_id="account_number",
    )
    # Last-4 shortcut: 4 digits are accepted and resolved via account lookup.
    assert (
        validate_captured_value(
            "1234",
            field_type="digits",
            field_id="account_number",
        )
        is None
    )


def test_cheque_leaf_choices_are_constrained() -> None:
    assert (
        validate_captured_value(
            "25",
            field_type="digits",
            field_id="number_of_leaves",
        )
        is None
    )
    assert validate_captured_value(
        "30",
        field_type="digits",
        field_id="number_of_leaves",
    )


def test_extracts_numeric_and_spoken_kannada_dates() -> None:
    assert extract_date_from_kannada("21 06 2005") == "21/06/2005"
    assert extract_date_from_kannada("ನಾನು ಹೇಳಿದ್ದು 21 06 2005") == "21/06/2005"
    assert (
        extract_date_from_kannada("ಇಪ್ಪತ್ತೊಂದು ಆರು ಎರಡು ಸಾವಿರ ಐದು")
        == "21/06/2005"
    )


def test_date_validation_rejects_garbage_and_impossible_dates() -> None:
    assert (
        validate_captured_value(
            "21/06/2005",
            field_type="date",
            field_id="date_of_birth",
        )
        is None
    )
    assert validate_captured_value(
        "British ten three thousand and eighteen",
        field_type="date",
        field_id="date_of_birth",
    )
    assert validate_captured_value(
        "31/02/2005",
        field_type="date",
        field_id="date_of_birth",
    )


def test_mobile_capture_requires_all_ten_digits() -> None:
    assert not plausible_digit_capture("11", "mobile_number")
    assert plausible_digit_capture("9741447767", "mobile_number")
    assert not plausible_digit_capture("123456789", "account_number")
    assert plausible_digit_capture("1234567890", "account_number")


def test_account_capture_accepts_last4_and_last6() -> None:
    # Customers give the last 4 (or 6 if ambiguous) — not a reason for a numeric retry.
    assert plausible_digit_capture("7890", "account_number")
    assert plausible_digit_capture("222233", "account_number")
    assert not plausible_digit_capture("78900", "account_number")


def test_form_stt_hints_are_short_and_length_neutral() -> None:
    from backend.forms.stt_tuning import form_fill_stt_hints

    acct_prompt, _ = form_fill_stt_hints("digits", "account_number")
    assert "10" not in acct_prompt and "ಸೊನ್ನೆ ಇರಬಹುದು" not in acct_prompt
    name_prompt, name_hot = form_fill_stt_hints("text", "full_name")
    assert name_prompt and len(name_prompt) < 40 and name_hot is None
    for ftype, fid in (("text", "address"), ("amount", "amount"), ("text", "confirm")):
        prompt, hot = form_fill_stt_hints(ftype, fid)
        assert prompt and len(prompt) < 60 and hot is None


@pytest.mark.parametrize(
    ("spoken", "date"),
    [
        ("twenty one six two thousand five", "21/06/2005"),  # was read as 20/07/2005
        ("thirty one twelve two thousand", "31/12/2000"),
        ("twenty two two two thousand five", "22/02/2005"),
        ("twenty ten two thousand three", "20/10/2003"),       # "twenty" alone is the day
        ("twenty five twelve nineteen ninety five", "25/12/1995"),
        ("fifteen eight two thousand ten", "15/08/2010"),
    ],
)
def test_english_word_dates_with_two_word_days(spoken: str, date: str) -> None:
    assert extract_field_value(spoken, "date", "date_of_birth") == date
