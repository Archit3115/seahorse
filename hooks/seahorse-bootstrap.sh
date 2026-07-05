#!/usr/bin/env bash
# Seahorse SessionStart bootstrap.
# Signals (never writes) when a project under ~/Work lacks a Seahorse project contract.
# Non-destructive by design: the model does the scaffolding per ~/.claude/CLAUDE.md §8.
set -euo pipefail

root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# Only act inside the user's work tree. Stay silent everywhere else.
case "$root" in
  "$HOME/Work"/*|"$HOME/Work") ;;
  *) exit 0 ;;
esac

# Already bootstrapped → silent.
[ -f "$root/.claude/CLAUDE.md" ] && exit 0

read -r -d '' MSG <<EOF || true
SEAHORSE BOOTSTRAP — no project contract at ${root}/.claude/CLAUDE.md.
Per ~/.claude/CLAUDE.md §8 (Project Bootstrap), do this ONCE early, then continue the task:
1) inspect the stack; 2) generate a tailored .claude/CLAUDE.md from the Seahorse project template;
3) build the knowledge graph (graphify . -> knowledge/); 4) ensure .github/workflows CI for the stack.
Do not overwrite an existing contract; do not scaffold outside ~/Work.
EOF

# Emit as SessionStart additionalContext (JSON), safely escaped.
python3 - "$MSG" <<'PY'
import json, sys
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": sys.argv[1],
    }
}))
PY
