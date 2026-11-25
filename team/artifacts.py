"""Phase documents: created from templates, checked for leftover TODO: markers."""

import re
from pathlib import Path

from team.fsutil import write_text_atomic
from team.paths import TEMPLATES_DIR
from team.state import State, item_dir

TODO_MARKER = "TODO:"
VERDICT_PATTERN = re.compile(r"^Verdict:\s*(pass|changes)\b", re.IGNORECASE | re.MULTILINE)


def render(template_name: str, values: dict[str, str]) -> str:
    text = (TEMPLATES_DIR / template_name).read_text(encoding="utf-8")

    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)

    return text


def ensure_document(root: Path, state: State, file_name: str) -> Path:
    """Create the document from its template once. An existing document is never overwritten."""
    path = item_dir(root, state["id"]) / file_name

    if not path.exists():
        write_text_atomic(path, render(file_name, {"title": state["title"], "id": state["id"]}))

    return path


def story_path(root: Path, state: State, story_id: str) -> Path:
    return item_dir(root, state["id"]) / "stories" / f"{story_id}.md"


def create_story(root: Path, state: State, story_id: str, title: str) -> Path:
    path = story_path(root, state, story_id)
    values = {"title": title, "id": story_id, "item": state["id"]}

    write_text_atomic(path, render("story.md", values))

    return path


def unfinished_reason(path: Path) -> str | None:
    """Why a document is not done yet, or None when it is filled in."""
    if not path.is_file():
        return f"{path.name} is missing"

    todo_count = path.read_text(encoding="utf-8").count(TODO_MARKER)

    if todo_count:
        return f"{path.name} still has {todo_count} {TODO_MARKER} marker(s) to fill in"

    return None


def review_verdict(root: Path, state: State) -> str | None:
    path = item_dir(root, state["id"]) / "review.md"

    if not path.is_file():
        return None

    match = VERDICT_PATTERN.search(path.read_text(encoding="utf-8"))

    return match.group(1).lower() if match else None
