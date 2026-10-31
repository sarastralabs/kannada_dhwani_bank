"""Money effects of approving an application: deposits, withdrawals, transfers, loans,
fixed deposits, cheque books, cards, stopped cheques, mobile updates — and the customer summary.

All on a mock MongoDB. Demo account 1234567890 (balance in data/demo_accounts.json) is seeded.
"""

from __future__ import annotations

import mongomock
import pytest

from backend import applications
from backend.db import account_numbers, customers, ledger, store

ACCT = "1234567890"


@pytest.fixture
def db(tmp_path, monkeypatch):
    mock = mongomock.MongoClient()["dhwani_test"]
    monkeypatch.setattr(store, "_get_db", lambda: mock)
    monkeypatch.setattr(store, "_submissions_path", lambda: str(tmp_path / "subs.jsonl"))
    monkeypatch.setenv("BANK_CUSTOMER_STORE", "mongo")
    customers.init_customer_db()
    return mock


def balance(db, number=ACCT) -> float:
    return float(db.accounts.find_one({"account_number": number})["balance_inr"])


def submit(form_id, values):
    return store.save_form_submission(form_id, "ಅರ್ಜಿ", form_id, dict(values), kiosk_session_id="s1")


def approve(form_id, values, **kw):
    return applications.decide(submit(form_id, values)["id"], "approve", admin="admin", **kw)


def open_account(db, mobile="9876543210", name="ರಾಮಕೃಷ್ಣ"):
    done = approve("open_account", {"full_name": name, "mobile_number": mobile, "account_type": "ಉಳಿತಾಯ"})
    return done["decision"]["result"]["account_number"]


# ── Deposit / withdrawal / transfer ──────────────────────────────────────────

def test_deposit_credits_the_account_and_writes_the_ledger(db):
    before = balance(db)
    done = approve("cash_deposit", {"full_name": "x", "account_number": ACCT, "amount": "5,000", "deposit_mode": "cash"})
    assert balance(db) == before + 5000
    assert done["decision"]["result"]["balance_after"] == before + 5000
    row = db.transactions.find_one({"account_number": ACCT, "kind": "deposit"})
    assert row["amount"] == 5000 and row["ref"] == done["ref"] and row["by"] == "admin"


def test_last_four_digits_are_enough_when_they_are_unique(db):
    before = balance(db)
    approve("cash_deposit", {"account_number": ACCT[-4:], "amount": "100"})
    assert balance(db) == before + 100


def test_withdrawal_debits_and_refuses_to_overdraw(db):
    before = balance(db)
    approve("cash_withdrawal", {"account_number": ACCT, "amount": "1000", "purpose": "rent"})
    assert balance(db) == before - 1000
    huge = submit("cash_withdrawal", {"account_number": ACCT, "amount": str(int(before) * 10)})
    with pytest.raises(applications.DecisionError, match="Not enough balance"):
        applications.decide(huge["id"], "approve", admin="admin")
    assert balance(db) == before - 1000  # untouched
    assert store.get_application(huge["id"])["status"] == "submitted"


def test_transfer_between_our_accounts_moves_money_both_ways(db):
    other = open_account(db)
    before = balance(db)
    done = approve("rtgs_neft", {"remitter_name": "x", "remitter_account": ACCT, "beneficiary_account": other, "amount": "2500"})
    assert balance(db) == before - 2500 and balance(db, other) == 2500
    assert done["decision"]["result"]["external"] is False
    kinds = sorted(t["kind"] for t in db.transactions.find({"ref": done["ref"]}))
    assert kinds == ["transfer_in", "transfer_out"]


def test_transfer_to_another_bank_only_debits(db):
    before = balance(db)
    done = approve("rtgs_neft", {"remitter_account": ACCT, "beneficiary_account": "9999999999", "amount": "700"})
    assert balance(db) == before - 700 and done["decision"]["result"]["external"] is True


