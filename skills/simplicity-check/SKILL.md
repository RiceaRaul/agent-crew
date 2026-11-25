---
name: simplicity-check
description: "The 'do we really need this? isn't it over-engineering?' check. Keeps designs and code simple enough to maintain without AI. Load it when designing, adding abstractions, dependencies or options, and when reviewing."
---

# Simplicity check

Goal: a developer who has never seen the code can follow it from the entry point in a few minutes,
without AI.

## Ask before adding anything

For every new layer, pattern, interface, generic, dependency, config option, factory or "for later" hook:

1. Which requirement needs it **today**? Name it. No name → do not add it.
2. What is the simplest thing that meets that requirement? Did you try it first?
3. How many places use it? One use → inline it.
4. Could a new developer explain it after reading it once?

## Red flags (reviewer blocks on these)

- An interface with one implementation and no test double need.
- A wrapper or service that only forwards calls.
- Generic types, strategies or plugins with one concrete case.
- Config options nobody sets differently.
- A layer that adds no rule (controller → service → manager → repository doing the same thing).
- A queue, broker, cache, lock or new datastore without a stated load or failure case.
- Code generation or reflection where plain code fits.

## When the user's request itself is over-engineered

Say so in one or two sentences, propose the simpler path with its reason, and ask before going on.
Example: "A plugin engine for one fixed pipeline adds 4 types and a registry. A plain list of steps
does the same today. Go with the list?"

## Write it down

In the ADR: "Simplest option that works" first, then each extra part with its need, then a
"Not doing" list with reasons.
