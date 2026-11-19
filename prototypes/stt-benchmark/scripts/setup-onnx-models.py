from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def main() -> int:
    try:
        import onnx_asr
    except ImportError:
        print(
            "onnx-asr ontbreekt. Installeer eerst: python -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 2

    config = json.loads(
        (PROJECT_ROOT / "config" / "models.json").read_text(encoding="utf-8-sig")
    )
    for name, entry in config["engines"].items():
        if entry["kind"] != "onnx-asr":
            continue
        model_path = PROJECT_ROOT / entry["model_path"]
        print(f"ONNX-model voorbereiden: {name}")
        kwargs = {"providers": ["CPUExecutionProvider"]}
        if entry.get("quantization"):
            kwargs["quantization"] = entry["quantization"]
        model = onnx_asr.load_model(entry["model_id"], str(model_path), **kwargs)
        del model
        config_file = model_path / "config.json"
        if not config_file.is_file():
            raise FileNotFoundError(f"ONNX-config ontbreekt na download: {config_file}")
        print(f"  gereed: {directory_size(model_path) / (1024 * 1024):.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
