---
name: pipeline-idempotency
description: "Designing and refactoring work into idempotent, checkpointed, resumable pipeline steps - idempotency keys, checkpoint storage, resume rules, at-least-once with dedupe, outbox, retries with backoff, poison items. Load it for pipelines, jobs, state machines, message handlers, or 'make it idempotent / resumable / scalable'."
---

# Idempotent, resumable pipelines

## Shape

A pipeline is an ordered list of steps. Each step: `input → output`, plus at most one side effect.
Keep it a plain list of functions until a real need says otherwise (skill simplicity-check).

## Rules

1. **Idempotency key per step**: derived from the input, for example `{runId}:{stepName}` or a hash of
   the business key. The same input gives the same key.
2. **Checkpoint after each step**: store `(runId, step, status, outputRef, attempt, updatedAt)`.
   One table or file is enough. Write the checkpoint in the **same transaction** as the step's
   database change when you can.
3. **Resume rule**: on start, load checkpoints and skip steps with status `done`. Re-run `running`
   steps; that is safe because they are idempotent.
4. **Side effects outside the database** (HTTP, email, queue): use an outbox row written with the
   checkpoint, sent by a separate loop, deduped by the idempotency key on the receiver
   or with a "sent" table.
5. **Delivery**: assume at-least-once. Exactly-once = at-least-once + dedupe by key.
6. **Retries**: only for transient errors, exponential backoff with jitter, a max attempt count.
   After the max, mark the item `failed` (poison) with the error and keep going; never loop forever.
7. **Concurrency**: one run per key. Use a unique constraint or a conditional update
   (`where status = 'pending'`) before you reach for a distributed lock.
8. **Scale** by running more workers over independent keys. Do not shard or add a broker before you measure a need.

## Tests that prove it

- Running a step twice with the same input → one side effect.
- Kill after step N, restart → resumes at N+1, final result equals an uninterrupted run.
- Transient failure → retried; permanent failure → marked failed, others continue.
- Two workers on the same key → only one does the work.
