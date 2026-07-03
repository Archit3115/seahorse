---
description: Seahorse advisor plans a task — Fable decomposes it and assigns each chunk a model.
argument-hint: <task to plan>
---

Run the Seahorse **advisor** loop for: **$ARGUMENTS**

1. Spawn the `advisor` agent (Fable; Opus 4.8 1M if Fable unavailable) to produce the plan and the
   chunk→model assignment table.
2. Show me the table (`# | chunk | model | effort | verification`) and the proposed `/goal` condition.
3. Wait for my go-ahead, then delegate each chunk to its assigned executor (`builder-light` = Sonnet,
   `builder-heavy` = Opus, `/codex:*` = GPT) and verify per the table.

Keep it terse. Do not start building before I approve the plan.
