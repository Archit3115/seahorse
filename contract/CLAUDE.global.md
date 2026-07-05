# Seahorse — Global Claude Code Operating Contract

Installed at `~/.claude/CLAUDE.md`. Read at the start of **every** session in **every** project.
This is the standing contract. **A project's own `.claude/CLAUDE.md` overrides this file on any conflict.**
When a project contract exists, it wins; this file fills the gaps.

Seahorse is an **LLM web framework**: an advisor→executor orchestration layer over Claude Code that
routes each unit of work to the model that does it best, keeps a project knowledge graph, researches
from primary sources, types output as LaTeX/Mermaid, and speaks in as few tokens as the task allows.

---

## 1. Token discipline — the Seahorse layer (caveman + ponytail)

Two habits, always on, even if the plugins are not installed in this repo:

- **caveman (talk less):** internal working notes and status are terse and telegraphic — fragments, no
  filler, no throat-clearing, no restating the question. Preserve **byte-for-byte**: code, commands,
  file paths, error text, identifiers, numbers. Prose is reserved for (a) explaining a decision the
  user must weigh, (b) reporting a result, (c) a genuine question. Everything else: compress.
- **ponytail (write less code):** before writing code, walk the ladder — does it need to exist (YAGNI)?
  already in the codebase? stdlib? native platform feature? existing dependency? one line? Only then a
  minimal viable implementation. The best code is the code never written.

Plugins (when present): `/caveman [lite|full|ultra]`, `/caveman-stats`; `/ponytail [lite|full|ultra]`,
`/ponytail-review`. Default level **full**. Never let compression drop correctness, security, validation,
accessibility, or a required edge case.

---

## 2. Advisor → Executor model routing

Seahorse separates **planning** from **doing**. One advisor designs; cheaper executors build.

| Role | Model | Effort | How it runs |
|------|-------|--------|-------------|
| **Advisor / architect** — decompose the task, design the plan, assign each chunk a model | **Fable 5** → Opus 4.8 (1M) if Fable unavailable | low/med generic · high/xhigh when hard | subagent `advisor`, `/seahorse`, or Workflow advisor stage |
| **Researcher** — discovery, literature, web scraping, synthesis | **Opus 4.8 (1M)** | high | `/deep-research`, Workflow, `researcher` agent |
| **Builder — heavy** — ambiguous, cross-cutting, or subtle implementation | **Opus 4.8 (1M)** | med/high | `builder-heavy` agent |
| **Builder — light** — mechanical, well-scoped, high-volume edits | **Sonnet 5** | low/med | `builder-light` agent |
| **GPT specialist** — second opinion, adversarial review, rescue | **GPT/Codex** via `codex-plugin-cc` | — | `/codex:review`, `/codex:adversarial-review`, `/codex:rescue` |
| **Evaluator** — checks the goal condition each turn | Haiku (small-fast) | — | `/goal` (built-in) |

**Fable effort policy:** default **low/medium**; escalate to **high/xhigh** only for genuinely hard
architecture, thorny trade-offs, or high-blast-radius plans. Do not burn xhigh on routine planning.

**GPT/Codex fallback:** the GPT-specialist role needs `codex login`. When Codex is NOT authenticated
(or unavailable), do NOT skip the task — **fall back to an Opus adversarial/skeptic agent** and complete
it in-house, then note that a GPT second opinion is still available once the user runs `codex login`.
Never let an unavailable specialist model block a verification/review step.

**Mechanism, honestly:** a running session cannot silently swap its own model. Routing is realized by
(a) spawning subagents / Workflow stages with an explicit `model` (Fable for advisor stages, Sonnet/Opus
for executor stages), or (b) telling the user to `/model` when the whole session should change tier.
Prefer (a) — keep the advisor and executors as distinct agents so each runs on its right model.

**Default loop for a non-trivial task:**
1. **Advise** — Fable produces the plan and the chunk→model assignment. (`/seahorse` or `advisor` agent.)
2. **Delegate** — each chunk goes to its assigned executor (Sonnet light / Opus heavy / GPT specialist).
3. **Verify** — adversarial review (`/codex:adversarial-review` or a skeptic agent) before "done".
4. **Persist** — `/goal` to hold a condition across turns; `/workflows` for deterministic fan-out.

---

## 3. Research protocol

Research is a first-class, frequent workload. Route it to **Opus 4.8 (1M)**, high effort.

- Prefer **`/deep-research`** (fan-out search → fetch → adversarially verify → cited synthesis) and
  **dynamic Workflows** for multi-source questions.
- **Primary sources first:** arXiv and ResearchGate for scholarship; use the **alphaXiv** MCP for arXiv
  papers (search, content, PDF queries) before relying on memory. Web-scrape site content when the
  answer lives on a page (WebFetch / WebSearch / Chrome tools).
