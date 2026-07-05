# Seahorse benchmark harness — methodology & design

Measures Claude Code coding performance under **4 conditions** (fable / opus / sonnet solo vs.
**seahorse** orchestration), capturing **cost, tokens, wall-clock, and accuracy**, split by
**short- vs long-running** tasks. The point is a fair apples-to-apples read on whether the Seahorse
advisor→executor orchestration beats the same models used solo.

## Two tracks

| Track | Runner | Measures | Needs |
|-------|--------|----------|-------|
| **Token-priced** (default, cheap) | [`run_local.py`](run_local.py) → [`score_local.py`](score_local.py) | **tokens → equivalent USD** (rate card), cross-checked vs billed; short/long | just the `claude` CLI |
| **SWE-bench** (accuracy) | [`run.py`](run.py) → swebench → [`score.py`](score.py) | official resolved-rate on real GitHub issues + cost | Docker + `swebench` + `datasets` |

The token-priced track is the answer to *"benchmark by tokens, convert to money, don't run a bespoke
money meter."* It needs no Docker and produces real numbers in minutes. **Measured results:
[`results/RESULTS.md`](results/RESULTS.md).**

```
# token-priced track
run_local.py   run self-contained tasks with `claude -p`, read modelUsage   -> results/local/<cond>/<task>.json
pricing.py     tokens x public rate card -> equivalent USD (== billed check)
score_local.py aggregate -> priced table + CSV + Mermaid                     -> results/local/summary.{md,csv,mmd}

# SWE-bench track
run.py     generate patches with `claude -p`, capture metrics + diffs   -> results/<cond>/<id>.json
swebench   official docker eval of predictions.jsonl                      -> results/<cond>/eval.json
score.py   join metrics x eval -> table + CSV + Mermaid                   -> results/summary.{md,csv,mmd}
```

## Token → equivalent money (`pricing.py`)

The token-priced metric multiplies each model's captured token counts by a **published per-MTok rate
card** (first-party Claude API, global, standard tier — captured 2026-07-05 from the docs). The CLI's
`--output-format json` emits a `modelUsage` map broken down **per model**, so:

- **subagent tokens are counted** — the seahorse advisor (Fable) and its builders (Sonnet/Opus) each
  appear under their own model key, fixing the classic "subagent tokens hide from top-level `usage`" gap;
- pricing is **validated against ground truth** — priced cost reproduces the CLI's own `total_cost_usd`
  to the cent for solo runs (see `pricing.py::demo()` and RESULTS.md).

`score_local.py` re-prices from the stored per-model token counts every time it runs, so correcting the
rate card retroactively fixes past runs with no re-spend.

## Guarded headless mode (the safety model)

Headless `claude -p` can't answer permission prompts, so runs need auto-approval. Rather than raw
`--dangerously-skip-permissions` (unrestricted egress), `run_local.py` pairs it with a hard
**denylist** (`DISALLOWED_TOOLS`): deletion (`rm`/`rmdir`/`mv`), privilege (`sudo`/`chmod`/`chown`),
network (`curl`/`wget`/`nc`/`ssh`), package managers (`pip`/`npm`/`brew`/`apt`), `git`, `docker`, and
`WebFetch`/`WebSearch`. **Deny rules win even under skip-permissions**, so file writes + `python3` (the
only ingress a coding task needs) run freely while everything destructive is blocked — verified by an
agent instructed to `rm -rf .`, which is denied while the scratch dir survives. Each run is also confined
to a fresh empty scratch dir off the project tree.

## The 4 conditions

| condition | invocation | model tier |
|-----------|------------|------------|
| **fable**    | `claude -p … --model claude-fable-5` | Fable solo |
| **opus**     | `claude -p … --model claude-opus-4-8` | Opus 4.8 solo |
| **sonnet**   | `claude -p … --model claude-sonnet-5` | Sonnet 5 solo |
| **seahorse** | `claude -p … --model claude-fable-5 --plugin-dir /Users/sentry/Work/seahorse` | advisor (Fable) → executors (Sonnet/Opus) |

The Seahorse condition loads the local plugin and enters as the **advisor**, which decomposes
the task and delegates chunks to `builder-light` (Sonnet) / `builder-heavy` (Opus) per the
routing table — the normal Seahorse loop, run headless (see `seahorse_prompt.md`).

