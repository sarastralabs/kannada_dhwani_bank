"""
Run STT + IndicTrans2 Kn→En + typed field extract for one form answer.

Usage: python run_form_fill_subprocess.py <wav_path> [field_type] [field_id]

Prints JSON: kannada_text, english_text, value, error
"""
from __future__ import annotations

import json
import os
import sys

os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.forms.extract import extract_field_value
from backend.forms.stt_tuning import (
    NAME_FIELD_IDS,
    english_digit_retry_hints,
    form_fill_beam_size,
    form_fill_stt_hints,
    plausible_digit_capture,
)
from backend.stt import transcribe, unload_model as unload_stt
from backend.translation import translate_kn_to_en, unload_model as unload_trans

def _spoken_kn(kannada_text: str, fid: str) -> str:
    """Cleaned Kannada of a name/address answer — read back in Kannada, not English letters."""
    from backend.forms.as_spoken import clean_spoken, is_as_spoken_field

    return clean_spoken(kannada_text) if is_as_spoken_field(fid) else ""


wav_path = sys.argv[1]
field_type = sys.argv[2] if len(sys.argv) > 2 else "text"
field_id = sys.argv[3] if len(sys.argv) > 3 else ""

kannada = ""
english = ""
value = ""
error = None
validation_error = None
numeric_retry_used = False

beam = form_fill_beam_size(field_type, field_id)
prompt, hotwords = form_fill_stt_hints(field_type, field_id)

try:
    kannada = transcribe(
        wav_path,
        beam_size=beam,
        initial_prompt=prompt,
        hotwords=hotwords,
    ) or ""
    if not kannada.strip():
        error = "STT returned empty (silent audio)"
    else:
        normalized_type = (field_type or "").lower()
        if normalized_type == "digits":
            from backend.forms.kannada_digits import extract_digits_from_kannada

            primary_digits = extract_digits_from_kannada(kannada)
            if plausible_digit_capture(primary_digits, field_id):
                value = primary_digits
            else:
                numeric_retry_used = True
                retry_prompt, retry_hotwords = english_digit_retry_hints(field_id)
                retry_text = transcribe(
                    wav_path,
                    beam_size=beam,
                    initial_prompt=retry_prompt,
                    hotwords=retry_hotwords,
                    language="en",
                ) or ""
                retry_digits = extract_digits_from_kannada(retry_text)
                if plausible_digit_capture(retry_digits, field_id) or len(
                    retry_digits
                ) > len(primary_digits):
                    value = retry_digits
                    english = retry_text

        if not value and (
            normalized_type == "date" or "date" in (field_id or "").lower()
        ):
            from backend.forms.date_kn import extract_date_from_kannada

            value = extract_date_from_kannada(kannada)
        try:
            unload_stt()
        except Exception:
            pass
        from backend.forms.as_spoken import as_spoken_value, is_as_spoken_field

        if not value and is_as_spoken_field(field_id):
            # Names / addresses: keep what was said — translating them gives nonsense.
            value = as_spoken_value(kannada)
        if not value:
            english = translate_kn_to_en(kannada) or ""
            try:
                unload_trans("kn_to_en")
            except Exception:
                pass
            if not english.strip():
                value = kannada.strip()
                error = "Translation returned empty; using Kannada text"
            else:
                value = extract_field_value(
                    english,
                    field_type=field_type,
                    field_id=field_id,
                    kannada_text=kannada,
                )

        if not (value or "").strip() and (field_id or "").lower() in NAME_FIELD_IDS:
            value = extract_field_value(english or kannada, field_type=field_type, field_id=field_id)
            if not value.strip():
                value = kannada.strip()

        if field_type == "digits" or field_id == "account_number":
            from backend.forms.kannada_digits import extract_digits_from_kannada

            candidates = [
                "".join(ch for ch in (value or "") if ch.isdigit()),
                extract_digits_from_kannada(kannada),
                extract_digits_from_kannada(english) if english else "",
            ]
            best = ""
            for candidate in candidates:
                if not candidate:
                    continue
                if plausible_digit_capture(candidate, field_id):
                    best = candidate
                    break
                if len(candidate) > len(best):
                    best = candidate
            if best:
                value = best
        from backend.forms.validation import validate_captured_value

        validation_error = validate_captured_value(
            value,
            field_type=field_type,
            field_id=field_id,
        )
except Exception as exc:
    error = str(exc)
    try:
        unload_stt()
    except Exception:
        pass
    try:
        unload_trans("kn_to_en")
    except Exception:
        pass

print(
    json.dumps(
        {
            "kannada_text": kannada,
            "english_text": english,
            "value": value,
            "spoken_kn": _spoken_kn(kannada, field_id),
            "error": error,
            "validation_error": validation_error,
            "digit_count": len("".join(ch for ch in value if ch.isdigit())),
            "numeric_retry_used": numeric_retry_used,
        }
    )
)
if error and not value:
    sys.exit(1)