def test_bad_amounts_are_refused(db):
    for bad in ("", "abc", "0", "-5"):
        app = submit("cash_deposit", {"account_number": ACCT, "amount": bad})
        with pytest.raises(applications.DecisionError):
            applications.decide(app["id"], "approve", admin="admin")


# ── Loans ────────────────────────────────────────────────────────────────────

def test_loan_needs_an_existing_customer(db):
    app = submit("apply_loan", {"full_name": "ಅಪರಿಚಿತ", "mobile_number": "9000000001", "loan_amount": "100000"})
    with pytest.raises(applications.DecisionError, match="Open an account"):
        applications.decide(app["id"], "approve", admin="admin")


def test_loan_is_created_and_paid_into_the_account(db):
    number = open_account(db)
    done = approve("apply_loan", {"full_name": "x", "mobile_number": "9876543210", "loan_type": "personal", "loan_amount": "120000"},
                   terms={"annual_rate_pct": 12, "tenure_months": 12})
    result = done["decision"]["result"]
    assert balance(db, number) == 120000
    assert result["emi_inr"] == pytest.approx(10661.85, abs=0.05)  # 120000 at 12% over 12 months
    loan = db.loans.find_one({"id": result["loan_id"]})
    assert loan["outstanding_inr"] == 120000 and loan["status"] == "active" and loan["application_ref"] == done["ref"]
    assert db.transactions.find_one({"account_number": number, "kind": "loan_disbursal"})["amount"] == 120000


def test_repayments_pay_interest_first_and_close_the_loan(db):
    open_account(db)
    done = approve("apply_loan", {"mobile_number": "9876543210", "loan_amount": "100000"}, terms={"annual_rate_pct": 12, "tenure_months": 12})
    loan_id = done["decision"]["result"]["loan_id"]
    first = ledger.repay_loan(loan_id, 10000, by="admin")
    assert first["interest_part"] == 1000 and first["principal_part"] == 9000 and first["outstanding_after"] == 91000
    assert not first["closed"]
    final = ledger.repay_loan(loan_id, 200000, by="admin")  # more than enough
    assert final["closed"] and db.loans.find_one({"id": loan_id})["status"] == "closed"
    with pytest.raises(ledger.LedgerError):
        ledger.repay_loan(loan_id, 100, by="admin")


def test_emi_formula():
    assert ledger.emi(120000, 12, 12) == pytest.approx(10661.85, abs=0.05)
    assert ledger.emi(12000, 0, 12) == 1000


# ── Fixed deposits, cheque books, cards, stopped cheques, mobile ─────────────

def test_fixed_deposit_locks_money_and_computes_maturity(db):
    before = balance(db)
    done = approve("fixed_deposit", {"account_number": ACCT, "fd_amount": "20000", "tenure": "2 years"})
    result = done["decision"]["result"]
    assert result["tenure_months"] == 24 and balance(db) == before - 20000
    assert result["maturity_inr"] == pytest.approx(20000 * (1 + 0.065 / 4) ** 8, abs=0.5)
    assert db.deposits.find_one({"id": result["deposit_id"]})["status"] == "active"


def test_fixed_deposit_cannot_exceed_the_balance(db):
    app = submit("fixed_deposit", {"account_number": ACCT, "fd_amount": str(int(balance(db)) + 1_000_000), "tenure": "1 year"})
    with pytest.raises(applications.DecisionError, match="Not enough balance"):
        applications.decide(app["id"], "approve", admin="admin")


def test_cheque_book_and_card_are_recorded(db):
    approve("cheque_book_request", {"account_number": ACCT, "number_of_leaves": "50"})
    assert db.service_requests.find_one({"kind": "cheque_book"})["details"]["leaves"] == 50
    done = approve("atm_debit_card", {"account_number": ACCT, "card_type": "Rupay"})
    last4 = done["decision"]["result"]["card_last4"]
    assert len(last4) == 4 and db.service_requests.find_one({"kind": "atm_card"})["details"]["last4"] == last4