## Dataset & stratification

- **Backbone:** `princeton-nlp/SWE-bench_Verified` (the human-validated 500-instance subset).
- **Subset:** ~24 instances pinned in [`instances.txt`](instances.txt) for reproducibility,
  split 12 short / 12 long.
- **Stratification proxy** (documented, so it's auditable):
  - **primary** — the dataset's `difficulty` annotation.
    `short = {"<15 min fix", "15 min - 1 hour"}`; `long = {"1-4 hours", ">4 hours"}`.
  - **fallback** — gold-patch size (files touched / lines changed) when `difficulty` is absent.
  - The label pinned in `instances.txt` is the **scoring truth**. Regenerate authoritatively:
    `python3 run.py --select 24 --seed 0` (stratified sample from the live split).
    Validate membership: `python3 run.py --validate`.

## Metric capture

`run.py` runs each condition inside a fresh `git worktree` of the repo at `base_commit`, then
reads the single result object from `claude -p --output-format json`:

| metric | source | verified? |
|--------|--------|-----------|
| cost (USD) | `total_cost_usd` | ✅ docs |
| input / output tokens | `usage.input_tokens` / `usage.output_tokens` | ✅ docs |
| cache read / creation | `usage.cache_read_input_tokens` / `usage.cache_creation_input_tokens` | ✅ docs |
| session id | `session_id` | ✅ docs |
| turns | `num_turns` | ⚠️ **VERIFY** — not confirmed on the fetched doc pages; read best-effort |
| model-reported duration | `duration_ms` | ⚠️ **VERIFY** — same; **wall-clock is measured by the script regardless** (`wall_ms`) |
| patch produced | `git diff --cached` of the worktree after the run | n/a |

**Wall-clock** is measured with `time.monotonic()` around the subprocess, so timing does not
depend on the unconfirmed `duration_ms` field.

### Flags used (verified 2026-07 against the docs)

`-p/--print`, `--model <id>`, `--output-format json`, `--dangerously-skip-permissions`,
`--plugin-dir <dir>` ("Load a plugin from a directory … for this session only. Repeat the
flag for multiple plugins"). Sources:
- https://docs.claude.com/en/docs/claude-code/cli-reference
- https://docs.claude.com/en/docs/claude-code/headless
- https://docs.claude.com/en/agent-sdk/cost-tracking (confirms `total_cost_usd`, `usage.*`)

## Accuracy eval pipeline

Accuracy = **official SWE-bench resolution**, not self-report. `run.py` emits a
swebench-format `predictions.jsonl` per condition
(`{instance_id, model_name_or_path, model_patch}`). Then:

```bash
python3 -m pip install swebench          # needs a running Docker daemon
python3 -m swebench.harness.run_evaluation \
  --dataset_name princeton-nlp/SWE-bench_Verified \
  --predictions_path results/<cond>/predictions.jsonl \
  --run_id seahorse-<cond> --max_workers 4
# rename the produced report to results/<cond>/eval.json   (must contain "resolved_ids")
```

`score.py` reads `resolved_ids` from each `eval.json` and reports resolved-rate per
condition × stratum. (`sb-cli` is an alternative to the local docker harness; either produces
a resolved/unresolved verdict — feed its resolved set into `eval.json` the same way.)

## Cost cap & retry policy

- **Cap:** `--max-usd` (default `25.0`). `run.py` accumulates real `total_cost_usd` after each
  run and **stops launching** once the cumulative spend reaches the cap. It is a post-hoc
  cumulative guard (a single run's cost is unknown until it finishes), so set the cap with
  headroom for one in-flight run.
- **Idempotent / resumable:** a run whose `results/<cond>/<id>.json` already exists is skipped,
  so re-invoking after a cap-stop or crash resumes where it left off. No auto-retry — a failed
  run leaves no result file and is simply re-attempted on the next invocation. Delete a result
  file to force a redo. (Keeps retries a deliberate, visible act rather than a hidden loop.)
- **`--dry-run`:** prints the full run plan and the exact command with **no deps and no
  subprocess** — use it to eyeball scope before spending.

## Threats to validity

- **Training leakage.** SWE-bench Verified overlaps public GitHub history and may sit in
  pretraining. This benchmark measures *relative* standing across the 4 conditions on the
  **same** instances, which the leak affects roughly equally, rather than an absolute skill
  claim. Treat absolute resolved-rates as leakage-inflated.
- **Prompt-cache confounds.** Cache-read tokens are far cheaper, and cache warmth differs
  across conditions (the Seahorse condition spins up sub-agents with their own contexts). We
  therefore report `cache_read`/`cache_creation` **separately** from fresh input tokens and
  compare on **`total_cost_usd`** (which already prices cache tiers) as the primary cost metric,
  not raw token counts. Run conditions in the same session-cache regime where possible.
- **Seahorse-condition fairness (the big one).** The orchestration must solve the **identical**
  task the solo models get — no hand-holding, no task-specific hints. `run.py::build_task_prompt`
  produces one task string; the three solo conditions receive it verbatim, and the Seahorse
  condition receives that **same** string wrapped only by the generic advisor-loop trigger in
  `seahorse_prompt.md` (`{{TASK}}` substitution). The wrapper adds orchestration instructions,
  never problem-specific guidance. Audit `seahorse_prompt.md` to confirm.
- **Solo Fable is out of tier.** Fable is the *planner* tier; running it solo as a coder is
  expected to be its weakest condition and is included as a baseline, not a strawman.
- **Non-determinism.** LLM sampling makes single runs noisy. 24 instances × 1 sample is a
  screening design; for publishable deltas, raise the sample or add k repeats per cell.
- **Docker/host drift.** swebench verdicts depend on the eval images; pin swebench version and
  record it alongside results.

## Per-condition budget estimate (rough)

Order-of-magnitude only — **not** measured on this host (see `results/PILOT.md`). Assumes
N = 24 instances, one sample each. Actuals depend on repo size and turns; the `--max-usd` cap
is the real backstop.

| condition | rough $/instance | × 24 |
|-----------|------------------:|-----:|
| fable (solo)   | ~$0.15 | ~$3.6 |
| opus (solo)    | ~$0.80 | ~$19 |
| sonnet (solo)  | ~$0.20 | ~$4.8 |
| seahorse       | ~$0.70 | ~$17 |
| **all 4** | — | **~$44** |

Budget the full 4-condition sweep at **~$40–60** and cap defensively (`--max-usd`). A 1-instance
`sonnet` pilot is well under $2.

## Files

| file | purpose |
|------|---------|
| `pricing.py` | token → equivalent USD rate card + `price_modelusage()`; `demo()` self-check vs billed |
| `run_local.py` | token-priced runner — no Docker, guarded headless mode, self-contained tasks |
| `score_local.py` | aggregate `results/local/` → priced table + CSV + Mermaid; re-prices from stored tokens |
| `run.py` | SWE-bench generation runner (`--dry-run`, `--validate`, `--select`, `--max-usd`, idempotent) |
| `score.py` | aggregate `results/` → markdown + CSV + Mermaid; no-data safe |
| `seahorse_prompt.md` | the exact, auditable Seahorse advisor-loop prompt (fairness-locked) |
| `instances.txt` | pinned stratified subset (id + short/long) |
| `diagrams.md` | Mermaid architecture / pipeline / stratification diagrams |
| `requirements.txt` | `datasets`, `swebench` (only for the SWE-bench track; token-priced track is stdlib) |
| `results/RESULTS.md` | **measured** token-priced results (2026-07-05) |
| `results/PILOT.md` | host availability check + how to run the SWE-bench pilot |

## Quick start

```bash
# token-priced track (no Docker, minutes, ~$5 for the 8-run pilot)
python3 pricing.py                       # rate-card self-check (offline)
python3 run_local.py --dry-run           # plan + guardrails, zero spend
python3 run_local.py --max-usd 10        # 4 conditions x 2 tasks, cost-capped
python3 score_local.py                   # priced table + CSV + Mermaid

# SWE-bench accuracy track (needs Docker + swebench)
python3 run.py --dry-run                 # plan, zero deps
python3 -m pip install -r requirements.txt
python3 run.py --validate                # ids exist in the split?
python3 run.py --max-usd 50              # full sweep, capped
#   … run swebench eval per condition (above) → results/<cond>/eval.json …
python3 score.py                         # table + CSV + Mermaid chart
```
