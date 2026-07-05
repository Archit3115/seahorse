#!/usr/bin/env python3
"""Seahorse SWE-bench harness — aggregator.

Joins the per-run generation metrics (results/<condition>/<instance>.json, written by
run.py) with the official swebench evaluation report (results/<condition>/eval.json,
produced by `python -m swebench.harness.run_evaluation`) and emits:

  - stdout : a markdown table, per condition x stratum (short/long/all)
  - results/summary.csv
  - results/summary.md
  - results/summary.mmd : a Mermaid xychart-beta (cost + accuracy) from REAL data only

Runs cleanly against an empty results/ dir (prints "no data").
STDLIB ONLY — no deps.

swebench report shape (v3): a JSON dict with a "resolved_ids" list (and/or per-instance
"resolved" flags). We read resolved_ids; if eval.json is absent, accuracy = None ("run eval").
"""
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
CONDITIONS = ["fable", "opus", "sonnet", "seahorse"]
STRATA = ["short", "long", "all"]
RESERVED = {"eval.json", "report.json", "summary.json"}  # not per-instance run files


def load_runs(condition):
    cdir = RESULTS / condition
    if not cdir.exists():
        return []
    out = []
    for f in sorted(cdir.glob("*.json")):
        if f.name in RESERVED:
            continue
        try:
            out.append(json.loads(f.read_text()))
        except json.JSONDecodeError:
            continue
    return out


def load_resolved(condition):
    """-> set of resolved instance_ids from the swebench eval report, or None if absent."""
    for name in ("eval.json", "report.json"):
        f = RESULTS / condition / name
        if f.exists():
            try:
                rep = json.loads(f.read_text())
            except json.JSONDecodeError:
                continue
            if isinstance(rep, dict) and "resolved_ids" in rep:
                return set(rep["resolved_ids"])
            # swebench per-instance form: {iid: {"resolved": bool}}
            if isinstance(rep, dict):
                return {k for k, v in rep.items()
                        if isinstance(v, dict) and v.get("resolved")}
    return None


def mean(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return statistics.mean(xs) if xs else None


def fmt(x, kind=""):
    if x is None:
        return "-"
    if kind == "usd":
        return f"${x:.4f}"
    if kind == "pct":
        return f"{x*100:.1f}%"
    if kind == "int":
        return f"{int(round(x)):,}"
    if kind == "s":
        return f"{x/1000:.1f}s"
    return f"{x:.2f}"


def aggregate():
    """-> rows: list of dict(condition, stratum, n, cost, in_tok, out_tok, cache,
                             wall_ms, resolved_rate)."""
    rows = []
    for c in CONDITIONS:
        runs = load_runs(c)
        resolved = load_resolved(c)
        for stratum in STRATA:
            sel = runs if stratum == "all" else [r for r in runs if r.get("stratum") == stratum]
            if not sel:
                rows.append(dict(condition=c, stratum=stratum, n=0, cost=None,
                                 in_tok=None, out_tok=None, cache=None,
                                 wall=None, acc=None))
                continue
            if resolved is None:
                acc = None
            else:
                acc = sum(1 for r in sel if r["instance_id"] in resolved) / len(sel)
            rows.append(dict(
                condition=c, stratum=stratum, n=len(sel),
                cost=mean([r.get("total_cost_usd") for r in sel]),
                in_tok=mean([r.get("input_tokens") for r in sel]),
                out_tok=mean([r.get("output_tokens") for r in sel]),
                cache=mean([r.get("cache_read_input_tokens") for r in sel]),
                wall=mean([r.get("wall_ms") for r in sel]),
                acc=acc,
            ))
    return rows


def to_markdown(rows):
    hdr = ("| condition | stratum | n | accuracy | mean cost | mean in-tok | "
           "mean out-tok | mean cache-read | mean wall |")
    sep = "|" + "|".join(["---"] * 9) + "|"
    lines = [hdr, sep]
    for r in rows:
        # seahorse token columns are the ADVISOR loop only — nested builder subagent
        # contexts are not in the top-level `usage`. Cost (total_cost_usd) IS the full
        # rollup, so compare conditions on cost, not tokens, for the seahorse row.
        star = "*" if r["condition"] == "seahorse" else ""
        lines.append("| {condition} | {stratum} | {n} | {acc} | {cost} | {intok}{star} | "
                     "{outtok}{star} | {cache} | {wall} |".format(
            condition=r["condition"], stratum=r["stratum"], n=r["n"],
            acc=fmt(r["acc"], "pct"), cost=fmt(r["cost"], "usd"),
            intok=fmt(r["in_tok"], "int"), outtok=fmt(r["out_tok"], "int"),
            cache=fmt(r["cache"], "int"), wall=fmt(r["wall"], "s"), star=star))
    lines.append("")
    lines.append("\\* seahorse token counts are advisor-loop only (nested builder "
                 "subagent tokens are not in top-level `usage`); compare cost, not tokens. "
                 "`total_cost_usd` is the full rollup and is accurate for all conditions.")
    return "\n".join(lines)


def to_csv(rows, path):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "stratum", "n", "accuracy", "mean_cost_usd",
                    "mean_input_tokens", "mean_output_tokens",
                    "mean_cache_read_tokens", "mean_wall_ms"])
        for r in rows:
            w.writerow([r["condition"], r["stratum"], r["n"],
                        "" if r["acc"] is None else round(r["acc"], 4),
                        "" if r["cost"] is None else round(r["cost"], 6),
                        "" if r["in_tok"] is None else round(r["in_tok"]),
                        "" if r["out_tok"] is None else round(r["out_tok"]),
                        "" if r["cache"] is None else round(r["cache"]),
                        "" if r["wall"] is None else round(r["wall"])])


def to_mermaid(rows):
    """xychart-beta of mean cost (USD) over the 'all' stratum — real data only."""
    allrows = [r for r in rows if r["stratum"] == "all" and r["cost"] is not None]
    if not allrows:
        return None
    labels = ", ".join(f'"{r["condition"]}"' for r in allrows)
    costs = ", ".join(f'{r["cost"]:.4f}' for r in allrows)
    top = max(r["cost"] for r in allrows) * 1.2 or 1.0
    return ("```mermaid\n"
            "xychart-beta\n"
            '    title "Mean cost per SWE-bench instance (USD, lower is better)"\n'
            f"    x-axis [{labels}]\n"
            f'    y-axis "USD" 0 --> {top:.4f}\n'
            f"    bar [{costs}]\n"
            "```\n")


def main():
    if not RESULTS.exists() or not any(RESULTS.glob("*/*.json")):
        print("no data in results/ yet — run.py first, then swebench eval. "
              "Nothing to aggregate.")
        return
    rows = aggregate()
    md = to_markdown(rows)
    print(md)
    (RESULTS / "summary.md").write_text(md + "\n")
    to_csv(rows, RESULTS / "summary.csv")
    mmd = to_mermaid(rows)
    if mmd:
        (RESULTS / "summary.mmd").write_text(mmd)
        print("\n" + mmd)
    print("\nwrote: results/summary.md, results/summary.csv"
          + (", results/summary.mmd" if mmd else ""))
    if any(r["acc"] is None for r in rows if r["n"]):
        print("\nNOTE: accuracy is '-' where results/<condition>/eval.json is missing. "
              "Run the swebench docker eval (see README) to populate it.")


if __name__ == "__main__":
    main()
