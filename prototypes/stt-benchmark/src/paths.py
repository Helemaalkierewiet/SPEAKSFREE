from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def project_path(value: str | Path) -> Path:
    """Resolve a project-relative path without depending on the current directory."""
    path = Path(value)
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def load_json(path: str | Path) -> Any:
    with project_path(path).open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def dump_json(path: str | Path, value: Any) -> Path:
    output = project_path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(output)
    return output

