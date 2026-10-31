"""Public landing-page data for the product home screen."""

from __future__ import annotations

import json
import os

from fastapi import APIRouter

from backend.db import store

router = APIRouter(tags=["landing"])

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BANK_INFO_PATH = os.path.join(PROJECT_ROOT, "data", "bank_info.json")

INTENTS = [
    {"id": "check_balance", "label": "Check account balance", "example": "ನನ್ನ ಖಾತೆಯ ಶಿಲ್ಕು ಎಷ್ಟು?"},
    {"id": "interest_rate_query", "label": "Interest rate info", "example": "ಉಳಿತಾಯ ಖಾತೆಯ ಬಡ್ಡಿ ದರ ಎಷ್ಟು?"},
    {"id": "open_account", "label": "How to open an account", "example": "ಹೊಸ ಖಾತೆ ತೆರೆಯಬೇಕು"},
    {"id": "apply_loan", "label": "How to apply for a loan", "example": "ಸಾಲಕ್ಕೆ ಅರ್ಜಿ ಸಲ್ಲಿಸುವುದು ಹೇಗೆ?"},
    {"id": "deposit_money", "label": "How to deposit money", "example": "ಹಣ ಜಮಾ ಮಾಡಬೇಕು"},
    {"id": "withdraw_money", "label": "How to withdraw money", "example": "ಹಣ ಹಿಂಪಡೆಯಬೇಕು"},
    {"id": "account_info_query", "label": "Account procedure help", "example": "ಮೊಬೈಲ್ ಸಂಖ್ಯೆಯನ್ನು ಬದಲಾಯಿಸುವುದು ಹೇಗೆ?"},
]

PIPELINE = [
    {"step": 1, "name": "Speech to text", "detail": "Kannada Whisper (VAANI)"},
    {"step": 2, "name": "Translation", "detail": "Kannada → English (IndicTrans2)"},
    {"step": 3, "name": "Intent understanding", "detail": "DistilBERT banking NLU"},
    {"step": 4, "name": "Decision + voice", "detail": "Router answer → Kannada TTS"},
]


def _load_bank_info() -> dict:
    try:
        with open(BANK_INFO_PATH, encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return {}


@router.get("/landing")
def landing_data() -> dict:
    bank = _load_bank_info()
    rates = bank.get("interest_rates") or {}
    rate_rows = [
        {"product": key.replace("_", " ").title(), "rate": value}
        for key, value in rates.items()
    ]
    history_items = store.list_queries(limit=200)
    return {
        "product": {
            "name": "Kannada Voice Banking",
            "tagline": "Spoken guidance on how to bank in Kannada — never fetches your real account details.",
            "language": "Kannada",
            "mode": "Informational demo: how-to steps only, no live bank data",
        },
        "stats": {
            "supported_intents": len(INTENTS),
            "history_queries": len(history_items),
            "pipeline_stages": len(PIPELINE),
            "typical_latency_s": "10–25",
        },
        "intents": INTENTS,
        "interest_rates": rate_rows,
        "pipeline": PIPELINE,
        # Public landing responses must not expose customer transcripts.
        "recent": [],
    }
