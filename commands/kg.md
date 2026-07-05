---
description: Build/refresh & query the project knowledge graph (graphify → OKF).
argument-hint: [query | path A B | rebuild]
---

Project knowledge graph (graphify + OKF). Arg: **$ARGUMENTS**

- No arg or `rebuild`: run `graphify .` → `knowledge/graphify-out/` (graph.html, GRAPH_REPORT.md, graph.json).
- `query <question>`: run `graphify query "<question>"` and answer from the graph, not a raw file sweep.
- `path A B`: run `graphify path "A" "B"` to trace how two entities connect.

Consult the graph BEFORE manual grepping. Keep the graph in OKF (Open Knowledge Format) shape when
exporting/sharing. If graphify isn't installed here: `uv tool install graphifyy && graphify install --platform claude`.
