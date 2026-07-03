# 🐚 Seahorse — an LLM web framework for Claude Code

Seahorse turns Claude Code into an **advisor→executor orchestration layer**: one architect model plans,
cheaper specialist models build, every unit of work is routed to the model that does it best — under a
strict token diet, over a live project knowledge graph, with typeset output.

> **seahorse** = the token-reduction layer (caveman + ponytail).
> **Seahorse** (capital S) = the whole framework this repo installs.

## What it wires together

| Concern | Tooling |
|---------|---------|
| Talk less / write less code | [caveman](https://github.com/JuliusBrussee/caveman) + [ponytail](https://github.com/DietrichGebert/ponytail) |
| Plan → delegate → verify | **Fable** advisor → **Sonnet/Opus** executors → **GPT** ([codex-plugin-cc](https://github.com/openai/codex-plugin-cc)) review |
| Research | `/deep-research`, dynamic Workflows, arXiv (alphaXiv MCP), ResearchGate, web scraping |
| Knowledge graph | [graphify](https://github.com/safishamsi/graphify) → [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) |
| Hold work across turns | `/goal`, `/workflows` |
| Outputs | PDFs = **LaTeX/tectonic**, diagrams = **Mermaid** |
| CI/CD | GitHub Actions templates (lint → type → test → build) |

See [`docs/architecture.md`](docs/architecture.md) for the flow + sequence diagrams and the full
model-routing table.

## Install

```bash
./install.sh          # installs global CLAUDE.md, hook, agents, commands into ~/.claude
```

Prerequisites the script checks/installs where it can: `tectonic` (LaTeX), `uv` + `graphifyy`
(knowledge graph), the Claude Code plugins (`caveman`, `ponytail`, `codex`), and the `codex` CLI.
GPT delegation additionally needs `codex login` (your ChatGPT/OpenAI auth) — run it once, manually.

## Layout

```
llm-web-framework/
├── claude/
│   ├── CLAUDE.global.md            # → ~/.claude/CLAUDE.md   (standing contract)
│   ├── CLAUDE.project.template.md  # per-project contract template
│   ├── settings.snippet.json       # SessionStart hook to merge into settings.json
│   ├── hooks/seahorse-bootstrap.sh # signals project bootstrap (safe, gated to ~/Work)
│   ├── agents/                     # advisor · researcher · builder-heavy · builder-light
│   └── commands/                   # /plan · /research · /kg · /pdf
├── docs/architecture.md            # Mermaid diagrams + routing table
└── templates/ci/                   # node.yml · python.yml
```

## How a task flows

1. `/plan <task>` → **advisor** (Fable) returns a chunk→model table + a `/goal` condition.
2. You approve → each chunk goes to its executor (`builder-light`=Sonnet, `builder-heavy`=Opus,
   `/codex:*`=GPT), verified adversarially.
3. `/goal` holds the end-state across turns; `/workflows` runs deterministic fan-outs.
4. Research → `/research`/`/deep-research` (Opus, primary sources, cited).
5. Docs → `/pdf` (LaTeX/tectonic); diagrams → Mermaid; `/kg` keeps the knowledge graph fresh.

A project's own `.claude/CLAUDE.md` always overrides Seahorse. New projects under `~/Work` get a
tailored project contract scaffolded automatically on first session.

## License

MIT — see [LICENSE](LICENSE).
