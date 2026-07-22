#!/usr/bin/env python3
"""Seahorse local token-cost benchmark — no Docker, no SWE-bench dataset.

Runs a small set of *self-contained* coding tasks (they create their own files
from scratch, so no repo checkout / eval image is needed) under each condition,
captures the per-model token usage from `claude -p --output-format json`, and
prices those tokens into equivalent USD via pricing.py (a published rate card).
This is the "convert tokens to equivalent money" benchmark — the metric is
token cost priced from public rates, cross-checked against the CLI's own billed
figure, NOT a bespoke money meter.

Conditions (same as the SWE-bench harness):
  fable / opus / sonnet  -> solo `claude -p --model <m>`
  seahorse               -> fable advisor + --plugin-dir, delegates to builders

GUARDED HEADLESS MODE
  Headless runs can't answer permission prompts, so they need auto-approval.
  Instead of raw `--dangerously-skip-permissions` (unrestricted egress), every
  run also carries a hard DENYLIST (DISALLOWED_TOOLS). Deny rules win even under
  skip-permissions, so file writes + `python3` run freely (the only ingress the
  test needs) while deletion / move / network / privilege / package-manager /
  VCS commands are blocked. Verified: an agent told to `rm -rf .` is denied and
  the scratch dir survives.
  ponytail: python3 is allowed and could shell out (os.system) — the denylist
  covers direct dangerous commands, not that indirection; the scratch dir is
  disposable and off the project tree, which is the real containment.

Each (task x condition) runs in a fresh empty scratch dir. The task string is
BYTE-IDENTICAL across conditions (fairness); only the seahorse orchestration
wrapper differs. A best-effort `check` command gives a cheap correctness proxy
(did the produced code run / pass its own self-check) — headline metric is cost.

  python3 run_local.py --dry-run                 # list runs + sample cmd, no spend
  python3 run_local.py --conditions sonnet,seahorse --max-usd 5
  python3 score_local.py                         # aggregate -> priced table + mmd
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pricing

HERE = Path(__file__).resolve().parent
SEAHORSE_ROOT = HERE.parent
RESULTS = HERE / "results" / "local"
WORK = RESULTS / "_work"
SEAHORSE_PROMPT = HERE / "seahorse_prompt.md"

# condition -> (model_id, use_seahorse_plugin)
CONDITIONS = {
    "fable":    ("claude-fable-5",  False),
    "opus":     ("claude-opus-4-8", False),
    "sonnet":   ("claude-sonnet-5", False),
    "seahorse": ("claude-fable-5",  True),
}

# Guardrails: blocked in EVERY run (deny wins over skip-permissions). Ingress the
# test needs (Write/Edit/Read/Bash python3) is allowed by omission; egress and
# anything destructive/system-touching is denied here.
DISALLOWED_TOOLS = ",".join([
    "Bash(rm:*)", "Bash(rmdir:*)", "Bash(mv:*)", "Bash(cp:*)", "Bash(dd:*)",
    "Bash(sudo:*)", "Bash(chmod:*)", "Bash(chown:*)", "Bash(kill:*)",
    "Bash(curl:*)", "Bash(wget:*)", "Bash(nc:*)", "Bash(ssh:*)", "Bash(scp:*)",
    "Bash(git:*)", "Bash(pip:*)", "Bash(pip3:*)", "Bash(npm:*)", "Bash(npx:*)",
    "Bash(brew:*)", "Bash(apt:*)", "Bash(docker:*)", "Bash(launchctl:*)",
    "WebFetch", "WebSearch",
])

# Self-contained tasks. `check` runs in the scratch dir (best-effort pass/fail).
# Keep the task string identical across conditions — do NOT add hints here.
TASKS = [
    {
        "id": "palindrome",
        "stratum": "short",
        "prompt": (
            "Create a file `palindrome.py` containing a function "
            "`is_palindrome(s: str) -> bool` that returns True if `s` is a "
            "palindrome ignoring case, spaces, and punctuation (compare only "
            "alphanumeric characters). Add a `demo()` with a few `assert` "
            "checks and call it under `if __name__ == '__main__':`. Make the "
            "smallest correct change."
        ),
        "check": "python3 palindrome.py",
    },
    {
        "id": "portfolio-netflix",
        "stratum": "long",
        "prompt": (
            "Build a portfolio website for Archit Srivastava(me) and the "
            "style needs to be as netflix."
        ),
        # proxy: did the run produce at least one HTML page?
        "check": (
            "python3 -c \"import glob,sys; "
            "sys.exit(0 if glob.glob('**/*.html', recursive=True) else 1)\""
        ),
    },
    {
        "id": "todo-cli",
        "stratum": "long",
        "prompt": (
            "Build a small command-line todo app in a single file `todo.py` "
            "using only the Python standard library. It must support four "
            "subcommands via argparse, persisting tasks to `todo.json` in the "
            "current directory:\n"
            "  add <text>   -> append a task (auto integer id, done=False)\n"
            "  list         -> print each task as `<id> [x| ] <text>`\n"
            "  done <id>    -> mark that task done\n"
            "  rm <id>      -> delete that task\n"
            "Persist as JSON; create the file if missing; handle a missing/"
            "unknown id without crashing (print a message, exit non-zero). "
            "Also write `test_todo.py` that exercises add, list, done, and rm "
            "end to end using a temp working directory and asserts the JSON "
            "state after each step. Tests must pass under `python3 -m pytest` "
            "OR plain `python3 test_todo.py` (make one of them work with no "
            "third-party deps)."
        ),
        "check": "python3 test_todo.py",
    },
]


def seahorse_wrap(task_prompt: str) -> str:
    body = SEAHORSE_PROMPT.read_text().split("-->", 1)[-1]
    return body.replace("{{TASK}}", task_prompt)


def build_cmd(prompt, model, use_seahorse):
    cmd = ["claude", "-p", prompt, "--model", model,
           "--output-format", "json",
           "--dangerously-skip-permissions",
           "--disallowedTools", DISALLOWED_TOOLS]
    if use_seahorse:
        cmd += ["--plugin-dir", str(SEAHORSE_ROOT)]
    return cmd


def result_path(condition, task_id):
    return RESULTS / condition / f"{task_id}.json"


def run_one(condition, task, timeout_s):
    model, use_seahorse = CONDITIONS[condition]
    prompt = seahorse_wrap(task["prompt"]) if use_seahorse else task["prompt"]
    cmd = build_cmd(prompt, model, use_seahorse)

    wt = WORK / f"{condition}-{task['id']}"
    if wt.exists():
        shutil.rmtree(wt, ignore_errors=True)
    wt.mkdir(parents=True)

    t0 = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(cmd, cwd=str(wt), capture_output=True,
                              text=True, timeout=timeout_s)
        stdout, stderr, rc = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = (e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")) \
            + f"\n[timeout after {timeout_s}s]"
        rc, timed_out = -1, True
    wall_ms = int((time.monotonic() - t0) * 1000)

    files = sorted(p.name for p in wt.iterdir() if p.is_file())

    rec = {
        "task": task["id"], "stratum": task["stratum"], "condition": condition,
        "entry_model": model, "wall_ms": wall_ms, "exit_code": rc,
        "timed_out": timed_out, "files_written": files,
        "raw_stdout_head": stdout[:400],
    }

    # correctness proxy: run the task's check inside the scratch dir
    if task.get("check") and not timed_out:
        try:
            chk = subprocess.run(task["check"], cwd=str(wt), shell=True,
                                capture_output=True, text=True, timeout=120)
            rec["check_ok"] = chk.returncode == 0
            rec["check_tail"] = (chk.stdout + chk.stderr)[-300:]
        except subprocess.TimeoutExpired:
            rec["check_ok"] = False
            rec["check_tail"] = "[check timeout]"
    else:
        rec["check_ok"] = None

    try:
        j = json.loads(stdout)
        mu = j.get("modelUsage", {}) or {}
        priced = pricing.price_modelusage(mu)
        rec.update({
            "parse_ok": True,
            "billed_usd": j.get("total_cost_usd"),
            "priced_usd": priced["total_priced_usd"],
            "priced_billed_usd": priced["total_billed_usd"],
            "tokens": priced["tokens"],
            "per_model": priced["per_model"],
            "num_turns": j.get("num_turns"),
            "models_used": sorted(mu.keys()),
        })
    except (json.JSONDecodeError, TypeError):
        rec["parse_ok"] = False
        rec["stderr_head"] = stderr[:400]
    return rec


def do_dry_run(conditions, tasks):
    n = len(conditions) * len(tasks)
    print(f"DRY RUN — {len(tasks)} tasks x {len(conditions)} conditions = {n} runs\n")
    for t in tasks:
        for c in conditions:
            done = "DONE" if result_path(c, t["id"]).exists() else "todo"
            print(f"  [{done}] {c:8s} {t['stratum']:5s} {t['id']}")
    c0 = conditions[0]
    model, use_sh = CONDITIONS[c0]
    sample = build_cmd("<TASK PROMPT>", model, use_sh)
    print(f"\nsample command ({c0}):")
    print("  " + " ".join(f'"{a}"' if " " in a else a for a in sample))
    print(f"\nguardrails (denied every run): {DISALLOWED_TOOLS}")


def do_run(conditions, tasks, max_usd, timeout_s):
    for c in conditions:
        (RESULTS / c).mkdir(parents=True, exist_ok=True)
    spent = 0.0
    for t in tasks:
        for c in conditions:
            rp = result_path(c, t["id"])
            if rp.exists():
                print(f"skip done: {c} {t['id']}")
                continue
            if spent >= max_usd:
                print(f"STOP: cost cap ${max_usd} reached (billed ${spent:.2f}).")
                return
            print(f"RUN {c} {t['id']} ...", flush=True)
            rec = run_one(c, t, timeout_s)
            rp.write_text(json.dumps(rec, indent=2))
            billed = rec.get("billed_usd") or 0.0
            spent += billed
            print(f"  priced=${(rec.get('priced_usd') or 0):.4f} "
                  f"billed=${billed:.4f} cum=${spent:.2f} "
                  f"wall={rec['wall_ms']}ms check_ok={rec.get('check_ok')} "
                  f"models={rec.get('models_used')} parse_ok={rec.get('parse_ok')}",
                  flush=True)
    print(f"\nDONE. total billed ${spent:.2f}. Aggregate: python3 score_local.py")


def main():
    ap = argparse.ArgumentParser(description="Seahorse local token-cost benchmark")
    ap.add_argument("--conditions", default=",".join(CONDITIONS))
    ap.add_argument("--tasks", default=",".join(t["id"] for t in TASKS),
                    help="comma-separated task ids to run (default: all)")
    ap.add_argument("--max-usd", type=float, default=10.0,
                    help="cumulative BILLED cost cap (safety); metric is priced_usd")
    ap.add_argument("--timeout", type=int, default=900, help="per-run wall timeout (s)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    bad = [c for c in conditions if c not in CONDITIONS]
    if bad:
        sys.exit(f"unknown condition(s): {bad}; valid: {list(CONDITIONS)}")

    task_ids = [t.strip() for t in args.tasks.split(",") if t.strip()]
    known = {t["id"]: t for t in TASKS}
    bad = [t for t in task_ids if t not in known]
    if bad:
        sys.exit(f"unknown task(s): {bad}; valid: {list(known)}")
    tasks = [known[t] for t in task_ids]

    if args.dry_run:
        return do_dry_run(conditions, tasks)
    return do_run(conditions, tasks, args.max_usd, args.timeout)


if __name__ == "__main__":
    main()
