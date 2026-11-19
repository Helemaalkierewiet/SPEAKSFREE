from __future__ import annotations

import argparse
import copy
import csv
import json
import multiprocessing
import os
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from .audio import inspect_wav
from .engines import create_engine
from .metrics import measure
from .monitor import ResourceMonitor
from .paths import PROJECT_ROOT, dump_json, load_json, project_path
from .system_info import collect_system_info


_WORKER_ENGINE = None
_WORKER_MODE = "offline"


def _resolve_audio(manifest_path: Path, value: str) -> Path:
    project_candidate = project_path(value)
    manifest_candidate = (manifest_path.parent / value).resolve()
    if project_candidate.exists():
        return project_candidate
    return manifest_candidate


def _resolve_reference(manifest_path: Path, value: str) -> Path:
    manifest_candidate = (manifest_path.parent / value).resolve()
    if manifest_candidate.exists():
        return manifest_candidate
    return project_path(value)


def load_corpus(manifest_value: str | Path) -> tuple[Path, list[dict[str, Any]]]:
    manifest_path = project_path(manifest_value)
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Testsetmanifest ontbreekt: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if not manifest.get("consent_confirmed"):
        raise ValueError("Het testsetmanifest bevestigt geen toestemming voor de opnamen")
    items: list[dict[str, Any]] = []
    for entry in manifest.get("items", []):
        item = dict(entry)
        audio_path = _resolve_audio(manifest_path, item["audio_file"])
        reference_path = _resolve_reference(manifest_path, item["reference_file"])
        inspect_wav(audio_path)
        if not reference_path.is_file():
            raise FileNotFoundError(f"Referentietekst ontbreekt: {reference_path}")
        item["audio_file_resolved"] = str(audio_path)
        item["reference_file_resolved"] = str(reference_path)
        items.append(item)
    if not items:
        raise ValueError(f"Geen testclips gevonden in {manifest_path}")
    return manifest_path, items


def _init_worker(
    engine_name: str,
    models_config: dict[str, Any],
    mode: str,
    concurrency: int,
    warmup_audio: str | None,
) -> None:
    global _WORKER_ENGINE, _WORKER_MODE
    config = copy.deepcopy(models_config)
    entry = config["engines"][engine_name]
    if entry["kind"] in {"whisper.cpp", "onnx-asr"} and int(entry.get("threads", 0)) <= 0:
        entry["threads"] = max(1, (os.cpu_count() or 1) // max(1, concurrency))
    _WORKER_ENGINE = create_engine(engine_name, config)
    _WORKER_MODE = mode
    if warmup_audio:
        _WORKER_ENGINE.transcribe(warmup_audio, near_live=False)


def _worker_task(item: dict[str, Any], repetition: int, stream_index: int) -> dict[str, Any]:
    if _WORKER_ENGINE is None:
        raise RuntimeError("Benchmarkworker is niet geïnitialiseerd")
    result = _WORKER_ENGINE.transcribe(
        item["audio_file_resolved"], near_live=_WORKER_MODE == "near-live"
    ).to_dict()
    reference = Path(item["reference_file_resolved"]).read_text(encoding="utf-8-sig").strip()
    result.update(measure(reference, result["transcript_raw"], item.get("critical_words", [])))
    result.update(
        {
            "clip_id": item["id"],
            "reference_raw": reference,
            "category": item.get("category", "unknown"),
            "speaker_alias": item.get("speaker_alias", "unknown"),
            "noise": item.get("noise"),
            "speaking_style": item.get("speaking_style"),
            "repetition": repetition,
            "stream_index": stream_index,
            "worker_pid": os.getpid(),
            "mode": _WORKER_MODE,
        }
    )
    return result


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * percentile + 0.999999)))
    return ordered[rank]


def _aggregate(records: list[dict[str, Any]], total_seconds: float, resources) -> dict[str, Any]:
    successful = [record for record in records if record.get("exit_status") == "ok"]
    processing = [float(record["processing_seconds"]) for record in successful]
    rtfs = [float(record["realtime_factor"]) for record in successful]
    return {
        "tasks": len(records),
        "successful_tasks": len(successful),
        "failed_tasks": len(records) - len(successful),
        "total_wall_seconds": total_seconds,
        "processing_seconds_mean": statistics.fmean(processing) if processing else None,
        "processing_seconds_p95": _percentile(processing, 0.95),
        "rtf_mean": statistics.fmean(rtfs) if rtfs else None,
        "rtf_max": max(rtfs) if rtfs else None,
        "streams_realtime": bool(rtfs) and all(value < 1.0 for value in rtfs),
        "cluster_cpu_average_percent": resources.cpu_average_percent,
        "cluster_cpu_peak_percent": resources.cpu_peak_percent,
        "cluster_peak_rss_mb": resources.peak_rss_mb,
        "resource_samples": resources.samples,
    }


def _write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    fields = sorted({key for record in records for key in record})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = {
                key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
                for key, value in record.items()
            }
            writer.writerow(row)


