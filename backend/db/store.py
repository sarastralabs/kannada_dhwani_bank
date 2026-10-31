"""
Unified persistence: MongoDB Atlas when configured, else local SQLite (history only).

Env:
  MONGODB_URI=mongodb+srv://user:pass@cluster...
  MONGODB_DB_NAME=bank_assistant  (default)
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

_client = None
_db = None
_init_attempted = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mongo_enabled() -> bool:
    return bool(os.environ.get("MONGODB_URI", "").strip())


def _get_db():
    global _client, _db, _init_attempted
    if _db is not None:
        return _db
    if _init_attempted or not mongo_enabled():
        _init_attempted = True
        return None
    _init_attempted = True
    try:
        from pymongo import MongoClient
        from pymongo.errors import ConfigurationError, ServerSelectionTimeoutError

        uri = os.environ["MONGODB_URI"].strip()
        db_name = os.environ.get("MONGODB_DB_NAME", "bank_assistant").strip() or "bank_assistant"
        _client = MongoClient(uri, serverSelectionTimeoutMS=8000, connectTimeoutMS=8000)
        _client.admin.command("ping")
        _db = _client[db_name]
        _ensure_indexes(_db)
        print(f"[store] MongoDB connected — database '{db_name}'", flush=True)
        return _db
    except Exception as exc:
        print(f"[store] MongoDB unavailable, using SQLite fallback: {exc}", flush=True)
        _client = None
        _db = None
        return None


def _ensure_indexes(db) -> None:
    db.query_history.create_index([("created_at", -1)])
    db.form_submissions.create_index([("created_at", -1)])
    db.form_submissions.create_index([("form_id", 1)])
    db.kiosk_sessions.create_index([("session_id", 1)], unique=True)
    db.kiosk_sessions.create_index([("started_at", -1)])


def save_query(result: dict[str, Any]) -> dict[str, Any]:
    """Persist pipeline result. Returns summary dict with id."""
    db = _get_db()
    if db is not None:
        doc = {
            "created_at": _now(),
            "kannada_text": result.get("kannada_text") or "",
            "english_text": result.get("english_text") or "",
            "intent": result.get("intent") or "",
            "confidence": float(result.get("confidence") or 0),
            "route": result.get("route") or "",
            "response_text": result.get("response_text") or "",
            "form_id": result.get("form_id") or "",
            "total_time_s": result.get("total_time_s"),
            "stage_times": result.get("stage_times") or {},
            "kiosk_session_id": result.get("kiosk_session_id") or "",
        }
        ins = db.query_history.insert_one(doc)
        oid = str(ins.inserted_id)
        return {
            "id": oid,
            "created_at": doc["created_at"],
            "kannada_text": doc["kannada_text"],
            "english_text": doc["english_text"],
            "intent": doc["intent"],
            "confidence": doc["confidence"],
            "route": doc["route"],
            "response_text": doc["response_text"],
            "has_audio": False,
            "total_time_s": doc["total_time_s"],
            "stage_times": doc["stage_times"],
        }

    from api import history as sqlite_history

    return sqlite_history.save_query(result)


def list_queries(limit: int = 50) -> list[dict[str, Any]]:
    db = _get_db()
    if db is not None:
        rows = db.query_history.find().sort("created_at", -1).limit(limit)
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "id": str(row["_id"]),
                    "created_at": row.get("created_at", ""),
                    "kannada_text": row.get("kannada_text", ""),
                    "english_text": row.get("english_text", ""),
                    "intent": row.get("intent", ""),
                    "confidence": row.get("confidence", 0),
                    "route": row.get("route", ""),
                    "response_text": row.get("response_text", ""),
                    "has_audio": False,
                    "total_time_s": row.get("total_time_s"),
                    "stage_times": row.get("stage_times") or {},
                }
            )
        return out

    from api import history as sqlite_history

    return sqlite_history.list_history(limit)


def get_query(item_id: str | int, include_audio: bool = True) -> dict[str, Any] | None:
    db = _get_db()
    if db is not None:
        from bson import ObjectId
        from bson.errors import InvalidId

        try:
            oid = ObjectId(str(item_id))
        except (InvalidId, TypeError):
            return None
        row = db.query_history.find_one({"_id": oid})
        if not row:
            return None
        return {
            "id": str(row["_id"]),
            "created_at": row.get("created_at", ""),
            "kannada_text": row.get("kannada_text", ""),
            "english_text": row.get("english_text", ""),
            "intent": row.get("intent", ""),
            "confidence": row.get("confidence", 0),
            "route": row.get("route", ""),
            "response_text": row.get("response_text", ""),
            "has_audio": False,
            "audio_b64": "",
            "total_time_s": row.get("total_time_s"),
            "stage_times": row.get("stage_times") or {},
        }

    from api import history as sqlite_history

    try:
        iid = int(item_id)
    except (TypeError, ValueError):
        return None
    return sqlite_history.get_history_item(iid, include_audio=include_audio)


def delete_query(item_id: str | int) -> bool:
    db = _get_db()
    if db is not None:
        from bson import ObjectId
        from bson.errors import InvalidId

        try:
            oid = ObjectId(str(item_id))
        except (InvalidId, TypeError):
            return False
        res = db.query_history.delete_one({"_id": oid})
        return res.deleted_count > 0

    from api import history as sqlite_history

    try:
        return sqlite_history.delete_history_item(int(item_id))
    except (TypeError, ValueError):
        return False


def clear_queries() -> int:
    db = _get_db()
    if db is not None:
        res = db.query_history.delete_many({})
        return int(res.deleted_count)

    from api import history as sqlite_history

    return sqlite_history.clear_history()


def _submissions_path() -> str:
    """Local form submissions file (used when MongoDB is not configured)."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data",
        "form_submissions.jsonl",
    )


