from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from .paths import load_json, project_path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Controleer runtime, modellen en downloads.")
    parser.add_argument("--hashes", action="store_true", help="Bereken alle download-hashes opnieuw")
    args = parser.parse_args(argv)
    errors: list[str] = []
    warnings: list[str] = []
    if sys.version_info[:2] != (3, 11):
        warnings.append(
            f"Python {sys.version_info.major}.{sys.version_info.minor} actief; Python 3.11 is de vastgezette benchmarkruntime"
        )
    config = load_json("config/models.json")
    print("Engines:")
    for name, entry in config["engines"].items():
        model = project_path(entry["model_path"])
        present = model.is_dir() if entry["kind"] in {"vosk", "onnx-asr"} else model.is_file()
        print(f"  {'OK' if present else 'ONTBREEKT':9} {name}: {model}")
        if not present:
            errors.append(f"model ontbreekt: {name}")
        if entry["kind"] == "whisper.cpp":
            binary = project_path(entry["binary_path"])
            print(f"  {'OK' if binary.is_file() else 'ONTBREEKT':9} whisper-cli: {binary}")
            if not binary.is_file():
                errors.append("whisper-cli ontbreekt")
            if entry.get("language") != "nl" or entry.get("translate") is not False:
                errors.append("Whisper is niet vastgezet op nl/transcribe")
            vad = project_path(entry["vad_model_path"])
            print(f"  {'OK' if vad.is_file() else 'ONTBREEKT':9} Silero VAD: {vad}")
            if not vad.is_file():
                errors.append("Silero VAD-model ontbreekt")
        if entry["kind"] == "onnx-asr" and not (model / "config.json").is_file():
            errors.append(f"ONNX-modelconfig ontbreekt: {name}")

    manifest_path = project_path("models/manifest.local.json")
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        print(f"\nDownloadmanifest: {manifest_path}")
        for artifact in manifest.get("artifacts", []):
            path = Path(artifact["local_path"])
            status = path.is_file() and path.stat().st_size == artifact.get("bytes")
            if status and args.hashes:
                status = _sha256(path) == artifact.get("sha256")
            print(f"  {'OK' if status else 'FOUT':9} {artifact.get('name')}")
            if not status:
                errors.append(f"downloadmanifest wijkt af: {artifact.get('name')}")
    else:
        errors.append("models/manifest.local.json ontbreekt")

    if warnings:
        print("\nWaarschuwingen:")
        for warning in warnings:
            print(f"  - {warning}")
    if errors:
        print("\nNiet gereed:")
        for error in errors:
            print(f"  - {error}")
        print("\nVoer scripts/setup-models.ps1 uit en controleer opnieuw.")
        return 2
    print("\nGereed voor de rooktest en benchmark.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

