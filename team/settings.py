"""Copilot CLI user settings: set subagents.agents.team-* model and effort, touch nothing else.

`copilot config` refuses these keys and a repository cannot set them, so this edits
<COPILOT_HOME>/settings.json directly. It keeps a backup, and if the file is not plain JSON it
stops and prints the snippet instead of rewriting what it cannot parse.
"""

import json
import shutil
from pathlib import Path
from typing import Any

from team.fsutil import Refusal, write_json_atomic
from team.models import INHERIT
from team.paths import copilot_home

AGENT_PREFIX = "team-"


def settings_path() -> Path:
    return copilot_home() / "settings.json"


def _load(path: Path) -> dict[str, Any] | Refusal:
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return Refusal(f"{path} is not plain JSON ({error.msg} at line {error.lineno})")

    if not isinstance(data, dict):
        return Refusal(f"{path} does not hold a JSON object")

    return data


def snippet(entries: dict[str, dict[str, Any]]) -> str:
    """The JSON to paste by hand when the file cannot be edited safely."""
    agents = {agent: _setting(entry) for agent, entry in entries.items()}

    return json.dumps({"subagents": {"agents": agents}}, indent=2)


def _setting(entry: dict[str, Any]) -> dict[str, str]:
    model = entry.get("model") or INHERIT

    return {"model": model, "effortLevel": entry.get("effort") or INHERIT}


def apply(entries: dict[str, dict[str, Any]]) -> Path | Refusal:
    """Write model and effort for team-* agents. Returns the settings path that was written."""
    path = settings_path()
    data = _load(path)

    if isinstance(data, Refusal):
        return Refusal(f"{data.message}. Paste this yourself:\n{snippet(entries)}")

    agents = data.setdefault("subagents", {}).setdefault("agents", {})

    for agent, entry in entries.items():
        if not agent.startswith(AGENT_PREFIX):
            return Refusal(f"Refusing to change settings for {agent}: only {AGENT_PREFIX}* agents")

        agents[agent] = _setting(entry)

    _backup(path)
    write_json_atomic(path, data)

    return path


def remove_team_entries() -> Path | Refusal | None:
    """Uninstall: drop subagents.agents.team-* keys. None when there was nothing to remove."""
    path = settings_path()
    data = _load(path)

    if isinstance(data, Refusal):
        return data

    agents = data.get("subagents", {}).get("agents", {})
    team_agents = [name for name in agents if name.startswith(AGENT_PREFIX)]

    if not team_agents:
        return None

    for name in team_agents:
        del agents[name]

    _backup(path)
    write_json_atomic(path, data)

    return path


def _backup(path: Path) -> None:
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".team-bak"))
