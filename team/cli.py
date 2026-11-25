"""Command line: `team <command>`. Every command works by hand, without Copilot."""

import argparse
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from team import artifacts, context, gates, hooks, install, models, settings, state, workflow
from team.fsutil import Refusal
from team.paths import find_project_root

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2

Handler = Callable[[argparse.Namespace], int]


def refuse(message: str) -> int:
    print(message, file=sys.stderr)

    return EXIT_REFUSED


def root_here() -> Path:
    return find_project_root(Path.cwd())


def load_or_refuse() -> tuple[Path, state.State | None, int]:
    root = root_here()
    loaded = state.load(root)

    if isinstance(loaded, Refusal):
        return root, None, refuse(loaded.message)

    return root, loaded, EXIT_OK


def finish(root: Path, loaded: state.State, outcome: Refusal | None, success: str) -> int:
    """Save and print on success; on refusal print why and save nothing."""
    if outcome is not None:
        return refuse(outcome.message)

    state.save(root, loaded)
    print(success)

    return EXIT_OK


def cmd_init(_: argparse.Namespace) -> int:
    root = root_here()
    folder = state.ai_dir(root)
    folder.mkdir(exist_ok=True)
    print(f"Ready: {folder}. Commit the .ai/ folder so docs get reviewed with the code.")

    return EXIT_OK


def cmd_new(args: argparse.Namespace) -> int:
    root = root_here()
    first_phase = workflow.phases(args.track)[0]["name"]
    created = state.new_state(args.title, args.track, args.difficulty, first_phase)

    if state.state_path(root, created["id"]).exists():
        return refuse(f"Work item {created['id']} already exists. Pick another title.")

    workflow.enter_phase(root, created, first_phase)
    state.save(root, created)
    state.set_current(root, created["id"])
    print(context.status_text(root, created))
    print(f"\nCreate the branch yourself: git switch -c {created['branch']}")

    return EXIT_OK


def cmd_status(_: argparse.Namespace) -> int:
    root, loaded, code = load_or_refuse()

    if loaded is None:
        return code

    print(context.status_text(root, loaded))

    return EXIT_OK


def cmd_context(args: argparse.Namespace) -> int:
    root, loaded, code = load_or_refuse()

    if loaded is None:
        return code

    print(context.context_pack(root, loaded, args.agent))

    return EXIT_OK


def cmd_next(_: argparse.Namespace) -> int:
    root, loaded, code = load_or_refuse()

    if loaded is None:
        return code

    outcome = workflow.advance(root, loaded)
    agents = ", ".join(workflow.agents_for(loaded)) or "-"

    return finish(root, loaded, outcome, f"Phase: {loaded['phase']}. Next agent(s): {agents}")


def cmd_done(args: argparse.Namespace) -> int:
    root, loaded, code = load_or_refuse()

    if loaded is None:
        return code

    if loaded["phase"] != "review":
        return refuse(f"done is the last step after review; current phase is {loaded['phase']}")

    return cmd_next(args)


def cmd_handoff(args: argparse.Namespace) -> int:
    root, loaded, code = load_or_refuse()

    if loaded is None:
        return code

    state.add_handoff(loaded, args.from_agent, args.summary)

    return finish(root, loaded, None, f"Handoff from {args.from_agent} recorded.")


def cmd_story(args: argparse.Namespace) -> int:
    root, loaded, code = load_or_refuse()

    if loaded is None:
        return code

    if args.action == "add":
        story_id = f"S{len(loaded['stories']) + 1}"
        path = artifacts.create_story(root, loaded, story_id, args.value)
        loaded["stories"].append({"id": story_id, "title": args.value, "status": "todo"})

        return finish(root, loaded, None, f"Added {story_id}: {path}")

    story = next((item for item in loaded["stories"] if item["id"] == args.value), None)

    if story is None:
        return refuse(f"No story {args.value} in {loaded['id']}")

    problem = artifacts.unfinished_reason(artifacts.story_path(root, loaded, story["id"]))

    if problem:
        return refuse(f"Story {story['id']} is not finished: {problem}")

    story["status"] = "done"

    return finish(root, loaded, None, f"Story {story['id']} done.")


