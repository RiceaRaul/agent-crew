# agent-crew: a Copilot CLI agent team with shared code rules

Fourteen single-job agents (`team-*`) for GitHub Copilot CLI, the shared rules from
[`CODE_STYLE.md`](CODE_STYLE.md), and `team.py`: a small tool (Python 3.11+, standard
library only, Linux/macOS/Windows) that keeps the workflow state, creates the phase documents,
runs the quality gates, proposes models and powers the hooks.

Prompts **decide**, `team.py` **records and checks**, hooks **enforce**.
Inspired by the ideas of the BMAD method (tracks, role agents, documents passed between roles); all
text here is original.

- Requirements: [docs/requirements.md](docs/requirements.md)
- Design: [docs/design.md](docs/design.md)

## Install

```bash
git clone https://github.com/RiceaRaul/agent-crew.git ~/dev/agent-crew
# uses CODE_STYLE.md from this repo; pass --code-style <path> to use another
python3 ~/dev/agent-crew/team.py install            # Windows: python  %USERPROFILE%\dev\agent-crew\team.py install
```

It writes into `~/.copilot` (or `$COPILOT_HOME`): `agents/team-*.agent.md`, `skills/*`,
`hooks/team.json` and `instructions/code-style.instructions.md`. Files are rendered and copied (no
symlinks, so it works on Windows without admin rights); the command inside them is the absolute path
of the Python that ran the install. Restart Copilot CLI afterwards so it loads the hooks.

- Re-run after you edit anything in this repo. Files you changed by hand in `~/.copilot` are
  never replaced (tracked in `~/.copilot/team-install.json`).
- `team.py install --uninstall` removes only what it installed, plus the `team-*` model settings.
- `team.py install --project <repo>` puts the team into `<repo>/.github/` and a copy of the tool
  into `<repo>/.ai/tool/`, so everyone who clones the repo gets it.
- `team.py check` validates the agent and skill frontmatter.

## Manual install (without `team.py install`)

Agents and skills contain the placeholder `{{TEAM}}`; replace it with the command that runs
`team.py` on your machine. Everything goes into `~/.copilot` (Windows: `%USERPROFILE%\.copilot`).

Linux / macOS:

```bash
TEAM='python3 /home/<you>/dev/agent-crew/team.py'
mkdir -p ~/.copilot/agents ~/.copilot/skills ~/.copilot/hooks ~/.copilot/instructions

for f in ~/dev/agent-crew/agents/*.agent.md; do
  sed "s|{{TEAM}}|$TEAM|g" "$f" > ~/.copilot/agents/"$(basename "$f")"
done

cp -r ~/dev/agent-crew/skills/* ~/.copilot/skills/
sed -i "s|{{TEAM}}|$TEAM|g" ~/.copilot/skills/*/SKILL.md
cp ~/dev/agent-crew/CODE_STYLE.md ~/.copilot/skills/code-style/
{ printf -- '---\napplyTo: "**"\n---\n\n'; cat ~/dev/agent-crew/CODE_STYLE.md; } \
  > ~/.copilot/instructions/code-style.instructions.md   # rules for every session
```

Windows (PowerShell 7):

