---
name: python-engineering
description: Python engineering guidelines for this repository and its owner. Use this skill whenever writing, reviewing, refactoring, or designing ANY Python code — parsers, services, analytics, scripts, FastAPI routes, one-off tools — even if the task seems too small to need guidelines. Also use when choosing dependencies, structuring modules, or designing APIs between components.
---

# Python engineering guidelines

## Operator profile — how the owner thinks

Abhi is an embedded software engineer working on satellites, developing
exclusively in C++ and Python. Two lenses dominate his analysis of any
problem: **efficiency** (least code, least machinery, least runtime waste that
still solves the problem) and **dependency** (what relies on what — in the
package sense, the architectural sense, and the "what breaks if this breaks"
sense). Code written for him should survive both lenses. When two designs are
equivalent, pick the one with fewer moving parts and a clearer dependency
arrow.

Development priority is working code first: implement, then test if and when
testing is asked for. Don't default to test-first, don't propose test
scaffolding unprompted, and don't gate implementation work on a test plan
existing first.

## Core rules

### Pure core, thin I/O shell

- Business logic (parsing, analytics, scoring) lives in pure functions:
  bytes/values in, values out, no I/O, no globals, no hidden state. This keeps
  the core easy to reason about and easy to test later, if and when that's
  wanted.
- I/O (BLE, DB, HTTP, filesystem) lives in thin adapter layers that call the
  pure core. The adapter is boring on purpose; the core is where correctness
  lives.

### Dependency minimalism

- Standard library first. Every third-party package must justify itself
  against "could `stdlib` do this in 30 lines?" — `sqlite3` over an ORM,
  `dataclasses` over pydantic (unless validation at a boundary is the point),
  `argparse` over click for small tools.
- Pin what you depend on; know why each line of requirements exists.
- No framework for a problem a function solves. No plugin architecture until
  there are two real plugins (rule of three for abstractions generally).

### Explicitness

- Type hints on every public function signature. `dataclass(frozen=True)` for
  value objects. `Optional` means "absence is a real case you handle."
- No bare `except:`. Catch the narrowest exception you can name; let the rest
  crash loudly — a stack trace in journald beats silent corruption.
- Timestamps: UTC ISO-8601 strings at every boundary, always. Convert to local
  time only at the display layer, never in storage or logic.
- `logging` module, never `print`, in anything long-running. Log levels mean
  something: DEBUG = development noise, INFO = state changes, WARNING =
  degraded but working, ERROR = a human should look.

### Async discipline (bleak / FastAPI territory)

- Every `await` on external I/O gets a timeout (`asyncio.wait_for` or the
  library's own). An awaited call with no timeout is a hang waiting to happen.
- No fire-and-forget tasks: every created task is awaited, gathered, or
  attached to explicit lifecycle management with error logging.
- Keep async at the edges; pure core functions stay synchronous.

### Data pipelines

- Idempotency is a property, not a hope: re-running any ingest with the same
  input produces the same DB state. Dedupe on natural keys before insert.
- Validate at the boundary, trust the interior: parse/validate external bytes
  once, then pass typed values inward.

## Style defaults

- Small modules with one job; prefer editing existing files to creating new
  ones; no speculative "utils" dumping grounds.
- Readable beats clever. If a comprehension needs a comment, use a loop.
- Measure before optimizing: profile (`cProfile`, `time.perf_counter`) before
  claiming something is slow. Efficiency claims need numbers.

## References (consult, don't inline)

- PEP 8 (style), PEP 20 (philosophy — "explicit is better than implicit" is
  the house motto), `sqlite3` docs.
