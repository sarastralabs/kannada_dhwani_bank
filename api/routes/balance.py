"""Demo balance lookup API."""

from __future__ import annotations

from fastapi import APIRouter

from backend.balance_lookup import lookup_balance

router = APIRouter()


@router.get("/balance/{account_number}")
def get_balance(account_number: str) -> dict:
    """Always 200 — caller uses found + message_kn for voice UX."""
    return lookup_balance(account_number)
