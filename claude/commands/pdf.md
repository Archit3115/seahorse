---
description: Produce a PDF the Seahorse way — LaTeX source compiled with tectonic. Never HTML-print.
argument-hint: <document topic or .tex path>
---

Build a PDF for: **$ARGUMENTS**

- Author/keep **LaTeX** source (`.tex`) in the repo — never pass off HTML/Markdown-print as a PDF.
- Any diagram inside it is **Mermaid**-rendered (validate via the Mermaid MCP, embed the SVG/PNG).
- Compile with **tectonic**: `tectonic <file>.tex` (self-contained, auto-fetches packages).
- Report the output path and confirm it compiled cleanly (show tectonic's exit result).
