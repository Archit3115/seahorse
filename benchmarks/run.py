#!/usr/bin/env python3
"""Seahorse SWE-bench harness — generation runner.

For each pinned instance x each of 4 conditions, invoke `claude -p` headless inside a
checkout of the repo at base_commit, capture the result JSON (cost / tokens / duration)
and the git diff it produced, and write results/<condition>/<instance>.json plus a
swebench-ready predictions.jsonl per condition.

Conditions:
  fable   -> claude -p --model claude-fable-5           (solo)
  opus    -> claude -p --model claude-opus-4-8          (solo)
  sonnet  -> claude -p --model claude-sonnet-5          (solo)
  seahorse-> claude -p --model claude-fable-5 --plugin-dir <SEAHORSE>  (advisor loop)

Accuracy is NOT computed here — it comes from the official swebench docker eval run over
the emitted predictions.jsonl (see README). score.py joins these metrics with that report.

Flags verified against https://docs.claude.com/en/docs/claude-code/cli-reference (2026-07):
  -p/--print, --model, --output-format json, --dangerously-skip-permissions, --plugin-dir.
JSON fields verified: total_cost_usd, usage.{input_tokens,output_tokens,
cache_read_input_tokens,cache_creation_input_tokens}, session_id, result.
num_turns / duration_ms are read best-effort and marked VERIFY (not confirmed on the
fetched doc pages); wall-clock is measured by this script regardless.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEAHORSE_ROOT = HERE.parent                       # /Users/sentry/Work/seahorse
RESULTS = HERE / "results"
REPOS = HERE / "repos"                             # cached full clones
INSTANCES_FILE = HERE / "instances.txt"
SEAHORSE_PROMPT = HERE / "seahorse_prompt.md"
DATASET = "princeton-nlp/SWE-bench_Verified"
MODEL_NAME_PREFIX = "seahorse-bench"              # goes into predictions model_name_or_path

# condition -> (model_id, use_seahorse_plugin)
CONDITIONS = {
    "fable":    ("claude-fable-5",  False),
    "opus":     ("claude-opus-4-8", False),
    "sonnet":   ("claude-sonnet-5", False),
    "seahorse": ("claude-fable-5",  True),
}

SHORT_DIFFS = {"<15 min fix", "15 min - 1 hour"}
LONG_DIFFS = {"1-4 hours", ">4 hours"}


# ----------------------------------------------------------------------------- instances
def read_instances():
    """-> list[(instance_id, stratum)] from the pinned file."""
    out = []
    for line in INSTANCES_FILE.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        iid = parts[0]
        stratum = parts[1] if len(parts) > 1 else "short"
        out.append((iid, stratum))
    return out


def load_dataset_map():
    """-> {instance_id: row}. Requires `datasets`; only used for real runs / select / validate."""
    try:
        from datasets import load_dataset
    except ImportError:
        sys.exit("ERROR: `datasets` not installed. `pip install -r requirements.txt` "
                 "(not needed for --dry-run / score.py).")
    ds = load_dataset(DATASET, split="test")
    return {r["instance_id"]: r for r in ds}


# ----------------------------------------------------------------------------- prompts
def build_task_prompt(row):
    """The BYTE-IDENTICAL task string all 4 conditions receive (fairness contract)."""
    return (
        f"You are working in a fresh checkout of the `{row['repo']}` repository at commit "
        f"{row['base_commit']}. Resolve the issue described below by editing the source code "
        f"in the working tree. Make the smallest correct change. Do not add new tests unless "
        f"you need them to verify your fix; leave all changes applied to the working tree.\n\n"
        f"<issue>\n{row['problem_statement']}\n</issue>"
    )


def build_prompt(row, use_seahorse):
    task = build_task_prompt(row)
    if not use_seahorse:
        return task
    tmpl = SEAHORSE_PROMPT.read_text()
    # strip the HTML design-note comment; keep only the live instruction body
    body = tmpl.split("-->", 1)[-1]
    return body.replace("{{TASK}}", task)


def build_claude_cmd(prompt, model, use_seahorse):
    cmd = ["claude", "-p", prompt, "--model", model,
           "--output-format", "json", "--dangerously-skip-permissions"]
    if use_seahorse:
        cmd += ["--plugin-dir", str(SEAHORSE_ROOT)]
    return cmd


# ----------------------------------------------------------------------------- git checkout
def repo_slug(repo):                       # "django/django" -> "django__django"
    return repo.replace("/", "__")


def ensure_clone(repo):
    """Full clone cached under repos/. Returns the cache path."""
    dest = REPOS / repo_slug(repo)
    if not (dest / ".git").exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", f"https://github.com/{repo}.git", str(dest)],
                       check=True)
    return dest


def make_worktree(repo, base_commit):
    """Fresh worktree at base_commit. Returns path; caller must drop_worktree() it."""
    cache = ensure_clone(repo)
    subprocess.run(["git", "-C", str(cache), "fetch", "--quiet", "origin", base_commit],
                   check=False)  # commit is usually already present; fetch is best-effort
    wt = HERE / "worktrees" / f"{repo_slug(repo)}-{base_commit[:8]}-{os.getpid()}"
    if wt.exists():
        shutil.rmtree(wt, ignore_errors=True)
    wt.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(cache), "worktree", "add", "--detach",
                    str(wt), base_commit], check=True)
    return cache, wt


def drop_worktree(cache, wt):
    subprocess.run(["git", "-C", str(cache), "worktree", "remove", "--force", str(wt)],
                   check=False)
    shutil.rmtree(wt, ignore_errors=True)


def capture_diff(wt):
    subprocess.run(["git", "-C", str(wt), "add", "-A"], check=False)
    r = subprocess.run(["git", "-C", str(wt), "diff", "--cached"],
                       capture_output=True, text=True)
    return r.stdout


# ----------------------------------------------------------------------------- one run
def result_path(condition, iid):
    return RESULTS / condition / f"{iid}.json"


def run_one(condition, iid, row, wall_only=False):
    model, use_seahorse = CONDITIONS[condition]
    prompt = build_prompt(row, use_seahorse)
    cmd = build_claude_cmd(prompt, model, use_seahorse)

    cache, wt = make_worktree(row["repo"], row["base_commit"])
    t0 = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=str(wt), capture_output=True, text=True)
        wall_ms = int((time.monotonic() - t0) * 1000)
        patch = capture_diff(wt)
    finally:
        drop_worktree(cache, wt)

    rec = {
        "instance_id": iid,
        "condition": condition,
        "model": model,
        "stratum": row.get("_stratum"),
        "wall_ms": wall_ms,
        "exit_code": proc.returncode,
        "model_patch": patch,
        "raw_stdout_head": proc.stdout[:500],
    }
    try:
        j = json.loads(proc.stdout)
        usage = j.get("usage", {}) or {}
        rec.update({
            "total_cost_usd": j.get("total_cost_usd"),
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
            "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
            "num_turns": j.get("num_turns"),        # VERIFY: field not confirmed in docs
            "duration_ms": j.get("duration_ms"),    # VERIFY: field not confirmed in docs
            "session_id": j.get("session_id"),
            "parse_ok": True,
        })
    except (json.JSONDecodeError, TypeError):
        rec["parse_ok"] = False
        rec["stderr_head"] = proc.stderr[:500]
    return rec


# ----------------------------------------------------------------------------- predictions
def write_predictions(condition):
    """Aggregate per-run patches into swebench predictions.jsonl for this condition."""
    cdir = RESULTS / condition
    preds = []
    for f in sorted(cdir.glob("*.json")):
        rec = json.loads(f.read_text())
        preds.append({
            "instance_id": rec["instance_id"],
            "model_name_or_path": f"{MODEL_NAME_PREFIX}-{condition}",
            "model_patch": rec.get("model_patch", ""),
        })
    out = cdir / "predictions.jsonl"
    out.write_text("".join(json.dumps(p) + "\n" for p in preds))
    return out, len(preds)


# ----------------------------------------------------------------------------- modes
def do_validate():
    dmap = load_dataset_map()
    missing = [iid for iid, _ in read_instances() if iid not in dmap]
    if missing:
        print(f"MISSING from {DATASET} ({len(missing)}):")
        for m in missing:
            print("  ", m)
        sys.exit(1)
    print(f"OK: all {len(read_instances())} instances present in {DATASET}.")


def do_select(n, seed):
    dmap = load_dataset_map()
    short, long = [], []
    for iid, row in dmap.items():
        diff = row.get("difficulty")
        if diff in SHORT_DIFFS:
            short.append(iid)
        elif diff in LONG_DIFFS:
            long.append(iid)
    rng = random.Random(seed)
    rng.shuffle(short)
    rng.shuffle(long)
    half = n // 2
    pick = [(i, "short") for i in short[:half]] + [(i, "long") for i in long[:n - half]]
    lines = ["# Regenerated by run.py --select "
             f"{n} --seed {seed} from {DATASET} difficulty annotations.\n"]
    lines += ["# ---- short ----\n"]
    lines += [f"{i}  short\n" for i, s in pick if s == "short"]
    lines += ["# ---- long ----\n"]
    lines += [f"{i}  long\n" for i, s in pick if s == "long"]
    INSTANCES_FILE.write_text("".join(lines))
    print(f"Wrote {len(pick)} instances to {INSTANCES_FILE} "
          f"({sum(s=='short' for _,s in pick)} short / {sum(s=='long' for _,s in pick)} long).")


def do_dry_run(conditions):
    """No deps, no subprocess: list planned (instance x condition) runs + a sample command."""
    inst = read_instances()
    print(f"DRY RUN — {len(inst)} instances x {len(conditions)} conditions "
          f"= {len(inst) * len(conditions)} runs\n")
    for iid, stratum in inst:
        for c in conditions:
            done = "DONE" if result_path(c, iid).exists() else "todo"
            print(f"  [{done}] {c:8s} {stratum:5s} {iid}")
    c0 = conditions[0]
    model, use_sh = CONDITIONS[c0]
    sample = build_claude_cmd("<TASK PROMPT>", model, use_sh)
    print("\nsample command (" + c0 + "):")
    print("  " + " ".join(f'"{a}"' if " " in a else a for a in sample))


def do_run(conditions, max_usd):
    dmap = load_dataset_map()
    inst = read_instances()
    spent = 0.0
    for c in conditions:
        (RESULTS / c).mkdir(parents=True, exist_ok=True)
    for iid, stratum in inst:
        if iid not in dmap:
            print(f"SKIP (not in dataset): {iid}")
            continue
        row = dict(dmap[iid])
        row["_stratum"] = stratum
        for c in conditions:
            rp = result_path(c, iid)
            if rp.exists():
                print(f"skip done: {c} {iid}")
                continue
            if spent >= max_usd:
                print(f"STOP: cost cap ${max_usd} reached (spent ${spent:.2f}).")
                _finalize(conditions)
                return
            print(f"RUN {c} {iid} ...")
            rec = run_one(c, iid, row)
            rp.write_text(json.dumps(rec, indent=2))
            cost = rec.get("total_cost_usd") or 0.0
            spent += cost
            print(f"  cost=${cost:.4f} wall={rec['wall_ms']}ms "
                  f"cum=${spent:.2f} parse_ok={rec.get('parse_ok')}")
    _finalize(conditions)


def _finalize(conditions):
    for c in conditions:
        if (RESULTS / c).exists():
            out, n = write_predictions(c)
            print(f"predictions[{c}]: {n} -> {out}")


# ----------------------------------------------------------------------------- cli
def main():
    ap = argparse.ArgumentParser(description="Seahorse SWE-bench generation runner")
    ap.add_argument("--conditions", default=",".join(CONDITIONS),
                    help="comma list of: " + ",".join(CONDITIONS))
    ap.add_argument("--max-usd", type=float, default=25.0, help="cumulative cost cap")
    ap.add_argument("--dry-run", action="store_true",
                    help="list planned runs (no deps, no subprocess)")
    ap.add_argument("--validate", action="store_true",
                    help="check instances.txt ids exist in the dataset")
    ap.add_argument("--select", type=int, metavar="N",
                    help="regenerate instances.txt: stratified sample of N from the dataset")
    ap.add_argument("--seed", type=int, default=0, help="sample seed for --select")
    args = ap.parse_args()

    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    bad = [c for c in conditions if c not in CONDITIONS]
    if bad:
        sys.exit(f"unknown condition(s): {bad}; valid: {list(CONDITIONS)}")

    if args.select:
        return do_select(args.select, args.seed)
    if args.validate:
        return do_validate()
    if args.dry_run:
        return do_dry_run(conditions)
    return do_run(conditions, args.max_usd)


if __name__ == "__main__":
    main()
