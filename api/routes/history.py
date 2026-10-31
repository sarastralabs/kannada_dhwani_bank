"""Query history HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api import admin_auth
from backend.db import store

router = APIRouter(prefix="/history", tags=["history"])


@router.get("")
def list_items(limit: int = 50) -> dict:
    items = store.list_queries(limit=min(max(limit, 1), 200))
    return {"items": items, "count": len(items), "backend": "mongodb" if store.mongo_enabled() else "sqlite"}


@router.get("/{item_id}")
def get_item(item_id: str) -> dict:
    item = store.get_query(item_id, include_audio=True)
    if item is None:
        raise HTTPException(status_code=404, detail="History item not found")
    return item


@router.delete("/{item_id}")
def delete_item(item_id: str, _admin: dict = Depends(admin_auth.require_admin)) -> dict:
    if not store.delete_query(item_id):
        raise HTTPException(status_code=404, detail="History item not found")
    return {"ok": True, "id": item_id}


@router.delete("")
def clear_all(_admin: dict = Depends(admin_auth.require_admin)) -> dict:
    deleted = store.clear_queries()
    return {"ok": True, "deleted": deleted}
