---
name: git-commit
description: Draft a concise, paste-ready git commit message from the current changes (staged or unstaged) or from a task just completed in this session. Use this skill whenever the user asks for a commit message, asks you to "write the commit," or asks you to summarize what was just done for a commit — even if they don't say the word "skill." Output the message only, nothing else, so it can be pasted directly into the commit editor.
---

# git-commit

Generate a commit message from real, observed changes — never from memory of
what was *supposed* to happen. Read the diff, then write.

## Process

1. Run `git status` and `git diff` (staged first via `git diff --cached`; if
   nothing is staged, use the unstaged diff) to see the actual changes. If the
   task in this session already produced a clear before/after (files created,
   counts of things fixed), prefer that over re-deriving it from a diff you
   haven't seen — but always reconcile against `git status`/`git diff` before
   finalizing, since the working tree is the source of truth, not the
   conversation.
2. Identify what changed at the level a reviewer cares about: which files,
   what kind of change (add / fix / refactor / remove / rename), and why —
   the "why" only if it's evident from context (a stated goal, a linked
   issue, a design doc referenced in the session), never invented.
3. Pull out anything objectively quantifiable and lead with it or fold it into
   the summary line: file counts, issue counts fixed, lines changed, tests
   added/passing, before → after numbers. Prefer a real number over a vague
   adjective — "fixed 148 lint issues across 9 files" beats "cleaned up
   linting."

## Output format

```text
<type>: <concise summary line, imperative mood, ideally under 72 chars>

- <bullet, quantified where possible>
- <bullet, quantified where possible>
```

- `<type>` is a short conventional prefix (`feat`, `fix`, `docs`, `chore`,
  `refactor`, `test`) — use `docs` for markdown/planning-only changes, `chore`
  for tooling/config. Skip the prefix entirely if this repo's history doesn't
  use conventional commits (check `git log --oneline -10` if unsure).
- Body is only as long as needed. A one-file change gets a one-line message,
  no bullets. Don't pad a small change to look substantial.
- Every bullet states a fact about the diff, not a narrative about the
  session ("added X", not "I worked on adding X" or "this commit adds X").
- No filler adjectives (robust, comprehensive, various, several) where a
  number or a name would do instead.
- **No `Co-Authored-By` trailer or any AI-attribution line** — this repo's
  owner has said explicitly not to include one.
- Output *only* the fenced message block (or the raw message text) — no
  preamble like "Here's your commit message," no trailing explanation. The
  point is that it's paste-ready as-is.

## What this skill does not do

- It does not run `git commit`, `git add`, or any other mutating git command.
  Drafting the message is the entire job; committing is the user's action,
  per this repo's Git Safety Protocol.
- It does not invent scope, motivation, or ticket references that aren't
  visible in the diff or the conversation.
