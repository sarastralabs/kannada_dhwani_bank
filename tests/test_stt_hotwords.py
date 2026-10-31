"""STT hotwords must be a string for faster-whisper."""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


class TestSTTHotwords(unittest.TestCase):
    @patch("backend.stt.transcriber.WhisperModel")
    @patch("backend.stt.transcriber.sf.read", return_value=([0.0] * 1600, 16000))
    @patch("backend.stt.transcriber.is_silent", return_value=False)
    @patch("backend.stt.transcriber.validate_audio_file")
    def test_hotwords_passed_as_string(self, _val, _silent, _read, _model_cls):
        from backend.stt.transcriber import KannadaTranscriber, _BANKING_HOTWORDS

        self.assertIsInstance(_BANKING_HOTWORDS, str)

        mock_model = MagicMock()
        seg = MagicMock()
        seg.text = "ಪರೀಕ್ಷೆ"
        mock_model.transcribe.return_value = ([seg], None)
        _model_cls.return_value = mock_model

        t = KannadaTranscriber("models/whisper-medium-vaani-ct2", device="cpu")
        out = t.transcribe(
            "fake.wav",
            initial_prompt="ದಿನಾಂಕದ ಉತ್ತರ",
            hotwords="ಹದಿನಾಲ್ಕು ಎರಡು ಸಾವಿರ ಮೂರು",
        )
        self.assertEqual(out, "ಪರೀಕ್ಷೆ")

        _kwargs = mock_model.transcribe.call_args.kwargs
        self.assertIsInstance(_kwargs["hotwords"], str)
        self.assertIn("ಖಾತೆ", _kwargs["hotwords"])
        self.assertIn("ಹದಿನಾಲ್ಕು", _kwargs["hotwords"])
        self.assertEqual(_kwargs["initial_prompt"], "ದಿನಾಂಕದ ಉತ್ತರ")
        self.assertEqual(_kwargs["language"], "kn")
        self.assertEqual(_kwargs["task"], "transcribe")
        self.assertTrue(_kwargs["vad_filter"])
        self.assertEqual(_kwargs["beam_size"], 1)

        t.transcribe(
            "fake.wav",
            language="en",
            initial_prompt="A ten digit mobile number.",
            hotwords="zero one two three four five six seven eight nine",
        )
        english_kwargs = mock_model.transcribe.call_args.kwargs
        self.assertEqual(english_kwargs["language"], "en")
        self.assertNotIn("ಖಾತೆ", english_kwargs["hotwords"])
        self.assertIn("nine", english_kwargs["hotwords"])

    @patch("backend.stt.transcriber.WhisperModel")
    @patch("backend.stt.transcriber.sf.read", return_value=([0.0] * 1600, 16000))
    @patch("backend.stt.transcriber.is_silent", return_value=False)
    @patch("backend.stt.transcriber.validate_audio_file")
    def test_truncated_character_is_stripped(self, _val, _silent, _read, _model_cls):
        from backend.stt.transcriber import KannadaTranscriber

        mock_model = MagicMock()
        seg = MagicMock()
        seg.text = " ನನ್ನ ಖಾತೆಯ ಬಾಕಿ ಎ�"
        mock_model.transcribe.return_value = ([seg], None)
        _model_cls.return_value = mock_model

        t = KannadaTranscriber("models/whisper-medium-vaani-ct2", device="cpu")
        self.assertNotIn("�", t.transcribe("fake.wav"))


if __name__ == "__main__":
    unittest.main()
