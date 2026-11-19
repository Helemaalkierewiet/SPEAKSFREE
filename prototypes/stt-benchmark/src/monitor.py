from __future__ import annotations

import os
import threading
import time
from dataclasses import asdict, dataclass


@dataclass
class ResourceStats:
    cpu_average_percent: float = 0.0
    cpu_peak_percent: float = 0.0
    peak_rss_mb: float = 0.0
    samples: int = 0

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


class ResourceMonitor:
    """Sample CPU time and RSS for a process plus all descendants."""

    def __init__(self, pid: int | None = None, interval: float = 0.05) -> None:
        self.pid = pid or os.getpid()
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._stats = ResourceStats()
        self._cpu_samples: list[float] = []

    @staticmethod
    def _cluster(process):
        try:
            return [process, *process.children(recursive=True)]
        except Exception:
            return [process]

    @staticmethod
    def _cpu_time(processes) -> float:
        total = 0.0
        for process in processes:
            try:
                value = process.cpu_times()
                total += value.user + value.system
            except Exception:
                continue
        return total

    @staticmethod
    def _rss(processes) -> int:
        total = 0
        for process in processes:
            try:
                total += process.memory_info().rss
            except Exception:
                continue
        return total

    def start(self) -> "ResourceMonitor":
        try:
            import psutil
        except ImportError:
            return self
        root = psutil.Process(self.pid)

        def sample() -> None:
            previous_time = time.perf_counter()
            previous_cpu = self._cpu_time(self._cluster(root))
            while not self._stop.wait(self.interval):
                now = time.perf_counter()
                processes = self._cluster(root)
                cpu_time = self._cpu_time(processes)
                elapsed = max(now - previous_time, 1e-9)
                cpu_percent = max(0.0, (cpu_time - previous_cpu) / elapsed * 100.0)
                rss_mb = self._rss(processes) / (1024 * 1024)
                self._cpu_samples.append(cpu_percent)
                self._stats.cpu_peak_percent = max(self._stats.cpu_peak_percent, cpu_percent)
                self._stats.peak_rss_mb = max(self._stats.peak_rss_mb, rss_mb)
                previous_time, previous_cpu = now, cpu_time

        self._thread = threading.Thread(target=sample, name="resource-monitor", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> ResourceStats:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.interval * 4))
        self._stats.samples = len(self._cpu_samples)
        if self._cpu_samples:
            self._stats.cpu_average_percent = sum(self._cpu_samples) / len(self._cpu_samples)
        return self._stats

    def __enter__(self) -> "ResourceMonitor":
        return self.start()

    def __exit__(self, *_args) -> None:
        self.stop()

