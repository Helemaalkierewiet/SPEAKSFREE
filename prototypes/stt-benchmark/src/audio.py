from __future__ import annotations

import contextlib
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


TARGET_SAMPLE_RATE = 16_000


@dataclass(frozen=True)
class AudioData:
    path: Path
    pcm16: bytes
    sample_rate: int
    channels: int
    frames: int

    @property
    def duration_seconds(self) -> float:
        return self.frames / self.sample_rate if self.sample_rate else 0.0


def inspect_wav(path: str | Path) -> AudioData:
    source = Path(path).resolve()
    with contextlib.closing(wave.open(str(source), "rb")) as handle:
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        sample_rate = handle.getframerate()
        frames = handle.getnframes()
        compression = handle.getcomptype()
        pcm = handle.readframes(frames)
    if compression != "NONE":
        raise ValueError(f"{source} is geen ongecomprimeerde PCM-WAV")
    if sample_width != 2:
        raise ValueError(f"{source} is geen 16-bit PCM-WAV")
    if channels != 1:
        raise ValueError(f"{source} is niet mono (kanalen: {channels})")
    if sample_rate != TARGET_SAMPLE_RATE:
        raise ValueError(
            f"{source} heeft {sample_rate} Hz; vereist is {TARGET_SAMPLE_RATE} Hz"
        )
    return AudioData(source, pcm, sample_rate, channels, frames)


def write_pcm16_wav(path: str | Path, pcm16: bytes, sample_rate: int = TARGET_SAMPLE_RATE) -> Path:
    destination = Path(path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.closing(wave.open(str(destination), "wb")) as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm16)
    return destination


@contextlib.contextmanager
def temporary_wav(pcm16: bytes, sample_rate: int = TARGET_SAMPLE_RATE) -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="stt-benchmark-") as directory:
        path = Path(directory) / "window.wav"
        write_pcm16_wav(path, pcm16, sample_rate)
        yield path

