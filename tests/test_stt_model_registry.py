"""Environment-selectable STT model registry tests."""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

import backend.stt as stt


class TestSTTModelRegistry(unittest.TestCase):
    def setUp(self) -> None:
        stt._model_cache.clear()

    def tearDown(self) -> None:
        stt._model_cache.clear()

    def test_vasista_is_the_default_model(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(stt.active_model_name(), "vasista-medium")

    def test_default_transcribe_loads_local_vasista_model(self):
        transcriber = MagicMock()
        transcriber.transcribe.return_value = "ಪರೀಕ್ಷೆ"

        with (
            patch.dict(os.environ, {"BANK_STT_MODEL": "vasista-medium"}),
            patch("backend.stt.os.path.isdir", return_value=True),
            patch("backend.stt.KannadaTranscriber", return_value=transcriber) as cls,
        ):
            result = stt.transcribe("fake.wav", beam_size=3)

        self.assertEqual(result, "ಪರೀಕ್ಷೆ")
        self.assertTrue(
            cls.call_args.args[0].endswith(
                os.path.join("models", "whisper-kannada-medium-ct2")
            )
        )
        transcriber.transcribe.assert_called_once_with("fake.wav", beam_size=3)

    def test_environment_can_roll_back_to_specialized(self):
        transcriber = MagicMock()
        transcriber.transcribe.return_value = "ಹಳೆಯ ಮಾದರಿ"

        with (
            patch.dict(os.environ, {"BANK_STT_MODEL": "specialized"}),
            patch("backend.stt.KannadaTranscriber", return_value=transcriber) as cls,
        ):
            result = stt.transcribe("fake.wav")

        self.assertEqual(result, "ಹಳೆಯ ಮಾದರಿ")
        self.assertTrue(
            cls.call_args.args[0].endswith(
                os.path.join("models", "whisper-medium-vaani-ct2")
            )
        )

    def test_invalid_environment_model_is_rejected(self):
        with patch.dict(os.environ, {"BANK_STT_MODEL": "unknown"}):
            with self.assertRaisesRegex(ValueError, "Unknown BANK_STT_MODEL"):
                stt.transcribe("fake.wav")


if __name__ == "__main__":
    unittest.main()
