from __future__ import annotations

import argparse
import json
import math
import queue
import re
import signal
import tempfile
import threading
import time
import webbrowser
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np

from .audio import TARGET_SAMPLE_RATE, write_pcm16_wav
from .engines import create_engine
from .paths import PROJECT_ROOT, load_json, project_path
from .raw_wasapi import RawWasapiCapture


WEB_ROOT = PROJECT_ROOT / "web" / "live"
DEFAULT_ENGINE = "whisper-small-q5"
DEFAULT_COLORS = ("#2563eb", "#d97706", "#7c3aed", "#059669")


def rms_to_dbfs(rms: float) -> float:
    return 20.0 * math.log10(max(float(rms), 1e-7))


def resample_to_16k(samples: np.ndarray, source_rate: int) -> np.ndarray:
    """Resample mono float audio to 16 kHz with a small windowed-sinc filter."""
    source = np.asarray(samples, dtype=np.float32).reshape(-1)
    if source_rate == TARGET_SAMPLE_RATE:
        return source.copy()
    if source_rate <= 0:
        raise ValueError("Ongeldige samplefrequentie")

    ratio = TARGET_SAMPLE_RATE / source_rate
    cutoff = min(0.95 * ratio, 0.95)
    half = 31
    positions = np.arange(-half, half + 1, dtype=np.float64)
    kernel = cutoff * np.sinc(cutoff * positions) * np.hamming(positions.size)
    kernel /= kernel.sum()
    filtered = np.convolve(source, kernel.astype(np.float32), mode="same")

    target_length = max(1, round(source.size * ratio))
    source_positions = np.arange(source.size, dtype=np.float64)
    target_positions = np.linspace(0, max(0, source.size - 1), target_length)
    return np.interp(target_positions, source_positions, filtered).astype(np.float32)


def float_to_pcm16(samples: np.ndarray) -> bytes:
    clipped = np.clip(np.asarray(samples), -1.0, 0.9999695)
    return (clipped * 32768.0).astype("<i2").tobytes()


def dutch_cleanup(text: str) -> str:
    """Apply only conservative presentation fixes; keep the raw model text too."""
    replacements = {
        r"\byeah\b": "ja",
        r"\byep\b": "ja",
        r"\bokay\b": "oké",
    }
    cleaned = text.strip()
    # Whisper occasionally completes near-silence as a subtitle copyright line
    # learned from television training captions. Only discard the complete,
    # highly specific line so ordinary mentions of a broadcaster remain intact.
    if re.fullmatch(
        r"\s*(?:\(\s*c\s*\)|©)\s*(?:tv\s+)?[\wÀ-ÿ .'-]{2,50}\s+(?:19|20)\d{2}\s*[.!]?\s*",
        cleaned,
        flags=re.IGNORECASE,
    ):
        return ""
    for pattern, replacement in replacements.items():
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


@dataclass
class CompletedUtterance:
    channel: int
    samples: np.ndarray
    duration_seconds: float
    completed_at: float


