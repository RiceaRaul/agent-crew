---
name: team-workflow
description: "How the team-* agents work together - phases, the team command, handoffs, approvals and gates. Load it whenever you act as a team-* agent or the user mentions a work item, phase, handoff or the .ai/ folder."
---

# Team workflow

`team` below means this command: `{{TEAM}}`

## Phases

| track | phases |
| --- | --- |
| quick | plan → implement → review → done |
| full | analyze → design → stories → implement → test → review → done |

Full track when the change crosses modules, touches stored data or concurrency, changes a public API,
or the requirements are unclear. Otherwise quick.

## Every agent, every time

1. Start: run `team context --agent <your id>`. Read the files it lists. Do not re-explore what is already written.
2. Do only your phase's job. Stay inside the files of your story.
3. Before adding anything new ask: do we really need this? Is it over-engineering? (skill simplicity-check)
4. Write your output into the document the context names. Replace every `TODO:` marker.
5. End: `team handoff --from <your id> --summary "<3 lines: done, open, risk>"`, then reply
   `HANDOFF team-orchestrator` with the same 3 lines.

## Commands

| command | use |
| --- | --- |
| `team status` | where are we |
| `team context --agent <id>` | what to read for this phase |
| `team story add "<title>"` / `team story done S1` | stories (done only when its file has no TODO:) |
| `team gate` | run build/lint/format/tests; must be green before review passes |
| `team next` | finish the phase; refuses with the reason when something is missing |
| `team models plan` / `team models apply` | orchestrator only, after the user accepted the table |

## Rules you cannot break

- Only the user runs `team approve design|done`. Never run it, never ask to run it for them; ask them to.
- Never edit `.ai/work/*/state.json`. Use the commands.
- Full track: code edits are locked until the design is approved. Edit only `.ai/` and `docs/` before that.
- When a command refuses, read its message, fix the cause, run it again. Do not work around it.
