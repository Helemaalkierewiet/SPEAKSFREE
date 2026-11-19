from __future__ import annotations

from typing import Any

from .base import SpeechEngine


def create_engine(name: str, config: dict[str, Any]) -> SpeechEngine:
    entry = config["engines"][name]
    kind = entry["kind"]
    if kind == "vosk":
        from .vosk_engine import VoskEngine

        return VoskEngine(name, entry)
    if kind == "whisper.cpp":
        from .whisper_cpp_engine import WhisperCppEngine

        return WhisperCppEngine(name, entry)
    if kind == "onnx-asr":
        from .onnx_asr_engine import OnnxAsrEngine

        return OnnxAsrEngine(name, entry)
    raise ValueError(f"Onbekend engine-type: {kind}")


__all__ = ["SpeechEngine", "create_engine"]

