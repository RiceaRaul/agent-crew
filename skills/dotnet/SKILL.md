---
name: dotnet
description: "C# / .NET conventions for this team - Result<T> errors, ValueTask, CancellationToken, analyzers, dotnet format, test commands. Load it when writing or reviewing C# code."
---

# .NET

- Errors: expected failures return `Result<T>` (validation, not found, conflict, forbidden). No `throw`
  in domain/feature code; one middleware turns real exceptions into 500s.
- Async: `ValueTask` for methods that often finish synchronously, `Task` when awaited twice, stored or
  used with `Task.WhenAll`. A `CancellationToken` on every async method, passed down.
- `sealed` classes by default, `readonly record struct` for small values, file-scoped namespaces.
- Naming: `_camelCase` private fields, `PascalCase` constants, `I` prefix on interfaces, `Async` suffix.
- Idempotency in EF Core: unique index on the idempotency key; catch `DbUpdateException` for the
  unique violation and convert it to a "duplicate" result. Write checkpoint + change in one `SaveChangesAsync`.
- Measure before you optimise (BenchmarkDotNet). Readability wins where the gain is not measured.

Gates: `dotnet build -warnaserror`, `dotnet format --verify-no-changes --severity warn`, `dotnet test`.
Fix formatting: `dotnet format --severity warn`.
