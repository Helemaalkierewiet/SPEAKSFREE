from __future__ import annotations

import argparse
import json
import queue
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .audio import TARGET_SAMPLE_RATE, write_pcm16_wav
from .paths import PROJECT_ROOT, dump_json, project_path


SAFE_NAME = re.compile(r"[^a-zA-Z0-9_-]+")


def list_devices() -> int:
    try:
        import sounddevice as sd
    except ImportError:
        print("sounddevice ontbreekt; installeer requirements.txt", file=sys.stderr)
        return 2
    print(sd.query_devices())
    return 0


def _safe_name(value: str) -> str:
    result = SAFE_NAME.sub("_", value.strip()).strip("_")
    if not result:
        raise ValueError("De opnamenaam bevat geen bruikbare tekens")
    return result


def _meter(peak: float, clipped: bool, width: int = 36) -> str:
    filled = min(width, round(max(0.0, peak) * width))
    bar = "#" * filled + "." * (width - filled)
    warning = " CLIPPING!" if clipped else ""
    return f"[{bar}] {peak * 100:5.1f}%{warning}"


def record(
    output: Path,
    duration: float | None,
    device: str | int | None,
    block_ms: int = 100,
) -> dict[str, Any]:
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError("numpy en sounddevice zijn vereist voor opname") from exc

    blocks: queue.Queue[Any] = queue.Queue()
    status_messages: queue.Queue[str] = queue.Queue()
    clipping_blocks = 0

    def callback(indata, frames, _time_info, status) -> None:
        if status:
            status_messages.put(str(status))
        blocks.put(indata.copy())

    block_size = int(TARGET_SAMPLE_RATE * block_ms / 1000)
    started = time.perf_counter()
    collected = []
    print("Opname gestart. Druk Ctrl+C om te stoppen." if duration is None else "Opname gestart.")
    try:
        with sd.InputStream(
            samplerate=TARGET_SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=block_size,
            device=device,
            callback=callback,
        ):
            while duration is None or time.perf_counter() - started < duration:
                try:
                    block = blocks.get(timeout=0.25)
                except queue.Empty:
                    continue
                collected.append(block)
                peak = float(np.max(np.abs(block))) if block.size else 0.0
                clipped = peak >= 0.98
                clipping_blocks += int(clipped)
                print(f"\r{_meter(peak, clipped)}", end="", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        print()

    if not collected:
        raise RuntimeError("Geen audioblokken ontvangen van de microfoon")
    samples = np.concatenate(collected, axis=0).reshape(-1)
    samples = np.clip(samples, -1.0, 0.9999695)
    pcm = (samples * 32768.0).astype("<i2").tobytes()
    write_pcm16_wav(output, pcm, TARGET_SAMPLE_RATE)
    return {
        "frames": int(samples.size),
        "duration_seconds": float(samples.size / TARGET_SAMPLE_RATE),
        "clipping_blocks": clipping_blocks,
        "stream_status": list(status_messages.queue),
    }


def _update_manifest(
    manifest_path: Path,
    item: dict[str, Any],
    session: str,
    consent: bool,
) -> None:
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    else:
        manifest = {
            "schema_version": 1,
            "session": session,
            "created_at": datetime.now().astimezone().isoformat(),
            "consent_confirmed": consent,
            "items": [],
        }
    manifest["consent_confirmed"] = bool(manifest.get("consent_confirmed") and consent)
    manifest["items"] = [entry for entry in manifest["items"] if entry.get("id") != item["id"]]
    manifest["items"].append(item)
    dump_json(manifest_path, manifest)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Neem een private Nederlandse 16-kHz mono PCM-WAV-testclip op."
    )
    parser.add_argument("--list-devices", action="store_true", help="Toon microfoons en stop")
    parser.add_argument("--session", default="baseline")
    parser.add_argument("--name", help="Bestandsnaam zonder .wav")
    parser.add_argument("--duration", type=float, help="Opnameduur; zonder waarde stopt Ctrl+C")
    parser.add_argument("--device", help="Microfoonindex of exacte apparaatnaam")
    parser.add_argument("--speaker", default="adult-a", help="Niet-herleidbare sprekeralias")
    parser.add_argument("--category", default="household-conversation")
    parser.add_argument("--distance-cm", type=float, default=50.0)
    parser.add_argument("--noise", default="quiet room")
    parser.add_argument("--speaking-style", default="normal")
    parser.add_argument("--reference", help="Letterlijk uitgesproken Nederlandse tekst")
    parser.add_argument("--critical-word", action="append", default=[])
    parser.add_argument(
        "--consent",
        action="store_true",
        help="Bevestig toestemming van iedere opgenomen persoon (verplicht)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list_devices:
        return list_devices()
    if not args.consent:
        print("Opname geweigerd: bevestig toestemming met --consent.", file=sys.stderr)
        return 2
    name = _safe_name(args.name or datetime.now().strftime("clip_%Y%m%d_%H%M%S"))
    session = _safe_name(args.session)
    recording_path = project_path(Path("recordings") / session / f"{name}.wav")
    reference_dir = project_path(Path("references/private") / session)
    reference_path = reference_dir / f"{name}.txt"
    manifest_path = reference_dir / "manifest.json"
    reference_dir.mkdir(parents=True, exist_ok=True)
    selected_device: str | int | None = args.device
    if isinstance(selected_device, str) and selected_device.isdigit():
        selected_device = int(selected_device)
    metadata = record(recording_path, args.duration, selected_device)
    reference = args.reference
    if reference is None:
        reference = input("Typ nu letterlijk wat er is uitgesproken: ").strip()
    reference_path.write_text(reference.strip() + "\n", encoding="utf-8", newline="\n")
    try:
        device_info = selected_device if selected_device is not None else "default input"
    except Exception:
        device_info = "default input"
    item = {
        "id": name,
        "audio_file": str(recording_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "reference_file": str(reference_path.relative_to(manifest_path.parent)).replace("\\", "/"),
        "speaker_alias": args.speaker,
        "category": args.category,
        "microphone": device_info,
        "distance_cm": args.distance_cm,
        "noise": args.noise,
        "speaking_style": args.speaking_style,
        "critical_words": args.critical_word,
        **metadata,
    }
    _update_manifest(manifest_path, item, session, args.consent)
    print(f"WAV: {recording_path}")
    print(f"Referentie: {reference_path}")
    print(f"Manifest: {manifest_path}")
    if metadata["clipping_blocks"]:
        print("Waarschuwing: clipping gedetecteerd; neem deze clip bij voorkeur opnieuw op.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

