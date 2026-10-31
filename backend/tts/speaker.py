"""
backend/tts/speaker.py

Kannada speech synthesis using Facebook MMS-TTS (facebook/mms-tts-kan).

Pipeline:
    English text -> sentence split -> translate_en_to_kn() per sentence
                 -> digit normalisation -> VitsModel -> concatenate -> .wav

Model: facebook/mms-tts-kan
    Public, not gated, 36 MB, CC-BY-NC 4.0
    VitsModel natively in transformers 4.57.6 -- zero new dependencies

Quality notes
-------------
1. Sentence splitting: VITS models produce better output on shorter inputs.
   synthesise() splits on sentence boundaries (. ! ?), translates each
   sentence separately, synthesises each, and concatenates with a 0.4s
   silence gap. This fixes both truncation and prosody artefacts on
   longer responses.

2. Digit normalisation: IndicTrans2 sometimes preserves ASCII digits in
   Kannada output (e.g. "3" instead of "ಮೂರು"). VitsModel produces
   artefacts on mixed-script tokens. _normalise_digits() replaces common
   ASCII digits with their Kannada word equivalents before synthesis.

Model decision history: see README.md
"""

from __future__ import annotations

import os
import re
import time
import warnings

import numpy as np
import soundfile as sf
import torch
from transformers import AutoTokenizer, VitsModel

_DEFAULT_MODEL_ID = "facebook/mms-tts-kan"

# Kannada digit words -- used to replace ASCII digits in translated text
_DIGIT_MAP: dict[str, str] = {
    "0": "\u0cb6\u0cc2\u0ca8\u0ccd\u0caf",       # ಶೂನ್ಯ
    "1": "\u0c92\u0c82\u0ca6\u0cc1",             # ಒಂದು
    "2": "\u0c8e\u0cb0\u0ca1\u0cc1",             # ಎರಡು
    "3": "\u0cae\u0cc2\u0cb0\u0cc1",             # ಮೂರು
    "4": "\u0ca8\u0cbe\u0cb2\u0ccd\u0c95\u0cc1", # ನಾಲ್ಕು
    "5": "\u0c90\u0ca6\u0cc1",                   # ಐದು
    "6": "\u0c86\u0cb0\u0cc1",                   # ಆರು
    "7": "\u0c8f\u0cb3\u0cc1",                   # ಏಳು
    "8": "\u0c8e\u0c82\u0c9f\u0cc1",             # ಎಂಟು
    "9": "\u0c92\u0c82\u0cac\u0ca4\u0ccd\u0ca4\u0cc1",  # ಒಂಬತ್ತು
}

# Silence gap between synthesised sentences (seconds)
_INTER_SENTENCE_SILENCE_S = 0.4

_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')


def _detect_device() -> str:
    """Return 'cuda' if a GPU is available, else 'cpu'."""
    try:
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _split_sentences(text: str) -> list[str]:
    """
    Split text into sentences on . ! ? boundaries.
    Returns the original text as a single-element list if no boundary found.
    """
    parts = _SENTENCE_SPLIT_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def prepare_kannada_for_tts(text: str) -> str:
    """
    Replace digits with Kannada word equivalents before synthesis.

    Parler mis-reads long ASCII digit strings (account / mobile numbers) as
    huge quantities or English nonsense. Digit-by-digit Kannada words keep
    confirmations intelligible.
    """
    if not text:
        return text

    from backend.forms.summary_kn import amount_speak_kn, digits_to_kannada_words

    # Native Kannada numerals → ASCII first
    text = text.translate(str.maketrans("೦೧೨೩೪೫೬೭೮೯", "0123456789"))

    text = re.sub(
        r"(?<!\d)(\d[\d,]*(?:\.\d{1,2})?)\s*ರೂಪಾಯಿ",
        lambda match: amount_speak_kn(match.group(1)),
        text,
    )
    text = re.sub(
        r"(?<!\d)(\d+)\.(\d+)(?!\d)",
        lambda match: (
            f"{digits_to_kannada_words(match.group(1))} ಪಾಯಿಂಟ್ "
            f"{digits_to_kannada_words(match.group(2))}"
        ),
        text,
    )
    return re.sub(
        r"\d+",
        lambda match: digits_to_kannada_words(match.group(0)),
        text,
    )


# Backward-compatible alias used by MMS path below.
_normalise_digits = prepare_kannada_for_tts


