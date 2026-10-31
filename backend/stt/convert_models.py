"""
backend/stt/convert_models.py

One-time model conversion script: HuggingFace checkpoint → CTranslate2 int8.

Run this ONCE before using the STT module.  The converted models are saved
locally under models/ and are never downloaded again (fully offline after
this step).

Usage
-----
    # Convert every registered model
    python backend/stt/convert_models.py --model all

    # Convert only the baseline (openai/whisper-medium)
    python backend/stt/convert_models.py --model baseline

    # Convert only the Kannada-specialized model
    python backend/stt/convert_models.py --model specialized

    # Convert the Vasista Kannada Medium production model
    python backend/stt/convert_models.py --model vasista-medium

Requirements
------------
- Internet connection (one-time only, for HuggingFace download)
- ctranslate2 installed: pip install ctranslate2
- ~6 GB free disk space for both models during conversion
  (int8 output is ~400 MB per model; originals are ~1.5 GB each)
- GPU not required, but speeds up conversion if available

Implementation note — why no subprocess call
--------------------------------------------
ctranslate2 exposes ctranslate2.converters.TransformersConverter as a fully
supported Python API.  Using it directly means this script works regardless
of whether the ct2-transformers-converter CLI is on PATH — which it often
is NOT on Windows when ctranslate2 is installed into a user-site-packages
directory (e.g. %APPDATA%\\Python\\Python3xx\\Scripts is not added to PATH
by default).  The programmatic API is identical in behaviour to the CLI.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from ctranslate2.converters import TransformersConverter


class _CompatibleTransformersConverter(TransformersConverter):
    """Bridge CTranslate2 4.8's loader argument to Transformers < 4.56."""

    def load_model(self, model_class, model_name_or_path, **kwargs):
        # CTranslate2 4.8 uses the newer ``dtype`` argument. Transformers
        # 4.53 still expects ``torch_dtype`` and otherwise forwards ``dtype``
        # into Whisper's constructor, where it raises TypeError.
        if "dtype" in kwargs:
            import transformers

            version = tuple(
                int(part)
                for part in transformers.__version__.split(".")[:2]
                if part.isdigit()
            )
            if version < (4, 56):
                kwargs["torch_dtype"] = kwargs.pop("dtype")
        return super().load_model(model_class, model_name_or_path, **kwargs)


# ---------------------------------------------------------------------------
# Model registry
# Add new models here — nothing else needs to change.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

MODELS: dict[str, dict[str, str]] = {
    "baseline": {
        "hf_id": "openai/whisper-medium",
        "output_dir": os.path.join(_PROJECT_ROOT, "models", "whisper-medium-ct2"),
        "description": "Generic multilingual Whisper (not Kannada-tuned) — benchmark baseline",
    },
    "specialized": {
        "hf_id": "ARTPARK-IISc/whisper-medium-vaani-kannada",
        "output_dir": os.path.join(_PROJECT_ROOT, "models", "whisper-medium-vaani-ct2"),
        "description": "Whisper fine-tuned on VAANI Kannada dataset — rollback model",
    },
    "vasista-medium": {
        "hf_id": "vasista22/whisper-kannada-medium",
        "output_dir": os.path.join(_PROJECT_ROOT, "models", "whisper-kannada-medium-ct2"),
        "description": "Vasista Whisper Medium fine-tuned for Kannada — production default",
    },
}

# Files expected in every valid CTranslate2 Whisper output directory.
_EXPECTED_FILES = ["model.bin", "config.json", "vocabulary.json", "tokenizer.json"]

# Standard Whisper feature-extractor settings (shared across all Whisper sizes).
_PREPROCESSOR_CONFIG = {
    "chunk_length": 30,
    "feature_size": 80,
    "hop_length": 160,
    "n_fft": 400,
    "n_samples": 480000,
    "nb_max_frames": 3000,
    "padding_side": "right",
    "padding_value": 0.0,
    "sampling_rate": 16000,
}


