"""Copilot CLI hook entry points. Read JSON on stdin, print one JSON line on stdout.

Every hook is a no-op in a folder without an active .ai/ work item, so repos that don't
use the team never notice it. The one exception is doc-only, which is scoped to doc agents.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from team import context, gates, state, workflow
from team.fsutil import now_iso, tail
from team.paths import AI_DIR_NAME, find_project_root, relative_posix

HookInput = dict[str, Any]
HookOutput = dict[str, Any] | None

SHELL_TOOLS = {"bash", "shell", "powershell", "pwsh", "execute", "run_in_terminal"}
EDIT_WORDS = ("edit", "write", "create", "replace", "patch")
PATH_KEYS = ("path", "file_path", "filePath", "filename", "file", "target_file")
PATCH_FILE_PATTERN = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)
APPROVE_PATTERN = re.compile(r"team(?:\.py)?['\"]?\s+approve\b")
DOC_PREFIXES = (AI_DIR_NAME + "/", "docs/")
STOP_PHASES = {"implement", "test", "review"}
LINT_TAIL_LINES = 40
SUMMARY_LINES = 3


def read_input() -> HookInput:
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace").strip()
    log_file = os.environ.get("TEAM_HOOK_LOG")

    if log_file:
        with open(log_file, "a", encoding="utf-8") as log:
            log.write(f"{now_iso()} {raw}\n")

    return json.loads(raw) if raw else {}


def tool_args(data: HookInput) -> dict[str, Any]:
    """toolArgs arrives as a JSON string; the VS Code format uses tool_input as an object."""
    args = data.get("toolArgs", data.get("tool_input", {}))

    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return {"raw": args}

    return args if isinstance(args, dict) else {}


def tool_name(data: HookInput) -> str:
    return str(data.get("toolName", data.get("tool_name", ""))).lower()


def is_shell_tool(name: str) -> bool:
    return name in SHELL_TOOLS


def is_edit_tool(name: str) -> bool:
    return not is_shell_tool(name) and any(word in name for word in EDIT_WORDS)


def edited_paths(args: dict[str, Any]) -> list[str]:
    paths = [str(args[key]) for key in PATH_KEYS if args.get(key)]

    for value in args.values():
        if isinstance(value, str):
            paths.extend(match.strip() for match in PATCH_FILE_PATTERN.findall(value))

    return paths


def deny(reason: str) -> HookOutput:
    return {"permissionDecision": "deny", "permissionDecisionReason": f"[team] {reason}"}


def project_root(data: HookInput) -> Path:
    return find_project_root(Path(data.get("cwd") or os.getcwd()))


def on_session_start(data: HookInput) -> HookOutput:
    root = project_root(data)
    loaded = state.load(root)

    if not isinstance(loaded, dict):
        return None

    return {"additionalContext": "[team] Active work item\n" + context.status_text(root, loaded)}


def on_subagent_start(data: HookInput) -> HookOutput:
    agent = str(data.get("agentName", ""))

    if not agent.startswith("team-"):
        return None

    root = project_root(data)
    loaded = state.load(root)

    if not isinstance(loaded, dict):
        return None

    return {"additionalContext": context.context_pack(root, loaded, agent)}


def on_subagent_stop(data: HookInput) -> HookOutput:
    agent = str(data.get("agentName", ""))
    root = project_root(data)
    loaded = state.load(root)

    if not agent.startswith("team-") or not isinstance(loaded, dict):
        return None

    response_lines = str(data.get("response", "")).strip().splitlines()
    state.add_handoff(loaded, agent, "\n".join(response_lines[:SUMMARY_LINES]) or "(no summary)")
    state.save(root, loaded)

    return None


def on_pre_tool(data: HookInput) -> HookOutput:
    root = project_root(data)

    if not state.has_active_item(root):
        return None

    name = tool_name(data)
    args = tool_args(data)

    if is_shell_tool(name):
        return _check_shell(args)

    if is_edit_tool(name):
        return _check_edit(root, edited_paths(args))

    return None


def _check_shell(args: dict[str, Any]) -> HookOutput:
    command = str(args.get("command", args.get("raw", "")))

    if APPROVE_PATTERN.search(command):
        return deny("Only you approve. Agents may not run 'team approve'; ask the user to run it.")

    if (
        "state.json" in command
        and AI_DIR_NAME in command
        and re.search(r">|Set-Content|Out-File", command)
    ):
        return deny("state.json is written only by team.py. Use a team command instead.")

    return None


def _check_edit(root: Path, paths: list[str]) -> HookOutput:
    loaded = state.load(root)

    if not isinstance(loaded, dict):
        return None

    for path_text in paths:
        relative = relative_posix(root, path_text)

        if relative is None:
            continue

        if relative.startswith(AI_DIR_NAME + "/") and relative.endswith("/state.json"):
            return deny(f"{relative} is written only by team.py. Use a team command instead.")

        if workflow.is_code_locked(loaded) and not relative.startswith(DOC_PREFIXES):
            return deny(
                f"Code edits are locked until the user approves the design ({relative}). "
                "Finish the ADR, then ask the user to run: team approve design",
            )

    return None


def on_post_edit(data: HookInput) -> HookOutput:
    root = project_root(data)

    if not state.has_active_item(root) or not is_edit_tool(tool_name(data)):
        return None

    problems = []

    for path_text in edited_paths(tool_args(data)):
        relative = relative_posix(root, path_text)

        if relative is None or relative.startswith(AI_DIR_NAME + "/"):
            continue

        result = gates.format_file(root, root / relative)

        if result is not None and not result["ok"]:
            problems.append(f"{relative}:\n{tail(result['tail'], LINT_TAIL_LINES)}")

    if not problems:
        return None

    return {"additionalContext": "[team] Lint/format problems, fix now:\n" + "\n".join(problems)}


def on_agent_stop(data: HookInput) -> HookOutput:
    if data.get("stop_hook_active"):
        return None

    root = project_root(data)
    loaded = state.load(root)

    if not isinstance(loaded, dict) or loaded["phase"] not in STOP_PHASES:
        return None

    if not gates.is_stale(root, loaded):
        return None

    return {
        "decision": "block",
        "reason": "[team] Code changed since the last gate run. Run the gates (team gate) "
        "and fix any failure before you stop.",
    }


def on_doc_only(data: HookInput) -> HookOutput:
    """Agent-scoped: doc agents (analyst, architects, writer) may edit only .ai/ and docs/."""
    name = tool_name(data)

    if not is_edit_tool(name):
        return None

    root = project_root(data)

    for path_text in edited_paths(tool_args(data)):
        relative = relative_posix(root, path_text)

        if relative is None or not relative.startswith(DOC_PREFIXES):
            return deny(f"This agent writes documents only (.ai/ and docs/), not {path_text}.")

    return None


HANDLERS = {
    "session-start": on_session_start,
    "subagent-start": on_subagent_start,
    "subagent-stop": on_subagent_stop,
    "pre-tool": on_pre_tool,
    "post-edit": on_post_edit,
    "agent-stop": on_agent_stop,
    "doc-only": on_doc_only,
}


def run(event: str) -> int:
    handler = HANDLERS.get(event)

    if handler is None:
        print(f"Unknown hook event {event}: {', '.join(HANDLERS)}", file=sys.stderr)

        return 2

    # Outer boundary: Copilot denies every tool when a preToolUse hook errors, so a bug here
    # must not lock the session. Report it on stderr and let the call through.
    try:
        output = handler(read_input())
    except Exception as error:  # noqa: BLE001
        print(f"[team] hook {event} failed: {type(error).__name__}: {error}", file=sys.stderr)

        return 0

    if output:
        sys.stdout.write(json.dumps(output, ensure_ascii=False) + "\n")

    return 0
