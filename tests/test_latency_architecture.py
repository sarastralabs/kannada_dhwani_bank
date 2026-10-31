"""Regression tests for non-blocking semantic responses and static TTS warming."""

from __future__ import annotations


def test_worker_process_can_skip_tts(monkeypatch) -> None:
    import backend.pipeline
    import run_pipeline_worker
    from backend.pipeline import PipelineResult

    seen: dict = {}

    def fake_pipeline(wav: str, **kwargs):
        seen.update(wav=wav, **kwargs)
        return PipelineResult(
            audio_path=wav,
            kannada_text="ನಮಸ್ಕಾರ",
            response_text_kn="ದಯವಿಟ್ಟು ಹೇಳಿ.",
        )

    monkeypatch.setattr(backend.pipeline, "run_pipeline", fake_pipeline)
    result = run_pipeline_worker._process(
        "sample.wav",
        {"mode": "assist"},
        include_audio=False,
    )

    assert seen["synthesise_audio"] is False
    assert result["audio_b64"] == ""
    assert result["response_text_kn"] == "ದಯವಿಟ್ಟು ಹೇಳಿ."


def test_bridge_sends_include_audio_flag(monkeypatch) -> None:
    from backend import pipeline_bridge

    seen: dict = {}
    monkeypatch.setattr(
        pipeline_bridge,
        "_request",
        lambda payload: seen.update(payload) or {"ok": True, "audio_b64": ""},
    )

    pipeline_bridge.process_wav(
        "sample.wav",
        {"mode": "assist"},
        include_audio=False,
    )

    assert seen["cmd"] == "process"
    assert seen["include_audio"] is False


def test_bridge_preserves_audio_for_legacy_callers(monkeypatch) -> None:
    from backend import pipeline_bridge

    seen: dict = {}
    monkeypatch.setattr(
        pipeline_bridge,
        "_request",
        lambda payload: seen.update(payload) or {"ok": True, "audio_b64": "audio"},
    )

    pipeline_bridge.process_wav("sample.wav")
    assert seen["include_audio"] is True


def test_static_phrase_registry_contains_only_fixed_content() -> None:
    from backend.tts.static_phrases import static_kannada_phrases

    phrases = static_kannada_phrases()
    assert "ದಯವಿಟ್ಟು ಮತ್ತೆ ಹೇಳಿ." in phrases
    assert len(phrases) >= 65
    assert len(phrases) == len(set(phrases))
    assert all("123456" not in phrase for phrase in phrases)
    assert all(phrase.strip() for phrase in phrases)


def test_mobile_fill_retries_same_model_with_english_digit_decode(monkeypatch) -> None:
    import backend.stt
    import run_pipeline_worker

    calls: list[str] = []

    def fake_transcribe(_wav: str, **kwargs) -> str:
        language = kwargs.get("language", "kn")
        calls.append(language)
        if language == "en":
            return "nine seven four one four four seven seven six seven"
        return "ಒಂದು ಒಂದು"

    monkeypatch.setattr(backend.stt, "transcribe", fake_transcribe)
    result = run_pipeline_worker._fill("sample.wav", "digits", "mobile_number")

    assert calls == ["kn", "en"]
    assert result["value"] == "9741447767"
    assert result["validation_error"] is None
    assert result["numeric_retry_used"] is True
