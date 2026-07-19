---
name: cpp-embedded
description: C and C++ embedded engineering guidelines for firmware work — ESP-IDF on ESP32-C3, the Travel Protocol satellite, Phase 3 ring firmware (BlueX RF03), and any other microcontroller or bare-metal code. Use this skill whenever writing, reviewing, or designing ANY C or C++ code, NimBLE/BLE code, ISR handlers, FreeRTOS tasks, state machines, or hardware-facing logic — even for small snippets, examples, or prototypes.
---

# C/C++ embedded engineering guidelines

## Operator profile — how the owner thinks

Abhi works on satellites: hardware that cannot be walked over to and rebooted.
That mindset governs all firmware here — **assume the device is unreachable
after deployment**, budget every resource explicitly, and design for the
failure modes first. His analytical lenses are efficiency and dependency;
embedded code should make both visible: where every byte and milliamp goes,
and what each module needs to function.

## Core rules

### Determinism and resources

- Fixed-width types always: `uint8_t`, `int32_t` from `<stdint.h>` — never
  bare `int`/`long` for anything that touches a wire, a register, or a struct
  layout.
- **Allocate at init, not in steady state.** All buffers, queues, and handles
  are created during startup with sizes from named constants. If steady-state
  operation calls `malloc`, justify it in a comment or redesign.
- Static buffer sizes are named, budgeted constants (`#define RING_PAYLOAD_MAX
  512`), not magic numbers — and the budget math (why 512?) lives in a comment.
- Know the numbers: stack per task, heap high-water mark, flash usage. Check
  `uxTaskGetStackHighWaterMark` / `esp_get_free_heap_size` during bring-up and
  log them; a leak found in soak-test is a leak not found in Mississauga.

### Every return value is checked

- `esp_err_t` is never ignored. Use `ESP_ERROR_CHECK` where failure is
  unrecoverable-by-design; otherwise handle explicitly and log. An unchecked
  return is an invisible failure mode.
- Timeouts on every blocking operation — queue receives, BLE operations,
  HTTP calls. `portMAX_DELAY` requires a written justification; an infinite
  wait is a hang you can't SSH into.

### ISRs and tasks

- ISRs do the minimum: capture, timestamp, push to a queue
  (`xQueueSendFromISR`), return. No logging, no allocation, no floating point,
  no protocol logic in interrupt context.
- One task, one job. Inter-task communication via queues, not shared globals;
  when shared state is unavoidable, guard it and document the owner.
- Feed watchdogs intentionally. A task that can starve the watchdog under
  load has a bug; a disabled watchdog hides one.

### State machines are explicit

- Connection/sync/update logic is an `enum` state + a `switch` transition
  function — never an accumulation of booleans (`is_connecting`, `has_synced`,
  `retry_pending`...). Every state and every transition has a name; invalid
  transitions log and recover to a known state.
- Draw the state diagram before coding it (house design-before-code rule);
  the enum in code must match the diagram in the design doc.

### Testability off-target

- Separate pure logic (framing, buffering decisions, backoff computation,
  policy) from the hardware abstraction layer. Pure C logic compiles and runs
  host-side, tested against the **same JSON fixture vectors as the Python
  parsers** — the cross-language oracle pattern.
- The HAL boundary is a small set of function pointers or a thin interface;
  hardware-specific code stays behind it.

### Deployment reality (the satellite rules)

- OTA self-update is a feature of the firmware, not an afterthought — a
  deployed device with no update path is one bug from being e-waste.
- Never mark data delivered until the receiving end acknowledges it.
- Log via `ESP_LOGx` with levels used honestly; on-device logs are the only
  witness after deployment.

### C++ subset (when C++ rather than C)

- RAII for every resource that has a release. No exceptions, no RTTI on
  embedded targets. `std::array`/fixed-capacity containers over dynamic ones;
  `constexpr` over macros where the toolchain allows. `const` everything that
  can be.

## Style defaults

- Clarity beats micro-optimization until measurements say otherwise; but on
  a battery or a radio duty cycle, *do* measure — power is a correctness
  requirement here, not a nicety.
- No vendor-example copy-paste without reading it: examples optimize for demo
  brevity, not robustness. Strip what isn't needed; add the error handling
  they skipped.

## References (consult, don't inline)

- ESP-IDF programming guide (esp32-c3 target), NimBLE host docs,
  `esp_https_ota` docs, C++ Core Guidelines (for the C++ subset),
  FreeRTOS task/queue documentation. MISRA-C in spirit, not ceremony:
  the goal is code whose failure modes are enumerable.
