"""Tests for Kannada digit extraction and speak cache."""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


class TestKannadaDigits(unittest.TestCase):
    def test_ascii_digits(self) -> None:
        from backend.forms.kannada_digits import extract_digits_from_kannada

        self.assertEqual(extract_digits_from_kannada("1234567890"), "1234567890")

    def test_embedded_digits(self) -> None:
        from backend.forms.kannada_digits import extract_digits_from_kannada

        self.assertEqual(
            extract_digits_from_kannada("ನನ್ನ ಖಾತೆ 1234567890"),
            "1234567890",
        )


class TestSpeakCache(unittest.TestCase):
    def test_cache_hit_no_synth(self) -> None:
        import base64
        import io

        import numpy as np
        import soundfile as sf

        from backend.tts.speak_cache import get_cached_b64, put_cached_b64

        # Real 0.5 s WAV — the cache refuses empty/too-short clips.
        buf = io.BytesIO()
        sf.write(buf, np.zeros(22050, dtype=np.float32), 44100, format="WAV")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        put_cached_b64("unit_test_only", b64)
        self.assertEqual(get_cached_b64("unit_test_only"), b64)


if __name__ == "__main__":
    unittest.main()
