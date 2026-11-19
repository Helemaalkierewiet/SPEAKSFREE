from __future__ import annotations

import argparse
import sys

from .benchmark import load_corpus
from .engines import create_engine
from .paths import load_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Laat alle engines één en hetzelfde Nederlandse fragment transcriberen."
    )
    parser.add_argument("--manifest", default="references/private/baseline/manifest.json")
    parser.add_argument("--clip", help="Clip-id; standaard de eerste clip")
    args = parser.parse_args(argv)
    try:
        _manifest, items = load_corpus(args.manifest)
        item = next(
            (entry for entry in items if entry["id"] == args.clip), items[0] if not args.clip else None
        )
        if item is None:
            raise ValueError(f"Clip-id niet gevonden: {args.clip}")
        config = load_json("config/models.json")
        print(f"Zelfde invoer voor alle engines: {item['audio_file_resolved']}")
        for name in config["engines"]:
            print(f"\n{name} laden...")
            engine = create_engine(name, config)
            result = engine.transcribe(item["audio_file_resolved"])
            if result.exit_status != "ok":
                raise RuntimeError(f"{name}: {result.error}")
            print(f"  {result.transcript_raw or '[lege transcriptie]'}")
            print(f"  {result.processing_seconds:.2f}s; RTF {result.realtime_factor:.3f}")
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Rooktest mislukt: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