class ChannelSegmenter:
    def __init__(
        self,
        channel: int,
        sample_rate: int,
        noise_margin_db: float = 12.0,
        minimum_voice_dbfs: float = -35.0,
        silence_ms: int = 450,
        calibration_ms: int = 3000,
        start_hold_ms: int = 120,
        hysteresis_db: float = 6.0,
        min_speech_ms: int = 250,
        pre_roll_ms: int = 250,
        max_seconds: float = 12.0,
    ) -> None:
        self.channel = channel
        self.sample_rate = sample_rate
        self.noise_margin_db = noise_margin_db
        self.minimum_voice_dbfs = minimum_voice_dbfs
        self.hysteresis_db = hysteresis_db
        self.calibration_frames_target = int(sample_rate * calibration_ms / 1000)
        self.start_hold_frames_target = int(sample_rate * start_hold_ms / 1000)
        self.silence_frames_target = int(sample_rate * silence_ms / 1000)
        self.min_speech_frames = int(sample_rate * min_speech_ms / 1000)
        self.pre_roll_frames_target = int(sample_rate * pre_roll_ms / 1000)
        self.max_frames = int(sample_rate * max_seconds)
        self.pre_roll: deque[np.ndarray] = deque()
        self.pre_roll_frames = 0
        self.active_blocks: list[np.ndarray] = []
        self.active_frames = 0
        self.voiced_frames = 0
        self.silent_frames = 0
        self.start_hold_frames = 0
        self.active = False
        self.calibrated = False
        self.calibration_frames = 0
        self.calibration_values: list[float] = []
        self.noise_floor_db = -70.0
        self.start_threshold_db = -55.0
        self.stop_threshold_db = -61.0

    def configure(
        self,
        noise_margin_db: float,
        minimum_voice_dbfs: float,
        silence_ms: int,
    ) -> None:
        self.noise_margin_db = max(6.0, min(24.0, float(noise_margin_db)))
        self.minimum_voice_dbfs = max(
            -55.0, min(-20.0, float(minimum_voice_dbfs))
        )
        self.silence_frames_target = int(
            self.sample_rate * max(200, min(2000, int(silence_ms))) / 1000
        )
        self._update_thresholds()

    def _update_thresholds(self) -> None:
        adaptive_threshold = self.noise_floor_db + self.noise_margin_db
        self.start_threshold_db = max(
            -55.0,
            min(-20.0, max(adaptive_threshold, self.minimum_voice_dbfs)),
        )
        self.stop_threshold_db = self.start_threshold_db - self.hysteresis_db

    @property
    def calibration_progress(self) -> float:
        if self.calibrated:
            return 1.0
        return min(1.0, self.calibration_frames / self.calibration_frames_target)

    def reset_calibration(self) -> None:
        self._reset_active()
        self.pre_roll.clear()
        self.pre_roll_frames = 0
        self.calibrated = False
        self.calibration_frames = 0
        self.calibration_values = []
        self.noise_floor_db = -70.0
        self._update_thresholds()

    def _remember(self, block: np.ndarray) -> None:
        self.pre_roll.append(block.copy())
        self.pre_roll_frames += block.size
        while self.pre_roll and self.pre_roll_frames > self.pre_roll_frames_target:
            removed = self.pre_roll.popleft()
            self.pre_roll_frames -= removed.size

    def _reset_active(self) -> None:
        self.active_blocks = []
        self.active_frames = 0
        self.voiced_frames = 0
        self.silent_frames = 0
        self.start_hold_frames = 0
        self.active = False

    def process(self, block: np.ndarray, rms: float) -> CompletedUtterance | None:
        mono = np.asarray(block, dtype=np.float32).reshape(-1)
        dbfs = rms_to_dbfs(rms)
        self._remember(mono)

        if not self.calibrated:
            self.calibration_values.append(dbfs)
            self.calibration_frames += mono.size
            if self.calibration_frames >= self.calibration_frames_target:
                values = np.asarray(self.calibration_values, dtype=np.float64)
                self.noise_floor_db = float(
                    np.clip(np.percentile(values, 30), -90.0, -35.0)
                )
                self.calibrated = True
                self._update_thresholds()
            return None

        if not self.active:
            if dbfs < self.start_threshold_db - self.hysteresis_db:
                self.noise_floor_db = 0.995 * self.noise_floor_db + 0.005 * dbfs
                self._update_thresholds()
            if dbfs < self.start_threshold_db:
                self.start_hold_frames = 0
                return None
            self.start_hold_frames += mono.size
            if self.start_hold_frames < self.start_hold_frames_target:
                return None
            self.active = True
            self.active_blocks = [item.copy() for item in self.pre_roll]
            self.active_frames = sum(item.size for item in self.active_blocks)
            self.voiced_frames = self.start_hold_frames
            self.silent_frames = 0
            self.start_hold_frames = 0
            return None

        self.active_blocks.append(mono.copy())
        self.active_frames += mono.size
        if dbfs >= self.stop_threshold_db:
            self.voiced_frames += mono.size
            self.silent_frames = 0
        else:
            self.silent_frames += mono.size

        complete = (
            self.silent_frames >= self.silence_frames_target
            or self.active_frames >= self.max_frames
        )
        if not complete:
            return None

        samples = np.concatenate(self.active_blocks) if self.active_blocks else mono
        voiced_enough = self.voiced_frames >= self.min_speech_frames
        duration = samples.size / self.sample_rate
        self._reset_active()
        self.pre_roll.clear()
        self.pre_roll_frames = 0
        if not voiced_enough:
            return None
        return CompletedUtterance(self.channel, samples, duration, time.time())


