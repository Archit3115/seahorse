# Seahorse Architecture

Seahorse is an **advisor→executor orchestration layer for Claude Code**. Instead of one model doing
everything at one price, Seahorse sends each unit of work to the model that does it best: a cheap
architect *plans*, cheap specialists *build*, an adversarial pass *verifies*, and the whole thing runs
under a strict token diet, over a live project knowledge graph, emitting typeset output.

> One sentence: **Fable plans, Sonnet/Opus build, GPT/Opus reviews — routed per chunk, priced per token.**

---

## What it is intended to do

| Goal | How Seahorse gets there |
|------|--------------------------|
| **Spend less per task** | Route trivial/mechanical chunks to the cheapest capable model (Sonnet) and reserve Opus for the subtle 20%. Don't pay Opus rates to rename a variable. |
| **Plan before building** | A dedicated **advisor** (Fable) decomposes the task and assigns each chunk a model *before* any code is written — planning is separated from doing. |
| **Be right, not just fast** | Every non-trivial result passes an **adversarial verify** (GPT via Codex, or an Opus skeptic when Codex is unauthenticated) before it counts as done. |
| **Remember the project** | A persistent **knowledge graph** (graphify → OKF) lets agents reason over structure instead of re-grepping every session. |
| **Research from sources** | Discovery is routed to Opus with primary-source tools (arXiv via alphaXiv, web scrape), adversarially verified and cited — not recalled from memory. |
| **Hold work across turns** | `/goal` pins a verifiable end-state; `/workflows` fans work out deterministically; `/autoresearch` refines one metric via keep-or-revert loops. |
| **Ship, not just draft** | PDFs are real LaTeX (tectonic), diagrams are Mermaid, and every shipping project gets a CI pipeline. |
| **Talk less, write less code** | The **caveman** (terse prose) + **ponytail** (minimal code) layer wraps every agent, so tokens go to substance. |

The **harness** is the measurement half of the same idea: it runs real coding tasks under each model —
solo vs. orchestrated — captures per-model token usage, and prices those tokens into equivalent dollars,
so the routing claim above is checked against numbers rather than asserted. See
[the benchmark](../benchmarks/README.md).

---

## The big picture

```mermaid
flowchart TD
    U([User task]):::user --> ADV["🧭 Advisor · Fable 5<br/>plan · decompose · route"]:::advisor
    ADV -->|chunk map| ROUTE{Route each chunk}:::route

    ROUTE -->|mechanical / high-volume| LIGHT["🔧 Light Builder · Sonnet 5"]:::light
    ROUTE -->|ambiguous / cross-cutting| HEAVY["🛠️ Heavy Builder · Opus 4.8 1M"]:::heavy
    ROUTE -->|discovery / literature| RES["🔬 Researcher · Opus 4.8 1M<br/>deep-research · arXiv · scrape"]:::research
    ROUTE -->|second opinion| GPT["🧪 GPT specialist · Codex<br/>(Opus skeptic fallback)"]:::gpt

    LIGHT --> VER["🛡️ Verify · adversarial review"]:::verify
    HEAVY --> VER
    RES --> VER
    GPT --> VER

    VER -->|fail| ADV
    VER -->|pass| GOAL{{"🎯 /goal condition met?"}}:::goal
    GOAL -->|no| ADV
    GOAL -->|yes| DONE([✅ Done]):::done

    KG[("🗺️ Knowledge graph<br/>graphify + OKF")]:::kg -.consulted by.-> ADV
    KG -.-> RES
    SEA["🐚 Seahorse layer · caveman + ponytail"]:::sea -.wraps every agent.-> ROUTE

    classDef user fill:#0ea5e9,stroke:#0369a1,color:#fff
    classDef advisor fill:#7c3aed,stroke:#4c1d95,color:#fff
    classDef route fill:#1e293b,stroke:#0f172a,color:#fff
    classDef light fill:#10b981,stroke:#047857,color:#fff
    classDef heavy fill:#f59e0b,stroke:#b45309,color:#111
    classDef research fill:#3b82f6,stroke:#1d4ed8,color:#fff
    classDef gpt fill:#64748b,stroke:#334155,color:#fff
    classDef verify fill:#ef4444,stroke:#991b1b,color:#fff
    classDef goal fill:#eab308,stroke:#a16207,color:#111
    classDef done fill:#22c55e,stroke:#15803d,color:#fff
    classDef kg fill:#14b8a6,stroke:#0f766e,color:#fff
    classDef sea fill:#ec4899,stroke:#9d174e,color:#fff
```

**Colour legend** — 🟣 advisor (plans) · 🟢 light builder (cheap/mechanical) · 🟠 heavy builder (subtle) ·
🔵 researcher · ⚪ GPT specialist · 🔴 verify · 🟡 goal gate · 🩷 token-discipline layer · 🩵 knowledge graph.

---

## Per-session lifecycle

```mermaid
sequenceDiagram
    autonumber
    participant S as 🚀 SessionStart hook
    participant G as 🌐 Global CLAUDE.md
    participant P as 📁 Project CLAUDE.md
    participant A as 🧭 Advisor (Fable)
    participant X as 🔧🛠️ Executors (Sonnet/Opus/GPT)
    S->>G: load standing contract
    S->>P: project contract exists?
    alt missing (under ~/Work)
        S-->>A: signal bootstrap
        A->>P: generate tailored contract + KG + CI
    end
    Note over P,G: project rules override global
    A->>A: plan + assign a model per chunk
    A->>X: delegate chunks
    X->>X: build + self-verify (caveman/ponytail)
    X-->>A: results
    A->>A: adversarial verify → /goal check
    Note over A,X: /goal holds the condition across turns until met
```

---

## How the pieces fit

