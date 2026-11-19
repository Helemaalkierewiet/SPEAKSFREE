from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ..audio import inspect_wav
from ..monitor import ResourceMonitor
from ..paths import project_path
from .base import SpeechEngine, Transcription


class VoskEngine(SpeechEngine):
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        super().__init__(name, config)
        try:
            from vosk import Model, SetLogLevel
        except ImportError as exc:
            raise RuntimeError("Vosk ontbreekt; installeer requirements.txt") from exc

        model_path = project_path(config["model_path"])
        if not model_path.is_dir():
            raise FileNotFoundError(
                f"Vosk-model ontbreekt: {model_path}. Voer scripts/setup-models.ps1 uit."
            )
        SetLogLevel(-1)
        started = time.perf_counter()
        self.model = Model(str(model_path))
        self.model_load_seconds = time.perf_counter() - started

    def transcribe(self, audio_file: str | Path, near_live: bool = False) -> Transcription:
        from vosk import KaldiRecognizer

        audio = inspect_wav(audio_file)
        recognizer = KaldiRecognizer(self.model, audio.sample_rate)
        recognizer.SetWords(True)
        chunk_frames = int(audio.sample_rate * 0.2)
        chunk_bytes = chunk_frames * 2
        parts: list[str] = []
        events: list[dict[str, Any]] = []
        previous_partial = ""
        first_text: float | None = None
        started = time.perf_counter()
        monitor = ResourceMonitor().start()
        try:
            for offset in range(0, len(audio.pcm16), chunk_bytes):
                block = audio.pcm16[offset : offset + chunk_bytes]
                if near_live:
                    time.sleep(len(block) / 2 / audio.sample_rate)
                if recognizer.AcceptWaveform(block):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").strip()
                    if text:
                        parts.append(text)
                        elapsed = time.perf_counter() - started
                        first_text = first_text if first_text is not None else elapsed
                        events.append({"at_seconds": elapsed, "kind": "final", "text": text})
                elif near_live:
                    partial = json.loads(recognizer.PartialResult()).get("partial", "").strip()
                    if partial and partial != previous_partial:
                        elapsed = time.perf_counter() - started
                        first_text = first_text if first_text is not None else elapsed
                        events.append({"at_seconds": elapsed, "kind": "partial", "text": partial})
                        previous_partial = partial
            final = json.loads(recognizer.FinalResult()).get("text", "").strip()
            if final:
                parts.append(final)
                elapsed = time.perf_counter() - started
                first_text = first_text if first_text is not None else elapsed
                events.append({"at_seconds": elapsed, "kind": "final", "text": final})
            elapsed = time.perf_counter() - started
            stats = monitor.stop()
            return Transcription(
                engine=self.name,
                audio_file=str(audio.path),
                audio_seconds=audio.duration_seconds,
                transcript_raw=" ".join(parts).strip(),
                processing_seconds=elapsed,
                realtime_factor=elapsed / max(audio.duration_seconds, 1e-9),
                model_load_seconds=self.model_load_seconds,
                peak_rss_mb=stats.peak_rss_mb,
                cpu_average_percent=stats.cpu_average_percent,
                cpu_peak_percent=stats.cpu_peak_percent,
                first_text_seconds=first_text,
                final_text_seconds=elapsed,
                partial_events=events,
            )
        except Exception as exc:
            elapsed = time.perf_counter() - started
            stats = monitor.stop()
            return Transcription(
                engine=self.name,
                audio_file=str(audio.path),
                audio_seconds=audio.duration_seconds,
                transcript_raw=" ".join(parts).strip(),
                processing_seconds=elapsed,
                realtime_factor=elapsed / max(audio.duration_seconds, 1e-9),
                model_load_seconds=self.model_load_seconds,
                peak_rss_mb=stats.peak_rss_mb,
                cpu_average_percent=stats.cpu_average_percent,
                cpu_peak_percent=stats.cpu_peak_percent,
                exit_status="error",
                first_text_seconds=first_text,
                final_text_seconds=None,
                partial_events=events,
                error=f"{type(exc).__name__}: {exc}",
            )

