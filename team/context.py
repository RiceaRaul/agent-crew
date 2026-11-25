"""Text summaries an agent reads: the status line and the context pack for the current phase."""

from pathlib import Path

from team import gates, workflow
from team.paths import AI_DIR_NAME
from team.state import State, item_dir

MAX_HANDOFFS_SHOWN = 3
MAX_CONTEXT_CHARS = 4000


def gate_status(root: Path, state: State) -> str:
    if state["gates"].get("ok") is None:
        return "not run"

    freshness = "stale" if gates.is_stale(root, state) else "current"

    return f"{'green' if state['gates']['ok'] else 'red'} ({freshness})"


def pending_approvals(state: State) -> list[str]:
    phase = workflow.current_phase(state)

    if phase is None or "approval" not in phase:
        return []

    kind = phase["approval"]

    return [] if state["approvals"].get(kind) else [kind]


def status_text(root: Path, state: State) -> str:
    lines = [
        f"Work item: {state['id']} - {state['title']}",
        f"Track: {state['track']}  Phase: {state['phase']}  Difficulty: {state['difficulty']}",
        f"Next agent(s): {', '.join(workflow.agents_for(state)) or '-'}",
        f"Gates: {gate_status(root, state)}",
        f"Suggested branch: {state['branch']}",
    ]
    pending = pending_approvals(state)

    if pending:
        lines.append(
            f"Waiting for your approval: {', '.join(pending)} (you run: team approve <kind>)"
        )

    if workflow.is_code_locked(state):
        lines.append("Code edits are locked until the design is approved.")

    for story in state["stories"]:
        lines.append(f"  story {story['id']} [{story['status']}] {story['title']}")

    return "\n".join(lines)


def context_pack(root: Path, state: State, agent: str | None = None) -> str:
    """What the next agent must read: files, decisions so far, open items. Paths, not contents."""
    folder = item_dir(root, state["id"])
    documents = sorted(folder.rglob("*.md"))
    relative_docs = [path.relative_to(root).as_posix() for path in documents]
    lines = [
        f"[team] You are {agent or 'a team agent'} on work item {state['id']}: {state['title']}",
        f"Phase: {state['phase']} (track {state['track']}). Do only this phase's job.",
        "Load skills: team-workflow, code-style, simplicity-check.",
        f"Read first: {', '.join(relative_docs) or 'no documents yet'}",
        f"Decisions: design approved = {_approval_text(state, 'design')}",
        f"Gates: {gate_status(root, state)}",
    ]
    open_stories = [story for story in state["stories"] if story["status"] != "done"]

    if open_stories:
        story_list = ", ".join(f"{story['id']} {story['title']}" for story in open_stories)
        lines.append(f"Open stories: {story_list}")

    for handoff in state["handoffs"][-MAX_HANDOFFS_SHOWN:]:
        summary = handoff["summary"].replace("\n", " / ")
        lines.append(f"Earlier: {handoff['from']}: {summary}")

    if workflow.is_code_locked(state):
        lines.append(
            f"Code is locked: edit only {AI_DIR_NAME}/ and docs/ until the design is approved."
        )

    lines.append("Before adding anything ask: do we really need this? Is it over-engineering?")
    lines.append('When finished: team handoff --from <your id> --summary "<3 lines>"')

    return "\n".join(lines)[:MAX_CONTEXT_CHARS]


def _approval_text(state: State, kind: str) -> str:
    approval = state["approvals"].get(kind)

    return f"yes, by {approval['by']}" if approval else "no"
