"""The work item state file: .ai/work/<id>/state.json. Only this module writes it."""

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from team.fsutil import Refusal, now_iso, read_json, write_json_atomic, write_text_atomic
from team.paths import AI_DIR_NAME

State = dict[str, Any]

TRACKS = ("quick", "full")
DIFFICULTIES = ("low", "medium", "high", "critical")
MAX_SLUG_LENGTH = 40


def ai_dir(root: Path) -> Path:
    return root / AI_DIR_NAME


def item_dir(root: Path, item_id: str) -> Path:
    return ai_dir(root) / "work" / item_id


def state_path(root: Path, item_id: str) -> Path:
    return item_dir(root, item_id) / "state.json"


def current_id(root: Path) -> str | None:
    pointer = ai_dir(root) / "current"

    if not pointer.is_file():
        return None

    value = pointer.read_text(encoding="utf-8").strip()

    return value or None


def has_active_item(root: Path) -> bool:
    item_id = current_id(root)

    return item_id is not None and state_path(root, item_id).is_file()


def load(root: Path) -> State | Refusal:
    item_id = current_id(root)

    if item_id is None:
        return Refusal(f'No active work item in {root}. Run: team new "<title>"')

    path = state_path(root, item_id)

    if not path.is_file():
        return Refusal(f"Work item {item_id} has no state file at {path}")

    return read_json(path)


def save(root: Path, state: State) -> None:
    write_json_atomic(state_path(root, state["id"]), state)


def set_current(root: Path, item_id: str) -> None:
    write_text_atomic(ai_dir(root) / "current", item_id + "\n")


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")

    return slug[:MAX_SLUG_LENGTH].rstrip("-") or "work"


def new_state(title: str, track: str, difficulty: str, first_phase: str) -> State:
    """Fresh state for a new work item. Id = date + slug, for example 20261125-state-to-pipeline."""
    today = datetime.now(UTC).strftime("%Y%m%d")
    item_id = f"{today}-{slugify(title)}"

    return {
        "id": item_id,
        "title": title,
        "track": track,
        "phase": first_phase,
        "difficulty": difficulty,
        "branch": f"ai/{item_id}",
        "models": {},
        "approvals": {"design": None, "done": None},
        "stories": [],
        "gates": {"fingerprint": None, "ok": None, "results": []},
        "handoffs": [],
        "history": [{"at": now_iso(), "event": "created", "value": track}],
    }


def add_history(state: State, event: str, value: str) -> None:
    state["history"].append({"at": now_iso(), "event": event, "value": value})


def add_handoff(state: State, from_agent: str, summary: str) -> None:
    state["handoffs"].append({"at": now_iso(), "from": from_agent, "summary": summary.strip()})
