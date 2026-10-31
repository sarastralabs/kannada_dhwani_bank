"""Names and addresses are kept as spoken (English letters), never translated."""

from __future__ import annotations

import pytest

from backend.forms.as_spoken import (
    as_spoken_value,
    clean_spoken,
    is_as_spoken_field,
    transliterate_kannada,
)
from backend.forms.extract import extract_field_value


@pytest.mark.parametrize(
    ("kannada", "expected"),
    [
        ("ಅಶ್ವಿನ್", "Ashwin"),            # ವ joined to a consonant → w
        ("ಬಂಟ್ವಾಳ", "Bantwala"),         # ಂ before ಟ → n
        ("ಮಂಗಳೂರು", "Mangaluru"),
        ("ಸಂಪತ್ ಕುಮಾರ್", "Sampat Kumar"),  # ಂ before ಪ → m
        ("ಸ್ವಾಮಿ", "Swami"),
        ("ರಮೇಶ್ ಕುಮಾರ್", "Ramesh Kumar"),
        ("ಮನೆ ಸಂಖ್ಯೆ ೧೨", "Mane Sankhye 12"),
        ("Ashwin", "Ashwin"),              # already English letters
    ],
)
def test_transliteration(kannada: str, expected: str) -> None:
    assert transliterate_kannada(kannada) == expected


@pytest.mark.parametrize(
    ("heard", "value", "spoken_kn"),
    [
        ("ನನ್ನ ಹೆಸರು ಅಶ್ವಿನ್", "Ashwin", "ಅಶ್ವಿನ್"),
        ("ಅಶ್ವಿನ್ ಅಂತ", "Ashwin", "ಅಶ್ವಿನ್"),
        ("ನನ್ನ ವಿಳಾಸ ಬಂಟ್ವಾಳ.", "Bantwala", "ಬಂಟ್ವಾಳ"),
        ("my name is Ashwin", "Ashwin", "Ashwin"),
    ],
)
def test_lead_ins_and_endings_are_dropped(heard: str, value: str, spoken_kn: str) -> None:
    assert as_spoken_value(heard) == value
    assert clean_spoken(heard) == spoken_kn


def test_which_fields_are_kept_as_spoken() -> None:
    for fid in ("full_name", "beneficiary_name", "remitter_name", "address", "branch_address"):
        assert is_as_spoken_field(fid)
    for fid in ("purpose", "remarks", "account_type", "mobile_number", "amount"):
        assert not is_as_spoken_field(fid)


def test_names_and_addresses_ignore_the_translation() -> None:
    # The real failures from kiosk testing: translation turned these into English words.
    assert extract_field_value("Be Aware", "text", "full_name", kannada_text="ಅಶ್ವಿನ್") == "Ashwin"
    assert (
        extract_field_value("We've come to", "text", "address", kannada_text="ಬಂಟ್ವಾಳ")
        == "Bantwala"
    )


def test_other_fields_still_use_the_translation() -> None:
    assert extract_field_value("personal use", "text", "purpose", kannada_text="ವೈಯಕ್ತಿಕ ಬಳಕೆ") == "Personal use"
    assert extract_field_value("Savings", "text", "account_type", kannada_text="ಉಳಿತಾಯ") == "Savings"


def test_without_kannada_falls_back_to_the_english_rules() -> None:
    assert extract_field_value("My name is Ramesh", "text", "full_name") == "Ramesh"


@pytest.mark.parametrize(
    ("english", "kannada", "rupees"),
    [
        ("10 lakh.", "10 ಲಕ್ಷ.", "1000000"),       # was read as ₹10
        ("1 million", "10 ಲಕ್ಷ", "1000000"),       # translation said "million"
        ("2.5 lakh", "2.5 ಲಕ್ಷ", "250000"),
        ("2 lakh 50 thousand", "2 ಲಕ್ಷ 50 ಸಾವಿರ", "250000"),
        ("3 lakh 500", "3 ಲಕ್ಷ 500", "300500"),
        ("5 thousand", "5 ಸಾವಿರ", "5000"),
        ("1 crore", "1 ಕೋಟಿ", "10000000"),
        ("ten lakh", "ಹತ್ತು ಲಕ್ಷ", "1000000"),
        ("Rs 50,000", "50,000", "50000"),
        ("500", "೫೦೦", "500"),
    ],
)
def test_amount_with_lakh_and_thousand(english: str, kannada: str, rupees: str) -> None:
    assert extract_field_value(english, "amount", "loan_amount", kannada_text=kannada) == rupees