def test_a_cheque_can_only_be_stopped_once(db):
    approve("stop_cheque", {"account_number": ACCT, "cheque_number": "000123", "reason": "lost"})
    again = submit("stop_cheque", {"account_number": ACCT, "cheque_number": "000123", "reason": "lost"})
    with pytest.raises(applications.DecisionError, match="already stopped"):
        applications.decide(again["id"], "approve", admin="admin")


def test_mobile_update_checks_the_old_number(db):
    number = open_account(db)
    wrong = submit("mobile_update", {"account_number": number, "old_mobile": "1111111111", "new_mobile": "9123456789"})
    with pytest.raises(applications.DecisionError, match="does not match"):
        applications.decide(wrong["id"], "approve", admin="admin")
    approve("mobile_update", {"account_number": number, "old_mobile": "9876543210", "new_mobile": "9123456789"})
    assert db.customers.find_one({"mobile": "9123456789"}) is not None


# ── Preview ──────────────────────────────────────────────────────────────────

def test_preview_shows_the_effect_or_the_problem_without_changing_anything(db):
    before = balance(db)
    ok = applications.preview(submit("cash_withdrawal", {"account_number": ACCT, "amount": "500"})["id"])
    assert ok["ok"] and "500" in ok["summary"] and balance(db) == before
    bad = applications.preview(submit("cash_withdrawal", {"account_number": "0000000000", "amount": "500"})["id"])
    assert not bad["ok"] and "No active account" in bad["problems"][0]
    loan = applications.preview(submit("apply_loan", {"mobile_number": "9000000009", "loan_amount": "1000"})["id"])
    assert not loan["ok"] and "Open an account" in loan["problems"][0]


# ── Returning customer ───────────────────────────────────────────────────────

def test_a_returning_customer_is_found_by_account_and_mobile_digits(db):
    number = open_account(db)
    approve("cash_deposit", {"account_number": number, "amount": "3000"})
    customer = ledger.identify(number[-4:], "3210")
    assert customer and customer["full_name"] == "ರಾಮಕೃಷ್ಣ"
    assert ledger.identify(number[-4:], "0000") is None  # wrong mobile digits
    assert ledger.identify("0000", "3210") is None


def test_customer_detail_collects_everything(db):
    number = open_account(db)
    approve("cash_deposit", {"account_number": number, "amount": "50000", "mobile_number": "9876543210"})
    approve("apply_loan", {"mobile_number": "9876543210", "loan_amount": "20000"})
    approve("fixed_deposit", {"account_number": number, "fd_amount": "10000", "tenure": "12"})
    cid = db.accounts.find_one({"account_number": number})["customer_id"]
    detail = ledger.customer_detail(cid)
    assert detail["accounts"][0]["balance_inr"] == 50000 + 20000 - 10000
    assert len(detail["loans"]) == 1 and len(detail["deposits"]) == 1
    kinds = {t["kind"] for t in detail["transactions"]}
    assert {"deposit", "loan_disbursal", "fd_open"} <= kinds
    assert {a["ref"] for a in detail["applications"]}  # the applications quoting this mobile or account


def test_new_account_numbers_still_pass_the_check_digit(db):
    assert account_numbers.is_valid(open_account(db))


# ── HTTP: preview, terms, repayment, customer view, limits ──────────────────

@pytest.fixture
def client(db, monkeypatch):
    from fastapi.testclient import TestClient

    from api import admin_auth, ratelimit

    ratelimit.reset()
    monkeypatch.setenv("BANK_ADMIN_USER", "admin")
    monkeypatch.setenv("BANK_ADMIN_PASS", "pw-for-tests")
    import api.main

    c = TestClient(api.main.app)
    c.staff = {"Authorization": "Bearer " + admin_auth.login("admin", "pw-for-tests")["token"]}
    return c


