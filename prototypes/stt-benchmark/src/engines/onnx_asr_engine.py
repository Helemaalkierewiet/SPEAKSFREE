from __future__ import annotations

import tempfile
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ..audio import inspect_wav, write_pcm16_wav
from ..monitor import ResourceMonitor
from ..paths import project_path
from .base import SpeechEngine, Transcription


def result_text(value: Any) -> str:
    """Turn onnx-asr's plain, timestamped or segmented result into text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("text", "transcript", "transcription"):
            if key in value:
                return result_text(value[key])
        return ""
    text = getattr(value, "text", None)
    if text is not None:
        return result_text(text)
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        return " ".join(part for item in value if (part := result_text(item))).strip()
    return str(value).strip()


class OnnxAsrEngine(SpeechEngine):
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        super().__init__(name, config)
        if config.get("language") != "nl":
            raise ValueError("De ONNX-route moet voor deze benchmark language=nl gebruiken")
        try:
            import onnx_asr
            import onnxruntime as ort
        except ImportError as exc:
            raise RuntimeError(
                "onnx-asr ontbreekt; installeer requirements.txt opnieuw"
            ) from exc

        self.model_path = project_path(config["model_path"])
        if not self.model_path.is_dir() or not (self.model_path / "config.json").is_file():
            raise FileNotFoundError(
                f"ONNX-model ontbreekt of is onvolledig: {self.model_path}. "
                "Voer scripts/setup-models.ps1 uit."
            )
        self.window_seconds = float(config.get("near_live_window_seconds", 5.0))
        session_options = ort.SessionOptions()
        threads = int(config.get("threads") or 0)
        if threads > 0:
            session_options.intra_op_num_threads = threads
            session_options.inter_op_num_threads = 1

        load_kwargs: dict[str, Any] = {
            "sess_options": session_options,
            "providers": ["CPUExecutionProvider"],
        }
        if config.get("quantization"):
            load_kwargs["quantization"] = config["quantization"]
        started = time.perf_counter()
        self.model = onnx_asr.load_model(
            config["model_id"], str(self.model_path), **load_kwargs
        )
        self.model_load_seconds = time.perf_counter() - started

    def _recognize(self, audio_path: Path) -> str:
        return result_text(self.model.recognize(str(audio_path)))

    def transcribe(self, audio_file: str | Path, near_live: bool = False) -> Transcription:
        audio = inspect_wav(audio_file)
        started = time.perf_counter()
        monitor = ResourceMonitor().start()
        parts: list[str] = []
        events: list[dict[str, Any]] = []
        first_text: float | None = None
        try:
            if not near_live:
                parts.append(self._recognize(audio.path))
            else:
                temporary_root = project_path("results/tmp")
                temporary_root.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(
                    prefix="onnx-asr-benchmark-", dir=temporary_root
                ) as directory:
                    temp = Path(directory)
                    window_bytes = max(2, int(self.window_seconds * audio.sample_rate) * 2)
                    for index, offset in enumerate(range(0, len(audio.pcm16), window_bytes)):
                        pcm = audio.pcm16[offset : offset + window_bytes]
                        time.sleep(len(pcm) / 2 / audio.sample_rate)
                        window_path = temp / f"window-{index:04d}.wav"
                        write_pcm16_wav(window_path, pcm, audio.sample_rate)
                        text = self._recognize(window_path)
                        if text:
                            parts.append(text)
                            elapsed = time.perf_counter() - started
                            first_text = first_text if first_text is not None else elapsed
                            events.append(
                                {"at_seconds": elapsed, "kind": "final-window", "text": text}
                            )

            elapsed = time.perf_counter() - started
            stats = monitor.stop()
            raw = " ".join(part.strip() for part in parts if part.strip()).strip()
            if raw and first_text is None:
                first_text = elapsed
            return Transcription(
                engine=self.name,
                audio_file=str(audio.path),
                audio_seconds=audio.duration_seconds,
                transcript_raw=raw,
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