```powershell
$team = '& "C:\Path\To\python.exe" "C:\Users\<you>\dev\agent-crew\team.py"'
$cop = "$HOME\.copilot"
New-Item -ItemType Directory -Force "$cop\agents", "$cop\skills", "$cop\hooks", "$cop\instructions" | Out-Null

Get-ChildItem "$HOME\dev\agent-crew\agents\*.agent.md" | ForEach-Object {
  (Get-Content $_ -Raw).Replace('{{TEAM}}', $team) | Set-Content "$cop\agents\$($_.Name)" -NoNewline
}

Copy-Item "$HOME\dev\agent-crew\skills\*" "$cop\skills" -Recurse -Force
Get-ChildItem "$cop\skills\*\SKILL.md" | ForEach-Object {
  (Get-Content $_ -Raw).Replace('{{TEAM}}', $team) | Set-Content $_ -NoNewline
}
Copy-Item "$HOME\dev\agent-crew\CODE_STYLE.md" "$cop\skills\code-style\"

$rules = Get-Content "$HOME\dev\agent-crew\CODE_STYLE.md" -Raw
"---`napplyTo: `"**`"`n---`n`n$rules" | Set-Content "$cop\instructions\code-style.instructions.md"
```

Hooks: create `~/.copilot/hooks/team.json`. Each event has a `bash` command (Linux/macOS) and a
`powershell` command (Windows); put your own paths in both:

```json
{
  "version": 1,
  "hooks": {
    "sessionStart":  [{"type": "command", "bash": "python3 /home/<you>/dev/agent-crew/team.py hook session-start",  "powershell": "& python C:\\Users\\<you>\\dev\\ai\\team.py hook session-start",  "timeoutSec": 5}],
    "subagentStart": [{"type": "command", "bash": "python3 /home/<you>/dev/agent-crew/team.py hook subagent-start", "powershell": "& python C:\\Users\\<you>\\dev\\ai\\team.py hook subagent-start", "timeoutSec": 5}],
    "subagentStop":  [{"type": "command", "bash": "python3 /home/<you>/dev/agent-crew/team.py hook subagent-stop",  "powershell": "& python C:\\Users\\<you>\\dev\\ai\\team.py hook subagent-stop",  "timeoutSec": 10}],
    "preToolUse":    [{"type": "command", "bash": "python3 /home/<you>/dev/agent-crew/team.py hook pre-tool",       "powershell": "& python C:\\Users\\<you>\\dev\\ai\\team.py hook pre-tool",       "timeoutSec": 5}],
    "postToolUse":   [{"type": "command", "bash": "python3 /home/<you>/dev/agent-crew/team.py hook post-edit",      "powershell": "& python C:\\Users\\<you>\\dev\\ai\\team.py hook post-edit",      "timeoutSec": 60}],
    "agentStop":     [{"type": "command", "bash": "python3 /home/<you>/dev/agent-crew/team.py hook agent-stop",     "powershell": "& python C:\\Users\\<you>\\dev\\ai\\team.py hook agent-stop",     "timeoutSec": 10}]
  }
}
```

Then restart Copilot CLI and check with `/agent` (the `team-*` agents are listed) and `/skills`.

Per project instead of per user: same files into `<repo>/.github/agents`, `<repo>/.github/skills`
and `<repo>/.github/hooks/team.json`. Copilot asks you to trust the folder the first time.

Hooks are optional: without them the agents still work, but nothing enforces the rules (code
lock, approve guard, gate check before stop).

Mixing both ways: `team.py install` does not replace files it did not write unless they are
identical to what it would write; it reports the others as "changed by hand". To switch
from manual to automatic, delete the manual files first.

Shortcut used below: `alias team="python3 ~/dev/agent-crew/team.py"` (PowerShell:
`function team { python $HOME\dev\agent-crew\team.py @args }`).

## Use it in Copilot CLI

```text
copilot
> /agent team-orchestrator
> Refactor the order state machine in src/Orders into an idempotent pipeline with checkpoints.
```

The orchestrator picks the track and difficulty, shows you the proposed models, then delegates one
phase at a time. It stops twice for you:

```bash
team approve design   # after you read .ai/work/<id>/adr.md
team approve done     # after you read .ai/work/<id>/review.md
```

Only you can approve: a hook denies agents running `approve`, and it asks you to type the work item id.

## Tracks and phases

| track | phases | when |
| --- | --- | --- |
| quick | plan → implement → review → done | small, local change |
| full | analyze → design → stories → implement → test → review → done | crosses modules, stored data, concurrency, public API, or unclear |

`team next` moves on only when the phase output exists and has no `TODO:` markers left. In the full
track, code edits are locked until the design is approved. Phase documents live in the target repo
under `.ai/work/<id>/` (brief, adr, stories, review, state.json); commit them.

## Run it by hand (no AI needed)

```bash
team init
team new "Order state machine to pipeline" --track full --difficulty high
team status                    # phase, next agent, gates, approvals
team context                   # what the next person/agent must read
team next                      # finish the phase (tells you what is missing)
team story add "Characterization tests"
team story done S1
team gate                      # build, lint, format, tests for C# and TS
team reopen design             # go back; clears later approvals
team done
```

## Models

`config/models.json` holds your choices:

- `favorites`: models you prefer (`team models fav add claude-sonnet-5.5`).
- `pins`: one fixed model for an agent (`team models pin team-reviewer gpt-5.5`; without a model it unpins).
- `catalog`: model → tier (`fast`, `standard`, `strong`, `premium`) and `cost`. The cost numbers are
  yours: check the multipliers `/model` shows and edit them. IDs come from `copilot help config`.

Per work item: `team models plan` proposes a model per agent. A pin wins. Otherwise it takes the
cheapest favorite in the tier the difficulty needs, else the cheapest catalog model in that tier. It
steps **down** a tier when nothing fits, never up. **Premium is never picked unasked**: for a critical
task it is only offered. A task raises a role's difficulty by at most one level above the role's own.
Change rows with `team models set <agent> <model> [effort]`, then
`team models apply` writes `subagents.agents.team-*` into `~/.copilot/settings.json` (backup first,
other keys untouched; it refuses to rewrite a file it cannot parse and prints the snippet instead).
`team models cmd <agent>` prints the `copilot --agent ... --model ...` line for a manual run.

## Gates

`config/gates.json` detects the stack (C#: `*.sln`/`*.csproj`, TS: `tsconfig.json`) and runs its
commands. A project overrides them with `.ai/gates.json`. Results are tied to a fingerprint of the
code, so a change after a green run makes them stale again. Add a stack by adding JSON.

## Hooks

| event | does |
| --- | --- |
| sessionStart | shows the active work item |
| subagentStart | gives a `team-*` agent its context pack |
| subagentStop | records the handoff |
| preToolUse | denies: `team approve` from agents, edits to state.json, code edits before design approval |
| postToolUse | formats/lints the edited file and returns the errors to the agent |
| agentStop | in implement/test/review, blocks stopping while gates are stale |

The analyst, the architects and the writer also have an agent-scoped hook: they may edit only `.ai/` and `docs/`.
Hooks do nothing in repos without an active `.ai/` work item. If a hook itself fails, it reports on
stderr and lets the call through. For debugging, set `TEAM_HOOK_LOG=/path/log` to record every hook input.

## Layout

```text
CODE_STYLE.md  the shared code rules (installed as Copilot instructions + code-style skill)
agents/      14 agent prompts (team-*.agent.md), {{TEAM}} = the team.py command
skills/      team-workflow, code-style, simplicity-check, pipeline-idempotency,
             pattern-migration, dotnet, typescript
