"""
backend/translation/translator.py

Core inference wrapper for IndicTrans2 Kannada ↔ English translation.

Usage
-----
    from backend.translation.translator import IndicTranslator

    # Kannada → English
    t = IndicTranslator("ai4bharat/indictrans2-indic-en-dist-200M")
    results = t.translate(
        ["ನನ್ನ ಖಾತೆಯ ಬಾಕಿ ಎಷ್ಟಿದೆ"],
        src_lang="kan_Knda",
        tgt_lang="eng_Latn",
    )
    print(results)            # ["What is the balance in my account?"]
    print(t.last_inference_time_s)   # e.g. 1.8

Model download
--------------
On the first call, ``from_pretrained()`` downloads the model from HuggingFace
and caches it in the HF hub cache directory (~/.cache/huggingface/hub on
Linux, %USERPROFILE%\\.cache\\huggingface\\hub on Windows).
All subsequent calls load from disk — no internet access needed after the
first run.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from IndicTransToolkit import IndicProcessor

from backend.translation.exceptions import TranslationInputError
from backend.translation.utils import is_empty_input, normalise_input, validate_direction


def _detect_device() -> str:
    """
    Return ``"cuda"`` if a CUDA-capable GPU is available, else ``"cpu"``.

    Mirrors the exact pattern used in ``backend/stt/transcriber.py`` so
    device detection is consistent across all pipeline modules.
    """
    return "cuda" if torch.cuda.is_available() else "cpu"


class IndicTranslator:
    """
    Translate text between Kannada and English using IndicTrans2 distilled 200M.

    Wraps HuggingFace ``AutoModelForSeq2SeqLM`` + ``AutoTokenizer`` with
    ``IndicTransToolkit.IndicProcessor`` for IndicTrans2-specific pre- and
    post-processing.

    Parameters
    ----------
    model_name:
        HuggingFace model ID.  Must be one of the two 200M dist models:
        - ``"ai4bharat/indictrans2-indic-en-dist-200M"`` (Kannada → English)
        - ``"ai4bharat/indictrans2-en-indic-dist-200M"`` (English → Kannada)
    device:
        ``"cpu"`` or ``"cuda"``.  If ``None`` (default), auto-detected via
        :func:`_detect_device`.  Mirrors the STT module's pattern.
    torch_dtype:
        PyTorch dtype for model weights.  If ``None`` (default), set to
        ``torch.float16`` on CUDA (halves memory use) and ``torch.float32``
        on CPU (float16 is not accelerated on most CPUs).

    Attributes
    ----------
    last_inference_time_s : float
        Wall-clock seconds taken by the most recent :meth:`translate` call.
        Initialised to ``0.0``; updated after every call.
    """

    def __init__(
        self,
        model_name: str,
        device: str | None = None,
        torch_dtype: torch.dtype | None = None,
    ) -> None:
        self._model_name = model_name
        self._device = device if device is not None else _detect_device()

        # float16 on CUDA (halves ~800 MB → ~400 MB); float32 on CPU
        # (float16 is not natively accelerated on most CPUs and can silently
        # produce lower-quality outputs with some transformers versions)
        if torch_dtype is not None:
            self._torch_dtype = torch_dtype
        else:
            self._torch_dtype = (
                torch.float16 if self._device == "cuda" else torch.float32
            )

        self.last_inference_time_s: float = 0.0

        # IndicProcessor is stateless for inference — one instance per
        # translator object, reused across all translate() calls.
        self._ip = IndicProcessor(inference=True)

        self._tokenizer, self._model = self._load_model()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_model(
        self,
    ) -> tuple[AutoTokenizer, AutoModelForSeq2SeqLM]:
        """
        Download (on first run) or load from cache the tokenizer and model.

        Returns
        -------
        tuple[AutoTokenizer, AutoModelForSeq2SeqLM]
            The loaded tokenizer and model, with the model already moved
            to the target device.
        """
        tokenizer = AutoTokenizer.from_pretrained(
            self._model_name,
            trust_remote_code=True,
        )
        # IndicTrans2 custom code rejects `dtype=` kwarg on __init__.
        # Load weights first, then cast/move — avoids transformers version skew.
        model = AutoModelForSeq2SeqLM.from_pretrained(
            self._model_name,
            trust_remote_code=True,
        )
        # IndicTrans2 custom code rejects `dtype=` on from_pretrained/__init__.
        model = model.to(device=self._device, dtype=self._torch_dtype)
        model.eval()   # disable dropout; no effect on output but good practice
        return tokenizer, model

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def translate(
        self,
        texts: list[str],
        src_lang: str,
        tgt_lang: str,
    ) -> list[str]:
        """
        Translate a batch of strings from *src_lang* to *tgt_lang*.

        Empty or whitespace-only strings are passed through as ``""``
        without being sent to the model — this matches the STT module's
        pattern of silently handling empty inputs.

        Parameters
        ----------
        texts:
            List of source-language strings to translate.  May be a
            single-element list for the common single-sentence case.
        src_lang:
            IndicTrans2 source language code (e.g. ``"kan_Knda"``).
        tgt_lang:
            IndicTrans2 target language code (e.g. ``"eng_Latn"``).

        Returns
        -------
        list[str]
            Translated strings in the same order as *texts*.
            Empty strings in input map to empty strings in output.

        Raises
        ------
        TranslationInputError
            If the ``(src_lang, tgt_lang)`` direction is not supported.
        TranslationInputError
            If any element of *texts* is not a ``str``.

        Examples
        --------
        >>> t = IndicTranslator("ai4bharat/indictrans2-indic-en-dist-200M")
        >>> t.translate(["ನನ್ನ ಖಾತೆಯ ಬಾಕಿ ಎಷ್ಟಿದೆ"], "kan_Knda", "eng_Latn")
        ["What is the balance in my account?"]
        """
        # --- 1. Validate direction ---
        validate_direction(src_lang, tgt_lang)

        # --- 2. Type-check all inputs ---
        for i, text in enumerate(texts):
            if not isinstance(text, str):
                raise TranslationInputError(
                    f"All inputs must be strings. "
                    f"Got {type(text).__name__!r} at index {i}."
                )

        # --- 3. Separate empty inputs from non-empty ones.
        #        Record original positions so we can reconstruct the full
        #        output list in the same order after inference.
        results: list[str] = [""] * len(texts)
        non_empty_indices: list[int] = []
        non_empty_texts: list[str] = []

        for i, text in enumerate(texts):
            if is_empty_input(text):
                results[i] = ""   # already set; explicit for clarity
            else:
                non_empty_indices.append(i)
                non_empty_texts.append(normalise_input(text))

        # If every input was empty, return early without touching the model.
        if not non_empty_texts:
            self.last_inference_time_s = 0.0
            return results

        # --- 4. Pre-process with IndicProcessor ---
        preprocessed = self._ip.preprocess_batch(
            non_empty_texts,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
        )

        # --- 5. Tokenize ---
        batch = self._tokenizer(
            preprocessed,
            padding="longest",
            truncation=True,
            max_length=256,
            return_tensors="pt",
        ).to(self._device)

        # --- 6. Generate with KV cache enabled using legacy tuple format ---
        # use_cache=True with cache_implementation="legacy" fixes the
        # _reorder_cache incompatibility in IndicTrans2's custom generate():
        #   - DynamicCache (default since transformers 4.38) breaks _reorder_cache
        #   - "legacy" forces the tuple-of-tuples format IndicTrans2 expects
        #   - This gives 2-4x speedup over use_cache=False on GPU
        # num_beams=2: banking queries are 5-8 words max — beam=2 gives
        # near-identical BLEU to beam=5 at half the compute for short sentences.
        t_start = time.perf_counter()

        # Set legacy cache once per model instance
        if not hasattr(self, "_legacy_cache_set"):
            self._model.config.cache_implementation = "legacy"
            self._legacy_cache_set = True

        from transformers import GenerationConfig  # noqa: PLC0415
        _gen_cfg = GenerationConfig(
            num_beams=2,
            max_length=256,
            use_cache=True,
        )

        with torch.inference_mode():
            generated_ids = self._model.generate(
                **batch,
                generation_config=_gen_cfg,
            )

        self.last_inference_time_s = time.perf_counter() - t_start

        # --- 7. Decode ---
        decoded = self._tokenizer.batch_decode(
            generated_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        )

        # --- 8. Post-process with IndicProcessor ---
        translated = self._ip.postprocess_batch(decoded, lang=tgt_lang)

        # --- 9. Reinsert translated strings at their original positions ---
        for idx, translation in zip(non_empty_indices, translated):
            results[idx] = translation

        return results
