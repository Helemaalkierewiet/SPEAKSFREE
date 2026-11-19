from __future__ import annotations

import struct
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable

import numpy as np

from .paths import PROJECT_ROOT


STREAM_MAGIC = b"DJIRAW1\0"
HEADER_SIZE = 16
DEFAULT_HELPER = (
    PROJECT_ROOT / "native" / "wasapi-raw-meter" / "WasapiRawMeter.exe"
)


@dataclass(frozen=True)
class RawStreamMetadata:
    channels: int
    sample_rate: int


def read_exact(stream: BinaryIO, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def parse_stream_header(header: bytes) -> RawStreamMetadata:
    if len(header) != HEADER_SIZE:
        raise RuntimeError("De RAW WASAPI-helper stuurde geen volledige header.")
    if header[:8] != STREAM_MAGIC:
        raise RuntimeError("De RAW WASAPI-helper stuurde een onbekend protocol.")
    channels, sample_rate = struct.unpack("<ii", header[8:])
    if not 1 <= channels <= 16 or not 8_000 <= sample_rate <= 384_000:
        raise RuntimeError(
            f"Ongeldig RAW-audioformaat: {channels} kanalen, {sample_rate} Hz."
        )
    return RawStreamMetadata(channels=channels, sample_rate=sample_rate)


class RawWasapiCapture:
    """Read discrete float32 microphone channels from the native RAW WASAPI helper."""

    def __init__(
        self,
        on_block: Callable[[np.ndarray], None],
        on_error: Callable[[str], None],
        device_name: str = "Wireless Mic Rx",
        block_ms: int = 50,
        helper_path: Path = DEFAULT_HELPER,
    ) -> None:
        self.on_block = on_block
        self.on_error = on_error
        self.device_name = device_name
        self.block_ms = block_ms
        self.helper_path = helper_path
        self.process: subprocess.Popen[bytes] | None = None
        self.metadata: RawStreamMetadata | None = None
        self.stop_event = threading.Event()
        self.stderr_lines: list[str] = []

    def start(self) -> RawStreamMetadata:
        if self.process is not None and self.process.poll() is None:
            if self.metadata is None:
                raise RuntimeError("RAW WASAPI draait zonder audioformaat.")
            return self.metadata
        if not self.helper_path.is_file():
            raise FileNotFoundError(
                "RAW WASAPI-helper ontbreekt. Voer scripts\\build-wasapi-meter.ps1 uit."
            )

        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.stop_event.clear()
        self.stderr_lines.clear()
        self.process = subprocess.Popen(
            [
                str(self.helper_path),
                "--device",
                self.device_name,
                "--pcm",
            ],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creation_flags,
        )
        if self.process.stdout is None:
            raise RuntimeError("RAW WASAPI heeft geen audiopijp geopend.")
        header = read_exact(self.process.stdout, HEADER_SIZE)
        self.metadata = parse_stream_header(header)

        threading.Thread(
            target=self._read_audio,
            name="raw-wasapi-audio",
            daemon=True,
        ).start()
        threading.Thread(
            target=self._read_stderr,
            name="raw-wasapi-errors",
            daemon=True,
        ).start()
        return self.metadata

    def _read_audio(self) -> None:
        process = self.process
        metadata = self.metadata
        if process is None or process.stdout is None or metadata is None:
            return
        frames = max(1, round(metadata.sample_rate * self.block_ms / 1000))
        block_size = frames * metadata.channels * 4
        try:
            while not self.stop_event.is_set():
                payload = read_exact(process.stdout, block_size)
                if len(payload) != block_size:
                    break
                block = np.frombuffer(payload, dtype="<f4").reshape(
                    frames, metadata.channels
                )
                self.on_block(block.copy())
        except Exception as exc:
            if not self.stop_event.is_set():
                self.on_error(f"{type(exc).__name__}: {exc}")
        finally:
            if not self.stop_event.is_set() and process.poll() not in (None, 0):
                detail = self.stderr_lines[-1] if self.stderr_lines else "onbekende fout"
                self.on_error(f"RAW WASAPI stopte: {detail}")

    def _read_stderr(self) -> None:
        process = self.process
        if process is None or process.stderr is None:
            return
        for raw in process.stderr:
            text = raw.decode("utf-8", errors="replace").strip()
            if text:
                self.stderr_lines.append(text)
                self.stderr_lines = self.stderr_lines[-20:]

    def stop(self) -> None:
        process = self.process
        self.process = None
        self.stop_event.set()
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        if process is not None:
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()

