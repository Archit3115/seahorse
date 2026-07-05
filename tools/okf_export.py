#!/usr/bin/env python3
"""Export a graphify graph.json to OKF v0.1 (Markdown + YAML frontmatter).

Spec: github.com/GoogleCloudPlatform/knowledge-catalog okf/SPEC.md v0.1.
OKF v0.1 only hard-requires a `type` field per entity; frontmatter is YAML.
JSON is valid YAML, so we emit frontmatter as JSON — no PyYAML dependency.

Usage: python3 tools/okf_export.py [graph.json] [out_dir]
Defaults: graphify-out/graph.json -> okf/
"""
import json
import sys
from pathlib import Path

DEFAULT_GRAPH = "graphify-out/graph.json"
DEFAULT_OUT = "okf"


def node_type(node: dict) -> str:
    # ponytail: kind/category fallback chain, "entity" if nothing usable
    return (node.get("metadata") or {}).get("kind") or node.get("file_type") or "entity"


def export(graph_path: str = DEFAULT_GRAPH, out_dir: str = DEFAULT_OUT) -> int:
    graph = json.loads(Path(graph_path).read_text())
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    outgoing: dict[str, list[dict]] = {}
    for e in edges:
        outgoing.setdefault(e.get("source"), []).append(
            {"relation": e.get("relation"), "target": e.get("target"), "confidence": e.get("confidence")}
        )

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    count = 0
    for node in nodes:
        node_id = node.get("id") or f"node_{count}"
        frontmatter = {
            "type": node_type(node),
            "id": node_id,
            "name": node.get("label", node_id),
            "source_file": node.get("source_file"),
            "relations": outgoing.get(node_id, []),
        }
        body = node.get("label", "") or ""
        text = f"---\n{json.dumps(frontmatter, indent=2)}\n---\n\n{body}\n"
        (out / f"{node_id}.md").write_text(text)
        count += 1
    return count


def _parse_frontmatter(text: str) -> dict:
    assert text.startswith("---\n"), "missing frontmatter fence"
    end = text.index("\n---\n", 4)
    return json.loads(text[4:end])


def demo():
    """ponytail: the one runnable check — no test framework."""
    import tempfile

    fake_graph = {
        "nodes": [
            {"id": "a", "label": "A", "file_type": "code", "source_file": "a.py"},
            {"id": "b", "label": "B", "metadata": {"kind": "function"}},
            {"id": "c", "label": "C"},
        ],
        "edges": [{"source": "a", "target": "b", "relation": "calls", "confidence": "EXTRACTED"}],
    }
    with tempfile.TemporaryDirectory() as tmp:
        graph_path = Path(tmp) / "graph.json"
        graph_path.write_text(json.dumps(fake_graph))
        out_dir = Path(tmp) / "okf"
        n = export(str(graph_path), str(out_dir))
        assert n == 3
        files = list(out_dir.glob("*.md"))
        assert len(files) == 3
        for f in files:
            fm = _parse_frontmatter(f.read_text())
            assert fm.get("type"), f"{f} missing non-empty type"
        a_fm = _parse_frontmatter((out_dir / "a.md").read_text())
        assert a_fm["type"] == "code"
        assert a_fm["relations"] == [{"relation": "calls", "target": "b", "confidence": "EXTRACTED"}]
        c_fm = _parse_frontmatter((out_dir / "c.md").read_text())
        assert c_fm["type"] == "entity"  # fallback
    print("demo: ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo()
    else:
        graph_arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_GRAPH
        out_arg = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT
        demo()
        n = export(graph_arg, out_arg)
        print(f"wrote {n} OKF entities -> {out_arg}/")
