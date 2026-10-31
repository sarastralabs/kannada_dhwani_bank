"""Applications and customers: staff decisions and money (admin), and what a customer sees at the kiosk."""

from __future__ import annotations

import csv
import io
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from api import admin_auth
from backend import applications, customer_view
from backend.db import ledger, store

router = APIRouter(tags=["applications"])


class DecisionBody(BaseModel):
    action: Literal["approve", "reject", "needs_info"]
    note: str = Field(default="", max_length=500)
    # Loan / fixed deposit: amount, annual_rate_pct, tenure_months (anything left out uses the default).
    terms: dict[str, Any] | None = None


class RepaymentBody(BaseModel):
    amount: float = Field(..., gt=0, le=100_000_000)


@router.get("/admin/applications/{app_id}")
def get_application(app_id: str, _admin: dict = Depends(admin_auth.require_admin)) -> dict:
    app = store.get_application(app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


@router.get("/admin/applications/{app_id}/preview")
def preview_application(app_id: str, _admin: dict = Depends(admin_auth.require_admin)) -> dict:
    """What approving would do (or why it cannot be done), without changing anything."""
    try:
        return applications.preview(app_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/admin/applications/{app_id}/decision")
def decide_application(
    app_id: str,
    body: DecisionBody,
    admin: dict = Depends(admin_auth.require_admin),
) -> dict:
    """Approve, reject or ask for more information. Approving carries out the form's effect."""
    try:
        return applications.decide(
            app_id, body.action, admin=str(admin.get("username") or "admin"), note=body.note, terms=body.terms
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except applications.DecisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not complete the decision: {exc}") from exc


@router.get("/admin/customers/{customer_id}")
def customer_detail(customer_id: str, _admin: dict = Depends(admin_auth.require_admin)) -> dict:
    """One customer: accounts, loans, fixed deposits, recent movements, applications."""
    try:
        return ledger.customer_detail(customer_id)
    except ledger.LedgerError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/admin/loans/{loan_id}/repayment")
def record_repayment(loan_id: str, body: RepaymentBody, admin: dict = Depends(admin_auth.require_admin)) -> dict:
    """A loan payment received at the counter (interest first, then the loan itself)."""
    try:
        return ledger.repay_loan(loan_id, body.amount, by=str(admin.get("username") or "admin"))
    except ledger.LedgerError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/admin/export/transactions.csv")
def export_transactions(_admin: dict = Depends(admin_auth.require_admin)) -> Response:
    try:
        rows = list(ledger._db().transactions.find().sort("at", -1).limit(1000))  # noqa: SLF001
    except ledger.LedgerError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    cols = ["at", "account_number", "kind", "amount", "balance_after", "counterparty", "ref", "by", "note"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: row.get(c, "") for c in cols})
    return Response(
        content=("﻿" + buf.getvalue()).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="transactions.csv"'},
    )


@router.get("/applications/status")
def application_status(
    ref: str = Query(..., min_length=3, max_length=24),
    mobile_last4: str = Query(default="", max_length=8),
) -> dict:
    """Public: the customer's own application, with its number (and last 4 digits of the mobile)."""
    found = applications.public_status(ref, mobile_last4)
    if found is None:
        raise HTTPException(status_code=404, detail="No application matches that number")
    return found


@router.get("/customer/summary")
def customer_summary(
    account_last4: str = Query(..., min_length=4, max_length=10),
    mobile_last4: str = Query(..., min_length=4, max_length=10),
) -> dict:
    """Public: a returning customer's accounts, loans, deposits and recent activity.

    Needs the last 4 digits of one of their accounts AND of their registered mobile number.
    A wrong answer looks exactly like "no such customer".
    """
    summary = customer_view.summary(account_last4, mobile_last4)
    if summary is None:
        raise HTTPException(status_code=404, detail="No customer matches those digits")
    return summary