class KannadaSpeaker:
    """
    Synthesise Kannada speech from English text using Facebook MMS-TTS.

    Parameters
    ----------
    model_id:
        HuggingFace model ID. Default: "facebook/mms-tts-kan".
    device:
        "cpu" or "cuda". Auto-detected if None.

    Attributes
    ----------
    sample_rate : int
        Output sample rate (16000 Hz for MMS-TTS).
    last_synthesis_time_s : float
        Wall-clock seconds for the most recent synthesise() call.
    """

    def __init__(
        self,
        model_id: str = _DEFAULT_MODEL_ID,
        device: str | None = None,
    ) -> None:
        self._model_id = model_id
        self._device = device if device is not None else _detect_device()
        self.last_synthesis_time_s: float = 0.0

        self._model, self._tokenizer = self._load_model()
        self.sample_rate: int = self._model.config.sampling_rate

    def _load_model(self) -> tuple[VitsModel, AutoTokenizer]:
        try:
            model = VitsModel.from_pretrained(self._model_id).to(self._device)
            model.eval()
            tokenizer = AutoTokenizer.from_pretrained(self._model_id)
            return model, tokenizer
        except Exception:
            if self._device == "cpu":
                raise
            warnings.warn(
                f"CUDA TTS initialization failed ({Exception}); falling back to CPU.",
                stacklevel=2,
            )
            self._device = "cpu"
            model = VitsModel.from_pretrained(self._model_id).to(self._device)
            model.eval()
            tokenizer = AutoTokenizer.from_pretrained(self._model_id)
            return model, tokenizer

    def _synthesise_kannada(self, kannada_text: str) -> np.ndarray:
        """
        Synthesise a single Kannada string and return a float32 audio array.
        Applies digit normalisation before synthesis.
        """
        normalised = _normalise_digits(kannada_text)
        inputs = self._tokenizer(normalised, return_tensors="pt")
        input_ids = inputs["input_ids"].long().to(self._device)
        with torch.no_grad():
            output = self._model(input_ids=input_ids).waveform
        return output.squeeze().cpu().numpy().astype(np.float32)

    def synthesise_kannada(
        self,
        kannada_text: str,
        output_path: str | None = None,
        play: bool = False,
    ) -> tuple[np.ndarray, int] | None:
        """
        Synthesise spoken audio from Kannada text (skips En→Kn translation).
        Used for fixed lobby greetings so TTS does not depend on IndicTrans2.
        """
        if not kannada_text or not kannada_text.strip():
            return None

        parts = re.split(r"(?<=[।.!?])\s+", kannada_text.strip())
        sentences = [p.strip() for p in parts if p.strip()] or [kannada_text.strip()]

        silence = np.zeros(
            int(_INTER_SENTENCE_SILENCE_S * self.sample_rate),
            dtype=np.float32,
        )

        t_start = time.perf_counter()
        audio_parts: list[np.ndarray] = []
        for sentence in sentences:
            audio_parts.append(self._synthesise_kannada(sentence))
            if len(sentences) > 1:
                audio_parts.append(silence)

        self.last_synthesis_time_s = time.perf_counter() - t_start

        if len(sentences) > 1 and audio_parts:
            audio_parts = audio_parts[:-1]

        audio = np.concatenate(audio_parts)
        sr = self.sample_rate

        if output_path:
            out_dir = os.path.dirname(output_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            sf.write(output_path, audio, sr)

        if play:
            try:
                import sounddevice as sd  # noqa: PLC0415
                sd.play(audio, sr)
                sd.wait()
            except Exception:
                pass

        return audio, sr

    def synthesise(
        self,
        english_text: str,
        output_path: str | None = None,
        play: bool = False,
        voice_description: str | None = None,  # kept for API compat; unused
    ) -> tuple[np.ndarray, int] | None:
        """
        Translate English text to Kannada and synthesise spoken audio.

        Long texts are split into sentences before translation and synthesis.
        Each sentence is synthesised separately and concatenated with a
        0.4-second silence gap. This produces better prosody and avoids
        VITS quality degradation on longer inputs.

        Parameters
        ----------
        english_text:
            English text to speak (Decision Router's response_text).
        output_path:
            Save audio to this .wav path if given.
        play:
            Play via sounddevice if True (skipped silently if not installed).
        voice_description:
            Accepted for API compatibility; ignored by MMS-TTS.

        Returns
        -------
        tuple[np.ndarray, int] | None
            (audio_array, sample_rate) or None for empty input.
        """
        if not english_text or not english_text.strip():
            return None

        # Lazy import keeps translation model out of memory at TTS import time
        from backend.translation import translate_en_to_kn  # noqa: PLC0415

        sentences = _split_sentences(english_text)
        silence = np.zeros(int(_INTER_SENTENCE_SILENCE_S * self.sample_rate),
                           dtype=np.float32)

        t_start = time.perf_counter()
        audio_parts: list[np.ndarray] = []

        for sentence in sentences:
            kannada = translate_en_to_kn(sentence)
            if not kannada or not kannada.strip():
                continue
            audio_parts.append(self._synthesise_kannada(kannada))
            if len(sentences) > 1:
                audio_parts.append(silence)

        self.last_synthesis_time_s = time.perf_counter() - t_start

        if not audio_parts:
            return None

        # Remove trailing silence if we added one
        if len(sentences) > 1 and len(audio_parts) > 0:
            audio_parts = audio_parts[:-1]

        audio = np.concatenate(audio_parts)
        sr = self.sample_rate

        if output_path:
            out_dir = os.path.dirname(output_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            sf.write(output_path, audio, sr)

        if play:
            try:
                import sounddevice as sd  # noqa: PLC0415
                sd.play(audio, sr)
                sd.wait()
            except ImportError:
                warnings.warn(
                    "sounddevice not installed -- playback skipped. "
                    "pip install sounddevice",
                    stacklevel=2,
                )
            except Exception as exc:
                warnings.warn("Playback failed: " + str(exc), stacklevel=2)

        return audio, sr
