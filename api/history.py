"""SQLite-backed query history for the voice banking assistant."""

from __future__ import annotations

import base64
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "history.db")
AUDIO_DIR = os.path.join(DATA_DIR, "history_audio")


def _ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(AUDIO_DIR, exist_ok=True)


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS query_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                kannada_text TEXT NOT NULL DEFAULT '',
                english_text TEXT NOT NULL DEFAULT '',
                intent TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0,
                route TEXT NOT NULL DEFAULT '',
                response_text TEXT NOT NULL DEFAULT '',
                audio_filename TEXT,
                total_time_s REAL,
                stage_times_json TEXT
            )
            """
        )


def save_query(result: dict[str, Any]) -> dict[str, Any]:
    """Persist a successful pipeline result. Returns the saved history summary."""
    init_db()
    created_at = datetime.now(timezone.utc).isoformat()
    audio_filename: str | None = None

    audio_b64 = result.get("audio_b64") or ""
    if audio_b64:
        # Temporary id placeholder — write after insert with real id
        pass

    stage_times = result.get("stage_times") or {}
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO query_history (
                created_at, kannada_text, english_text, intent, confidence,
                route, response_text, audio_filename, total_time_s, stage_times_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                result.get("kannada_text") or "",
                result.get("english_text") or "",
                result.get("intent") or "",
                float(result.get("confidence") or 0),
                result.get("route") or "",
                result.get("response_text") or "",
                None,
                result.get("total_time_s"),
                json.dumps(stage_times),
            ),
        )
        row_id = int(cur.lastrowid)

        if audio_b64:
            audio_filename = f"query_{row_id}.wav"
            audio_path = os.path.join(AUDIO_DIR, audio_filename)
            with open(audio_path, "wb") as f:
                f.write(base64.b64decode(audio_b64))
            conn.execute(
                "UPDATE query_history SET audio_filename = ? WHERE id = ?",
                (audio_filename, row_id),
            )

    return get_history_item(row_id, include_audio=False)


def list_history(limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, kannada_text, english_text, intent, confidence,
                   route, response_text, audio_filename, total_time_s, stage_times_json
            FROM query_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row_to_summary(row) for row in rows]


def get_history_item(item_id: int, include_audio: bool = True) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM query_history WHERE id = ?",
            (item_id,),
        ).fetchone()
    if row is None:
        return None
    item = _row_to_summary(row)
    if include_audio and row["audio_filename"]:
        audio_path = os.path.join(AUDIO_DIR, row["audio_filename"])
        if os.path.isfile(audio_path):
            with open(audio_path, "rb") as f:
                item["audio_b64"] = base64.b64encode(f.read()).decode()
        else:
            item["audio_b64"] = ""
    else:
        item["audio_b64"] = ""
        item["has_audio"] = bool(row["audio_filename"])
    return item


def delete_history_item(item_id: int) -> bool:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT audio_filename FROM query_history WHERE id = ?",
            (item_id,),
        ).fetchone()
        if row is None:
            return False
        if row["audio_filename"]:
            path = os.path.join(AUDIO_DIR, row["audio_filename"])
            if os.path.isfile(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass
        conn.execute("DELETE FROM query_history WHERE id = ?", (item_id,))
    return True


def clear_history() -> int:
    init_db()
    with _connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM query_history").fetchone()[0]
        rows = conn.execute("SELECT audio_filename FROM query_history").fetchall()
        for row in rows:
            if row["audio_filename"]:
                path = os.path.join(AUDIO_DIR, row["audio_filename"])
                if os.path.isfile(path):
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
        conn.execute("DELETE FROM query_history")
    return int(count)


def _row_to_summary(row: sqlite3.Row) -> dict[str, Any]:
    stage_times: dict[str, Any] = {}
    raw = row["stage_times_json"]
    if raw:
        try:
            stage_times = json.loads(raw)
        except json.JSONDecodeError:
            stage_times = {}
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "kannada_text": row["kannada_text"],
        "english_text": row["english_text"],
        "intent": row["intent"],
        "confidence": row["confidence"],
        "route": row["route"],
        "response_text": row["response_text"],
        "has_audio": bool(row["audio_filename"]),
        "total_time_s": row["total_time_s"],
        "stage_times": stage_times,
    }
