# Copilot CLI agent team: requirements

Status: draft from brainstorm, 2026-11-25. Next step: `/sc:design`.

## 1. Goal

A team of single-job AI agents for **GitHub Copilot CLI** that follow one shared set of code rules
(`~/dev/code-style/CODE_STYLE.md`). A stdlib-only Python tool runs the work the way BMAD does:
phases, documents passed between agents, saved state and quality gates.

Reference task the team must handle well:

> Refactor existing code that uses the State pattern into a pipeline that is idempotent,
> checkpointed, resumable and scalable, without changing what the code does.

## 2. Decisions taken

| topic | decision |
| --- | --- |
| Surface | Copilot CLI only (CLI-specific features allowed) |
| Home | new repo `~/dev/agent-crew`; reads rules from `~/dev/code-style` |
| Roster | all 13 roles (section 4) |
| Script scope | workflow state, artifacts and handoffs, quality gates |
| Tracks | adapts to task size: quick or full, chosen automatically, user can override |
| Approvals | after design (ADR/plan) and before marking done |
| First stacks | C# / .NET, TypeScript |
| Model choice | not fixed per agent; the orchestrator suggests a model for each task and asks the user (R6) |
| Handoffs | orchestrator is the hub; a direct handoff between two agents only on allow-listed pairs (R7) |
| BMAD | its ideas only, with our own names and templates; no BMAD text or branding (R8) |

## 2a. Verified Copilot CLI facts (2026-11-25)

- Agents: `~/.copilot/agents/*.agent.md` (user) and `.github/agents/*.agent.md` (project). If both
  have the same ID, the personal one wins.
- Frontmatter: `name`, `description` (required), `tools`, `model`, `model-policy`,
  `disable-model-invocation`, `user-invocable`, `include-custom-instructions`, `mcp-servers`, `metadata`.
- `tools` aliases: `execute`, `read`, `edit`, `search`, `agent` (call another custom agent), `web`, `todo`.
- A delegated agent runs as a subagent with its own context. By default it **does not** read the repo's
  custom instructions; `include-custom-instructions: true` turns that on.
- Skills: `~/.copilot/skills/<name>/SKILL.md` or `~/.agents/skills/` (user), and `.github/skills/` (project).
- Hooks: `.github/hooks/*.json`, `~/.copilot/hooks/*.json`, or `hooks:` in agent frontmatter.
  Events: `sessionStart`, `sessionEnd`, `userPromptSubmitted`, `preToolUse`, `postToolUse`,
  `postToolUseFailure`, `agentStop`, `subagentStart`, `subagentStop`, `errorOccurred`, `preCompact`,
  `permissionRequest`, `notification`. Subagent hook input carries `parentAgentId`, which suggests
  subagents can nest.
- Not yet verified: whether a subagent can call another subagent (nesting), and whether `handoffs` work in the CLI.

## 3. Out of scope (v1)

- VS Code Copilot Chat, Claude Code, Cursor and other tools (the format should not block adding them later).
- Python and Rust quality gates (the rules still apply; the gates come later).
- Any network calls or third-party Python packages in the script.
- A UI or dashboard. Output is Markdown and JSON files in the repo.

## 4. Functional requirements

### R1. Code style available to Copilot

- R1.1 Copilot CLI loads `CODE_STYLE.md` in every session (user-level instructions).
- R1.2 A **code-style skill** gives on-demand detail: the per-language notes, the stack's
  enforce commands from the code-style README, and a self-check checklist an agent runs before it hands off.
- R1.3 `CODE_STYLE.md` stays the only source; the Copilot files are generated or linked from it, never edited by hand.
- R1.4 Project linter/formatter config wins over the rules (CODE_STYLE §8). Agents must say so when it applies.

### R2. Agents (one job each)

Each agent has: one job, inputs it reads, the output file it writes, an exit checklist, and the next agent it hands off to.

