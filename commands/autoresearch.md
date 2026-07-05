---
description: Karpathy-style overnight autoresearch loop — one hypothesis, one file, one budgeted experiment, one metric, keep-or-revert. Works for any task with a single measurable metric.
argument-hint: <goal or path to program.md>
---

Autoresearch loop. Arg: **$ARGUMENTS**

Origin of the pattern: github.com/karpathy/autoresearch (Andrej Karpathy). This generalizes it beyond ML —
any task that exposes ONE measurable metric.

## 0. Bootstrap (once)

Ensure `.claude/autoresearch/` exists with these two files; create from the templates below if absent.

- If `$ARGUMENTS` is a path to an existing `program.md`, use it as-is.
- Otherwise treat `$ARGUMENTS` as the GOAL. Draft `program.md`, then **ask me to confirm the single METRIC,
  TARGET file(s), and BUDGET before the first iteration.**

**Refuse to run** if `program.md` has no single, measurable `metric:` (name + how to read it + direction).
"Make it better" is not a metric. Say what's missing and stop.

`program.md` (source of truth — goal + ONE metric + target + budget):
```md
# GOAL
<one sentence: the end state>

metric: <name> — <exact command/observation that reads it> — <lower|higher is better> — target: <value>
target_files: <glob or list — the ONE surface edits are allowed to touch>
budget: <N iterations OR wall-clock, e.g. "20 iters" or "8h"> — per_iter: <e.g. "5 min">
invariants: <constraints that must hold every iteration; leave blank if none>
```

`scoreboard.md` (append-only history; every iteration lands a row):
```md
# scoreboard — <goal>
metric: <name> (<direction>) · best-so-far: <value @ iter N>

| iter | hypothesis (1 sentence) | file | metric | Δ | decision | note |
|------|-------------------------|------|--------|---|----------|------|
```

## 1. Run the loop

If a Seahorse `autoresearch` agent is available, dispatch the loop to it:
`Task autoresearch "run the loop in .claude/autoresearch/program.md until budget or goal"`.
Otherwise run it inline yourself. Each iteration:

1. **Read** `program.md` + `scoreboard.md` (best-so-far is your baseline).
2. **Hypothesize** ONE change — write it as a single sentence.
3. **Edit** ONE file inside `target_files`. Never bundle changes.
4. **Experiment** — run the metric's read command within `per_iter` budget (build / test / measure). Respect
   every `invariant`.
5. **Score + decide**: metric improved past best-so-far AND invariants hold → **keep**, update best-so-far.
   Else → **revert** (`git checkout -- <file>`).
6. **Append** the row to `scoreboard.md` (kept OR reverted, with the reason) so the next iteration has context.

Stop when the metric hits `target`, the budget is exhausted, or the last K iterations show no improvement.
Report best-so-far, the winning diff(s), and the scoreboard tail.

Invariants: one file per iteration · fixed per-iteration budget · a single, never-silently-changed metric ·
honest keep/revert. The discipline is the point.
