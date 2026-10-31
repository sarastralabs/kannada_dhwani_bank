"""Application workflow: reference numbers, staff decisions, account opening, status check.

Runs against the local stores (sqlite + jsonl) and against a mock MongoDB, which is what
the live site uses.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from api import admin_auth, ratelimit
from backend import applications
from backend.db import account_numbers, customers, store

OPEN_ACCOUNT = {
    "full_name": "ರಾಮಕೃಷ್ಣ ಹೆಗಡೆ",
    "date_of_birth": "21/06/1990",
    "address": "ಮೈಸೂರು",
    "mobile_number": "9876543210",
    "account_type": "ಉಳಿತಾಯ",
    "date": "31/10/2026",
}


@pytest.fixture(params=["local", "mongo"])
def backend(request, tmp_path, monkeypatch):
    """The same tests on the local files and on a (mock) MongoDB."""
    monkeypatch.setattr(store, "_submissions_path", lambda: str(tmp_path / "subs.jsonl"))
    monkeypatch.setenv("BANK_CUSTOMER_DB_PATH", str(tmp_path / "cust.db"))
    if request.param == "mongo":
        import mongomock

        db = mongomock.MongoClient()["dhwani_test"]
        monkeypatch.setattr(store, "_get_db", lambda: db)
        monkeypatch.setenv("BANK_CUSTOMER_STORE", "mongo")
    else:
        monkeypatch.setattr(store, "_get_db", lambda: None)
        monkeypatch.setenv("BANK_CUSTOMER_STORE", "sqlite")
    customers.init_customer_db()
    return request.param


def submit(form_id="open_account", values=None):
    return store.save_form_submission(form_id, "ಖಾತೆ", "Account", dict(values or OPEN_ACCOUNT), kiosk_session_id="s1")


def test_references_are_sequential(backend):
    a, b = submit(), submit()
    assert re.fullmatch(r"DH-\d\d-000001", a["ref"])
    assert b["ref"].endswith("000002")
    assert a["status"] == "submitted"


def test_approving_opens_a_working_account(backend):
    app = submit()
    done = applications.decide(app["id"], "approve", admin="admin")
    assert done["status"] == "approved"
    result = done["decision"]["result"]
    number = result["account_number"]
    assert account_numbers.is_valid(number)  # carries a correct check digit
    record = customers.get_account_balance(number)
    assert record and record["holder_name"] == OPEN_ACCOUNT["full_name"]
    assert record["balance_inr"] == 0 and record["account_type"] == "Savings"
    # and it is findable the way the kiosk finds accounts: by the last 4 digits
    assert any(r["account_number"] == number for r in customers.get_account_by_last4(number[-4:]))
    assert done["decision"]["by"] == "admin"


def test_a_decision_can_only_be_made_once(backend):
    app = submit()
    applications.decide(app["id"], "approve", admin="admin")
    with pytest.raises(applications.DecisionError):
        applications.decide(app["id"], "approve", admin="admin")  # would open a second account
    with pytest.raises(applications.DecisionError):
        applications.decide(app["id"], "reject", admin="admin", note="late")
    assert len([c for c in customers.list_customers(limit=500) if c["holder_name"] == OPEN_ACCOUNT["full_name"]]) == 1


def test_rejecting_needs_a_message_for_the_customer(backend):
    app = submit()
    with pytest.raises(applications.DecisionError):
        applications.decide(app["id"], "reject", admin="admin", note="  ")
    done = applications.decide(app["id"], "reject", admin="admin", note="ದಾಖಲೆಗಳು ಇಲ್ಲ")
    assert done["status"] == "rejected" and done["decision"]["note"] == "ದಾಖಲೆಗಳು ಇಲ್ಲ"
    assert not [c for c in customers.list_customers(limit=500) if c["holder_name"] == OPEN_ACCOUNT["full_name"]]


def test_needs_info_can_still_be_decided_later(backend):
    app = submit()
    applications.decide(app["id"], "needs_info", admin="admin", note="ಆಧಾರ್ ತನ್ನಿ")
    assert store.get_application(app["id"])["status"] == "needs_info"
    assert applications.decide(app["id"], "approve", admin="admin")["status"] == "approved"


def test_same_mobile_adds_an_account_to_the_existing_customer(backend):
    first = applications.decide(submit()["id"], "approve", admin="admin")
    second = applications.decide(submit()["id"], "approve", admin="admin")
    r1, r2 = first["decision"]["result"], second["decision"]["result"]
    assert r2["existing_customer"] is True and r1["customer_id"] == r2["customer_id"]
    assert r1["account_number"] != r2["account_number"]


def test_other_forms_are_approved_without_side_effects(backend):
    app = submit("cheque_book_request", {"full_name": "ರಾಮ", "account_number": "1234567890", "number_of_leaves": "25"})
    done = applications.decide(app["id"], "approve", admin="admin")
    assert done["status"] == "approved" and done["decision"]["result"] == {}


def test_status_check_needs_the_right_mobile_digits(backend):
    app = submit()
    ref = app["ref"]
    assert applications.public_status(ref, "")is None
    assert applications.public_status(ref, "1111") is None
    assert applications.public_status("DH-26-999999", "3210") is None  # unknown looks the same
    pending = applications.public_status(ref, "3210")
    assert pending["status"] == "submitted" and "account_number" not in pending

    applications.decide(app["id"], "approve", admin="admin")
    approved = applications.public_status(ref.lower(), "3210")
    assert approved["status"] == "approved"
    assert account_numbers.is_valid(approved["account_number"])
    assert approved["status_kn"]


def test_status_without_a_mobile_field_needs_only_the_number(backend):
    app = submit("cheque_book_request", {"full_name": "ರಾಮ", "account_number": "1234567890", "number_of_leaves": "25"})
    assert applications.public_status(app["ref"], "")["status"] == "submitted"


# ── HTTP layer ──────────────────────────────────────────────────────────────

@pytest.fixture
def client(backend, monkeypatch):
    ratelimit.reset()
    monkeypatch.setenv("BANK_ADMIN_USER", "admin")
    monkeypatch.setenv("BANK_ADMIN_PASS", "pw-for-tests")
    import api.main

    token = admin_auth.login("admin", "pw-for-tests")["token"]
    c = TestClient(api.main.app)
    c.headers_admin = {"Authorization": f"Bearer {token}"}
    return c


def test_staff_can_decide_over_http_and_customers_cannot(client):
    app = submit()
    path = f"/api/admin/applications/{app['id']}/decision"
    assert client.post(path, json={"action": "approve"}).status_code == 401  # no staff login
    ok = client.post(path, json={"action": "approve"}, headers=client.headers_admin)
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    again = client.post(path, json={"action": "approve"}, headers=client.headers_admin)
    assert again.status_code == 409
    assert client.post("/api/admin/applications/nope/decision", json={"action": "approve"}, headers=client.headers_admin).status_code == 404


def test_public_status_over_http_hides_wrong_guesses(client):
    app = submit()
    ok = client.get("/api/applications/status", params={"ref": app["ref"], "mobile_last4": "3210"})
    assert ok.status_code == 200 and ok.json()["ref"] == app["ref"]
    assert client.get("/api/applications/status", params={"ref": app["ref"], "mobile_last4": "0000"}).status_code == 404


def test_status_lookups_are_rate_limited(client, monkeypatch):
    monkeypatch.setenv("BANK_LOOKUP_PER_MIN", "3")
    codes = [client.get("/api/applications/status", params={"ref": "DH-26-000001", "mobile_last4": str(i)}).status_code for i in range(5)]
    assert codes[:3] == [404, 404, 404] and codes[3:] == [429, 429]


def test_check_digit_rejects_misheard_numbers():
    good = account_numbers.new_account_number()
    assert account_numbers.is_valid(good)
    for pos in range(10):  # any single wrong digit is caught
        wrong = str((int(good[pos]) + 1) % 10)
        assert not account_numbers.is_valid(good[:pos] + wrong + good[pos + 1:])


def test_spoken_digits_find_the_application_and_a_sentence_is_ready_to_read(backend):
    app = submit()
    applications.decide(app["id"], "approve", admin="admin")
    spoken = re.sub(r"\D", "", app["ref"])  # the customer says "2 6 0 0 0 0 0 1"
    assert applications.normalize_ref(spoken) == app["ref"]
    assert applications.normalize_ref(app["ref"].lower()) == app["ref"]
    info = applications.public_status(spoken, "3210")
    number = info["account_number"]
    assert " ".join(number) in info["message_kn"]  # digits are read one by one
    assert "ಅನುಮೋದಿಸ" in info["message_kn"]


def test_rejection_message_is_read_to_the_customer(backend):
    app = submit()
    applications.decide(app["id"], "reject", admin="admin", note="ದಾಖಲೆ ತನ್ನಿ")
    assert "ದಾಖಲೆ ತನ್ನಿ" in applications.public_status(app["ref"], "3210")["message_kn"]


def test_speaking_about_an_application_reaches_the_status_form():
    from backend.forms.form_menu import match_form_from_speech, _menu_forms
    from api import forms_catalog

    assert match_form_from_speech("", "what is my application status") == "application_status"
    assert match_form_from_speech("ನನ್ನ ಅರ್ಜಿ ಸ್ಥಿತಿ ಏನು", "") == "application_status"
    assert match_form_from_speech("", "open account") == "open_account"
    form = forms_catalog.get_form("application_status")
    assert [f["id"] for f in form["fields"]] == ["application_number", "mobile_last4"]
    assert "application_status" not in [f["id"] for f in _menu_forms()]  # an enquiry, not an application
