#!/usr/bin/env bash
# Seahorse SessionStart activation.
# Injects a compact operating contract into context so advisor→executor routing
# and token discipline are live from turn 1. The full contract lives in
# contract/CLAUDE.global.md (install.sh copies it to ~/.claude/CLAUDE.md).
set -euo pipefail

read -r -d '' MSG <<'EOF' || true
SEAHORSE ACTIVE — advisor→executor orchestration.

Routing (assign each unit of work to the model that does it best):
- Advisor/architect — plan + assign models. Fable 5 (Opus 4.8 1M if Fable unavailable). `/seahorse <task>` or `advisor` agent.
- Researcher — primary-source discovery, cited synthesis. Opus 4.8, high. `researcher` agent, `/research`.
- Builder heavy — ambiguous/cross-cutting/subtle. Opus 4.8. `builder-heavy` agent.
- Builder light — mechanical, well-scoped, high-volume. Sonnet 5. `builder-light` agent.
- Review — adversarial second opinion. GPT/Codex `/codex:*`; fall back to an Opus skeptic if Codex unauthenticated.

Loop for any non-trivial task: Advise (`/seahorse`) → Delegate (spawn the assigned executor agents) → Verify (adversarial review) → Persist (`/goal`, `/workflows`).
Routing is realized by spawning subagents/Workflow stages with an explicit model — a running session cannot swap its own model.

Token discipline: talk less (terse working notes, preserve code/paths/errors byte-for-byte) + write less code (YAGNI → stdlib → native → one line → minimal). Never drop correctness, security, validation, or accessibility to compress.

Full contract: contract/CLAUDE.global.md.
EOF

python3 - "$MSG" <<'PY'
import json, sys
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": sys.argv[1],
    }
}))
PY