def _validate_engine_files(engine_name: str, config: dict[str, Any]) -> list[str]:
    entry = config["engines"][engine_name]
    missing: list[str] = []
    model = project_path(entry["model_path"])
    if not model.exists():
        missing.append(str(model))
    if entry["kind"] == "whisper.cpp":
        binary = project_path(entry["binary_path"])
        if not binary.is_file():
            missing.append(str(binary))
        if entry.get("vad_model_path"):
            vad_model = project_path(entry["vad_model_path"])
            if not vad_model.is_file():
                missing.append(str(vad_model))
    if entry["kind"] == "onnx-asr" and not (model / "config.json").is_file():
        missing.append(str(model / "config.json"))
    return missing


def run_engine(
    engine_name: str,
    models_config: dict[str, Any],
    manifest_path: Path,
    items: list[dict[str, Any]],
    concurrency: int,
    repetitions: int,
    mode: str,
    warmup: bool,
) -> Path:
    tasks = [
        (item, repetition, index % concurrency)
        for repetition in range(1, repetitions + 1)
        for index, item in enumerate(items)
    ]
    if len(tasks) < concurrency:
        raise ValueError(
            f"Concurrency {concurrency} vereist minimaal {concurrency} taken; "
            "voeg clips toe of verhoog repetitions."
        )

    run_started = datetime.now().astimezone()
    monitor = ResourceMonitor().start()
    wall_started = time.perf_counter()
    records: list[dict[str, Any]] = []
    warmup_audio = items[0]["audio_file_resolved"] if warmup else None
    with ProcessPoolExecutor(
        max_workers=concurrency,
        initializer=_init_worker,
        initargs=(engine_name, models_config, mode, concurrency, warmup_audio),
    ) as executor:
        futures = [
            executor.submit(_worker_task, item, repetition, stream_index)
            for item, repetition, stream_index in tasks
        ]
        for number, future in enumerate(as_completed(futures), start=1):
            try:
                record = future.result()
            except Exception as exc:
                record = {
                    "engine": engine_name,
                    "exit_status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "mode": mode,
                }
            records.append(record)
            status = record.get("exit_status", "error")
            clip = record.get("clip_id", "worker")
            print(f"[{engine_name}] {number}/{len(futures)} {clip}: {status}")
    wall_seconds = time.perf_counter() - wall_started
    resources = monitor.stop()
    records.sort(key=lambda record: (
        int(record.get("repetition", 0)), str(record.get("clip_id", ""))
    ))
    stamp = run_started.strftime("%Y%m%dT%H%M%S%z")
    session = manifest_path.parent.name
    basename = f"{stamp}_{session}_{engine_name}_{mode}_c{concurrency}"
    output_json = project_path(Path("results/raw") / f"{basename}.json")
    payload = {
        "schema_version": 1,
        "run": {
            "started_at": run_started.isoformat(),
            "engine": engine_name,
            "mode": mode,
            "concurrency": concurrency,
            "repetitions": repetitions,
            "warmup_per_worker": warmup,
            "manifest": str(manifest_path),
            "session": session,
            "language": models_config["engines"][engine_name].get("language"),
            "translate": models_config["engines"][engine_name].get("translate", False),
        },
        "system": collect_system_info(),
        "model": models_config["engines"][engine_name],
        "aggregate": _aggregate(records, wall_seconds, resources),
        "records": records,
    }
    dump_json(output_json, payload)
    _write_csv(output_json.with_suffix(".csv"), records)
    print(f"Resultaat: {output_json}")
    return output_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark lokale Nederlandse STT-modellen.")
    parser.add_argument(
        "--manifest",
        default="references/private/baseline/manifest.json",
        help="Testsetmanifest; alle engines gebruiken exact deze WAV-bestanden",
    )
    parser.add_argument(
        "--engines",
        nargs="+",
        default=None,
        help="Engine(s) om te testen; standaard worden alle geconfigureerde modellen gebruikt",
    )
    parser.add_argument("--concurrency", type=int, choices=(1, 2, 4), default=1)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--mode", choices=("offline", "near-live"), default="offline")
    parser.add_argument("--no-warmup", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.repetitions < 1:
        print("--repetitions moet minimaal 1 zijn", file=sys.stderr)
        return 2
    try:
        manifest_path, items = load_corpus(args.manifest)
        models_config = load_json("config/models.json")
        engine_names = args.engines or list(models_config["engines"])
        unknown = [name for name in engine_names if name not in models_config["engines"]]
        if unknown:
            raise ValueError(f"Onbekende engines: {', '.join(unknown)}")
        missing = {
            name: _validate_engine_files(name, models_config)
            for name in engine_names
            if _validate_engine_files(name, models_config)
        }
        if missing:
            formatted = "\n".join(
                f"  {name}: {', '.join(paths)}" for name, paths in missing.items()
            )
            raise FileNotFoundError(
                "Modelbestanden ontbreken. Voer scripts/setup-models.ps1 uit:\n" + formatted
            )
        dump_json("results/system-info.json", collect_system_info())
        for engine_name in engine_names:
            run_engine(
                engine_name,
                models_config,
                manifest_path,
                items,
                args.concurrency,
                args.repetitions,
                args.mode,
                not args.no_warmup,
            )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Fout: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())

