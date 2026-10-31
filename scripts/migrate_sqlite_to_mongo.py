"""Copy local SQLite history and JSONL form submissions into MongoDB (safe to re-run).

    python scripts/migrate_sqlite_to_mongo.py [--submissions PATH] [--dry-run]

Needs MONGODB_URI in .env. Rows are matched on created_at (+ text), so running it
twice never creates duplicates. Recordings (history_audio/) stay on disk — MongoDB
history does not store audio.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"), override=True)

from backend.db import store  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", default=os.path.join(ROOT, "data", "history.db"))
    ap.add_argument("--submissions", default=os.path.join(ROOT, "data", "form_submissions.jsonl"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db = store._get_db()  # noqa: SLF001
    if db is None:
        print("MongoDB is not configured or unreachable (check MONGODB_URI).")
        return 1

    added_h = skipped_h = 0
    if os.path.isfile(args.history):
        conn = sqlite3.connect(args.history)
        conn.row_factory = sqlite3.Row
        for row in conn.execute("SELECT * FROM query_history ORDER BY id"):
            key = {"created_at": row["created_at"], "kannada_text": row["kannada_text"]}
            if db.query_history.count_documents(key, limit=1):
                skipped_h += 1
                continue
            doc = {
                **key,
                "english_text": row["english_text"],
                "intent": row["intent"],
                "confidence": float(row["confidence"] or 0),
                "route": row["route"],
                "response_text": row["response_text"],
                "form_id": "",
                "total_time_s": row["total_time_s"],
                "stage_times": json.loads(row["stage_times_json"] or "{}"),
                "kiosk_session_id": "",
            }
            if not args.dry_run:
                db.query_history.insert_one(doc)
            added_h += 1
        conn.close()
    else:
        print(f"No history database at {args.history}")

    added_s = skipped_s = 0
    if os.path.isfile(args.submissions):
        with open(args.submissions, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    doc = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = {"created_at": doc.get("created_at", ""), "form_id": doc.get("form_id", "")}
                if db.form_submissions.count_documents(key, limit=1):
                    skipped_s += 1
                    continue
                if not args.dry_run:
                    db.form_submissions.insert_one(doc)
                added_s += 1
    else:
        print(f"No submissions file at {args.submissions}")

    verb = "would add" if args.dry_run else "added"
    print(f"history: {verb} {added_h}, already there {skipped_h}")
    print(f"form submissions: {verb} {added_s}, already there {skipped_s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
