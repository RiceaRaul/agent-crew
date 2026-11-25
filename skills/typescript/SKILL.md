---
name: typescript
description: "TypeScript conventions for this team - strict tsconfig, ESLint + Prettier, result unions for expected errors, test commands. Load it when writing or reviewing TypeScript or JavaScript."
---

# TypeScript

- `strict: true`. No `any`; use `unknown` and narrow at the boundary (validate input once, then trust types).
- Expected failures as values: `type Result<T, E> = { ok: true; value: T } | { ok: false; error: E }`.
  Throw only for bugs.
- Prefer `const`, small pure functions, plain objects over classes unless state needs them.
- No logic in JSX beyond a simple condition or map. Handlers longer than one call get a name.
- Formatting: Prettier (printWidth 100, double quotes, semicolons, trailing commas).
  Blank-line rules: ESLint `@stylistic/padding-line-between-statements`.

Gates: `npx tsc --noEmit`, `npx eslint .`, `npx prettier --check .`, `npm test`.
Fix: `npx eslint --fix . && npx prettier --write .`.
