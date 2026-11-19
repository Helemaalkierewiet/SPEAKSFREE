from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from ..audio import inspect_wav, write_pcm16_wav
from ..monitor import ResourceMonitor
from ..paths import project_path
from .base import SpeechEngine, Transcription


LOAD_TIME_PATTERN = re.compile(r"load time\s*=\s*([0-9.]+)\s*ms", re.IGNORECASE)


class WhisperCppEngine(SpeechEngine):
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        super().__init__(name, config)
        self.model_path = project_path(config["model_path"])
        self.binary_path = project_path(config["binary_path"])
        self.vad_model_path = (
            project_path(config["vad_model_path"])
            if config.get("vad_model_path")
            else None
        )
        if config.get("language") != "nl" or config.get("translate") is not False:
            raise ValueError("Whisper moet language=nl en translate=false gebruiken")
        if not self.model_path.is_file() or not self.binary_path.is_file():
            raise FileNotFoundError(
                "Whisper-model of whisper-cli ontbreekt. Voer scripts/setup-models.ps1 uit."
            )
        if self.vad_model_path is not None and not self.vad_model_path.is_file():
            raise FileNotFoundError(
                f"Silero VAD-model ontbreekt: {self.vad_model_path}. "
                "Voer scripts/setup-models.ps1 uit."
            )
        self.threads = int(config.get("threads") or max(1, os.cpu_count() or 1))
        self.window_seconds = float(config.get("near_live_window_seconds", 5.0))

    def _run_cli(self, audio_path: Path, output_prefix: Path) -> tuple[str, float, str]:
        command = [
            str(self.binary_path),
            "-m",
            str(self.model_path),
            "-f",
            str(audio_path),
            "-l",
            "nl",
            "-t",
            str(self.threads),
            "-nt",
            "-otxt",
            "-of",
            str(output_prefix),
        ]
        if self.vad_model_path is not None:
            command.extend(
                [
                    "--vad",
                    "--vad-model",
                    str(self.vad_model_path),
                    "--vad-threshold",
                    str(self.config.get("vad_threshold", 0.5)),
                    "--vad-min-speech-duration-ms",
                    str(self.config.get("vad_min_speech_ms", 250)),
                    "--vad-min-silence-duration-ms",
                    str(self.config.get("vad_min_silence_ms", 350)),
                    "--vad-max-speech-duration-s",
                    str(self.config.get("vad_max_speech_seconds", 15)),
                    "--vad-speech-pad-ms",
                    str(self.config.get("vad_speech_pad_ms", 150)),
                    "--vad-samples-overlap",
                    str(self.config.get("vad_samples_overlap_seconds", 0.1)),
                ]
            )
        # whisper.cpp enables translation only with -tr. Deliberately never add it.
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        combined = f"{completed.stdout}\n{completed.stderr}"
        if completed.returncode != 0:
            raise RuntimeError(
                f"whisper-cli stopte met code {completed.returncode}: {combined[-2000:].strip()}"
            )
        output_file = output_prefix.with_suffix(".txt")
        if not output_file.exists():
            raise RuntimeError("whisper-cli heeft geen tekstbestand gemaakt")
        text = output_file.read_text(encoding="utf-8-sig").strip()
        match = LOAD_TIME_PATTERN.search(combined)
        load_seconds = float(match.group(1)) / 1000.0 if match else 0.0
        return text, load_seconds, combined

    def transcribe(self, audio_file: str | Path, near_live: bool = False) -> Transcription:
        audio = inspect_wav(audio_file)
        started = time.perf_counter()
        monitor = ResourceMonitor().start()
        parts: list[str] = []
        events: list[dict[str, Any]] = []
        first_text: float | None = None
        load_seconds = 0.0
        try:
            temporary_root = project_path("results/tmp")
            temporary_root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix="whisper-benchmark-", dir=temporary_root
            ) as directory:
                temp = Path(directory)
                if not near_live:
                    text, load_seconds, _ = self._run_cli(audio.path, temp / "transcript")
                    parts.append(text)
                else:
                    # Baseline strategy: non-overlapping 5 s windows. This avoids duplicate
                    # words by construction and keeps the comparison reproducible.
                    window_bytes = max(2, int(self.window_seconds * audio.sample_rate) * 2)
                    for index, offset in enumerate(range(0, len(audio.pcm16), window_bytes)):
                        pcm = audio.pcm16[offset : offset + window_bytes]
                        time.sleep(len(pcm) / 2 / audio.sample_rate)
                        window_path = temp / f"window-{index:04d}.wav"
                        write_pcm16_wav(window_path, pcm, audio.sample_rate)
                        text, window_load, _ = self._run_cli(
                            window_path, temp / f"transcript-{index:04d}"
                        )
                        load_seconds += window_load
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
                model_load_seconds=load_seconds,
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
                model_load_seconds=load_seconds,
                peak_rss_mb=stats.peak_rss_mb,
                cpu_average_percent=stats.cpu_average_percent,
                cpu_peak_percent=stats.cpu_peak_percent,
                exit_status="error",
                first_text_seconds=first_text,
                error=f"{type(exc).__name__}: {exc}",
                partial_events=events,
            )

