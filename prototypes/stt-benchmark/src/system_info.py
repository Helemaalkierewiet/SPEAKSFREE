from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

from .paths import PROJECT_ROOT, dump_json, load_json, project_path


def _package_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _powershell_value(script: str) -> str | None:
    if os.name != "nt":
        return None
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        value = completed.stdout.strip()
        return value or None
    except (OSError, subprocess.SubprocessError):
        return None


def _whisper_version(config: dict[str, Any]) -> str | None:
    entry = config["engines"]["whisper-base-q5"]
    binary = project_path(entry["binary_path"])
    if not binary.exists():
        return None
    try:
        completed = subprocess.run(
            [str(binary), "--version"], capture_output=True, text=True, timeout=10
        )
        return (completed.stdout or completed.stderr).strip().splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return entry.get("runtime_release")


def collect_system_info() -> dict[str, Any]:
    try:
        import psutil

        virtual_memory = psutil.virtual_memory()
        battery = psutil.sensors_battery()
        physical_cores = psutil.cpu_count(logical=False)
        logical_cores = psutil.cpu_count(logical=True)
        ram_gb = virtual_memory.total / (1024**3)
        power = None if battery is None else {
            "plugged_in": battery.power_plugged,
            "percent": battery.percent,
        }
    except ImportError:
        physical_cores = None
        logical_cores = os.cpu_count()
        ram_gb = None
        power = None

    models = load_json("config/models.json")
    cpu_name = _powershell_value(
        "(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)"
    ) or _powershell_value(
        "(Get-ItemProperty -LiteralPath 'HKLM:\\HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0').ProcessorNameString"
    ) or platform.processor()
    gpu = _powershell_value(
        "(Get-CimInstance Win32_VideoController | ForEach-Object Name) -join '; '"
    )
    active_power_plan = _powershell_value(
        "(powercfg /getactivescheme) -replace '^.*?:\\s*',''"
    )
    return {
        "captured_at": __import__("datetime").datetime.now().astimezone().isoformat(),
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "architecture": platform.machine(),
        },
        "cpu": {
            "name": cpu_name,
            "physical_cores": physical_cores,
            "logical_cores": logical_cores,
        },
        "memory_total_gb": round(ram_gb, 2) if ram_gb is not None else None,
        "gpu": gpu,
        "gpu_used_by_default": False,
        "power": power,
        "active_power_plan": active_power_plan,
        "python": sys.version,
        "packages": {
            name: _package_version(name)
            for name in (
                "numpy",
                "sounddevice",
                "soundfile",
                "vosk",
                "onnx-asr",
                "onnxruntime",
                "psutil",
                "jiwer",
            )
        },
        "whisper_cpp": _whisper_version(models),
    }


def main() -> int:
    info = collect_system_info()
    output = dump_json("results/system-info.json", info)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    print(f"\nOpgeslagen: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

