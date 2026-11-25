"""Where things live: the team repo itself, the target project, and the Copilot home folder."""

import os
from pathlib import Path

TEAM_HOME = Path(__file__).resolve().parent.parent
CONFIG_DIR = TEAM_HOME / "config"
TEMPLATES_DIR = TEAM_HOME / "templates"
AGENTS_DIR = TEAM_HOME / "agents"
SKILLS_DIR = TEAM_HOME / "skills"
AI_DIR_NAME = ".ai"


def copilot_home() -> Path:
    """Copilot CLI reads COPILOT_HOME when set, otherwise ~/.copilot (also on Windows)."""
    override = os.environ.get("COPILOT_HOME")

    if override:
        return Path(override)

    return Path.home() / ".copilot"


def find_project_root(start: Path) -> Path:
    """Nearest folder with .ai/, else nearest with .git, else start itself."""
    start = start.resolve()
    candidates = [start, *start.parents]

    for folder in candidates:
        if (folder / AI_DIR_NAME).is_dir():
            return folder

    for folder in candidates:
        if (folder / ".git").exists():
            return folder

    return start


def relative_posix(root: Path, path_text: str) -> str | None:
    """Path relative to root in forward-slash form, or None when it is outside root."""
    path = Path(path_text)

    if not path.is_absolute():
        path = root / path

    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None
