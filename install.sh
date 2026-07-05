#!/usr/bin/env bash
# Seahorse installer — wires this framework into ~/.claude.
# Idempotent and non-destructive: merges, never clobbers your existing config.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
export PATH="$HOME/.local/bin:$PATH"

say() { printf '\033[1;36m›\033[0m %s\n' "$*"; }

mkdir -p "$CLAUDE_DIR/hooks" "$CLAUDE_DIR/agents" "$CLAUDE_DIR/commands" "$CLAUDE_DIR/skills" "$CLAUDE_DIR/tools"

# --- Global CLAUDE.md (merge graphify's trigger line if present) --------------
say "Installing global CLAUDE.md"
GLOBAL="$CLAUDE_DIR/CLAUDE.md"
if [ -f "$GLOBAL" ] && grep -q "Seahorse — Global Claude Code Operating Contract" "$GLOBAL"; then
  cp "$REPO/contract/CLAUDE.global.md" "$GLOBAL"          # already ours → refresh
else
  # preserve any pre-existing lines (e.g. graphify) by appending them below ours
  { cat "$REPO/contract/CLAUDE.global.md";
    if [ -f "$GLOBAL" ]; then printf '\n---\n<!-- preserved from prior CLAUDE.md -->\n'; cat "$GLOBAL"; fi
  } > "$GLOBAL.seahorse.tmp" && mv "$GLOBAL.seahorse.tmp" "$GLOBAL"
fi

# --- Agents, commands, hook ---------------------------------------------------
# Commands include seahorse.md -> gives you the bare /seahorse command (the plugin
# install would namespace it as /seahorse:seahorse; the standalone copy keeps /seahorse).
say "Installing agents, commands, hook"
cp "$REPO"/agents/*.md   "$CLAUDE_DIR/agents/"
cp "$REPO"/commands/*.md "$CLAUDE_DIR/commands/"
cp "$REPO/hooks/seahorse-bootstrap.sh" "$CLAUDE_DIR/hooks/"
chmod +x "$CLAUDE_DIR/hooks/seahorse-bootstrap.sh"

# Skills (autoresearch) + tools (OKF exporter). /kg export calls the installed exporter.
say "Installing skills + tools"
cp -R "$REPO"/skills/. "$CLAUDE_DIR/skills/" 2>/dev/null || true   # /. copies contents, no re-run nesting
cp "$REPO"/tools/*.py  "$CLAUDE_DIR/tools/"  2>/dev/null || true
# point every installed doc's /kg export at the cwd-independent installed exporter path
for f in "$CLAUDE_DIR/commands/kg.md" "$GLOBAL"; do
  [ -f "$f" ] && sed -i.bak 's#python3 tools/okf_export.py#python3 ~/.claude/tools/okf_export.py#g' "$f" && rm -f "$f.bak"
done

# --- Merge SessionStart hook into settings.json -------------------------------
say "Merging SessionStart hook into settings.json"
python3 - "$CLAUDE_DIR/settings.json" <<'PY'
import json, os, sys
p = sys.argv[1]
s = {}
if os.path.exists(p):
    with open(p) as f:
        s = json.load(f)
hook = {"type": "command", "command": "bash ~/.claude/hooks/seahorse-bootstrap.sh"}
hooks = s.setdefault("hooks", {}).setdefault("SessionStart", [])
# add our matcher block only if not already present
if not any(h.get("command") == hook["command"]
           for blk in hooks for h in blk.get("hooks", [])):
    hooks.append({"matcher": "startup|resume|clear", "hooks": [hook]})
with open(p, "w") as f:
    json.dump(s, f, indent=2)
print("  settings.json updated")
PY

# --- Optional tooling (best-effort) -------------------------------------------
say "Checking tooling"
command -v tectonic >/dev/null || say "  (missing) tectonic — install for LaTeX PDFs"
command -v graphify >/dev/null || say "  (missing) graphify — 'uv tool install graphifyy && graphify install --platform claude'"
command -v codex    >/dev/null || say "  (missing) codex CLI — 'npm i -g @openai/codex' then 'codex login'"

say "Done. Restart Claude Code. /seahorse is now available."
say "Bundled token-discipline plugins (caveman + ponytail) — install once:"
echo "     claude plugin marketplace add Archit3115/seahorse"
echo "     claude plugin install caveman@seahorse ponytail@seahorse"
