<!--
  Seahorse-condition prompt template.

  FAIRNESS CONTRACT (see README "Threats to validity"):
  The {{TASK}} placeholder is filled with the *byte-identical* task string the three
  solo conditions receive (built by run.py::build_task_prompt). The only difference
  between the Seahorse condition and a solo condition is the orchestration wrapper
  below — NOT the task, NOT extra hints, NOT hand-holding. Do not add task-specific
  guidance here; that would make the comparison dishonest.

  run.py substitutes {{TASK}} and invokes:
    claude -p "<this file, filled>" --model claude-fable-5 \
           --plugin-dir /Users/sentry/Work/seahorse \
           --output-format json --dangerously-skip-permissions
  The Fable entry session is the ADVISOR; it delegates chunks to builder-light
  (Sonnet) / builder-heavy (Opus) per the routing table, exactly as in normal use.
-->

Run the full Seahorse advisor to executor loop on the task below, end to end, autonomously.

You are the **advisor**. Do not wait for approval (this is a headless run):

1. Inspect just enough of the repo to plan accurately.
2. Decompose the task into small, independently verifiable chunks. For each chunk pick the
   executor per the Seahorse routing table — Sonnet (`builder-light`) for mechanical/well-scoped
   edits, Opus (`builder-heavy`) for ambiguous/cross-cutting/subtle work.
3. Delegate each chunk to its executor and have it implement + self-verify.
4. Integrate the chunks, run whatever check is available, and leave the fix applied to the
   working tree.

Work under ponytail (minimal code) and caveman (terse) discipline. The goal condition is: the
issue below is resolved with the smallest correct change, saved to the working tree.

--- TASK ---

{{TASK}}