class DjiLiveService:
    def __init__(
        self,
        device: str | int | None,
        engine_name: str = DEFAULT_ENGINE,
        auto_start: bool = True,
    ) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError("sounddevice ontbreekt; installeer requirements.txt") from exc

        self.sd = sd
        self.capture_backend = "RAW WASAPI"
        self.requested_device = device
        self.engine_name = engine_name
        self.device_index, self.device_info, self.host_api = self._find_device(device)
        self.sample_rate = int(round(float(self.device_info["default_samplerate"])))
        self.input_channels = min(4, int(self.device_info["max_input_channels"]))
        self.channels = min(2, self.input_channels)
        if self.input_channels < 2:
            raise RuntimeError(
                "De DJI-ontvanger biedt geen twee kanalen. Zet hem op Stereo en verbind via USB."
            )
        self.sd.check_input_settings(
            device=self.device_index,
            channels=self.input_channels,
            samplerate=self.sample_rate,
            dtype="float32",
        )

        self.lock = threading.RLock()
        self.audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=160)
        self.inference_queue: queue.Queue[CompletedUtterance] = queue.Queue(maxsize=32)
        self.stop_event = threading.Event()
        self.stream = None
        self.running = False
        self.model_status = "laden"
        self.model_error: str | None = None
        self.messages: list[dict[str, Any]] = []
        self.next_message_id = 1
        self.levels = [0.0, 0.0]
        self.peaks = [0.0, 0.0]
        self.input_levels = [0.0 for _ in range(self.input_channels)]
        self.input_peaks = [0.0 for _ in range(self.input_channels)]
        self.channel_active = [False, False]
        self.noise_margin_db = 12.0
        self.minimum_voice_dbfs = -35.0
        self.silence_ms = 450
        self.correlation_ema: float | None = None
        self.correlation_samples = 0
        self.dropped_blocks = 0
        self.last_stream_status = ""
        self.audio_error: str | None = None
        self.speakers = [
            {"name": "Spreker 1", "color": DEFAULT_COLORS[0]},
            {"name": "Spreker 2", "color": DEFAULT_COLORS[1]},
        ]
        self.segmenters = [
            ChannelSegmenter(
                channel=index,
                sample_rate=self.sample_rate,
                noise_margin_db=self.noise_margin_db,
                minimum_voice_dbfs=self.minimum_voice_dbfs,
                silence_ms=self.silence_ms,
            )
            for index in range(self.channels)
        ]

        config = load_json("config/models.json")
        if engine_name not in config["engines"]:
            raise ValueError(f"Onbekend model: {engine_name}")
        self.engine = create_engine(engine_name, config)
        self.model_status = "gereed"

        self.audio_thread = threading.Thread(
            target=self._audio_loop, name="dji-audio", daemon=True
        )
        self.inference_thread = threading.Thread(
            target=self._inference_loop, name="dji-inference", daemon=True
        )
        self.audio_thread.start()
        self.inference_thread.start()
        if auto_start:
            self.start_capture()

    def _find_device(self, requested: str | int | None):
        devices = list(self.sd.query_devices())
        host_apis = list(self.sd.query_hostapis())
        if isinstance(requested, str) and requested.isdigit():
            requested = int(requested)
        if isinstance(requested, int):
            info = dict(devices[requested])
            return requested, info, host_apis[int(info["hostapi"])]["name"]

        candidates = []
        needle = str(requested or "Wireless Mic Rx").lower()
        for index, raw in enumerate(devices):
            info = dict(raw)
            if int(info.get("max_input_channels", 0)) < 2:
                continue
            if needle not in str(info.get("name", "")).lower():
                continue
            api_name = str(host_apis[int(info["hostapi"])]["name"])
            preference = 3 if "WASAPI" in api_name else 2 if "DirectSound" in api_name else 1
            candidates.append((preference, index, info, api_name))
        if not candidates:
            raise RuntimeError(
                "DJI Mic 3 niet gevonden. Controleer USB en voer python -m src.capture --list-devices uit."
            )
        _score, index, info, api_name = max(candidates, key=lambda item: item[0])
        return index, info, api_name

    def _callback(self, indata, _frames, _time_info, status) -> None:
        if status:
            self.last_stream_status = str(status)
        try:
            self.audio_queue.put_nowait(indata.copy())
        except queue.Full:
            self.dropped_blocks += 1

    def _raw_callback(self, block: np.ndarray) -> None:
        try:
            self.audio_queue.put_nowait(block)
        except queue.Full:
            self.dropped_blocks += 1

    def _raw_error(self, message: str) -> None:
        with self.lock:
            self.audio_error = message
            self.running = False

    def start_capture(self) -> None:
        with self.lock:
            if self.running:
                return
            try:
                capture = RawWasapiCapture(
                    on_block=self._raw_callback,
                    on_error=self._raw_error,
                    device_name="Wireless Mic Rx",
                )
                metadata = capture.start()
                self.stream = capture
                if (
                    metadata.sample_rate != self.sample_rate
                    or metadata.channels != self.input_channels
                ):
                    self.sample_rate = metadata.sample_rate
                    self.input_channels = metadata.channels
                    self.channels = min(2, self.input_channels)
                    self.segmenters = [
                        ChannelSegmenter(
                            channel=index,
                            sample_rate=self.sample_rate,
                            noise_margin_db=self.noise_margin_db,
                            minimum_voice_dbfs=self.minimum_voice_dbfs,
                            silence_ms=self.silence_ms,
                        )
                        for index in range(self.channels)
                    ]
                    self.levels = [0.0 for _ in range(self.channels)]
                    self.peaks = [0.0 for _ in range(self.channels)]
                    self.input_levels = [0.0 for _ in range(self.input_channels)]
                    self.input_peaks = [0.0 for _ in range(self.input_channels)]
                    self.channel_active = [False for _ in range(self.channels)]
                self.running = True
                self.audio_error = None
                self.last_stream_status = ""
            except Exception as exc:
                self.stream = None
                self.running = False
                self.audio_error = (
                    f"{type(exc).__name__}: {exc}. "
                    "Klik op ‘Microfoon opnieuw verbinden’."
                )
                raise

    def stop_capture(self) -> None:
        with self.lock:
            if self.stream is not None:
                self.stream.stop()
                self.stream = None
            self.running = False
            self.channel_active = [False for _ in self.channel_active]

    def reconnect(self) -> None:
        """Refresh device metadata and restart the native RAW WASAPI stream."""
        self.stop_capture()
        with self.lock:
            # Windows creates a fresh endpoint after a USB reconnect. Refresh the
            # discovery metadata before the native helper selects the new endpoint.
            self.sd._terminate()
            self.sd._initialize()
            self.device_index, self.device_info, self.host_api = self._find_device(
                self.requested_device
            )
            self.sample_rate = int(round(float(self.device_info["default_samplerate"])))
            self.input_channels = min(4, int(self.device_info["max_input_channels"]))
            self.channels = min(2, self.input_channels)
            if self.input_channels < 2:
                raise RuntimeError(
                    "De DJI-ontvanger biedt geen twee kanalen. Zet hem op Stereo."
                )
            self.sd.check_input_settings(
                device=self.device_index,
                channels=self.input_channels,
                samplerate=self.sample_rate,
                dtype="float32",
            )
            self.segmenters = [
                ChannelSegmenter(
                    channel=index,
                    sample_rate=self.sample_rate,
                    noise_margin_db=self.noise_margin_db,
                    minimum_voice_dbfs=self.minimum_voice_dbfs,
                    silence_ms=self.silence_ms,
                )
                for index in range(self.channels)
            ]
            self.levels = [0.0 for _ in range(self.channels)]
            self.peaks = [0.0 for _ in range(self.channels)]
            self.input_levels = [0.0 for _ in range(self.input_channels)]
            self.input_peaks = [0.0 for _ in range(self.input_channels)]
            self.channel_active = [False for _ in range(self.channels)]
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break
        self.start_capture()

    def shutdown(self) -> None:
        self.stop_capture()
        self.stop_event.set()

    def _audio_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                block = self.audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            input_levels = []
            input_peaks = []
            for input_index in range(self.input_channels):
                input_mono = block[:, input_index]
                input_levels.append(
                    float(np.sqrt(np.mean(np.square(input_mono))))
                    if input_mono.size
                    else 0.0
                )
                input_peaks.append(
                    float(np.max(np.abs(input_mono))) if input_mono.size else 0.0
                )
            with self.lock:
                self.input_levels = input_levels
                self.input_peaks = input_peaks
            for index in range(self.channels):
                mono = block[:, index]
                rms = input_levels[index]
                peak = input_peaks[index]
                with self.lock:
                    self.levels[index] = rms
                    self.peaks[index] = peak
                    self.segmenters[index].configure(
                        self.noise_margin_db,
                        self.minimum_voice_dbfs,
                        self.silence_ms,
                    )
                utterance = self.segmenters[index].process(mono, rms)
                with self.lock:
                    self.channel_active[index] = self.segmenters[index].active
                if utterance is not None:
                    try:
                        self.inference_queue.put_nowait(utterance)
                    except queue.Full:
                        self.dropped_blocks += 1
            self._update_correlation(block)

    def _update_correlation(self, block: np.ndarray) -> None:
        if block.shape[1] < 2:
            return
        left, right = block[:, 0], block[:, 1]
        left_rms = float(np.sqrt(np.mean(np.square(left))))
        right_rms = float(np.sqrt(np.mean(np.square(right))))
        if len(self.segmenters) < 2 or not all(
            segmenter.calibrated for segmenter in self.segmenters[:2]
        ):
            return
        left_above = rms_to_dbfs(left_rms) >= self.segmenters[0].start_threshold_db
        right_above = rms_to_dbfs(right_rms) >= self.segmenters[1].start_threshold_db
        if not left_above and not right_above:
            return
        if not left_above or not right_above:
            correlation = 0.0
        else:
            value = np.corrcoef(left, right)[0, 1]
            correlation = 0.0 if not np.isfinite(value) else float(value)
        with self.lock:
            self.correlation_ema = (
                correlation
                if self.correlation_ema is None
                else 0.9 * self.correlation_ema + 0.1 * correlation
            )
            self.correlation_samples += 1

    def _inference_loop(self) -> None:
        temporary_root = project_path("results/tmp/live")
        temporary_root.mkdir(parents=True, exist_ok=True)
        while not self.stop_event.is_set():
            try:
                utterance = self.inference_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            started = time.perf_counter()
            try:
                samples_16k = resample_to_16k(utterance.samples, self.sample_rate)
                pcm16 = float_to_pcm16(samples_16k)
                with tempfile.TemporaryDirectory(prefix="utterance-", dir=temporary_root) as directory:
                    wav_path = Path(directory) / "speech.wav"
                    write_pcm16_wav(wav_path, pcm16)
                    result = self.engine.transcribe(wav_path)
                if result.exit_status != "ok":
                    raise RuntimeError(result.error or "Transcriptie mislukt")
                raw = result.transcript_raw.strip()
                text = dutch_cleanup(raw)
                if text:
                    self._add_message(
                        utterance.channel,
                        text,
                        raw,
                        utterance.duration_seconds,
                        time.perf_counter() - started,
                    )
            except Exception as exc:
                with self.lock:
                    self.model_error = f"{type(exc).__name__}: {exc}"

    def _add_message(
        self,
        channel: int,
        text: str,
        raw: str,
        duration: float,
        processing: float,
    ) -> None:
        with self.lock:
            speaker = self.speakers[channel]
            message = {
                "id": self.next_message_id,
                "channel": channel + 1,
                "speaker": speaker["name"],
                "color": speaker["color"],
                "text": text,
                "raw_text": raw,
                "corrected": text.casefold() != raw.casefold(),
                "time": datetime.now().astimezone().strftime("%H:%M:%S"),
                "audio_seconds": round(duration, 2),
                "processing_seconds": round(processing, 2),
            }
            self.next_message_id += 1
            self.messages.append(message)
            self.messages = self.messages[-120:]

    def configure(self, payload: dict[str, Any]) -> None:
        with self.lock:
            if "noise_margin_db" in payload:
                self.noise_margin_db = max(
                    6.0, min(24.0, float(payload["noise_margin_db"]))
                )
            if "minimum_voice_dbfs" in payload:
                self.minimum_voice_dbfs = max(
                    -55.0, min(-20.0, float(payload["minimum_voice_dbfs"]))
                )
            if "silence_ms" in payload:
                self.silence_ms = max(200, min(2000, int(payload["silence_ms"])))
            for index, incoming in enumerate(payload.get("speakers", [])):
                if index >= len(self.speakers):
                    break
                name = str(incoming.get("name", "")).strip()
                if name:
                    self.speakers[index]["name"] = name[:40]

    def recalibrate(self) -> None:
        """Measure each transmitter's room noise again for three seconds."""
        with self.lock:
            for segmenter in self.segmenters:
                segmenter.reset_calibration()
            self.channel_active = [False for _ in self.channel_active]
            self.correlation_ema = None
            self.correlation_samples = 0

    def clear(self) -> None:
        with self.lock:
            self.messages.clear()

    def status(self) -> dict[str, Any]:
        with self.lock:
            correlation = self.correlation_ema
            mono_suspected = bool(
                self.correlation_samples >= 12
                and correlation is not None
                and correlation > 0.965
            )
            channels = []
            for index in range(self.channels):
                rms = self.levels[index]
                db = rms_to_dbfs(rms)
                segmenter = self.segmenters[index]
                channels.append(
                    {
                        "number": index + 1,
                        "speaker": self.speakers[index]["name"],
                        "color": self.speakers[index]["color"],
                        "level": round(max(0.0, min(1.0, (db + 60.0) / 60.0)), 3),
                        "dbfs": round(db, 1),
                        "peak": round(self.peaks[index], 3),
                        "active": self.channel_active[index],
                        "calibrating": not segmenter.calibrated,
                        "calibration_progress": round(
                            segmenter.calibration_progress, 3
                        ),
                        "noise_floor_dbfs": round(segmenter.noise_floor_db, 1),
                        "start_threshold_dbfs": round(
                            segmenter.start_threshold_db, 1
                        ),
                        "stop_threshold_dbfs": round(
                            segmenter.stop_threshold_db, 1
                        ),
                    }
                )
            raw_channels = []
            for index, rms in enumerate(self.input_levels):
                db = rms_to_dbfs(rms)
                raw_channels.append(
                    {
                        "number": index + 1,
                        "dbfs": round(db, 1),
                        "peak": round(self.input_peaks[index], 3),
                    }
                )
            calibration_progress = min(
                (segmenter.calibration_progress for segmenter in self.segmenters),
                default=1.0,
            )
            return {
                "running": self.running,
                "model": self.engine_name,
                "model_status": self.model_status,
                "model_error": self.model_error,
                "device": {
                    "index": self.device_index,
                    "name": self.device_info["name"],
                    "host_api": self.capture_backend,
                    "sample_rate": self.sample_rate,
                    "channels": self.input_channels,
                    "processed_channels": self.channels,
                },
                "channels": channels,
                "raw_channels": raw_channels,
                "messages": list(self.messages),
                "settings": {
                    "noise_margin_db": self.noise_margin_db,
                    "minimum_voice_dbfs": self.minimum_voice_dbfs,
                    "silence_ms": self.silence_ms,
                    "start_hold_ms": 120,
                    "hysteresis_db": 6.0,
                },
                "calibrating": any(
                    not segmenter.calibrated for segmenter in self.segmenters
                ),
                "calibration_progress": round(calibration_progress, 3),
                "mono_suspected": mono_suspected,
                "correlation": round(correlation, 3) if correlation is not None else None,
                "dropped_blocks": self.dropped_blocks,
                "stream_status": self.last_stream_status,
                "audio_error": self.audio_error,
            }


