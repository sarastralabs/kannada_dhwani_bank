"""Staff-console insights: system status, usage stats and CSV exports."""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from api import admin_auth, system_status

router = APIRouter(tags=["insights"])


def _day(iso: str) -> str:
    return (iso or "")[:10]


@router.get("/admin/system")
def admin_system(_admin: dict = Depends(admin_auth.require_admin)) -> dict:
    """What is loaded, which engine each stage uses, and whether recent calls failed."""
    from backend import cloud
    from backend.db.store import mongo_enabled, ping_mongo

    _ = _admin
    cfg = cloud.public_config()
    stages = {
        name: {
            "provider": info["provider"],
            "using_local_now": info["using_local_now"],
            "last_ok": info["ok"],
            "last_error": info["error"],
        }
        for name, info in cfg["stages"].items()
    }
    pipeline_ready = False
    try:
        from backend import pipeline_bridge

        pipeline_ready = bool(pipeline_bridge._ready)  # noqa: SLF001 - status only
    except Exception:
        pass
    database = "mongodb" if mongo_enabled() else "sqlite"
    db_ok = ping_mongo() if mongo_enabled() else True
    return {
        "pipeline_ready": pipeline_ready,
        "stages": stages,
        "database": {"kind": database, "ok": db_ok},
        "cloud_key_set": cfg["key_set"],
        # The shipped default is public in the repo, so it must not stay in use.
        "default_admin_password": admin_auth._credentials()[1] == "bank@123",
        "recent": system_status.snapshot(),
    }


@router.get("/admin/stats")
def admin_stats(
    days: int = Query(14, ge=1, le=90),
    _admin: dict = Depends(admin_auth.require_admin),
) -> dict:
    """Per-day request counts and the intent mix, for the Overview charts."""
    from backend.db import store

    _ = _admin
    items = store.list_queries(limit=200)
    start = (datetime.now(timezone.utc) - timedelta(days=days - 1)).date()
    labels = [(start + timedelta(days=i)).isoformat() for i in range(days)]
    per_day = Counter(_day(i.get("created_at", "")) for i in items)
    intents = Counter(i.get("intent") or "unknown" for i in items)
    times = [i["total_time_s"] for i in items if isinstance(i.get("total_time_s"), (int, float))]
    return {
        "days": [{"date": d, "count": per_day.get(d, 0)} for d in labels],
        "intents": [{"intent": k, "count": v} for k, v in intents.most_common(8)],
        "avg_response_s": round(sum(times) / len(times), 2) if times else None,
        "sample_size": len(items),
    }


def _csv(rows: list[dict], columns: list[str], filename: str) -> Response:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: row.get(c, "") for c in columns})
    # BOM so Excel opens Kannada text correctly.
    body = "﻿" + buf.getvalue()
    return Response(
        content=body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/admin/export/history.csv")
def export_history(_admin: dict = Depends(admin_auth.require_admin)) -> Response:
    from backend.db import store

    _ = _admin
    rows = store.list_queries(limit=200)
    cols = ["created_at", "kannada_text", "english_text", "intent", "confidence", "route", "response_text", "total_time_s"]
    return _csv(rows, cols, "conversations.csv")


@router.get("/admin/export/submissions.csv")
def export_submissions(_admin: dict = Depends(admin_auth.require_admin)) -> Response:
    from backend.db import store

    _ = _admin
    rows = store.list_form_submissions(limit=200)
    for row in rows:
        row["values"] = json.dumps(row.get("values") or {}, ensure_ascii=False)
    cols = ["created_at", "form_id", "title_en", "title_kn", "status", "values", "kiosk_session_id"]
    return _csv(rows, cols, "form-submissions.csv")
