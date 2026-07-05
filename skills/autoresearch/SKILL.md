---
name: autoresearch
description: Run a disciplined autonomous refinement loop — one hypothesis, one file edit, one fixed-budget experiment, one metric, keep-or-revert — until the metric hits its target or the budget runs out. Auto-invoke when the user says "iteratively refine X to match Y", "optimize until <metric>", "autoresearch loop", "tune X overnight", or asks to keep improving something against a single measurable score.
---

# autoresearch — the loop

Origin of the pattern: **github.com/karpathy/autoresearch** (Andrej Karpathy). Karpathy built it to grind ML
training runs overnight; this skill generalizes it to **any task with one measurable metric** — visual diffs,
latency, bundle size, test pass-rate, benchmark score, token cost.

The power is discipline, not cleverness: **one variable per iteration, a hard budget, a single comparable
metric, honest keep/revert.** No batching "while I'm in here" edits — that destroys attribution.

## Files (source of truth)

Everything lives in `.claude/autoresearch/`. Two files, both required.

`program.md` — the goal + the ONE metric. Never let the metric drift silently mid-run.
```md
# GOAL
<one sentence: the end state you're grinding toward>

metric: <name> — <exact command/observation that reads it> — <lower|higher is better> — target: <value>
target_files: <glob or list — the ONLY surface edits may touch>
budget: <N iters OR wall-clock> — per_iter: <e.g. "5 min">
invariants: <constraints that must hold every iteration; blank if none>
```

`scoreboard.md` — append-only history. Every iteration adds a row (kept OR reverted). The next iteration reads
it, so this file IS the loop's memory.
```md
# scoreboard — <goal>
metric: <name> (<direction>) · best-so-far: <value @ iter N>

| iter | hypothesis (1 sentence) | file | metric | Δ | decision | note |
|------|-------------------------|------|--------|---|----------|------|
| 1    | tighten card padding    | Card.tsx | 7.1% diff | -0.8 | keep | closer to ref |
| 2    | swap font-weight 400→800| Card.tsx | 7.4% diff | +0.3 | revert | regressed |
```

## The loop (repeat until stop)

1. **Read** `program.md` (goal + metric) and `scoreboard.md` (best-so-far = your baseline).
2. **Hypothesize** exactly ONE change. Write it as a single sentence — if you can't, it's too big.
3. **Edit** ONE file inside `target_files`. One file. Not two.
4. **Experiment** — run the metric's read command within the `per_iter` budget (build / test / measure).
   Honor every `invariant`.
5. **Score + decide** — the keep-or-revert rule:
   - metric moved past best-so-far in the right direction **AND** invariants hold → **KEEP**; update best-so-far.
   - otherwise → **REVERT** the file (`git checkout -- <file>`), no exceptions, no "but it's cleaner".
6. **Append** the row to `scoreboard.md` — kept or reverted, with the reason. Then loop.

**Stop** when: the metric reaches `target`, the budget is exhausted, or the last K iterations yield no
improvement (plateau). Report best-so-far, the kept diffs, and the scoreboard tail.

## Invariants (do not compromise)

- **One file edit per iteration.** Bundled changes make the metric unattributable.
- **Fixed per-iteration budget.** A runaway experiment starves the run; cut it at `per_iter`.
- **Single metric**, declared in `program.md`, never silently redefined. No metric defined → do not start;
  say what's missing.
- **Honest keep/revert.** Revert on no-improvement even when the edit "feels" better. The scoreboard doesn't lie.
- **Append every iteration.** A reverted attempt is data — it stops the next iteration retrying it.

## Scaling / hygiene

If the run is long and `scoreboard.md` grows past ~200 lines, rotate: summarize the closed phase in one line,
move the old rows to `.claude/autoresearch/archive/<date>_<phase>.md`, reset the active board to header + the
running best-so-far. Keep the hot board lean so each iteration reads cheap context.

Invoke via the `/autoresearch <goal>` command, or dispatch to a Seahorse `autoresearch` agent when present.
