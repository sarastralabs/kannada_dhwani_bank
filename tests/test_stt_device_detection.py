import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.stt import transcriber


class TestSTTDeviceDetection(unittest.TestCase):
    def test_detect_device_falls_back_to_cpu_when_torch_import_fails(self):
        real_import = __import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "torch":
                raise OSError("Could not load symbol cudnnGetLibConfig. Error code 127")
            return real_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=fake_import):
            self.assertEqual(transcriber._detect_device(), "cpu")

    def test_cuda_uses_float16(self):
        with (
            mock.patch.object(transcriber.os.path, "isdir", return_value=True),
            mock.patch.object(transcriber, "_detect_device", return_value="cuda"),
            mock.patch.object(transcriber, "WhisperModel") as model_cls,
        ):
            transcriber.KannadaTranscriber("models/test")

        model_cls.assert_called_once_with(
            "models/test", device="cuda", compute_type="float16"
        )

    def test_cpu_uses_int8(self):
        with (
            mock.patch.object(transcriber.os.path, "isdir", return_value=True),
            mock.patch.object(transcriber, "_detect_device", return_value="cpu"),
            mock.patch.object(transcriber, "WhisperModel") as model_cls,
        ):
            transcriber.KannadaTranscriber("models/test")

        model_cls.assert_called_once_with(
            "models/test", device="cpu", compute_type="int8"
        )

    def test_cuda_initialization_failure_falls_back_to_cpu_int8(self):
        cpu_model = mock.MagicMock()
        with (
            mock.patch.object(transcriber.os.path, "isdir", return_value=True),
            mock.patch.object(transcriber, "_detect_device", return_value="cuda"),
            mock.patch.object(
                transcriber,
                "WhisperModel",
                side_effect=[RuntimeError("CUDA unavailable"), cpu_model],
            ) as model_cls,
            self.assertWarnsRegex(UserWarning, "falling back to CPU"),
        ):
            instance = transcriber.KannadaTranscriber("models/test")

        self.assertIs(instance._model, cpu_model)
        self.assertEqual(instance._device, "cpu")
        self.assertEqual(instance._compute_type, "int8")
        self.assertEqual(
            model_cls.call_args_list,
            [
                mock.call("models/test", device="cuda", compute_type="float16"),
                mock.call("models/test", device="cpu", compute_type="int8"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