def cmd_gate(_: argparse.Namespace) -> int:
    root, loaded, code = load_or_refuse()

    if loaded is None:
        return code

    result = gates.run_gates(root)
    loaded["gates"] = result
    state.add_history(loaded, "gates", "green" if result["ok"] else "red")
    state.save(root, loaded)

    if not result["stacks"]:
        return refuse("No stack detected (C# or TS). Add .ai/gates.json for this project.")

    for gate in result["results"]:
        print(f"{'PASS' if gate['ok'] else 'FAIL'} {gate['name']}: {gate['run']}")

        if not gate["ok"]:
            print(gate["tail"])

    return EXIT_OK if result["ok"] else EXIT_REFUSED


def cmd_approve(args: argparse.Namespace) -> int:
    """You only: the pre-tool hook denies agent shell calls, and this asks you to type the id."""
    root, loaded, code = load_or_refuse()

    if loaded is None:
        return code

    if not sys.stdin.isatty():
        return refuse("approve must be run by you in an interactive terminal.")

    typed = input(f"Type the work item id to approve '{args.kind}' ({loaded['id']}): ").strip()

    if typed != loaded["id"]:
        return refuse("Id did not match; nothing approved.")

    outcome = workflow.approve(root, loaded, args.kind, git_user(root))

    return finish(root, loaded, outcome, f"Approved {args.kind}. Next: team next")