def save_form_submission(
    form_id: str,
    title_kn: str,
    title_en: str,
    values: dict[str, str],
    *,
    kiosk_session_id: str = "",
    status: str = "submitted",
) -> dict[str, Any]:
    doc = {
        "created_at": _now(),
        "form_id": form_id,
        "title_kn": title_kn,
        "title_en": title_en,
        "values": values,
        "kiosk_session_id": kiosk_session_id,
        "status": status,
    }
    db = _get_db()
    if db is not None:
        ins = db.form_submissions.insert_one(doc)
        return {"id": str(ins.inserted_id), **doc}

    # Local fallback — append JSON lines file
    import json

    path = _submissions_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    return {"id": doc["created_at"], **doc}


def save_kiosk_session(event: dict[str, Any]) -> None:
    """Upsert kiosk session snapshot (best-effort)."""
    db = _get_db()
    if db is None:
        return
    sid = event.get("session_id") or event.get("id")
    if not sid:
        return
    db.kiosk_sessions.update_one(
        {"session_id": sid},
        {
            "$set": {
                **event,
                "session_id": sid,
                "updated_at": _now(),
            }
        },
        upsert=True,
    )


def clear_form_submissions() -> int:
    """Delete every saved form submission (admin "Clear all"). Returns how many were removed."""
    db = _get_db()
    if db is not None:
        return int(db.form_submissions.delete_many({}).deleted_count)

    path = _submissions_path()
    if not os.path.isfile(path):
        return 0
    with open(path, encoding="utf-8") as f:
        count = sum(1 for line in f if line.strip())
    os.remove(path)
    return count


def list_form_submissions(limit: int = 50) -> list[dict[str, Any]]:
    db = _get_db()
    if db is not None:
        rows = db.form_submissions.find().sort("created_at", -1).limit(limit)
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "id": str(row["_id"]),
                    "created_at": row.get("created_at", ""),
                    "form_id": row.get("form_id", ""),
                    "title_kn": row.get("title_kn", ""),
                    "title_en": row.get("title_en", ""),
                    "values": row.get("values") or {},
                    "kiosk_session_id": row.get("kiosk_session_id", ""),
                    "status": row.get("status", ""),
                }
            )
        return out

    import json

    path = _submissions_path()
    if not os.path.isfile(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
                out.append(
                    {
                        "id": doc.get("created_at", ""),
                        "created_at": doc.get("created_at", ""),
                        "form_id": doc.get("form_id", ""),
                        "title_kn": doc.get("title_kn", ""),
                        "title_en": doc.get("title_en", ""),
                        "values": doc.get("values") or {},
                        "kiosk_session_id": doc.get("kiosk_session_id", ""),
                        "status": doc.get("status", ""),
                    }
                )
            except json.JSONDecodeError:
                continue
    out.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return out[:limit]


def ping_mongo() -> bool:
    db = _get_db()
    if db is None:
        return False
    try:
        db.client.admin.command("ping")
        return True
    except Exception:
        return False
