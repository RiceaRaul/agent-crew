"""Quality gates: detect the stack, run its check commands, and fingerprint the code they ran on."""

import hashlib
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from team.fsutil import read_json, tail
from team.paths import AI_DIR_NAME, CONFIG_DIR
from team.state import State

OUTPUT_TAIL_LINES = 60
FORMAT_TIMEOUT_SEC = 50
SKIPPED_DIRS = {".git", AI_DIR_NAME, "node_modules", "bin", "obj", "dist", ".venv", "__pycache__"}


def load_config(root: Path) -> dict[str, Any]:
    """The project's own .ai/gates.json wins over the default config (CODE_STYLE section 8)."""
    project_config = root / AI_DIR_NAME / "gates.json"

    if project_config.is_file():
        return read_json(project_config)

    return read_json(CONFIG_DIR / "gates.json")


def detect_stacks(root: Path, config: dict[str, Any]) -> list[str]:
    found = []

    for name, stack in config["stacks"].items():
        if any(next(root.glob(pattern), None) for pattern in stack["detect"]):
            found.append(name)

    return found


def stack_for_file(file: Path, config: dict[str, Any]) -> dict[str, Any] | None:
    for stack in config["stacks"].values():
        if file.suffix.lower() in stack.get("extensions", []):
            return stack

    return None


def split_command(command: str) -> list[str] | None:
    """Split without a shell and resolve the program, so `npx` also finds `npx.cmd` on Windows."""
    parts = shlex.split(command)
    program = shutil.which(parts[0]) if parts else None

    if program is None:
        return None

    return [program, *parts[1:]]


def run_command(root: Path, command: str, timeout_sec: int) -> dict[str, Any]:
    argv = split_command(command)

    if argv is None:
        return {"ok": False, "exitCode": None, "tail": f"Command not found: {command}"}

    try:
        completed = subprocess.run(
            argv,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "exitCode": None, "tail": f"Timed out after {timeout_sec}s: {command}"}

    return {
        "ok": completed.returncode == 0,
        "exitCode": completed.returncode,
        "tail": tail(completed.stdout or "", OUTPUT_TAIL_LINES),
    }


def run_gates(root: Path) -> dict[str, Any]:
    """Run every gate of every detected stack, stop at the first failure."""
    config = load_config(root)
    stacks = detect_stacks(root, config)
    results = []

    for stack_name in stacks:
        for gate in config["stacks"][stack_name]["gates"]:
            result = run_command(root, gate["run"], config.get("timeoutSec", 1800))
            result["name"] = f"{stack_name}:{gate['name']}"
            result["run"] = gate["run"]
            results.append(result)

            if not result["ok"]:
                return _summary(root, stacks, results)

    return _summary(root, stacks, results)


def _summary(root: Path, stacks: list[str], results: list[dict[str, Any]]) -> dict[str, Any]:
    is_ok = bool(stacks) and all(result["ok"] for result in results)

    return {"fingerprint": fingerprint(root), "ok": is_ok, "stacks": stacks, "results": results}


def is_fresh_green(root: Path, state: State) -> bool:
    gates = state["gates"]

    return gates.get("ok") is True and gates.get("fingerprint") == fingerprint(root)


def is_stale(root: Path, state: State) -> bool:
    return state["gates"].get("fingerprint") != fingerprint(root)


def format_file(root: Path, file: Path) -> dict[str, Any] | None:
    """Run the stack's single-file formatter. None when no stack handles this file type."""
    config = load_config(root)
    stack = stack_for_file(file, config)

    if stack is None or "formatFile" not in stack:
        return None

    command = stack["formatFile"].replace("{file}", shlex.quote(str(file)))

    return run_command(root, command, FORMAT_TIMEOUT_SEC)


def fingerprint(root: Path) -> str:
    """Hash of HEAD plus changed and untracked files outside .ai/ (state writes never stale it)."""
    if _git(root, "rev-parse", "--is-inside-work-tree") is None:
        return _walk_fingerprint(root)

    digest = hashlib.sha256()
    digest.update((_git(root, "rev-parse", "HEAD") or "no-head").encode())
    status = _git(root, "status", "--porcelain", "-z", "--untracked-files=all") or ""

    for entry in sorted(part for part in status.split("\0") if part):
        relative = entry[3:] if len(entry) > 3 and entry[2] == " " else entry

        if relative.startswith(AI_DIR_NAME + "/"):
            continue

        digest.update(entry.encode())
        file = root / relative

        if file.is_file():
            digest.update(file.read_bytes())

    return digest.hexdigest()


def _git(root: Path, *args: str) -> str | None:
    git = shutil.which("git")

    if git is None:
        return None

    completed = subprocess.run(
        [git, *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if completed.returncode != 0:
        return None

    return completed.stdout.strip("\n")


def _walk_fingerprint(root: Path) -> str:
    """Fallback without git: hash path, size and modification time of every file."""
    digest = hashlib.sha256()

    for folder, dir_names, file_names in os.walk(root):
        dir_names[:] = sorted(name for name in dir_names if name not in SKIPPED_DIRS)

        for name in sorted(file_names):
            path = Path(folder) / name
            stat = path.stat()
            digest.update(
                f"{path.relative_to(root).as_posix()}|{stat.st_size}|{stat.st_mtime_ns}".encode()
            )

    return digest.hexdigest()
