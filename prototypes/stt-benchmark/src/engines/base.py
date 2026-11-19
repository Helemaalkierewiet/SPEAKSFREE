from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Transcription:
    engine: str
    audio_file: str
    audio_seconds: float
    transcript_raw: str
    processing_seconds: float
    realtime_factor: float
    model_load_seconds: float
    peak_rss_mb: float
    cpu_average_percent: float
    cpu_peak_percent: float
    exit_status: str = "ok"
    first_text_seconds: float | None = None
    final_text_seconds: float | None = None
    partial_events: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SpeechEngine(ABC):
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        self.name = name
        self.config = config
        self.model_load_seconds = 0.0

    @abstractmethod
    def transcribe(self, audio_file: str | Path, near_live: bool = False) -> Transcription:
        raise NotImplementedError

