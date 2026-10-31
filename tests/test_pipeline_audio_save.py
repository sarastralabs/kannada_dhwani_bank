import os
import tempfile
import unittest

import numpy as np

from backend.pipeline import _write_audio_to_disk


class TestPipelineAudioSave(unittest.TestCase):
    def test_write_audio_to_disk(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "pipeline_run1.wav")
            audio = (np.zeros(16000, dtype=np.float32), 16000)

            saved_path = _write_audio_to_disk(audio, output_path)

            self.assertEqual(saved_path, output_path)
            self.assertTrue(os.path.exists(output_path))


if __name__ == "__main__":
    unittest.main()
