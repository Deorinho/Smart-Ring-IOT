---
name: python-engineering
description: Python engineering guidelines for this repository and its owner. Use this skill whenever writing, reviewing, refactoring, or designing ANY Python code — parsers, services, analytics, tests, scripts, FastAPI routes, one-off tools — even if the task seems too small to need guidelines. Also use when choosing dependencies, structuring modules, designing APIs between components, or deciding how to test something in Python.
---

# Python engineering guidelines

## Operator profile — how the owner thinks

Abhi is a Python test engineer working on satellites. Two lenses dominate his
analysis of any problem: **efficiency** (least code, least machinery, least
runtime waste that still solves the problem) and **dependency** (what relies on
what — in the package sense, the architectural sense, and the "what breaks if
this breaks" sense). Code written for him should survive both lenses. When two
designs are equivalent, pick the one with fewer moving parts and a clearer
dependency arrow.

## Core rules

### Tests are the design tool, not the afterthought

- pytest-first: for any non-trivial function, sketch the test (or the fixture)
  before or alongside the implementation. If it's hard to test, the design is
  wrong — fix the design, don't write a clever test.
- **Fixtures over mocks.** Real captured data in JSON test vectors beats
  MagicMock every time. Mocks encode assumptions; fixtures encode reality.
  Reserve mocking for genuine externalities (network, time, radios).
- Use `pytest.mark.parametrize` to run one test body over many fixture cases.
- Every bug fixed gets a regression fixture reproducing it before the fix lands.
- Tests must be deterministic: no sleeps for timing, no wall-clock dependence
  (inject clocks), no ordering dependence between tests.

### Pure core, thin I/O shell

- Business logic (parsing, analytics, scoring) lives in pure functions:
  bytes/values in, values out, no I/O, no globals, no hidden state. This is
  what makes fixture-based testing possible.
- I/O (BLE, DB, HTTP, filesystem) lives in thin adapter layers that call the
  pure core. The adapter is boring on purpose; the core is where correctness
  lives and where tests concentrate.

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
- Keep async at the edges; pure core functions stay synchronous and testable
  without an event loop.

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
  the house motto), pytest docs (fixtures, parametrize), `sqlite3` docs.