| # | agent | job | main output |
| --- | --- | --- | --- |
| 1 | orchestrator / PM | classify the task, pick the track, run phases, ask for approvals | workflow state |
| 2 | analyst | read the existing code and constraints, write the brief | brief |
| 3 | system architect | system boundaries, scaling, data flow, trade-offs | ADR |
| 4 | code architect | modules, patterns, interfaces, migration path between patterns | design notes in the ADR |
| 5 | backend engineer | APIs, idempotency, transactions, retries, outbox, concurrency | code |
| 6 | data / DB engineer | schema, migrations, checkpoint/state storage, indexes | migrations + notes |
| 7 | frontend engineer | UI components, state, accessibility | code |
| 8 | implementer | general code changes from a story | code |
| 9 | test engineer | characterization tests before a refactor, TDD, acceptance tests | tests |
| 10 | refactoring expert | small safe steps that keep behavior the same | refactor plan + code |
| 11 | security reviewer | threats, input validation, secrets, authorization | findings |
| 12 | performance engineer | measure first, find bottlenecks, benchmarks | findings |
| 13 | reviewer (quality gate) | checks code-style and quality, gives the final verdict before done | review report |
| + | technical writer | READMEs, docs and the final ADR text | docs |

- R2.1 Agents can be picked from Copilot CLI by hand (`/agent`) and the orchestrator can also use them.
- R2.2 Every code-writing agent applies CODE_STYLE (blank-line rules, Result-type errors, naming, ≤ 40-line functions).
- R2.3 Agent prompts are short and to the point. The long know-how lives in skills that load when needed.
- R2.4 Content is ported from existing material where useful: `~/.claude/agents/*` (SuperClaude),
  `~/.claude/skills/agent-orchestrator`, BMAD method concepts. Anything not needed is dropped.

### R3. Knowledge skills

Reusable topic skills that agents load on demand. The first set needed for the reference task:

- R3.1 `code-style` (R1.2).
- R3.2 `pipeline-idempotency`: idempotency keys, checkpoints, resumable steps, exactly-once versus
  at-least-once delivery, outbox, retries with backoff, poison messages.
- R3.3 `pattern-migration`: moving from one pattern to another (State to Pipeline, for example) using
  characterization tests, strangler or branch-by-abstraction, and small reversible steps.
- R3.4 Stack notes for `.NET` (Result<T>, ValueTask, CancellationToken, analyzers) and `TypeScript`.

### R4. Orchestrator script (Python, stdlib only)

- R4.1 **Workflow state**: one state file per work item in the target repo (phase, track, tasks,
  status, approvals, timestamps). Re-running it is safe and the work can resume in a later session.
- R4.2 **Tracks**: the script classifies a task as *quick* (plan, implement, review) or *full*
  (analyze, design/ADR, stories, implement, test, review). The user can override the choice.
- R4.3 **Artifacts**: creates the documents for each phase from templates (brief, ADR, story files with
  acceptance criteria, review report) in a fixed folder in the target repo.
- R4.4 **Handoffs / context pack**: for the next step it prints what the next agent must read
  (files, decisions so far, open items). The agent then works without re-exploring.
- R4.5 **Approvals**: the workflow stops after design and before done until the user approves.
  The approval and who gave it are recorded in the state.
