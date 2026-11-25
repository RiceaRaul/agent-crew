"""Phases per track, what each phase must produce, approvals and moving between phases."""

from pathlib import Path
from typing import Any

from team import artifacts, gates
from team.fsutil import Refusal, now_iso, read_json
from team.paths import CONFIG_DIR
from team.state import State, add_history, item_dir

DONE_PHASE = "done"
PHASE_DOCUMENTS = {"analyze": "brief.md", "design": "adr.md", "review": "review.md"}


def load_tracks() -> dict[str, list[dict[str, Any]]]:
    return read_json(CONFIG_DIR / "tracks.json")


def phases(track: str) -> list[dict[str, Any]]:
    return load_tracks()[track]


def current_phase(state: State) -> dict[str, Any] | None:
    for phase in phases(state["track"]):
        if phase["name"] == state["phase"]:
            return phase

    return None


def phase_names(track: str) -> list[str]:
    return [phase["name"] for phase in phases(track)] + [DONE_PHASE]


def is_code_locked(state: State) -> bool:
    """Full track: no code edits until you approve the design."""
    return state["track"] == "full" and state["approvals"].get("design") is None


def output_problem(root: Path, state: State, check: str) -> str | None:
    """What is still missing for this check, or None when it passes."""
    if check.startswith("file:"):
        return artifacts.unfinished_reason(
            item_dir(root, state["id"]) / check.removeprefix("file:")
        )

    if check == "stories":
        return _stories_problem(root, state)

    if check == "stories-done":
        open_stories = [story["id"] for story in state["stories"] if story["status"] != "done"]

        return f"open stories: {', '.join(open_stories)}" if open_stories else None

    if check == "gates":
        return None if gates.is_fresh_green(root, state) else _gate_problem(root, state)

    if check == "review-pass":
        return _review_problem(root, state)

    return f"unknown check {check} in tracks.json"


def _stories_problem(root: Path, state: State) -> str | None:
    if not state["stories"]:
        return 'no stories yet. Run: team story add "<title>"'

    for story in state["stories"]:
        problem = artifacts.unfinished_reason(artifacts.story_path(root, state, story["id"]))

        if problem:
            return problem

    return None


def _gate_problem(root: Path, state: State) -> str:
    if state["gates"].get("ok") is None:
        return "gates never ran. Run: team gate"

    if gates.is_stale(root, state):
        return "code changed since the last gate run. Run: team gate"

    failed = [result["name"] for result in state["gates"]["results"] if not result["ok"]]

    return f"gates failing: {', '.join(failed) or 'no stack detected'}. Fix, then run: team gate"


def _review_problem(root: Path, state: State) -> str | None:
    problem = artifacts.unfinished_reason(item_dir(root, state["id"]) / "review.md")

    if problem:
        return problem

    verdict = artifacts.review_verdict(root, state)

    if verdict != "pass":
        return f"review verdict is {verdict or 'missing'}, needs 'Verdict: pass'"

    if not gates.is_fresh_green(root, state):
        return _gate_problem(root, state)

    return None


def enter_phase(root: Path, state: State, phase_name: str) -> None:
    """Set the phase and create its document from the template if it has one."""
    state["phase"] = phase_name
    add_history(state, "phase", phase_name)
    document = PHASE_DOCUMENTS.get(phase_name)

    if document:
        artifacts.ensure_document(root, state, document)


def advance(root: Path, state: State) -> Refusal | None:
    phase = current_phase(state)

    if phase is None:
        return Refusal(f"Work item {state['id']} is already {state['phase']}")

    problem = output_problem(root, state, phase["check"])

    if problem:
        return Refusal(f"Phase {phase['name']} is not finished: {problem}")

    approval = phase.get("approval")

    if approval and state["approvals"].get(approval) is None:
        return Refusal(
            f"Phase {phase['name']} waits for your approval. "
            f"Run it yourself in a terminal: team approve {approval}",
        )

    names = phase_names(state["track"])
    enter_phase(root, state, names[names.index(phase["name"]) + 1])

    return None


def approve(root: Path, state: State, kind: str, approved_by: str) -> Refusal | None:
    phase = current_phase(state)

    if phase is None or phase.get("approval") != kind:
        return Refusal(f"Nothing to approve as '{kind}' in phase {state['phase']}")

    problem = output_problem(root, state, phase["check"])

    if problem:
        return Refusal(f"Cannot approve {kind} yet: {problem}")

    state["approvals"][kind] = {"by": approved_by, "at": now_iso()}
    add_history(state, "approved", kind)

    return None


def reopen(root: Path, state: State, phase_name: str) -> Refusal | None:
    """Go back to an earlier phase. Approvals given after that phase are cleared."""
    names = phase_names(state["track"])

    if phase_name not in names or phase_name == DONE_PHASE:
        return Refusal(f"Unknown phase {phase_name} for track {state['track']}: {', '.join(names)}")

    state["approvals"]["done"] = None

    if names.index(phase_name) <= _design_index(names):
        state["approvals"]["design"] = None

    enter_phase(root, state, phase_name)

    return None


def _design_index(names: list[str]) -> int:
    return names.index("design") if "design" in names else -1


def agents_for(state: State) -> list[str]:
    phase = current_phase(state)

    return phase["agents"] if phase else []


def all_track_agents(track: str) -> list[str]:
    seen: list[str] = []

    for phase in phases(track):
        seen.extend(agent for agent in phase["agents"] if agent not in seen)

    return seen
