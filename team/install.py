"""Install agents, skills, hooks and the code-style instructions for Copilot CLI.

Files are rendered and copied, not symlinked: symlinks need admin rights or developer mode on
Windows. A manifest of what was written (path -> sha256) lets a re-run update our own files and
skip any file you changed by hand.
"""

import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from team import settings
from team.fsutil import Refusal, read_json, sha256_text, write_json_atomic, write_text_atomic
from team.paths import AGENTS_DIR, AI_DIR_NAME, SKILLS_DIR, TEAM_HOME, copilot_home

TEAM_PLACEHOLDER = "{{TEAM}}"
KNOWN_TOOLS = {"execute", "read", "edit", "search", "agent", "web", "todo"}
MANIFEST_NAME = "team-install.json"
INSTALL_SH_MARKER = "Generated from"
HOOK_EVENTS = {
    "sessionStart": ("session-start", 5),
    "subagentStart": ("subagent-start", 5),
    "subagentStop": ("subagent-stop", 10),
    "preToolUse": ("pre-tool", 5),
    "postToolUse": ("post-edit", 60),
    "agentStop": ("agent-stop", 10),
}
VENDORED_PARTS = ("team.py", "team", "config", "templates")
VENDORED_SUFFIXES = {".py", ".json", ".md"}


@dataclass
class Report:
    """What an install or uninstall did, one line per file."""

    lines: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def add(self, action: str, path: Path) -> None:
        self.lines.append(f"  {action:<8} {path}")


@dataclass(frozen=True)
class Commands:
    """How agents and hooks call team.py at the install target."""

    agent_text: str
    bash: str
    powershell: str


def is_windows() -> bool:
    return os.name == "nt"


def user_commands() -> Commands:
    """Absolute interpreter and script paths, so it works whatever python is on PATH."""
    python = sys.executable
    script = TEAM_HOME / "team.py"
    bash = f'"{python}" "{script}"'
    powershell = f'& "{python}" "{script}"'

    return Commands(powershell if is_windows() else bash, bash, powershell)


def project_commands() -> Commands:
    """Relative to the repo root, so the whole team can use the committed files."""
    script = f"{AI_DIR_NAME}/tool/team.py"
    bash = f"python3 {script}"
    powershell = f"python {script}"

    return Commands(powershell if is_windows() else bash, bash, powershell)


def hooks_json(commands: Commands) -> str:
    hooks: dict[str, list[dict[str, Any]]] = {}

    for event, (name, timeout_sec) in HOOK_EVENTS.items():
        hooks[event] = [
            {
                "type": "command",
                "bash": f"{commands.bash} hook {name}",
                "powershell": f"{commands.powershell} hook {name}",
                "timeoutSec": timeout_sec,
            },
        ]

    return json.dumps({"version": 1, "hooks": hooks}, indent=2) + "\n"


def parse_frontmatter(text: str) -> dict[str, str]:
    """Top-level `key: value` pairs between the first two --- lines. Nested blocks are skipped."""
    lines = text.splitlines()

    if not lines or lines[0].strip() != "---":
        return {}

    values = {}

    for line in lines[1:]:
        if line.strip() == "---":
            return values

        if line and not line[0].isspace() and ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()

    return {}


def validate_sources() -> list[str]:
    """Problems in agent and skill frontmatter (N5). Empty list means all good."""
    problems = []
    agent_ids = set()

    for path in sorted(AGENTS_DIR.glob("*.agent.md")):
        agent_id = path.name.removesuffix(".agent.md")
        meta = parse_frontmatter(path.read_text(encoding="utf-8"))
        problems += _agent_problems(path, agent_id, meta)
        agent_ids.add(agent_id)

    for path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        meta = parse_frontmatter(path.read_text(encoding="utf-8"))

        if meta.get("name") != path.parent.name:
            problems.append(f"{path}: name must be {path.parent.name}")

        if not meta.get("description"):
            problems.append(f"{path}: description is required")

    return problems


def _agent_problems(path: Path, agent_id: str, meta: dict[str, str]) -> list[str]:
    problems = []

    if not agent_id.startswith("team-"):
        problems.append(f"{path}: agent id must start with team-")

    if meta.get("name") != agent_id:
        problems.append(f"{path}: name must be {agent_id}")

    if not meta.get("description"):
        problems.append(f"{path}: description is required")

    try:
        tools = json.loads(meta.get("tools", "[]"))
    except json.JSONDecodeError:
        return [*problems, f'{path}: tools must be a JSON list like ["read", "search"]']

    unknown = sorted(set(tools) - KNOWN_TOOLS)

    if unknown:
        problems.append(f"{path}: unknown tools {unknown}, known: {sorted(KNOWN_TOOLS)}")

    return problems


class Installer:
    """Writes files under one target folder and remembers their hashes in a manifest."""

    def __init__(self, target: Path, manifest_path: Path, report: Report) -> None:
        self.target = target
        self.manifest_path = manifest_path
        self.report = report
        self.manifest: dict[str, str] = read_json(manifest_path) if manifest_path.is_file() else {}

    def write(self, path: Path, text: str, *, may_replace_marked: bool = False) -> None:
        key = path.as_posix()
        new_hash = sha256_text(text)

        if path.exists():
            current = path.read_text(encoding="utf-8")
            current_hash = sha256_text(current)
            is_ours = self.manifest.get(key) == current_hash
            is_marked = may_replace_marked and INSTALL_SH_MARKER in "\n".join(
                current.splitlines()[:5]
            )

            if current_hash == new_hash:
                self.manifest[key] = new_hash
                self.report.add("ok", path)

                return

            if not is_ours and not is_marked:
                self.report.add("skip", path)
                self.report.errors.append(f"{path} was changed by hand; not replaced")

                return

        write_text_atomic(path, text)
        self.manifest[key] = new_hash
        self.report.add("wrote", path)

    def save_manifest(self) -> None:
        write_json_atomic(self.manifest_path, self.manifest)


