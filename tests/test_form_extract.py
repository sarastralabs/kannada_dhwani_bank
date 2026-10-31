"""Unit tests for offline form field extractors (no models required)."""

from backend.forms.extract import extract_field_value
from backend.forms.intent_map import form_id_for_intent


def test_extract_name():
    assert extract_field_value("My name is Ramesh Kumar", "text", "full_name") == "Ramesh Kumar"
    assert extract_field_value("I am Priya", "text", "full_name") == "Priya"


def test_extract_amount():
    assert extract_field_value("five thousand", "amount", "amount") == "5000"
    assert extract_field_value("The amount is 50,000 rupees", "amount", "loan_amount") == "50000"
    assert extract_field_value("two lakh", "amount", "income") == "200000"


def test_extract_digits():
    assert extract_field_value("one two three four five", "digits", "account_number") == "12345"
    assert extract_field_value("Account number is 99887766", "digits", "account_number") == "99887766"


def test_extract_choices():
    assert extract_field_value("savings account", "text", "account_type") == "Savings"
    assert extract_field_value("I want a home loan", "text", "loan_type") == "Home Loan"
    assert extract_field_value("cash", "text", "deposit_mode") == "Cash"


def test_extract_date_today():
    out = extract_field_value("today", "date", "date")
    assert "/" in out and len(out) >= 8


def test_extract_mobile_ifsc_pan():
    assert extract_field_value(
        "nine eight seven six five four three two one zero", "digits", "mobile_number"
    ) == "9876543210"
    assert extract_field_value("SBIN0001234", "text", "beneficiary_ifsc") == "SBIN0001234"
    assert extract_field_value("ABCDE1234F", "text", "pan") == "ABCDE1234F"


def test_extract_cheque_leaves_and_card():
    assert extract_field_value("twenty five leaves", "digits", "number_of_leaves") == "25"
    assert extract_field_value("debit card please", "text", "card_type") == "ATM / Debit Card"


def test_intent_map():
    assert form_id_for_intent("apply_loan") == "apply_loan"
    assert form_id_for_intent("withdraw_money") == "cash_withdrawal"
    assert form_id_for_intent("check_balance") == "balance_inquiry"
