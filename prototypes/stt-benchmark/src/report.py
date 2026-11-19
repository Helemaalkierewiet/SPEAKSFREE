from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .paths import PROJECT_ROOT, load_json, project_path


def _fmt(value: float | int | None, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return f"{value:.{digits}f}"


def _pct(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value * 100:.{digits}f}%"


def _mean(values: Iterable[float | None]) -> float | None:
    usable = [float(value) for value in values if value is not None]
    return statistics.fmean(usable) if usable else None


def _quality(records: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [record for record in records if record.get("exit_status") == "ok"]
    spoken = [record for record in successful if record.get("reference_normalized")]
    reference_words = sum(int(record.get("reference_words", 0)) for record in successful)
    word_errors = sum(
        int(record.get("substitutions", 0))
        + int(record.get("deletions", 0))
        + int(record.get("insertions", 0))
        for record in successful
    )
    reference_characters = sum(int(record.get("reference_characters", 0)) for record in successful)
    character_errors = sum(int(record.get("character_errors", 0)) for record in successful)
    deletions = sum(int(record.get("deletions", 0)) for record in successful)
    critical_found = sum(int(record.get("critical_words_found", 0)) for record in successful)
    critical_total = sum(int(record.get("critical_words_total", 0)) for record in successful)
    return {
        "wer": word_errors / reference_words if reference_words else None,
        "cer": character_errors / reference_characters if reference_characters else None,
        "omission": deletions / reference_words if reference_words else None,
        "critical_recall": critical_found / critical_total if critical_total else None,
        "silence_words": sum(
            int(record.get("hallucinated_words", 0))
            for record in successful
            if record.get("category") == "silence" or not record.get("reference_normalized")
        ),
        "english_intrusions": sum(
            len(record.get("english_intrusions", [])) for record in successful
        ),
        "capitalized_rate": (
            sum(bool(record.get("starts_with_capital")) for record in spoken) / len(spoken)
            if spoken else None
        ),
        "punctuated_rate": (
            sum(int(record.get("sentence_boundary_count", 0)) > 0 for record in spoken) / len(spoken)
            if spoken else None
        ),
        "sentence_boundaries_per_clip": (
            sum(int(record.get("sentence_boundary_count", 0)) for record in spoken) / len(spoken)
            if spoken else None
        ),
        "rtf_mean": _mean(record.get("realtime_factor") for record in successful),
        "rtf_max": max(
            (float(record["realtime_factor"]) for record in successful), default=None
        ),
        "first_text_mean": _mean(record.get("first_text_seconds") for record in successful),
        "final_text_mean": _mean(record.get("final_text_seconds") for record in successful),
        "load_mean": _mean(record.get("model_load_seconds") for record in successful),
        "peak_rss_mb": max((float(record.get("peak_rss_mb", 0)) for record in successful), default=None),
        "failures": len(records) - len(successful),
        "records": len(records),
    }


def _run_session(run: dict[str, Any]) -> str:
    if run.get("session"):
        return str(run["session"])
    manifest = str(run.get("manifest", ""))
    return Path(manifest).parent.name


def _latest_runs(
    raw_dir: Path, session: str | None = None
) -> dict[tuple[str, str, int], dict[str, Any]]:
    latest: dict[tuple[str, str, int], dict[str, Any]] = {}
    for path in sorted(raw_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            run = payload["run"]
            if session is not None and _run_session(run) != session:
                continue
            key = (run["engine"], run["mode"], int(run["concurrency"]))
            current = latest.get(key)
            if current is None or run["started_at"] > current["run"]["started_at"]:
                payload["_path"] = str(path)
                latest[key] = payload
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return latest


def _model_size(entry: dict[str, Any]) -> str:
    path = project_path(entry["model_path"])
    if path.is_file():
        return f"{path.stat().st_size / (1024 * 1024):.1f} MB"
    if path.is_dir():
        total = sum(file.stat().st_size for file in path.rglob("*") if file.is_file())
        return f"{total / (1024 * 1024):.1f} MB"
    return "niet geïnstalleerd"


def _category_rows(records: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record.get("category", "unknown"))].append(record)
    return [(category, _quality(values)) for category, values in sorted(grouped.items())]


def _combined_csv(runs: dict[tuple[str, str, int], dict[str, Any]], output: Path) -> None:
    records = [
        {**record, "concurrency": key[2]}
        for key, payload in runs.items()
        for record in payload.get("records", [])
    ]
    if not records:
        return
    fields = sorted({key for record in records for key in record})
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({
                key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
                for key, value in record.items()
            })


def _decision(
    engines: list[str],
    runs: dict[tuple[str, str, int], dict[str, Any]],
    models: dict[str, Any],
    benchmark_config: dict[str, Any],
) -> tuple[list[str], str]:
    required = [(engine, "offline", concurrency) for engine in engines for concurrency in (1, 2, 4)]
    required += [(engine, "near-live", 1) for engine in engines]
    missing = [key for key in required if key not in runs]
    if missing:
        formatted = ", ".join(f"{engine}/{mode}/c{concurrency}" for engine, mode, concurrency in missing)
        return [], (
            "Er is nog geen winnaar: de verplichte meetmatrix is onvolledig. "
            f"Ontbrekend: {formatted}."
        )

    thresholds = benchmark_config["decision_thresholds"]
    weights = benchmark_config["score_weights"]
    total_ram_mb = next(iter(runs.values())).get("system", {}).get("memory_total_gb")
    total_ram_mb = float(total_ram_mb) * 1024 if total_ram_mb else None
    logical_cores = next(iter(runs.values())).get("system", {}).get("cpu", {}).get("logical_cores") or 1
    decisions: list[str] = []
    candidates: list[tuple[float, str]] = []
    technical_license_winner: tuple[float, str] | None = None
    for engine in engines:
        baseline = _quality(runs[(engine, "offline", 1)]["records"])
        four = runs[(engine, "offline", 4)]
        four_quality = _quality(four["records"])
        live = _quality(runs[(engine, "near-live", 1)]["records"])
        cluster = four.get("aggregate", {})
        reasons: list[str] = []
        if four_quality["failures"]:
            reasons.append(f"{four_quality['failures']} mislukte vier-streamtaken")
        if four_quality["rtf_max"] is None or four_quality["rtf_max"] >= thresholds["max_rtf_each_stream"]:
            reasons.append(f"vier-stream-RTF max {_fmt(four_quality['rtf_max'], 3)} is niet < 1,0")
        if baseline["wer"] is None or baseline["wer"] > thresholds["max_wer"]:
            reasons.append(f"WER {_pct(baseline['wer'])} overschrijdt de grens")
        if baseline["omission"] is None or baseline["omission"] > thresholds["max_omitted_word_rate"]:
            reasons.append(f"weglatingen {_pct(baseline['omission'])} overschrijden de grens")
        if baseline["critical_recall"] is not None and baseline["critical_recall"] < thresholds["min_critical_word_recall"]:
            reasons.append(f"kritieke-woordenrecall {_pct(baseline['critical_recall'])} is te laag")
        if baseline["silence_words"] > thresholds["max_silence_words"]:
            reasons.append(f"{baseline['silence_words']} woorden gehallucineerd in stilte")
        memory_peak = cluster.get("cluster_peak_rss_mb")
        if total_ram_mb and memory_peak and memory_peak / total_ram_mb > thresholds["max_memory_fraction"]:
            reasons.append("onvoldoende veilige geheugenmarge")
        cpu_average = cluster.get("cluster_cpu_average_percent")
        cpu_fraction = float(cpu_average or 0) / (float(logical_cores) * 100.0)
        if cpu_fraction > 1.0 - thresholds["min_free_cpu_fraction"]:
            reasons.append("minder dan 15% gemiddelde CPU-marge")

        critical = baseline["critical_recall"] if baseline["critical_recall"] is not None else 1.0
        wer_value = baseline["wer"] if baseline["wer"] is not None else 1.0
        omission_value = baseline["omission"] if baseline["omission"] is not None else 1.0
        rtf_value = four_quality["rtf_max"] if four_quality["rtf_max"] is not None else 1.0
        quality_score = max(0.0, 1.0 - float(wer_value)) * 0.6
        quality_score += max(0.0, 1.0 - float(omission_value)) * 0.15
        quality_score += critical * 0.25
        throughput_score = max(0.0, 1.0 - min(1.0, float(rtf_value)))
        latency_score = 1.0 / (1.0 + float(live["first_text_mean"] or live["final_text_mean"] or 99.0))
        memory_fraction = float(memory_peak or 0) / total_ram_mb if total_ram_mb else 0.5
        resource_score = max(0.0, 1.0 - memory_fraction)
        score = 100.0 * (
            weights["quality"] * quality_score
            + weights["four_stream_throughput"] * throughput_score
            + weights["near_live_latency"] * latency_score
            + weights["resources"] * resource_score
        )
        license_ok = bool(models["engines"][engine].get("commercial_use"))
        status = "afgekeurd" if reasons else "technisch geschikt"
        if not license_ok:
            status += "; niet geschikt voor commercieel productgebruik"
        decisions.append(
            f"- **{engine}: {status}** — score {score:.1f}/100"
            + (f"; {', '.join(reasons)}." if reasons else ".")
        )
        if not reasons:
            if technical_license_winner is None or score > technical_license_winner[0]:
                technical_license_winner = (score, engine)
            if license_ok:
                candidates.append((score, engine))

    if candidates:
        score, winner = max(candidates)
        conclusion = (
            f"**{winner} lijkt op deze laptop geschikt voor vier streams**, met een score van "
            f"{score:.1f}/100. Dit moet nog met echte vierkanaals-hardware worden getest."
        )
    elif technical_license_winner and not models["engines"][technical_license_winner[1]].get("commercial_use"):
        conclusion = (
            f"**{technical_license_winner[1]} wint technisch, maar valt af voor productgebruik "
            "totdat de licentie is opgelost.**"
        )
    else:
        realtime_results = [
            _quality(runs[(engine, "offline", 4)]["records"])["rtf_max"]
            for engine in engines
            if (engine, "offline", 4) in runs
        ]
        if realtime_results and all(value is not None and value < 1.0 for value in realtime_results):
            conclusion = (
                "**Geen model haalt alle ingestelde kwaliteitsgrenzen, hoewel de geteste modellen "
                "wel vier-stream-realtime halen.** De volgende stap is model-, VAD- en "
                "audiokwaliteit verbeteren; een snellere pc alleen lost de herkenningsfouten niet op."
            )
        else:
            conclusion = (
                "**Geen model haalt op deze laptop tegelijk de ingestelde kwaliteitsgrenzen en "
                "vier-stream-realtime.** Vergelijk de foutredenen voordat hardware of architectuur "
                "wordt aangepast."
            )
    return decisions, conclusion


def generate_report(raw_dir: Path, output: Path, session: str | None = None) -> int:
    runs = _latest_runs(raw_dir, session=session)
    models = load_json("config/models.json")
    benchmark_config = load_json("config/benchmark.json")
    engines = list(models["engines"])
    lines = ["# Nederlands STT-benchmarkrapport", ""]
    if session is not None:
        lines += [f"Testset: `{session}`", ""]
    if not runs:
        lines += [
            "Status: nog geen benchmarkresultaten gevonden.",
            "",
            "Voer eerst de offline runs bij concurrency 1, 2 en 4 en daarna de bijna-live run uit.",
        ]
        output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        return 0

    first = next(iter(runs.values()))
    system = first.get("system", {})
    cpu = system.get("cpu", {})
    package_versions = ", ".join(
        f"{name}={version or 'niet geïnstalleerd'}"
        for name, version in system.get("packages", {}).items()
    )
    lines += [
        "## Laptopconfiguratie",
        "",
        f"- OS: {system.get('os', {}).get('system', '—')} {system.get('os', {}).get('release', '')} ({system.get('os', {}).get('architecture', '—')})",
        f"- CPU: {cpu.get('name') or '—'}; {cpu.get('physical_cores') or '—'} fysiek / {cpu.get('logical_cores') or '—'} logisch",
        f"- RAM: {_fmt(system.get('memory_total_gb'))} GB",
        f"- GPU: {system.get('gpu') or 'niet gedetecteerd'}; standaard CPU-build gebruikt",
        f"- Voeding/energieprofiel: {system.get('power') or 'niet beschikbaar'} / {system.get('active_power_plan') or 'niet beschikbaar'}",
        f"- Python: {str(system.get('python', '—')).splitlines()[0]}",
        f"- Pakketten: {package_versions or 'niet vastgelegd'}",
        f"- whisper.cpp: {system.get('whisper_cpp') or 'niet gedetecteerd'}",
        "",
        "## Modelconfiguraties",
        "",
        "| Engine | Exact model | Licentie | Commercieel | Lokaal formaat |",
        "| --- | --- | --- | --- | ---: |",
    ]
    for engine, entry in models["engines"].items():
        lines.append(
            f"| {engine} | {entry['model_version']} | {entry['license']} | "
            f"{'ja' if entry.get('commercial_use') else 'nee'} | {_model_size(entry)} |"
        )

    lines += [
        "",
        "## Kwaliteit en één-streamdoorvoer",
        "",
        "| Engine | WER | CER | Weggelaten | Kritieke recall | Stiltewoorden | Engelse insluipsels | Laadtijd gem. | RTF gem. |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for engine in engines:
        payload = runs.get((engine, "offline", 1))
        if not payload:
            lines.append(f"| {engine} | — | — | — | — | — | — | — | — |")
            continue
        quality = _quality(payload["records"])
        lines.append(
            f"| {engine} | {_pct(quality['wer'])} | {_pct(quality['cer'])} | "
            f"{_pct(quality['omission'])} | {_pct(quality['critical_recall'])} | "
            f"{quality['silence_words']} | {quality['english_intrusions']} | {_fmt(quality['load_mean'])} s | {_fmt(quality['rtf_mean'], 3)} |"
        )

    lines += [
        "",
        "### Leesbaarheid buiten WER/CER",
        "",
        "| Engine | Clips met beginhoofdletter | Clips met zinsinterpunctie | Zinsgrenzen per spraakclip |",
        "| --- | ---: | ---: | ---: |",
    ]
    for engine in engines:
        payload = runs.get((engine, "offline", 1))
        quality = _quality(payload["records"]) if payload else {}
        lines.append(
            f"| {engine} | {_pct(quality.get('capitalized_rate'))} | "
            f"{_pct(quality.get('punctuated_rate'))} | "
            f"{_fmt(quality.get('sentence_boundaries_per_clip'))} |"
        )

    lines += [
        "",
        "## Belasting bij 1, 2 en 4 streams",
        "",
        "| Engine | Streams | Totale tijd | Proc. gem. | Proc. p95 | RTF gem. | RTF max | Realtime | Cluster CPU gem. | Cluster CPU piek | Cluster RSS piek | Mislukt |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for engine in engines:
        for concurrency in (1, 2, 4):
            payload = runs.get((engine, "offline", concurrency))
            if not payload:
                lines.append(f"| {engine} | {concurrency} | — | — | — | — | — | — | — | — | — | — |")
                continue
            quality = _quality(payload["records"])
            aggregate = payload.get("aggregate", {})
            lines.append(
                f"| {engine} | {concurrency} | {_fmt(aggregate.get('total_wall_seconds'))} s | "
                f"{_fmt(aggregate.get('processing_seconds_mean'))} s | {_fmt(aggregate.get('processing_seconds_p95'))} s | "
                f"{_fmt(quality['rtf_mean'], 3)} | {_fmt(quality['rtf_max'], 3)} | "
                f"{'ja' if aggregate.get('streams_realtime') else 'nee'} | "
                f"{_fmt(aggregate.get('cluster_cpu_average_percent'), 1)}% | "
                f"{_fmt(aggregate.get('cluster_cpu_peak_percent'), 1)}% | "
                f"{_fmt(aggregate.get('cluster_peak_rss_mb'), 1)} MB | {quality['failures']} |"
            )

    lines += [
        "",
        "## Bijna-live latency",
        "",
        "Vosk gebruikt 200-ms PCM-blokken. Whisper en ONNX gebruiken niet-overlappende vensters van vijf seconden; daardoor kunnen geen dubbele overlapwoorden ontstaan. Whisper gebruikt daarnaast Silero VAD om stilte uit te filteren.",
        "",
        "| Engine | Eerste leesbare tekst gem. | Definitieve tekst gem. |",
        "| --- | ---: | ---: |",
    ]
    for engine in engines:
        payload = runs.get((engine, "near-live", 1))
        quality = _quality(payload["records"]) if payload else {}
        lines.append(
            f"| {engine} | {_fmt(quality.get('first_text_mean'))} s | {_fmt(quality.get('final_text_mean'))} s |"
        )

    lines += ["", "## Resultaten per categorie", ""]
    for engine in engines:
        payload = runs.get((engine, "offline", 1))
        if not payload:
            continue
        lines += [
            f"### {engine}",
            "",
            "| Categorie | WER | CER | Weggelaten | Kritieke recall |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
        for category, quality in _category_rows(payload["records"]):
            lines.append(
                f"| {category} | {_pct(quality['wer'])} | {_pct(quality['cer'])} | "
                f"{_pct(quality['omission'])} | {_pct(quality['critical_recall'])} |"
            )
        lines.append("")

    lines += ["## Resultaten per spreker", ""]
    for engine in engines:
        payload = runs.get((engine, "offline", 1))
        if not payload:
            continue
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in payload["records"]:
            grouped[str(record.get("speaker_alias", "unknown"))].append(record)
        lines += [
            f"### {engine}",
            "",
            "| Sprekeralias | WER | CER | Weggelaten | Kritieke recall |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
        for speaker, records in sorted(grouped.items()):
            quality = _quality(records)
            lines.append(
                f"| {speaker} | {_pct(quality['wer'])} | {_pct(quality['cer'])} | "
                f"{_pct(quality['omission'])} | {_pct(quality['critical_recall'])} |"
            )
        lines.append("")

    decisions, conclusion = _decision(engines, runs, models, benchmark_config)
    lines += [
        "## Beslissing",
        "",
        *decisions,
        "",
        conclusion,
        "",
        "## Beperkingen",
        "",
        "- De vier-streamtest meet rekenkracht met vier workerprocessen, niet de betrouwbaarheid van een toekomstige USB-audio-interface.",
        "- De meting geldt alleen voor deze laptop, energie-instelling, testset en modelversies.",
        "- De Engelse-insluipselmeting gebruikt een kleine lijst ondubbelzinnige Engelse woorden en blijft een heuristiek.",
        "- Leesbaarheid (interpunctie en hoofdletters) is vastgelegd in de ruwe records maar telt niet mee voor WER/CER.",
        "- Vosk LGraph heeft een CC-BY-NC-SA-licentie en wordt niet als commerciële productkeuze aanbevolen zonder licentieoplossing.",
        "",
        "## Ruwe gegevens",
        "",
    ]
    for key, payload in sorted(runs.items()):
        path = Path(payload["_path"])
        lines.append(f"- `{path.name}` ({key[0]}, {key[1]}, concurrency {key[2]})")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    csv_name = f"benchmark-results-{session}.csv" if session else "benchmark-results.csv"
    _combined_csv(runs, project_path(Path("results") / csv_name))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genereer het Markdown-benchmarkrapport.")
    parser.add_argument("--raw-dir", default="results/raw")
    parser.add_argument("--output", default="results/BENCHMARK_REPORT.md")
    parser.add_argument(
        "--session",
        help="Gebruik alleen resultaten van deze opnamesessie, bijvoorbeeld dji_mini_baseline",
    )
    args = parser.parse_args(argv)
    output = project_path(args.output)
    status = generate_report(project_path(args.raw_dir), output, session=args.session)
    print(f"Rapport: {output}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())

