# Code style rules (all projects)

The goal is code that reads top to bottom like prose: small steps, separated by air.
Dense code saves lines and costs understanding. When in doubt, add the blank line.

These rules apply to every language. Language notes and tool configs are at the end.
Ready-to-copy configs live next to this file (see README.md).

## 1. Vertical spacing (blank lines)

1. **After a block closes**, put a blank line before the next statement:
   `if`, `for`, `while`, `switch`, `try`, `using`, `match`, `with`, a closure body, a JSX block.
   Exception: the next line is `else`, `catch`, `finally` or a closing brace.
2. **Before `return`** (and `throw`, `break`, `continue`, `yield`) put a blank line,
   unless it is the only statement in its block.
3. **After a group of declarations** (`const`, `let`, `var`, local variables), put a blank line before the logic that uses them.
   Consecutive declarations stay together.
4. **Before a block starts** (`if`, `for`, `try`, ...), put a blank line, unless it is the first statement in its parent block.
5. **Between logical steps** inside a function (load → validate → transform → save), put a blank line. A step is 1–5 lines.
6. **Between functions, methods and class members**, put one blank line. Between top-level sections of a file, one blank line plus an optional section comment.
7. **After guard clauses** (early returns at the top of a function), put a blank line.
8. **Never** more than one consecutive blank line. **Never** a blank line right after `{` or right before `}`.
9. **Imports**: groups in this order: standard library, external packages, internal (alias), relative. One blank line between groups.

```ts
// Bad
function grant(space: Space, member: Member) {
  const key = space.currentKey; if (!key) throw new Error("no key");
  const wrapped = wrap(key, member.publicKey); if (member.isPartner) { audit("grant.partner", member.id); }
  return save(space.id, member.id, wrapped);
}

// Good
function grant(space: Space, member: Member) {
  const key = space.currentKey;

  if (!key) {
    throw new Error("Space has no current key");
  }

  const wrapped = wrap(key, member.publicKey);

  if (member.isPartner) {
    audit("grant.partner", member.id);
  }

  return save(space.id, member.id, wrapped);
}
```

## 2. Lines and statements

1. **One statement per line.** No `a(); b();` on one line. No `if (x) { a(); }` on one line.
2. **Always use braces** for `if`/`else`/loops, even for one statement.
3. **Max line length 100.** When a call, signature or literal does not fit, put **one item per line** with a trailing comma.
4. **No nested ternaries.** A ternary only picks between two simple values. Anything else becomes `if` or a small function.
5. **No logic inside JSX/templates beyond a simple condition or map.** Event handlers longer than one call become named functions above the `return`.
6. **JSX:** more than 3 props, or a line too long → one prop per line. Separate sibling blocks of markup with a blank line when each spans several lines.
7. **Chained calls** longer than the line → one call per line, starting with `.`.
8. **Don't align with extra spaces.** Let the formatter decide horizontal spacing.

## 3. Structure

1. **Early return** instead of nesting. Maximum nesting depth: 3.
2. **Functions do one thing.** Aim for ≤ 40 lines. When a function needs a comment to separate its parts, split it.
3. **≤ 4 parameters.** More → pass one object with named fields.
4. **No magic values.** Name them: `const MAX_CHUNK_BYTES = 4 * 1024 * 1024;`.
5. **Declare variables close to first use**, with the narrowest scope possible. Prefer `const` / immutable.
6. **No dead code**, commented-out code, or unused imports. Version control remembers.

## 4. Naming

1. **Names say what, not how:** `pendingGrants`, not `arr2` or `data`.
2. **Booleans** read as questions: `isActive`, `hasKey`, `canUpload`, `shouldRetry`.
3. **Functions** are verbs: `wrapKey`, `loadSpace`, `verifySignature`. Event handlers: `handleX` / `onX`.
4. **Constants:** `UPPER_SNAKE_CASE` for module-level fixed values. Types/classes: `PascalCase`.
5. **No abbreviations** except universal ones (`id`, `url`, `api`, `db`, `io`). `message`, not `msg`. `index`, not `idx` outside one-line loops.
6. **Same concept, same name** everywhere (do not mix `member` / `user` / `participant` for one thing).

## 5. Comments and docs

1. **Comment why, not what.** The code says what.
2. **Doc comment on every exported function, type and module** that is not obvious from its name.
3. **TODOs** carry a reason and an owner or ticket: `// TODO(owner, TICKET-12): remove after v2 migration`.
4. Comments are full sentences, on their own line above the code, not at the end of long lines.

## 6. Errors

