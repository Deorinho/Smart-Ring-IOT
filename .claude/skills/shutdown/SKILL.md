---
name: shutdown
description: Session-close ritual for the RavenX Smart Ring project. Use whenever Abhi types "/shutdown", says he's done for the session, or asks to close out / wrap up / finish a working session. Surveys the working tree, reconciles unstaged and uncommitted work, updates notebook.md / PLAN.md / Bug_Backlog.md, then drafts a commit message and PR body. Never runs git commit, push, or pr create — Abhi does those himself.
---

# shutdown

The closing half of the session handshake. `/startup` opens a session; this closes it.
The goal is that Abhi can walk away and lose nothing — findings captured, docs true,
the branch ready to merge.

**This skill never runs `git commit`, `git push`, `git add`, or `gh pr create`.** It
drafts; Abhi executes. Same boundary as the `git-commit` skill.

## Steps (in order)

### 1. Survey the tree

Run `git branch --show-current`, `git status --short`, `git diff --stat`,
`git diff --cached --stat`, and `git log --oneline main..HEAD`. The working tree is
the source of truth — never write a summary from what the conversation *claims*
happened. If a file was supposedly edited and isn't in `git status`, say so.

If the branch is `main`, flag it: session work belongs on a session branch, and
`main` is the hub's deployment target.

### 2. Reconcile every changed path

Walk the list and state, per file, what changed and why. Then **ask about anything
that doesn't obviously belong in this session's PR**:

- Stubs filled halfway, or functions left raising `NotImplementedError` that the
  session was supposed to complete.
- Debug prints, commented-out experiments, hardcoded test values.
- Files touched incidentally that have nothing to do with the session's goal.
- Untracked files that may be scratch rather than deliverables.

Do not assume the answer. A half-finished function silently merged to `main` is the
exact failure the branch workflow exists to prevent.

### 3. Capture what lives outside the repo

Much of the real work happens in scratch scripts on the hub (`~/ProjectScratchPad`),
in terminal output, and in screenshots. None of it is in git. Ask what needs recording
before it's lost — protocol findings, byte layouts, device strings, measured numbers,
failures worth remembering.

### 4. Lint check and mechanical fixes

Run whatever the repo already has configured — `.markdownlint.jsonc` covers the docs.
If a language has no linter configured, do a light manual pass rather than installing
tooling mid-shutdown; adding a dependency is a decision for a session, not a closing step.

**Fix only mechanical, obviously-safe things:** trailing whitespace, inconsistent
indentation, unused imports, stray blank lines, trivial line-length overruns.

**Never do any of the following to satisfy a linter:**

- Restructure, rename, or change the behaviour of working code.
- "Complete" a scaffolded stub. `protocol/packets.py` and `protocol/commands.py` are
  full of functions that `raise NotImplementedError` with parameters they never use.
  Every Python linter flags those. **They are intentional and stay exactly as they
  are** — Abhi fills those bodies, not the linter.
- Touch anything outside the files this session already changed.

**Stop when it stops being mechanical.** If fixes start cascading, or a rule wants a
real code change, stop and report the remainder as a note in the closing summary.
Unfixed lint is a smaller problem than a shutdown step that quietly rewrites code.
Report what was fixed and what was deliberately left.

### 5. Update the documentation

- **`notebook.md`** — exactly ONE dated entry for the session. Narrative, not a
  changelog: what was done, what broke and in what order, how long it took, what's
  open. This file is the video's script skeleton, so failures and dead ends are
  content, not noise. Machine-generated change records belong in `journal/`.
- **`PLAN.md` §6** — mark the session's roadmap row complete, or split it and say
  which half landed. Correct anything the session proved wrong.
- **`Bug_Backlog.md`** — add bugs and risks found; move anything fixed to Closed with
  the date. Never delete a closed row; a fixed bug is video material.

### 6. Draft the commit message

Follow the `git-commit` skill's rules: read the real diff, quantify where possible,
no invented motivation, **no `Co-Authored-By` trailer**. Output it as a fenced block
Abhi can paste.

### 7. Draft the PR

Title and body. The body should state what the branch delivers, what was confirmed
empirically (with the evidence), and what was deliberately left open. Keep it short —
this is a solo repo, the PR is a self-review surface and a record, not a ceremony.

### 8. Say what opens next session

One or two lines. `/startup` will re-derive it properly, but ending a session knowing
the next move is worth more than the accuracy.

## Rules

- Trust the tree over the conversation. Always.
- Report honestly: if the session's goal was missed, the notebook says so.
- Don't pad. A short session gets a short entry.
- Lint fixes are mechanical only, and scaffolded stubs are never "fixed."
- Never commit, push, stage, or open the PR.
