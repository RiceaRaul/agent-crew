---
name: code-style
description: "The shared code rules (blank lines, one statement per line, braces, small functions, naming, errors as values) with a self-check list. Load it before writing or reviewing any code."
---

# Code style

Full rules: [CODE_STYLE.md](CODE_STYLE.md). The project's own formatter/linter config wins over them.

## Self-check before you hand off

- [ ] Blank line after every closed block, before `return`/`throw`, after a declaration group, before a block.
- [ ] Never two blank lines; never a blank line right after `{` or before `}`.
- [ ] One statement per line, braces always, lines ≤ 100 (C# 120).
- [ ] No nested ternaries. Early returns, nesting ≤ 3.
- [ ] Functions do one thing, ≤ 40 lines, ≤ 4 parameters.
- [ ] Names say what: booleans `isX/hasX/canX`, functions are verbs, no abbreviations.
- [ ] No magic values, no dead or commented-out code, no unused imports.
- [ ] Comments say why. Doc comment on exported API that is not obvious.
- [ ] Expected failures are returned as results, not thrown. No swallowed errors.
- [ ] Error messages say what failed and with which id.

## Enforce

| stack | check | fix |
| --- | --- | --- |
| C# | `dotnet build` + `dotnet format --verify-no-changes --severity warn` | `dotnet format --severity warn` |
| TS | `npx eslint .` + `npx prettier --check .` | `npx eslint --fix . && npx prettier --write .` |

Rules the linters cannot check (blank lines in C#, Python and Rust; nested ternaries in C#) you check by hand.