def test_staff_see_a_preview_then_decide_with_loan_terms(client, db):
    number = open_account(db)
    app = submit("apply_loan", {"mobile_number": "9876543210", "loan_amount": "50000", "loan_type": "personal"})
    peek = client.get(f"/api/admin/applications/{app['id']}/preview", headers=client.staff).json()
    assert peek["ok"] and peek["details"]["tenure_months"] == 36 and "EMI" in peek["summary"]
    assert balance(db, number) == 0  # a preview changes nothing
    done = client.post(f"/api/admin/applications/{app['id']}/decision", headers=client.staff,
                       json={"action": "approve", "terms": {"amount": 40000, "annual_rate_pct": 9, "tenure_months": 24}})
    assert done.status_code == 200 and done.json()["decision"]["result"]["amount"] == 40000
    assert balance(db, number) == 40000


def test_a_refused_decision_explains_why_over_http(client, db):
    app = submit("cash_withdrawal", {"account_number": ACCT, "amount": "99999999"})
    res = client.post(f"/api/admin/applications/{app['id']}/decision", headers=client.staff, json={"action": "approve"})
    assert res.status_code == 409 and "Not enough balance" in res.json()["detail"]


def test_loan_repayment_and_customer_detail_over_http(client, db):
    number = open_account(db)
    done = approve("apply_loan", {"mobile_number": "9876543210", "loan_amount": "100000"}, terms={"annual_rate_pct": 12, "tenure_months": 12})
    loan_id = done["decision"]["result"]["loan_id"]
    paid = client.post(f"/api/admin/loans/{loan_id}/repayment", headers=client.staff, json={"amount": 10000})
    assert paid.status_code == 200 and paid.json()["outstanding_after"] == 91000
    cid = db.accounts.find_one({"account_number": number})["customer_id"]
    detail = client.get(f"/api/admin/customers/{cid}", headers=client.staff).json()
    assert detail["loans"][0]["outstanding_inr"] == 91000
    assert client.get(f"/api/admin/customers/{cid}").status_code == 401  # staff only
    assert client.post(f"/api/admin/loans/{loan_id}/repayment", json={"amount": 5}).status_code == 401
    csv_ = client.get("/api/admin/export/transactions.csv", headers=client.staff)
    assert csv_.status_code == 200 and "loan_disbursal" in csv_.text


def test_customer_summary_needs_both_sets_of_digits(client, db):
    number = open_account(db)
    approve("cash_deposit", {"account_number": number, "amount": "4000"})
    ok = client.get("/api/customer/summary", params={"account_last4": number[-4:], "mobile_last4": "3210"})
    assert ok.status_code == 200
    body = ok.json()
    assert body["accounts"][0]["balance_inr"] == 4000 and body["accounts"][0]["last4"] == number[-4:]
    assert number not in str(body)  # the full account number is never handed out
    assert "ಶಿಲ್ಕು" in body["message_kn"]
    assert client.get("/api/customer/summary", params={"account_last4": number[-4:], "mobile_last4": "0000"}).status_code == 404
    assert client.get("/api/customer/summary", params={"account_last4": "0000", "mobile_last4": "3210"}).status_code == 404


def test_customer_summary_is_rate_limited(client, db, monkeypatch):
    monkeypatch.setenv("BANK_LOOKUP_PER_MIN", "2")
    codes = [client.get("/api/customer/summary", params={"account_last4": "1234", "mobile_last4": f"000{i}"}).status_code for i in range(4)]
    assert codes == [404, 404, 429, 429]


def test_speech_reaches_the_account_details_form():
    from api import forms_catalog
    from backend.forms.form_menu import _menu_forms, match_form_from_speech

    assert match_form_from_speech("", "show my account details") == "my_account"
    assert match_form_from_speech("ನನ್ನ ಸಾಲ ಎಷ್ಟು", "") == "my_account"
    assert [f["id"] for f in forms_catalog.get_form("my_account")["fields"]] == ["account_last4", "mobile_last4"]
    assert "my_account" not in [f["id"] for f in _menu_forms()]
