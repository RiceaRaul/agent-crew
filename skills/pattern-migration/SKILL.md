---
name: pattern-migration
description: "Moving existing code from one design pattern to another (for example State pattern to Pipeline) safely - characterization tests first, branch by abstraction or strangler, one small green step at a time. Load it for any refactor that changes structure but must keep behavior."
---

# Pattern migration

## Order

1. **Characterization tests first** (team-tester): pin today's behavior, including odd cases, through
   the public entry point. They must pass on the old code before anything moves.
2. **Map old to new**: every old state/transition/side effect → which new step owns it. Write the table in the ADR.
3. **Seam**: one place where callers enter (branch by abstraction). Callers do not change.
4. **Move one piece per step**: build the new piece, switch the seam for that case, run the tests.
5. **Delete the old code** as soon as nothing uses it. No commented-out leftovers.

## Each step

- Compiles, gates green, characterization tests pass.
- Small enough to review in a few minutes.
- Reversible: if a step fails, revert that step only.

## State → Pipeline notes

- State classes with `Handle()` usually become steps; the "current state" field becomes the checkpoint.
- Transitions driven by events become step order plus resume rules (skill pipeline-idempotency).
- Keep the old state names as step names in logs while both exist. It helps whoever debugs it later.

## Don't

- Don't refactor and change behavior in the same step.
- Don't build a generic framework for the new pattern. A plain list of steps first.
