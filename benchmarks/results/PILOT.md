# Pilot report

Ran the harness's environment availability check on the build host (2026-07-05).
**No numbers are fabricated below** — a real pilot could not run because the eval
toolchain (Docker + swebench) is not installed on this host.

## Availability check

| Requirement | Command | Result |
|-------------|---------|--------|
| Claude CLI  | `claude --version`   | **present** — `2.1.201 (Claude Code)` |
| Docker      | `docker info`        | **MISSING** — `command not found: docker` |
| swebench    | `python3 -m pip show swebench` | **MISSING** — not installed |
| Python      | `python3 --version`  | **present** — `Python 3.9.6` (note: `python` alias absent; use `python3`) |
| pip         | `python3 -m pip --version` | present — `pip 21.2.4` |

`datasets` is also not installed (needed for full runs / `--select` / `--validate`).

## What this means

- The harness code is verified runnable with **zero deps**:
  - `python3 run.py --dry-run`  → prints the 96 planned runs + the exact `claude -p` command.
  - `python3 score.py`          → aggregates `results/`, exits cleanly on empty data.
- A **real** generation + accuracy pilot needs Docker (for the swebench eval images) and the
  `swebench` + `datasets` packages, none of which are present here. So no live cost/token/
  accuracy numbers are recorded — recording any would be fabrication.

## Run the pilot yourself

```bash
cd /Users/sentry/Work/seahorse/benchmarks
python3 -m pip install -r requirements.txt          # datasets + swebench
# ensure Docker Desktop / daemon is running: `docker info` must succeed

python3 run.py --validate                           # confirm pinned ids exist in the split

# TINY real pilot: 1 instance, 1 cheap condition, hard cost cap
printf 'astropy__astropy-14182  short\n' > instances.pilot.txt
cp instances.txt instances.full.txt && cp instances.pilot.txt instances.txt
python3 run.py --conditions sonnet --max-usd 2.0    # writes results/sonnet/*.json
cp instances.full.txt instances.txt                 # restore full list

# accuracy: official swebench docker eval over the emitted predictions
python3 -m swebench.harness.run_evaluation \
  --dataset_name princeton-nlp/SWE-bench_Verified \
  --predictions_path results/sonnet/predictions.jsonl \
  --run_id seahorse-pilot --max_workers 1
# copy/rename the produced report to results/sonnet/eval.json (contains resolved_ids)

python3 score.py                                    # metrics x accuracy table + CSV
```

Expected artifacts after a real pilot: `results/sonnet/astropy__astropy-14182.json`
(cost/tokens/wall + diff), `results/sonnet/predictions.jsonl`, `results/sonnet/eval.json`,
and `results/summary.{md,csv,mmd}`.