def install_sources(installer: Installer, commands: Commands, code_style: Path) -> None:
    target = installer.target

    for path in sorted(AGENTS_DIR.glob("*.agent.md")):
        installer.write(target / "agents" / path.name, _render(path, commands))

    for path in sorted(SKILLS_DIR.rglob("*")):
        if path.is_file():
            relative = path.relative_to(SKILLS_DIR)
            installer.write(target / "skills" / relative, _render(path, commands))

    installer.write(
        target / "skills" / "code-style" / "CODE_STYLE.md", code_style.read_text("utf-8")
    )
    installer.write(target / "hooks" / "team.json", hooks_json(commands))


def _render(path: Path, commands: Commands) -> str:
    return path.read_text(encoding="utf-8").replace(TEAM_PLACEHOLDER, commands.agent_text)


def instructions_text(code_style: Path) -> str:
    """Same shape as code-style/install.sh writes, so either tool can refresh the file."""
    header = '---\napplyTo: "**"\n---\n\n'
    note = (
        f"<!-- Generated from {code_style} by team install. Edit the source, then re-run. -->\n\n"
    )

    return header + note + code_style.read_text(encoding="utf-8")


def install_user(code_style: Path) -> Report | Refusal:
    problems = validate_sources()

    if problems:
        return Refusal("Fix these before installing:\n" + "\n".join(problems))

    if not code_style.is_file():
        return Refusal(f"CODE_STYLE.md not found at {code_style}. Pass --code-style <path>")

    report = Report()
    home = copilot_home()
    installer = Installer(home, home / MANIFEST_NAME, report)
    install_sources(installer, user_commands(), code_style)
    instructions = home / "instructions" / "code-style.instructions.md"
    installer.write(instructions, instructions_text(code_style), may_replace_marked=True)
    installer.save_manifest()
    report.lines.append("Restart Copilot CLI to load the hooks.")

    return report


def install_project(project: Path, code_style: Path) -> Report | Refusal:
    """Copies the team into <project>/.github and vendors team.py into <project>/.ai/tool."""
    problems = validate_sources()

    if problems:
        return Refusal("Fix these before installing:\n" + "\n".join(problems))

    if not project.is_dir():
        return Refusal(f"Project folder {project} does not exist")

    report = Report()
    installer = Installer(project / ".github", project / AI_DIR_NAME / MANIFEST_NAME, report)
    install_sources(installer, project_commands(), code_style)
    _vendor_tool(installer, project / AI_DIR_NAME / "tool")
    _add_agents_md_line(installer, project / "AGENTS.md")
    installer.save_manifest()

    return report


def _vendor_tool(installer: Installer, tool_dir: Path) -> None:
    for part in VENDORED_PARTS:
        source = TEAM_HOME / part
        files = [source] if source.is_file() else sorted(source.rglob("*"))

        for file in files:
            if file.suffix in VENDORED_SUFFIXES and "__pycache__" not in file.parts:
                installer.write(tool_dir / file.relative_to(TEAM_HOME), file.read_text("utf-8"))


def _add_agents_md_line(installer: Installer, agents_md: Path) -> None:
    line = (
        "Agent team: `.github/agents/team-*`. Workflow status: `python3 .ai/tool/team.py status`."
    )
    current = agents_md.read_text(encoding="utf-8") if agents_md.exists() else ""

    if line in current:
        installer.report.add("ok", agents_md)

        return

    write_text_atomic(agents_md, current.rstrip("\n") + ("\n\n" if current else "") + line + "\n")
    installer.report.add("updated", agents_md)


def uninstall_user() -> Report:
    report = Report()
    home = copilot_home()
    manifest_path = home / MANIFEST_NAME
    manifest: dict[str, str] = read_json(manifest_path) if manifest_path.is_file() else {}

    for key, expected_hash in sorted(manifest.items()):
        path = Path(key)

        if not path.exists():
            continue

        if sha256_text(path.read_text(encoding="utf-8")) != expected_hash:
            report.add("kept", path)
            report.errors.append(f"{path} was changed by hand; not removed")

            continue

        path.unlink()
        report.add("removed", path)

    _remove_empty_skill_dirs(home / "skills")
    manifest_path.unlink(missing_ok=True)
    result = settings.remove_team_entries()

    if isinstance(result, Refusal):
        report.errors.append(result.message)

    if isinstance(result, Path):
        report.add("cleaned", result)

    return report


def _remove_empty_skill_dirs(skills_dir: Path) -> None:
    if not skills_dir.is_dir():
        return

    for skill in SKILLS_DIR.iterdir():
        folder = skills_dir / skill.name

        if folder.is_dir() and not any(folder.rglob("*.*")):
            shutil.rmtree(folder)


def default_code_style() -> Path:
    return TEAM_HOME.parent / "code-style" / "CODE_STYLE.md"