def _write_offline_assets(hf_id: str, output_dir: str) -> None:
    """
    Copy tokenizer assets into the CT2 directory for fully offline inference.

    CTranslate2 conversion produces model.bin + vocabulary.json but not
    tokenizer.json.  faster-whisper falls back to HuggingFace Hub for the
    tokenizer when it is missing, which breaks offline mode (HF_HUB_OFFLINE=1).
    """
    from transformers import AutoTokenizer

    print("  Writing tokenizer.json for offline inference ...")
    tokenizer = AutoTokenizer.from_pretrained(hf_id)
    tokenizer.save_pretrained(output_dir)

    preprocessor_path = os.path.join(output_dir, "preprocessor_config.json")
    if not os.path.isfile(preprocessor_path):
        with open(preprocessor_path, "w", encoding="utf-8") as f:
            json.dump(_PREPROCESSOR_CONFIG, f, indent=2)


def convert_model(model_key: str) -> None:
    """
    Download and convert a single model to CTranslate2 int8 format.

    Uses ``ctranslate2.converters.TransformersConverter`` directly — no
    subprocess or PATH dependency.  The converter downloads the HuggingFace
    checkpoint on first call and caches it in the HF hub cache directory.

    Parameters
    ----------
    model_key:
        One of the keys in :data:`MODELS`.

    Raises
    ------
    SystemExit
        On conversion failure, with a descriptive message.
    """
    if model_key not in MODELS:
        print(f"[ERROR] Unknown model key '{model_key}'.", file=sys.stderr)
        sys.exit(1)

    cfg = MODELS[model_key]
    hf_id: str = cfg["hf_id"]
    output_dir: str = cfg["output_dir"]
    description: str = cfg["description"]

    print(f"\n{'='*60}")
    print(f"  Converting : {model_key}")
    print(f"  Source     : {hf_id}")
    print(f"  Purpose    : {description}")
    print(f"  Output     : {output_dir}")
    print(f"{'='*60}")
    print("  Downloading from HuggingFace and converting to CTranslate2 int8 ...")
    print("  (This may take several minutes on first run — model is ~1.5 GB)\n")

    try:
        converter = _CompatibleTransformersConverter(
            hf_id,
            low_cpu_mem_usage=True,   # Keeps peak RAM lower during conversion
        )
        converter.convert(
            output_dir,
            quantization="int8",
            force=True,               # Overwrite if output_dir already exists
        )
    except Exception as exc:
        print(
            f"\n[ERROR] Conversion failed for '{model_key}':\n  {exc}\n",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        _write_offline_assets(hf_id, output_dir)
    except Exception as exc:
        print(
            f"\n[WARNING] Could not write offline tokenizer assets for '{model_key}':\n  {exc}\n"
            "          STT may fail in offline mode without tokenizer.json in the model directory.",
            file=sys.stderr,
        )

    # --- Verify expected output files ---
    missing = [
        f for f in _EXPECTED_FILES
        if not os.path.exists(os.path.join(output_dir, f))
    ]

    if missing:
        print(
            f"\n[WARNING] Conversion completed but these expected files are missing: {missing}\n"
            f"          The model directory may be incomplete.",
            file=sys.stderr,
        )
    else:
        model_bin = os.path.join(output_dir, "model.bin")
        size_mb = os.path.getsize(model_bin) / (1024 * 1024)
        print(f"\n[OK] '{model_key}' converted successfully.")
        print(f"     model.bin size : {size_mb:.1f} MB")
        print(f"     Location       : {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Convert HuggingFace Whisper checkpoints to CTranslate2 int8 format.\n"
            "Run once before using the STT module.\n\n"
            "Models:\n"
            + "\n".join(f"  {k}: {v['hf_id']}" for k, v in MODELS.items())
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--model",
        choices=[*MODELS.keys(), "all"],
        default="all",
        help="Which model to convert (default: all)",
    )
    args = parser.parse_args()

    keys_to_convert = list(MODELS.keys()) if args.model == "all" else [args.model]

    for key in keys_to_convert:
        convert_model(key)

    print(f"\n{'='*60}")
    print("  All requested conversions complete.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