1. **Errors are values.** Expected failures (validation, not found, conflict, forbidden) are returned
   as a result type (`Result<T>` in C#, `Result<T, E>` in Rust), not thrown. Exceptions are only for
   bugs and broken invariants, caught once at the outer boundary. Adapters around libraries that
   throw catch the specific exceptions they expect and convert them to errors.
2. **Never swallow errors.** Every `catch` either handles, converts to a result, or rethrows.
3. **Error messages say what failed and with what:** `"Upload ${uploadId} chunk ${index} hash mismatch"`.
4. **Validate at the boundary** (API input, file, env), then trust the types inside.

## 7. Language notes

**TypeScript / JavaScript.** Prettier formats (printWidth 100, double quotes, semicolons, trailing commas).
ESLint enforces the blank-line rules with `@stylistic/padding-line-between-statements`, plus `curly: all`
and `no-nested-ternary`. Config: `eslint.config.js`, `.prettierrc.json` in this folder.

**Rust.** `rustfmt` + `clippy -D warnings`. rustfmt does not add blank lines, so rules 1.1–1.7 are applied by hand.
`max_width = 100` in `rustfmt.toml`. Errors: `thiserror` in libraries, `anyhow` with `.context("...")` in binaries.

**C# / .NET.** Copy `.editorconfig` to the repo root and `dotnet/Directory.Build.props` + `dotnet/stylecop.json`
next to the `.sln`. They add StyleCop.Analyzers + Roslynator, run style rules on every build
(`EnforceCodeStyleInBuild`), and make warnings errors in Release. Autofix: `dotnet format --severity warn`.
- Enforced and auto-fixed: braces always (IDE0011, SA1503), one statement per line (SA1501, SA1502, IDE2001),
  blank line after `}` (SA1513, IDE2003, RCS0008), blank line between members (SA1516), no double or padding
  blank lines (IDE2000, SA1505, SA1507, SA1508), file-scoped namespaces (IDE0161), unused usings (IDE0005).
- Naming: `_camelCase` private fields, `PascalCase` constants, `I` prefix on interfaces, `Async` suffix.
- Errors: `Result<T>` (readonly struct) with `Map`, `AndThen`, `MapError`, `OrElse`, `Match`, async variants and
  LINQ `Select`/`SelectMany` (query syntax = Rust's `?`). Error codes double as i18n keys. No `throw` in
  domain or feature code (enforce with an architecture test); one middleware turns real exceptions into 500s.
- Async: `ValueTask`/`ValueTask<T>` by default for methods that often finish synchronously; `Task` when
  awaited twice, stored or used with `Task.WhenAll`. `CancellationToken` on every async method.
- Memory: `Span<T>`/`ReadOnlySpan<T>` for parsing and buffers, `Memory<T>` across `await`, `stackalloc` for
  small fixed buffers. Pool what is costly: `ArrayPool<T>`/`MemoryPool<T>` (clear sensitive buffers before
  return), `ObjectPool<T>`, `RecyclableMemoryStream`, `IHttpClientFactory`, database connection pools.
- Prefer source generators on hot paths (System.Text.Json contexts, `[GeneratedRegex]`, `[LoggerMessage]`,
  `[LibraryImport]`). Reflection is allowed where it is simpler; under Native AOT keep it trim-safe
  (`[DynamicallyAccessedMembers]`, no `Reflection.Emit`, no runtime assembly loading). `sealed` classes, `readonly struct`/`record struct` for small values,
  `FrozenDictionary` for read-mostly lookups, `static` lambdas in hot paths, `IAsyncEnumerable<T>` for streams.
- Measure first (BenchmarkDotNet, `dotnet-counters`); readability wins where the gain is not measured.
- Not covered by any analyzer, so applied by hand: blank line before `return`/`throw` (1.2),
  after a declaration group (1.3), before a block (1.4).

```csharp
public async Task<FileReceipt> DownloadAsync(FileId id, CancellationToken ct)
{
    var file = await _files.GetAsync(id, ct);

    if (file is null)
    {
        throw new FileNotFoundException($"File {id} not found in space {_spaceId}");
    }

    var plaintext = await _crypto.DecryptAsync(file, ct);

    await _sink.WriteAsync(plaintext, ct);

    return await _receipts.SignAsync(file, ct);
}
```

**Python.** `ruff format` + `ruff check` (line length 100). Same blank-line rules by hand.
Type hints on every public function.

**SQL.** Lowercase keywords, one clause per line (`select`, `from`, `where`, `order by`),
one column per line when more than 3, explicit `on delete` on every foreign key.

## 8. When rules conflict

The project's own formatter or linter config wins over this file. If a project has none,
copy the configs from this folder (`install.sh project`).
