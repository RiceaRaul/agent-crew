"""Small file and time helpers shared by the team modules."""

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Refusal:
    """An expected failure: a rule said no. The message says what failed and how to fix it."""

    message: str


def now_iso() -> str:
    """Return the current UTC time as ISO 8601, without microseconds."""
    moment = datetime.now(UTC).replace(microsecond=0)

    return moment.isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text_atomic(path: Path, text: str) -> None:
    """Write through a temp file in the same folder, so a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")

    with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as file:
        file.write(text)

    os.replace(temp_name, path)


def write_json_atomic(path: Path, data: Any) -> None:
    write_text_atomic(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tail(text: str, line_count: int) -> str:
    lines = text.splitlines()

    return "\n".join(lines[-line_count:])
