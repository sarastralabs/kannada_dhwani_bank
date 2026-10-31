"""Parler batch chunking: fast long replies without losing or splitting words."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from parler_model_utils import chunk_pause_s, split_tts_chunks

ROOT = Path(__file__).resolve().parents[1]
BANK = json.loads((ROOT / "data" / "bank_info.json").read_text(encoding="utf-8"))
LONG_REPLIES = [
    BANK["interest_rates_all_kn"],
    BANK["loan_repayment"]["info_kn"],
    BANK["account_procedures"]["atm_block_kn"],
    "ಹೊಸ ಬ್ಯಾಂಕ್ ಖಾತೆ ತೆರೆಯಲು, ನಾನು ಈ ಕೆಳಗಿನ ವಿವರಗಳನ್ನು ಸಂಗ್ರಹಿಸಬೇಕು: ಪೂರ್ಣ ಹೆಸರು, "
    "ಜನ್ಮ ದಿನಾಂಕ, ವಿಳಾಸ, ಖಾತೆ ವಿಧ. ದಯವಿಟ್ಟು ಸಿದ್ಧರಾಗಿರಿ.",
]


def test_short_phrase_is_one_chunk() -> None:
    assert split_tts_chunks("ನಮಸ್ಕಾರ, ನಿಮಗೆ ಏನು ಸಹಾಯ ಬೇಕು?") == ["ನಮಸ್ಕಾರ, ನಿಮಗೆ ಏನು ಸಹಾಯ ಬೇಕು?"]


def test_empty_text() -> None:
    assert split_tts_chunks("   ") == []


@pytest.mark.parametrize("text", LONG_REPLIES)
def test_chunks_keep_every_word_in_order(text: str) -> None:
    chunks = split_tts_chunks(text, max_chars=60)
    assert " ".join(chunks).split() == text.split()


@pytest.mark.parametrize("text", LONG_REPLIES)
def test_chunks_respect_limit_unless_single_word(text: str) -> None:
    for chunk in split_tts_chunks(text, max_chars=60):
        assert len(chunk) <= 60 or " " not in chunk


def test_prefers_sentence_then_clause_boundaries() -> None:
    chunks = split_tts_chunks(BANK["interest_rates_all_kn"], max_chars=60)
    assert len(chunks) > 1
    # Every cut lands on punctuation — never mid-phrase when punctuation exists.
    assert all(c.endswith((".", ",", ":", ";", "?", "!", "।")) for c in chunks)


def test_unpunctuated_run_is_split_on_a_space() -> None:
    text = " ".join(["ಪದ"] * 40)  # 119 chars, no punctuation
    chunks = split_tts_chunks(text, max_chars=60)
    assert len(chunks) >= 2
    assert " ".join(chunks) == text


def test_pause_longer_after_sentence_end() -> None:
    assert chunk_pause_s("ದಯವಿಟ್ಟು ಸಿದ್ಧರಾಗಿರಿ.") > chunk_pause_s("ಹೊಸ ಖಾತೆ ತೆರೆಯಲು,")
