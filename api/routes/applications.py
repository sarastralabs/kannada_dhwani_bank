"""Applications: staff decisions (admin) and the customer's status check (kiosk)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api import admin_auth
from backend import applications
from backend.db import store

router = APIRouter(tags=["applications"])


class DecisionBody(BaseModel):
    action: Literal["approve", "reject", "needs_info"]
    note: str = Field(default="", max_length=500)


@router.get("/admin/applications/{app_id}")
def get_application(app_id: str, _admin: dict = Depends(admin_auth.require_admin)) -> dict:
    app = store.get_application(app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


@router.post("/admin/applications/{app_id}/decision")
def decide_application(
    app_id: str,
    body: DecisionBody,
    admin: dict = Depends(admin_auth.require_admin),
) -> dict:
    """Approve, reject or ask for more information. Approving an account opening creates it."""
    try:
        return applications.decide(
            app_id, body.action, admin=str(admin.get("username") or "admin"), note=body.note
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except applications.DecisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:  # e.g. customer store is read-only (json demo mode)
        raise HTTPException(status_code=500, detail=f"Could not complete the decision: {exc}") from exc


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