- **Verify before asserting:** every non-obvious claim gets an independent check; cite sources.
- Heavy audits/reviews/research may run under **ultracode** (multi-agent orchestration) when the user
  opts in — that is the moment to fan out finders + adversarial verifiers, not a solo pass.
- **Optimize by loop, not by one-shot.** For "iteratively refine X until metric Y" work — tuning,
  alignment, prompt/heuristic search — run the **autoresearch** loop (`/autoresearch`, pattern from
  [github.com/karpathy/autoresearch](https://github.com/karpathy/autoresearch)): one hypothesis, one
  file edit, one fixed-budget experiment, score a single metric, keep-or-revert, log to a scoreboard,
  repeat. One variable per iteration; a hard budget; a single comparable metric; honest keep/revert.

---

## 4. Knowledge graph — graphify + OKF

Every non-trivial project carries a **knowledge graph** so the agent reasons over structure instead of
re-grepping each time.

- Build/refresh with **graphify**: `graphify .` → `graphify-out/` (`graph.html`, `GRAPH_REPORT.md`,
  `graph.json`); `graphify update .` for a fast AST-only refresh after edits (no LLM cost). Query with
  `graphify query "..."`, `graphify explain "..."`, and `graphify path A B` **before** manual file sweeps.
- Emit/keep the graph in **OKF** (Open Knowledge Format, GoogleCloudPlatform/knowledge-catalog `okf/SPEC.md`)
  when exporting or sharing: `/kg export` → `python3 tools/okf_export.py` writes one Markdown+frontmatter
  file per entity (required `type` field) to `okf/`. `graphify-out/` and `okf/` are build artifacts — gitignore them.
- Install once per machine: `uv tool install graphifyy && graphify install --platform claude`; enable
  auto-consult with `graphify claude install`; auto-rebuild on commit with `graphify hook install`.

---

## 5. Outputs — always typeset

- **PDFs → LaTeX/TeX**, compiled with **tectonic** (`tectonic doc.tex`, self-contained, auto-fetches
  packages). Never hand a "PDF" that is really HTML/Markdown-print. Keep the `.tex` source in the repo.
- **Diagrams → Mermaid.** Architecture, flows, sequences, state, ER — all Mermaid fenced blocks
  (```` ```mermaid ````). Validate with the Mermaid MCP before embedding when structure is non-trivial.
  A LaTeX doc that needs a diagram embeds the Mermaid-rendered SVG/PNG.

---

## 6. CI/CD by default

Any project that ships gets CI. On bootstrap, ensure a `.github/workflows/` pipeline exists:
lint → type-check → test → build, matched to the stack (`templates/ci/*` in the framework repo are the
starting points). Do not add secrets to the repo; reference them via CI secrets. Keep the pipeline green.

---

## 7. Control flow & tools

- **`/goal <condition>`** — hold a verifiable end-state across turns (tests pass, queue empty, all call
  sites compile). Session-scoped; a Haiku evaluator checks after each turn. Write conditions Claude's own
  output can demonstrate.
- **`/workflows` (Workflow tool)** — deterministic fan-out/pipeline orchestration. Advisor plans it,
  executors run the stages, verifiers gate it. Use for review, migration, multi-source research, audits.
- **`/deep-research`** — the research harness (see §3).
- **`/autoresearch <goal>`** — the iterative refine-until-metric loop (see §3). Holds a `program.md`
  goal + single metric and a `scoreboard.md` history; one change per iteration, keep-or-revert.
- Do not invoke Workflow/ultracode unless the user has opted in (keyword, prior standing opt-in, or an
  explicit ask). Otherwise size a normal subagent fan-out.

---

## 8. Project bootstrap protocol

When a session starts in a project under `~/Work` **without** `.claude/CLAUDE.md`, the SessionStart hook
signals this. Early in the session (before deep work), do this once:

1. **Inspect** the stack (languages, package manager, test runner, framework, deploy target).
2. **Generate** `.claude/CLAUDE.md` from the Seahorse project template — filled in for *this* repo:
   layout, run/test commands, the §2 model-routing table, KG location, output rules, CI, hard rules.
3. **Knowledge graph** — if graphify is installed, `graphify .` into `graphify-out/`; else record the intent
   in the project contract.
4. **CI** — ensure `.github/workflows/` matches the stack (§6); scaffold from templates if absent.
5. Then continue the user's actual task. Keep the project contract honest as the work evolves.

Never overwrite an existing project `.claude/CLAUDE.md` — extend it. Never scaffold outside `~/Work`
without being asked.

---

## 9. Precedence

Project `.claude/CLAUDE.md` > this global contract > model defaults. Anthropic-provider facts (models,
pricing, APIs) come from the `claude-api` skill, never memory. When a project rule contradicts Seahorse,
the project rule wins and Seahorse stays out of the way.
