"""Server-side validation for persisted voice form submissions."""

import pytest
from fastapi import HTTPException

from api import forms_catalog
from api.routes import forms as form_routes


def test_rejects_unknown_and_missing_fields() -> None:
    form = forms_catalog.get_form("balance_inquiry")
    assert form is not None

    with pytest.raises(HTTPException) as unknown:
        form_routes._validate_submission(
            form,
            {"account_number": "1234567890", "unexpected": "value"},
        )
    assert unknown.value.status_code == 422

    with pytest.raises(HTTPException) as missing:
        form_routes._validate_submission(form, {})
    assert missing.value.status_code == 422


def test_submit_uses_server_canonical_titles(monkeypatch) -> None:
    captured: dict = {}

    def fake_save(form_id, title_kn, title_en, values, **kwargs):
        captured.update(
            form_id=form_id,
            title_kn=title_kn,
            title_en=title_en,
            values=values,
        )
        return {"id": "test"}

    monkeypatch.setattr(form_routes.store, "save_form_submission", fake_save)
    body = form_routes.FormSubmitBody(
        form_id="balance_inquiry",
        title_kn="client supplied",
        title_en="client supplied",
        values={"account_number": "1234567890"},
    )
    result = form_routes.submit_form(body)
    form = forms_catalog.get_form("balance_inquiry")

    assert result["ok"] is True
    assert captured["title_kn"] == form["title_kn"]
    assert captured["title_en"] == form["title_en"]
