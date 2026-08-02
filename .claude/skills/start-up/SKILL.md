---
name: start-up
description: Session-start briefing for the RavenX Smart Ring project. Use whenever Abhi types "/start-up", "start-up", or otherwise opens a working session and asks where things stand or what to work on today. Reads the repo state, notebook, and bug backlog, then produces last session's summary, today's baseline goal, stretch goals, open P1 bugs, and a prose implementation strategy. Explains the approach and gives starting ideas — never writes the code.
---

# start-up

The session-opening ritual. Abhi works in 2–4 hour sessions, roughly twice a weekend
plus one midweek. The job of this skill is to get him from cold start to writing code
in under five minutes, with no time spent re-reading his own repo.

**He writes the code. This briefing explains the approach and hands him a starting
point — it never contains implementation.** Snippets of existing code for orientation
are fine; new implementation is not.

## Read first (in this order)

1. `notebook.md` — the last dated entry is what happened most recently.
2. `Bug_Backlog.md` — every **P1** and any **RISK** relevant to today's work.
3. `PLAN.md` §6 session roadmap — which numbered session is next.
4. `git log --oneline -10` and `git status` — what actually landed versus what the
   notebook claims. The working tree is the source of truth; the notebook is a memoir.
5. The scaffolded files for the upcoming session's area, so the strategy references
   real function names rather than invented ones.

## Output format

### 1. Where we left off

Three to five sentences on last session: what got done, what broke, what was left
open. Name specific files and findings. If the last session ended mid-task, say so
plainly and lead with it.

### 2. Today's baseline goal

**One** goal, achievable in 2–4 hours by someone writing all the code themselves.
State its exit criterion as an observable fact ("a battery percentage prints in the
terminal"), never as an activity ("work on the BLE client"). If the roadmap's next
session is too big for one sitting, split it and say which half today is.

### 3. Stretch goals

One or two, clearly marked optional, only if the baseline lands early.

### 4. Bugs in scope

Every open **P1**, plus any **RISK** the day's work will touch. If none apply, say
so in one line rather than padding.

### 5. Implementation strategy

The substance. In prose:

- The order to build things, and why that order — what each step de-risks.
- Which existing scaffolded functions get filled, by name and file.
- The specific decisions he'll hit and what to weigh on each.
- Known traps: protocol gotchas, timezone handling, the ring's unset RTC, BLE
  connection ownership, off-by-one framing errors.
- How he'll know each piece works — the observable signal, not a test suite.

Do not write the functions. Describe what they must do, what they take, what they
return, and what "correct" looks like when he runs it.

### 6. First move

One concrete action to start with. Cold starts are the expensive part of a short
session; end by removing that friction.

## Rules

- **Never write implementation code in a briefing.** Guidance and starting ideas only.
- Ground everything in the repo as it actually is. If the notebook and the working tree
  disagree, trust the tree and flag the discrepancy.
- Scope honestly to the hours available. A briefing that overpromises makes every
  session feel like a failure.
- Hardware reality first: the R06 is the daily driver, it is factory-virgin, its RTC has
  never been set, and its raw log must be dumped before the clock is ever written.
- If something in `PLAN.md` or `CLAUDE.md` has gone stale, say so — doc drift is what
  broke the last version of this project.