- R4.6 **Quality gates**: detects the stack (C#, TS), runs its check commands (build/lint/format/test),
  and blocks marking a task done while any gate fails. The output shows which command failed and why.
- R4.7 Commands for status, next step, approve, gate, and reopening a step.
- R4.8 Copilot CLI agents call the script through shell commands, and a person can run it by hand too.

### R6. Model choice based on context

- R6.1 Agent files do not hard-code a model, so they keep the user's default.
- R6.2 Before it starts each phase, the orchestrator suggests a model tier. Strong for architecture,
  risky refactors and security; standard for implementation; fast for search and mechanical edits.
  It gives one line of reasoning and asks the user to accept or change it.
- R6.3 The choice is recorded in the workflow state and reused when the work resumes. The script
  prints the matching `copilot --agent <id> --model <model>` command.
- R6.4 Tier → model mapping lives in one config file that the user edits.
- R6.5 Settings hold a list of **favorite models** and optional per-agent **pins**. A pin always wins;
  otherwise the orchestrator picks from the favorites.
- R6.6 With no favorites set, it picks by difficulty from the catalog: the cheapest model in the wanted
  tier, never the most expensive (premium) tier unless the user says yes.

### R7. Handoffs

- R7.1 Default: hub and spoke. Each agent ends by handing back to the orchestrator, which records the
  step in the state and starts the next agent. This always works, nested subagents or not.
- R7.2 Direct handoff, agent to agent, only for allow-listed pairs where it saves a round trip
  (for example implementer → test engineer, reviewer → implementer for fixes). Those agents get the
  `agent` tool; everyone else does not.
- R7.3 The script still records every handoff, direct or not, so the state stays the source of truth.
- R7.4 If nesting proves unsupported during design, R7.2 is dropped and everything goes through the hub.
- R7.5 Every agent sets `include-custom-instructions: true`, so subagents follow CODE_STYLE (§2a).

### R8. BMAD-like, not BMAD

- R8.1 BMAD-METHOD is MIT licensed, but "BMad" / "BMAD-METHOD" are trademarks of BMad Code, LLC.
  We take only ideas: scale-adaptive tracks, roles as personas, planning documents passed between
  roles, story files carrying the context, and step checklists.
- R8.2 All names, templates, prompts and checklists are original. No BMAD files are copied, and
  "BMAD" does not appear in agent, skill or command names.
- R8.3 The README credits BMAD as inspiration in one line.

### R9. Simplicity gate: "Do we really need this? Isn't this over-engineering?"

The goal is code that a person can manage and maintain **without AI**.

- R9.1 Every agent asks this question before it adds anything: a new abstraction, layer, pattern,
  dependency, config option, generic type, interface with one implementation, or "for later" hook.
  Each addition must point to a requirement it serves today. Otherwise it is cut (YAGNI).
- R9.2 Architects (system and code) must write **the simplest option that works** first, then
  argue for anything more complex with a concrete need (load, failure mode, requirement).
  "Might need it later" is not a reason.
- R9.3 Each ADR has a **"Not doing"** section: what was deliberately left out and why.
- R9.4 Maintainable without AI means:
  - plain, idiomatic code for the stack: no clever metaprogramming, no AI-only conventions;
  - an unfamiliar developer can follow the flow from the entry point in a few minutes;
  - no behavior hidden in generated code they can't see;
  - the docs explain *why* in human terms;
  - the fewest moving parts that meet the requirement (fewer files, layers and dependencies).
- R9.5 The reviewer runs an **over-engineering check** as part of its verdict. It flags abstractions
  with a single use, wrappers that only forward calls, needless generics/configs/factories, and
  layers that add no rule. Any flag blocks done until it is removed or justified in the ADR.
- R9.6 When an agent finds that the user's request itself leads to over-engineering, it says so,
  proposes the simpler path, and asks the user before going on.
- R9.7 This applies to our own tooling too: the orchestrator script, agents and skills stay small
  and readable. A person can run the workflow by hand from the docs alone.

### R10. Hooks (enforce instead of trust)

Copilot CLI hooks are JSON files in `.github/hooks/*.json` (project) or `~/.copilot/hooks/*.json`
(user), or a `hooks:` map in an agent's frontmatter (runs only while that agent is active).
Each hook is a shell command that gets JSON on stdin and prints JSON on stdout. Every hook calls the
same stdlib Python script, so no `jq` is needed.

| event | use | effect |
| --- | --- | --- |
| `sessionStart` | print the current work item status | `additionalContext`: phase, next agent, pending approvals |
| `subagentStart` | give the starting agent its context pack | `additionalContext` added before its first message |
| `subagentStop` | record the handoff in the state | state stays the source of truth (R7.3) |
| `preToolUse` | block code edits while the design is not approved; block hand edits of the state file | `permissionDecision: "deny"` with a reason |
| `postToolUse` (edit tools) | run the formatter/linter on the changed files | `additionalContext` with the lint output, so the agent fixes it now |
| `agentStop` | block "done" while gates fail or the final approval is missing | `decision: "block"` with a reason; respects `stop_hook_active` |

- R10.1 Keep the hook set to this table. Add a hook only when a rule is broken often in practice (R9).
- R10.2 Hooks fail safe for us: a `preToolUse` error denies, other errors are logged and let through.
  Every hook has a `timeoutSec`. Gate hooks that run tests use a longer timeout, or run only at `agentStop`.
- R10.3 Every block or deny message says what rule failed and how to fix it (CODE_STYLE §6.3).
- R10.4 Approvals stay with the user. A hook can block, but only the user's `approve` command lifts an approval block.
- R10.5 The workflow still works without hooks (run by hand, R9.7). Hooks only add enforcement.
- R10.6 Hooks load when the CLI starts. Install tells the user to restart Copilot CLI.

### R5. Install

- R5.1 One command installs the agents, skills and instructions at user level (`~/.copilot/...`).
- R5.2 Optional per-project install (`.github/agents`, `.github/skills`, `AGENTS.md`) so the team shares it via git.
- R5.3 Never overwrites a user-edited project file without asking. Re-running the install is safe.

## 5. Non-functional requirements

- N1 Python 3.11+, standard library only, a single entry point, no network.
- N2 The script and all generated code follow CODE_STYLE (ruff config from code-style).
- N3 Plain-text state (JSON/Markdown) that diffs well and can be reviewed in a PR.
- N4 Same input gives the same files (deterministic templates).
- N5 Agent and skill files pass Copilot CLI's frontmatter rules. The install checks them.
- N6 Works on Linux; macOS shell differences avoided.
- N7 Adding a new agent, skill or stack gate = adding files, not changing script logic.

## 6. User stories and acceptance criteria

**US1: State pattern to idempotent pipeline (full track)**
As a developer I ask the orchestrator to refactor an existing State-pattern module into a pipeline.
- Picks the full track and writes a brief that lists the current states, transitions and side effects.
- Test engineer adds characterization tests that pass on the old code **before** any refactor.
- The ADR covers idempotency keys, checkpoint storage, resume rules, failure and retry handling, and how it scales.
- The ADR shows the simplest option that works, and a "Not doing" list. For example, no message
  broker or distributed lock unless a stated load or failure case needs it.
- The workflow stops for my approval of the ADR.
- The refactor is done in small steps and the tests pass after each step.
- Rerunning a pipeline step with the same input causes no duplicate side effects (a test proves it).
- Killing the run mid-way and starting it again resumes from the last checkpoint (a test proves it).
- Gates pass (`dotnet build` / `dotnet format --verify-no-changes` / `dotnet test`, or the TS equivalents).
- The reviewer's report confirms CODE_STYLE compliance and contains a passed over-engineering check,
  and I approve before the task becomes done.

**US6: Pushback on over-engineering**
- I ask for a generic plugin engine where one fixed pipeline would do. The architect asks
  "Do we really need this?", proposes the simpler design with its reasons, and waits for my answer.

**US2: Small fix (quick track)**
- Picks the quick track, writes no ADR, makes one story-sized change, runs the gates and gets a review.

**US3: Resume**
- In a new Copilot CLI session, the status command shows the phase, the next agent and the context pack.

**US4: Rules everywhere**
- In any repo, a Copilot CLI session follows CODE_STYLE without any setup in that project.

**US5: Gate blocks done**
- When lint fails, marking the task done is refused and the failing command and its output are shown.

## 7. Open questions

1. ~~Model per agent~~ → decided in R6.
2. ~~Direct handoffs~~ → decided in R7. Still to check at design: nested subagents in the CLI.
3. Artifact folder name in target repos (for example `.ai/` or `docs/ai/`), and should it be committed?
4. Git: should the script create a branch per work item, and/or a commit per step?
5. ~~BMAD reuse~~ → decided in R8 (ideas only).
6. Should the install also run code-style's `install.sh user copilot`, or replace that step?
7. Is a Plane issue tracker link (from the `plane-dev-workflow` skill) wanted for work items?