class LiveRequestHandler(BaseHTTPRequestHandler):
    service: DjiLiveService

    def log_message(self, format: str, *args) -> None:
        return

    def _json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/status":
            self._json(self.service.status())
            return
        static_files = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
        }
        selected = static_files.get(path)
        if selected is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        filename, content_type = selected
        body = (WEB_ROOT / filename).read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/start":
                self.service.start_capture()
            elif path == "/api/stop":
                self.service.stop_capture()
            elif path == "/api/reconnect":
                self.service.reconnect()
            elif path == "/api/clear":
                self.service.clear()
            elif path == "/api/calibrate":
                self.service.recalibrate()
            elif path == "/api/config":
                self.service.configure(self._read_json())
            else:
                self._json({"ok": False, "error": "Onbekende route"}, 404)
                return
            self._json({"ok": True})
        except Exception as exc:
            self._json({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, 500)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Live tweekanaals DJI Mic 3-transcriptie met vaste sprekerkleuren."
    )
    parser.add_argument("--device", help="Apparaatindex of deel van de apparaatnaam")
    parser.add_argument("--engine", default=DEFAULT_ENGINE)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--diagnose", action="store_true", help="Toon DJI-invoer en stop")
    return parser


def diagnose(device: str | None) -> int:
    import sounddevice as sd

    devices = list(sd.query_devices())
    host_apis = list(sd.query_hostapis())
    matches = []
    needle = str(device or "Wireless Mic Rx").lower()
    for index, raw in enumerate(devices):
        info = dict(raw)
        if needle in str(info.get("name", "")).lower() and info.get("max_input_channels", 0):
            matches.append(
                {
                    "index": index,
                    "name": info["name"],
                    "host_api": host_apis[int(info["hostapi"])]["name"],
                    "input_channels": int(info["max_input_channels"]),
                    "sample_rate": int(round(info["default_samplerate"])),
                }
            )
    print(json.dumps(matches, ensure_ascii=False, indent=2))
    return 0 if matches else 2


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.diagnose:
        return diagnose(args.device)
    service = DjiLiveService(args.device, args.engine)
    LiveRequestHandler.service = service
    server = ThreadingHTTPServer((args.host, args.port), LiveRequestHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"DJI Mic 3: {service.device_info['name']} via {service.host_api}")
    print(f"Kanalen: {service.channels}; samplefrequentie: {service.sample_rate} Hz")
    print(f"Model: {args.engine}")
    print(f"Prototype: {url}")
    print("Stoppen: Ctrl+C")

    def stop_server(_signum=None, _frame=None):
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, stop_server)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop_server)
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        service.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