templates/   brief, adr, story, review (TODO: markers mark what to fill)
config/      tracks.json, models.json, gates.json
team/        the tool: one module per job (state, workflow, artifacts, gates, models,
             settings, context, hooks, install, cli)
tests/       python3 -m unittest discover -s tests -t .
```

Lint (optional, only when you change the Python): `ruff check . && ruff format --check .`
(`ruff.toml` follows CODE_STYLE.md). Get ruff with `pipx install ruff`, `sudo pacman -S ruff`,
`winget install astral-sh.ruff` or `uvx ruff`. Not needed to run agent-crew.

## Verified against the live CLI (Copilot CLI 1.0.105, 2026-11-25)

| check | result |
| --- | --- |
| user-level agents load (`copilot --agent team-writer`) | works |
| tool names in hooks | `edit` (path, old_str, new_str), `create` (path, file_text), `bash`, `view`, `glob`, `grep`, `task` (delegation); `toolArgs` arrives as an object |
| code lock before design approval | `edit` and `create` on `src/` denied with the team message |
| agent-scoped hook (doc-only) | fires; gets VS Code-style input (`tool_name` `Write`/`Edit`/`Read`, `tool_input`) |
| `team approve` from an agent | denied |
| orchestrator → subagent, handoff recorded | works; `subagentStart`/`Stop` carry `agentName`, `agentId`, `parentAgentId` |
| `subagents.agents.<id>.model` | honored: team-writer started on its configured model while the session ran another |
| nested subagents (agent → agent → agent) | works |

Notes from the tests:

- Not every model in `copilot help config` is enabled for every account (`gpt-5-mini` and
  `gpt-5.4-mini` failed with "Model ... is not available"; that failure costs no request). Keep only
  models from your `/model` list in `config/models.json`.
- Doc agents have no shell, and `create` does not make folders. When `docs/` is missing they
  write into `.ai/work/<id>/` and say so.
- Direct agent-to-agent hand-offs are possible (nesting works). They stay off on purpose: only the
  orchestrator has the `agent` tool. To allow one, add `"agent"` to that agent's `tools` and say in
  its prompt which agent it may call.
- Debug any hook with `TEAM_HOOK_LOG=/path/log copilot ...`.
