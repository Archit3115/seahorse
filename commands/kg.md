---
description: Build/refresh & query the project knowledge graph (graphify → OKF).
argument-hint: [query | path A B | rebuild | export]
---

Project knowledge graph (graphify + OKF). Arg: **$ARGUMENTS**

- No arg or `rebuild`: run `graphify .` → `graphify-out/` (graph.html, GRAPH_REPORT.md, graph.json). `graphify update .` for a fast AST-only refresh after edits (no LLM cost).
- `query <question>`: run `graphify query "<question>"` and answer from the graph, not a raw file sweep.
- `path A B`: run `graphify path "A" "B"` to trace how two entities connect.
- `export`: run `python3 tools/okf_export.py` → `okf/` (OKF v0.1 Markdown+frontmatter, one file per entity, required `type`; see `examples/okf/` for the shape). Reads `graphify-out/graph.json`.

Consult the graph BEFORE manual grepping. Keep the graph in OKF (Open Knowledge Format) shape when
exporting/sharing. If graphify isn't installed here: `uv tool install graphifyy && graphify install --platform claude`.
Enable auto-consult + auto-rebuild once per machine: `graphify claude install && graphify hook install`.