def git_user(root: Path) -> str:
    completed = subprocess.run(
        ["git", "config", "user.name"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    return completed.stdout.strip() or "unknown"


def cmd_reopen(args: argparse.Namespace) -> int:
    root, loaded, code = load_or_refuse()

    if loaded is None:
        return code

    outcome = workflow.reopen(root, loaded, args.phase)

    return finish(root, loaded, outcome, f"Reopened at phase {args.phase}.")


def cmd_models(args: argparse.Namespace) -> int:
    config = models.load_config()
    action = args.action or "show"
    config_actions = {"show": _models_show, "fav": _models_fav, "pin": _models_pin}

    if action in config_actions:
        return config_actions[action](config, args.values)

    root, loaded, code = load_or_refuse()

    if loaded is None:
        return code

    item_actions = {
        "plan": _models_plan,
        "set": _models_set,
        "apply": _models_apply,
        "cmd": _models_cmd,
    }

    return item_actions[action](root, loaded, config, args.values)


def _models_show(config: dict, _: list[str]) -> int:
    print(f"Favorites: {', '.join(config['favorites']) or '(none: picks by difficulty)'}")
    print(f"Pins: {config['pins'] or '(none)'}")
    print(f"Premium without asking: {config['allowPremiumWithoutAsking']}")

    for model, info in config["catalog"].items():
        print(f"  {model:<22} tier {info['tier']:<9} cost {info['cost']}")

    for model in models.unknown_favorites(config):
        print(f"Warning: favorite {model} is not in catalog; add it with a tier and cost.")

    return EXIT_OK


def _models_fav(config: dict, values: list[str]) -> int:
    if len(values) != 2 or values[0] not in ("add", "rm"):
        return refuse("Usage: team models fav add|rm <model>")

    verb, model = values

    if verb == "add" and model not in config["favorites"]:
        config["favorites"].append(model)

    if verb == "rm" and model in config["favorites"]:
        config["favorites"].remove(model)

    models.save_config(config)

    return _models_show(config, [])


def _models_pin(config: dict, values: list[str]) -> int:
    if len(values) == 1:
        config["pins"].pop(values[0], None)
    elif len(values) == 2:
        config["pins"][values[0]] = values[1]
    else:
        return refuse("Usage: team models pin <agent> [<model>]  (no model = unpin)")

    models.save_config(config)

    return _models_show(config, [])


def _models_plan(root: Path, loaded: state.State, config: dict, _: list[str]) -> int:
    proposals = [
        models.propose(agent, loaded["difficulty"], config)
        for agent in workflow.all_track_agents(loaded["track"])
    ]
    loaded["models"] = {proposal.agent: proposal.to_dict() for proposal in proposals}
    state.save(root, loaded)
    print(f"Proposed models for {loaded['id']} (difficulty {loaded['difficulty']}):")

    for proposal in proposals:
        upgrade = f"  (premium option: {proposal.upgrade}, ask first)" if proposal.upgrade else ""
        print(
            f"  {proposal.agent:<22} {proposal.model:<20} effort {proposal.effort:<6} "
            f"{proposal.reason}{upgrade}",
        )

    print("Change a row: team models set <agent> <model> [effort]. Then: team models apply")

    return EXIT_OK


def _models_set(root: Path, loaded: state.State, _: dict, values: list[str]) -> int:
    if len(values) not in (2, 3):
        return refuse("Usage: team models set <agent> <model> [effort]")

    entry = loaded["models"].setdefault(values[0], {"agent": values[0]})
    entry["model"] = values[1]
    entry["reason"] = "set by you"

    if len(values) == 3:
        entry["effort"] = values[2]

    return finish(root, loaded, None, f"{values[0]} -> {values[1]}")


def _models_apply(_: Path, loaded: state.State, __: dict, ___: list[str]) -> int:
    if not loaded["models"]:
        return refuse("No models planned yet. Run: team models plan")

    outcome = settings.apply(loaded["models"])

    if isinstance(outcome, Refusal):
        return refuse(outcome.message)

    print(f"Wrote subagent models for {len(loaded['models'])} agents to {outcome}")

    return EXIT_OK


def _models_cmd(_: Path, loaded: state.State, __: dict, values: list[str]) -> int:
    agents = values or list(loaded["models"])

    for agent in agents:
        print(models.command_for(agent, loaded["models"].get(agent, {})))

    return EXIT_OK


def cmd_hook(args: argparse.Namespace) -> int:
    return hooks.run(args.event)


def cmd_install(args: argparse.Namespace) -> int:
    code_style = Path(args.code_style) if args.code_style else install.default_code_style()

    if args.uninstall:
        outcome: install.Report | Refusal = install.uninstall_user()
    elif args.project:
        outcome = install.install_project(Path(args.project).resolve(), code_style)
    else:
        outcome = install.install_user(code_style)

    if isinstance(outcome, Refusal):
        return refuse(outcome.message)

    print("\n".join(outcome.lines))

    for error in outcome.errors:
        print(f"Note: {error}", file=sys.stderr)

    return EXIT_OK


def cmd_check(_: argparse.Namespace) -> int:
    problems = install.validate_sources()

    for problem in problems:
        print(problem)

    if problems:
        return EXIT_REFUSED

    print("Agents and skills: frontmatter OK.")

    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="team", description="Copilot CLI agent team workflow.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create .ai/ in this project").set_defaults(run=cmd_init)

    new = sub.add_parser("new", help="start a work item")
    new.add_argument("title")
    new.add_argument("--track", choices=state.TRACKS, default="quick")
    new.add_argument("--difficulty", choices=state.DIFFICULTIES, default="medium")
    new.set_defaults(run=cmd_new)

    sub.add_parser("status", help="phase, stories, gates").set_defaults(run=cmd_status)

    ctx = sub.add_parser("context", help="what the next agent must read")
    ctx.add_argument("--agent")
    ctx.set_defaults(run=cmd_context)

    sub.add_parser("next", help="finish this phase, go to the next").set_defaults(run=cmd_next)
    sub.add_parser("done", help="finish the review phase").set_defaults(run=cmd_done)

    handoff = sub.add_parser("handoff", help="record a handoff")
    handoff.add_argument("--from", dest="from_agent", required=True)
    handoff.add_argument("--summary", required=True)
    handoff.set_defaults(run=cmd_handoff)

    story = sub.add_parser("story", help="add a story or mark one done")
    story.add_argument("action", choices=("add", "done"))
    story.add_argument("value", help="title for add, story id for done")
    story.set_defaults(run=cmd_story)

    sub.add_parser("gate", help="run the quality gates").set_defaults(run=cmd_gate)

    approve = sub.add_parser("approve", help="you approve design or done")
    approve.add_argument("kind", choices=("design", "done"))
    approve.set_defaults(run=cmd_approve)

    reopen = sub.add_parser("reopen", help="go back to a phase")
    reopen.add_argument("phase")
    reopen.set_defaults(run=cmd_reopen)

    model = sub.add_parser("models", help="show|fav|pin|plan|set|apply|cmd")
    model.add_argument(
        "action", nargs="?", choices=("show", "fav", "pin", "plan", "set", "apply", "cmd")
    )
    model.add_argument("values", nargs="*")
    model.set_defaults(run=cmd_models)

    hook = sub.add_parser("hook", help="Copilot CLI hook entry point")
    hook.add_argument("event", choices=sorted(hooks.HANDLERS))
    hook.set_defaults(run=cmd_hook)

    setup = sub.add_parser("install", help="install for Copilot CLI (user, or --project)")
    setup.add_argument("--project")
    setup.add_argument("--code-style", help="path to CODE_STYLE.md")
    setup.add_argument("--uninstall", action="store_true")
    setup.set_defaults(run=cmd_install)

    sub.add_parser("check", help="validate agent and skill files").set_defaults(run=cmd_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")

    args = build_parser().parse_args(argv)

    return args.run(args)