```mermaid
flowchart LR
    subgraph DISC["🐚 token discipline"]
        CAV["caveman<br/>talk less"]:::sea
        PON["ponytail<br/>write less code"]:::sea
    end
    subgraph BRAIN["🧠 orchestration"]
        ADV2["advisor · Fable"]:::advisor
        EXE["executors<br/>Sonnet · Opus"]:::light
        REV["verify<br/>Codex / Opus skeptic"]:::verify
    end
    subgraph MEM["🗺️ memory & research"]
        GRAPH["graphify → OKF"]:::kg
        RSCH["/deep-research · alphaXiv"]:::research
        AUTO["/autoresearch loop"]:::research
    end
    subgraph SHIP["📦 outputs & flow"]
        TEX["LaTeX · tectonic"]:::out
        MMD["Mermaid diagrams"]:::out
        FLOW["/goal · /workflows"]:::goal
        CI["GitHub Actions CI"]:::out
    end
    DISC --> BRAIN
    MEM --> BRAIN
    BRAIN --> SHIP

    classDef sea fill:#ec4899,stroke:#9d174e,color:#fff
    classDef advisor fill:#7c3aed,stroke:#4c1d95,color:#fff
    classDef light fill:#10b981,stroke:#047857,color:#fff
    classDef verify fill:#ef4444,stroke:#991b1b,color:#fff
    classDef kg fill:#14b8a6,stroke:#0f766e,color:#fff
    classDef research fill:#3b82f6,stroke:#1d4ed8,color:#fff
    classDef goal fill:#eab308,stroke:#a16207,color:#111
    classDef out fill:#8b5cf6,stroke:#5b21b6,color:#fff
```

---

## Components

| Layer | Tool | Role |
|-------|------|------|
| Token discipline | **caveman** + **ponytail** (= *seahorse*) | talk less, write less code |
| Advisor | **Fable 5** (→ Opus 4.8 1M) | plan + decompose + assign models |
| Executors | **Sonnet 5** / **Opus 4.8 1M** | light / heavy build + research |
| GPT bridge | **codex-plugin-cc** | second opinion, adversarial review, rescue |
| Research | **/deep-research**, Workflows, alphaXiv MCP | primary-source, cited, verified |
| Knowledge | **graphify** + **OKF** | persistent project knowledge graph |
| Control flow | **/goal**, **/workflows**, **/autoresearch** | hold conditions, fan-out, refine-to-metric |
| Outputs | **tectonic** (LaTeX), **Mermaid** | typeset PDFs + diagrams |
| CI/CD | GitHub Actions templates | lint → type → test → build |

## Model-routing table

| Role | Model | Effort | Mechanism |
|------|-------|--------|-----------|
| Advisor / architect | Fable 5 → Opus 4.8 1M | low/med · high/xhigh when hard | `advisor` agent, `/seahorse` |
| Researcher | Opus 4.8 1M | high | `researcher` agent, `/deep-research` |
| Heavy builder | Opus 4.8 1M | med/high | `builder-heavy` agent |
| Light builder | Sonnet 5 | low/med | `builder-light` agent |
| GPT specialist | GPT/Codex | — | `/codex:*` |
| Goal evaluator | Haiku | — | `/goal` (built-in) |

**Honest limitation:** a running session can't silently change its own model. Routing is realized by
spawning subagents / Workflow stages with explicit `model` overrides, or by the user running `/model`.
1M-context is primarily the main session's tier; subagents run standard Opus/Sonnet/Fable.

---

## The benchmark harness — measuring the claim

Seahorse ships its own harness so the "route to save money" claim is *measured*, not asserted. Two tracks:

```mermaid
flowchart LR
    T([coding task]):::user --> SOLO["solo<br/>fable · opus · sonnet"]:::light
    T --> SEA["seahorse<br/>advisor → builders"]:::advisor
    SOLO --> J["claude -p --output-format json<br/>→ modelUsage (per-model tokens)"]:::route
    SEA --> J
    J --> PRICE["pricing.py<br/>tokens × public rate card"]:::out
    PRICE --> COST["equivalent USD<br/>cross-checked vs billed"]:::done

    classDef user fill:#0ea5e9,stroke:#0369a1,color:#fff
    classDef light fill:#10b981,stroke:#047857,color:#fff
    classDef advisor fill:#7c3aed,stroke:#4c1d95,color:#fff
    classDef route fill:#1e293b,stroke:#0f172a,color:#fff
    classDef out fill:#8b5cf6,stroke:#5b21b6,color:#fff
    classDef done fill:#22c55e,stroke:#15803d,color:#fff
```

- **Token-priced track** ([`run_local.py`](../benchmarks/run_local.py)) — no Docker. Runs self-contained
  coding tasks, reads the CLI's `modelUsage` (which rolls up *subagent* tokens, so the seahorse advisor's
  Sonnet/Opus builders are counted), and prices tokens via a published rate card. **Cost is converted from
  tokens**, then cross-checked against the CLI's own billed figure. This is the "no real-money meter" path.
- **SWE-bench track** ([`run.py`](../benchmarks/run.py)) — the heavyweight accuracy path (Docker + official
  swebench eval) for resolved-rate on real GitHub issues.

Both runs headless. Because a headless agent can't answer permission prompts, the local runner uses a
**guarded** mode: `--dangerously-skip-permissions` for auto-approval, but with a hard denylist
(`rm`, `mv`, `curl`, `wget`, `git`, `sudo`, `pip`, `npm`, …) that wins over skip — so file writes and
`python3` run freely while destructive / network / privilege commands are blocked, verified by an agent
that is told to `rm -rf .` and is denied.

See [`benchmarks/README.md`](../benchmarks/README.md) for methodology and
[`benchmarks/results/`](../benchmarks/results/) for the measured numbers.
