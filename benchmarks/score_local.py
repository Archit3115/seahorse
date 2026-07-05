#!/usr/bin/env python3
"""Aggregate the local token-cost benchmark into a priced table + Mermaid.

Reads results/local/<condition>/<task>.json (written by run_local.py) and emits,
per condition x stratum (short/long/all):
  n, check-pass rate, mean priced USD (rate card), mean billed USD (CLI),
  mean total tokens, mean wall seconds, and the models each condition actually
  used (proves seahorse's subagent rollup shows up in modelUsage).

  - stdout + results/local/summary.md   (markdown table)
  - results/local/summary.csv
  - results/local/summary.mmd           (colorful xychart: priced cost by condition)

STDLIB ONLY. Runs cleanly on an empty results dir.
"""
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

import pricing

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results" / "local"
CONDITIONS = ["fable", "opus", "sonnet", "seahorse"]
STRATA = ["short", "long", "all"]


def reprice(rec):
    """Recompute priced_usd from stored per-model tokens with the CURRENT rate
    card, so a rate-card fix corrects old runs without re-running them. Falls
    back to the value stored at run time if per_model tokens are absent."""
    pm = rec.get("per_model")
    if not pm:
        return rec.get("priced_usd")
    total = 0.0
    for mid, u in pm.items():
        total += pricing.price(mid, u.get("input", 0), u.get("output", 0),
                               u.get("cache_read", 0), u.get("cache_creation", 0))
    return total


def load_runs(condition):
    cdir = RESULTS / condition
    if not cdir.exists():
        return []
    out = []
    for f in sorted(cdir.glob("*.json")):
        try:
            rec = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        rec["priced_usd"] = reprice(rec)   # re-price with current card
        out.append(rec)
    return out


def mean(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return statistics.mean(xs) if xs else None


def fmt(x, kind=""):
    if x is None:
        return "-"
    if kind == "usd":
        return f"${x:.4f}"
    if kind == "pct":
        return f"{x*100:.0f}%"
    if kind == "int":
        return f"{int(round(x)):,}"
    if kind == "s":
        return f"{x/1000:.1f}s"
    return f"{x:.2f}"


def aggregate():
    rows = []
    for c in CONDITIONS:
        runs = load_runs(c)
        for stratum in STRATA:
            sel = runs if stratum == "all" else [r for r in runs if r.get("stratum") == stratum]
            if not sel:
                rows.append(dict(condition=c, stratum=stratum, n=0))
                continue
            checks = [r.get("check_ok") for r in sel if r.get("check_ok") is not None]
            models = sorted({m for r in sel for m in (r.get("models_used") or [])})
            rows.append(dict(
                condition=c, stratum=stratum, n=len(sel),
                check=(sum(bool(x) for x in checks) / len(checks)) if checks else None,
                priced=mean([r.get("priced_usd") for r in sel]),
                billed=mean([r.get("billed_usd") for r in sel]),
                toks=mean([(r.get("tokens") or {}).get("total") for r in sel]),
                wall=mean([r.get("wall_ms") for r in sel]),
                models=models,
            ))
    return rows


def to_markdown(rows):
    hdr = ("| condition | stratum | n | check-pass | mean priced $ | mean billed $ | "
           "mean tokens | mean wall | models used |")
    sep = "|" + "|".join(["---"] * 9) + "|"
    lines = [hdr, sep]
    for r in rows:
        if not r["n"]:
            lines.append(f"| {r['condition']} | {r['stratum']} | 0 | - | - | - | - | - | - |")
            continue
        mods = ", ".join(m.replace("claude-", "") for m in r["models"]) or "-"
        lines.append(
            f"| {r['condition']} | {r['stratum']} | {r['n']} | {fmt(r['check'],'pct')} | "
            f"{fmt(r['priced'],'usd')} | {fmt(r['billed'],'usd')} | {fmt(r['toks'],'int')} | "
            f"{fmt(r['wall'],'s')} | {mods} |")
    lines.append("")
    lines.append("priced $ = tokens x public rate card (pricing.py). billed $ = the CLI's own "
                 "total_cost_usd (ground-truth cross-check). Both roll up subagent models via "
                 "`modelUsage`, so the seahorse row includes builder-subagent tokens.")
    return "\n".join(lines)


def to_csv(rows, path):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "stratum", "n", "check_pass_rate",
                    "mean_priced_usd", "mean_billed_usd", "mean_total_tokens",
                    "mean_wall_ms", "models_used"])
        for r in rows:
            if not r["n"]:
                w.writerow([r["condition"], r["stratum"], 0, "", "", "", "", "", ""])
                continue
            w.writerow([r["condition"], r["stratum"], r["n"],
                        "" if r["check"] is None else round(r["check"], 3),
                        "" if r["priced"] is None else round(r["priced"], 6),
                        "" if r["billed"] is None else round(r["billed"], 6),
                        "" if r["toks"] is None else round(r["toks"]),
                        "" if r["wall"] is None else round(r["wall"]),
                        " ".join(r["models"])])


def to_mermaid(rows):
    allrows = [r for r in rows if r["stratum"] == "all" and r.get("priced") is not None]
    if not allrows:
        return None
    labels = ", ".join(f'"{r["condition"]}"' for r in allrows)
    priced = ", ".join(f'{r["priced"]:.4f}' for r in allrows)
    top = max(r["priced"] for r in allrows) * 1.25 or 1.0
    return ("```mermaid\n"
            "xychart-beta\n"
            '    title "Mean priced cost per task (USD, lower is better)"\n'
            f"    x-axis [{labels}]\n"
            f'    y-axis "USD (token-priced)" 0 --> {top:.4f}\n'
            f"    bar [{priced}]\n"
            "```\n")


def main():
    if not RESULTS.exists() or not any(RESULTS.glob("*/*.json")):
        print("no data in results/local/ yet — run run_local.py first.")
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
    print("wrote: results/local/summary.{md,csv,mmd}")


if __name__ == "__main__":
    main()
