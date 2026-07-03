# Seahorse Architecture

Seahorse is an **LLM web framework** for Claude Code: a thin orchestration layer that routes each unit of
work to the model that does it best, keeps a project knowledge graph, researches from primary sources,
typesets output, and speaks in as few tokens as the task allows.

## Advisor → Executor flow

```mermaid
flowchart TD
    U([User task]) --> ADV["Advisor · Fable<br/>plan + decompose"]
    ADV -->|chunk map| ROUTE{Route each chunk}
    ROUTE -->|mechanical| LIGHT["Light Builder · Sonnet 5"]
    ROUTE -->|ambiguous / heavy| HEAVY["Heavy Builder · Opus 4.8 1M"]
    ROUTE -->|discovery| RES["Researcher · Opus 4.8 1M<br/>deep-research · arXiv · scrape"]
    ROUTE -->|second opinion| GPT["GPT specialist · codex-plugin-cc"]
    LIGHT --> VER["Verify · adversarial review"]
    HEAVY --> VER
    RES --> VER
    GPT --> VER
    VER -->|fail| ADV
    VER -->|pass| GOAL{{"/goal condition met?"}}
    GOAL -->|no| ADV
    GOAL -->|yes| DONE([Done])
    KG[("Knowledge graph<br/>graphify + OKF")] -.consulted by.-> ADV
    KG -.-> RES
    SEA["Seahorse layer · caveman + ponytail"] -.wraps all agents.-> ROUTE
```

## Per-session lifecycle

```mermaid
sequenceDiagram
    participant S as SessionStart hook
    participant G as Global CLAUDE.md
    participant P as Project CLAUDE.md
    participant A as Advisor (Fable)
    participant X as Executors (Sonnet/Opus/GPT)
    S->>G: load standing contract
    S->>P: project contract exists?
    alt missing (under ~/Work)
        S-->>A: signal bootstrap
        A->>P: generate tailored contract + KG + CI
    end
    Note over P,G: project rules override global
    A->>A: plan + assign models
    A->>X: delegate chunks
    X->>X: build + verify (caveman/ponytail)
    X-->>A: results
    Note over A,X: /goal holds condition across turns
```

## Components

| Layer | Tool | Role |
|-------|------|------|
| Token discipline | **caveman** + **ponytail** (= *seahorse*) | talk less, write less code |
| Advisor | **Fable 5** (→ Opus 4.8 1M) | plan + decompose + assign models |
| Executors | **Sonnet 5** / **Opus 4.8 1M** | light / heavy build + research |
| GPT bridge | **codex-plugin-cc** | second opinion, adversarial review, rescue |
| Research | **/deep-research**, Workflows, alphaXiv MCP | primary-source, cited, verified |
| Knowledge | **graphify** + **OKF** | persistent project knowledge graph |
| Control flow | **/goal**, **/workflows** | hold conditions, deterministic fan-out |
| Outputs | **tectonic** (LaTeX), **Mermaid** | typeset PDFs + diagrams |
| CI/CD | GitHub Actions templates | lint → type → test → build |

## Model-routing table

| Role | Model | Effort | Mechanism |
|------|-------|--------|-----------|
| Advisor / architect | Fable 5 → Opus 4.8 1M | low/med · high/xhigh when hard | `advisor` agent, `/plan` |
| Researcher | Opus 4.8 1M | high | `researcher` agent, `/deep-research` |
| Heavy builder | Opus 4.8 1M | med/high | `builder-heavy` agent |
| Light builder | Sonnet 5 | low/med | `builder-light` agent |
| GPT specialist | GPT/Codex | — | `/codex:*` |
| Goal evaluator | Haiku | — | `/goal` (built-in) |

**Honest limitation:** a running session can't silently change its own model. Routing is realized by
spawning subagents / Workflow stages with explicit `model` overrides, or by the user running `/model`.
1M-context is primarily the main session's tier; subagents run standard Opus/Sonnet/Fable.
