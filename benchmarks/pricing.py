#!/usr/bin/env python3
"""Token -> equivalent USD, from a published rate card. STDLIB ONLY.

The Seahorse benchmark scores conditions by *token cost priced from public
per-MTok rates* — not by trusting a single billed figure. This module is that
rate card + the pricing function.

Rates: first-party Claude API, global routing, standard tier, captured
2026-07-05 from https://platform.claude.com/docs/en/about-claude/pricing .
Only base-input and output $/MTok are stored; the cache multipliers are fixed
by the docs:  5m write = 1.25x base, 1h write = 2x base, cache read = 0.1x base.

Claude Code caches its big system/tools prefix at the **1h** TTL, so we price
cache-creation at 1h by default. Verified against a live `claude -p` probe:
pricing (input 10, cache_read 17209, cache_creation 13579@1h, output 57) on
Haiku 4.5 reproduces the CLI's own total_cost_usd = $0.029174 to 4 decimals
(see demo() below).

Model-id matching is by substring so it survives dated ids like
`claude-haiku-4-5-20251001`. Longest key wins, so `opus-4-8` beats `opus`.
"""
from __future__ import annotations

# substring -> (base_input_usd_per_mtok, output_usd_per_mtok)
# Sonnet 5's list intro rate is $2/$10 thru 2026-08-31, but the CLI's own
# total_cost_usd bills it at the standard $3/$15 (verified: priced-at-intro was
# exactly 1.5x under billed on a live sonnet run). Ground truth = billed, so the
# card uses $3/$15 to reproduce what the API actually charges.
RATE_CARD = {
    "fable-5":    (10.0, 50.0),
    "mythos-5":   (10.0, 50.0),
    "opus-4-8":   (5.0, 25.0),
    "opus-4-7":   (5.0, 25.0),
    "opus-4-6":   (5.0, 25.0),
    "opus-4-5":   (5.0, 25.0),
    "opus":       (5.0, 25.0),
    "sonnet-5":   (3.0, 15.0),   # CLI bills standard, not the $2/$10 list intro
    "sonnet-4":   (3.0, 15.0),
    "sonnet":     (3.0, 15.0),
    "haiku-4-5":  (1.0, 5.0),
    "haiku":      (1.0, 5.0),
}

CACHE_WRITE_MULT = {"5m": 1.25, "1h": 2.0}
CACHE_READ_MULT = 0.1


def rate_for(model_id: str):
    """-> (base_input, output) $/MTok for the model, matching by substring.

    Longest matching key wins so dated/specific ids beat generic ones.
    Raises KeyError on an unknown model rather than guessing a price.
    """
    m = model_id.lower()
    best = None
    for key, rate in RATE_CARD.items():
        if key in m and (best is None or len(key) > len(best[0])):
            best = (key, rate)
    if best is None:
        raise KeyError(f"no rate card entry for model {model_id!r}")
    return best[1]


def price(model_id, input_tokens=0, output_tokens=0,
          cache_read=0, cache_creation=0, cache_ttl="1h"):
    """USD for one model's token usage, priced from the rate card."""
    base, out = rate_for(model_id)
    write_mult = CACHE_WRITE_MULT[cache_ttl]
    usd = (
        input_tokens * base
        + cache_read * base * CACHE_READ_MULT
        + cache_creation * base * write_mult
        + output_tokens * out
    ) / 1_000_000
    return usd


def price_modelusage(model_usage: dict, cache_ttl="1h"):
    """Price a `modelUsage` map from `claude -p --output-format json`.

    modelUsage = {model_id: {inputTokens, outputTokens, cacheReadInputTokens,
                             cacheCreationInputTokens, costUSD, ...}}
    Returns {"total_priced_usd", "total_billed_usd", "per_model": {...},
             "tokens": {input, output, cache_read, cache_creation, total}}.
    total_billed_usd sums the CLI's own costUSD (ground-truth cross-check).
    """
    per_model, tok = {}, dict(input=0, output=0, cache_read=0, cache_creation=0)
    total_priced = total_billed = 0.0
    for mid, u in (model_usage or {}).items():
        it = u.get("inputTokens", 0) or 0
        ot = u.get("outputTokens", 0) or 0
        cr = u.get("cacheReadInputTokens", 0) or 0
        cc = u.get("cacheCreationInputTokens", 0) or 0
        p = price(mid, it, ot, cr, cc, cache_ttl)
        billed = u.get("costUSD")
        per_model[mid] = {"priced_usd": p, "billed_usd": billed,
                          "input": it, "output": ot,
                          "cache_read": cr, "cache_creation": cc}
        total_priced += p
        if isinstance(billed, (int, float)):
            total_billed += billed
        tok["input"] += it; tok["output"] += ot
        tok["cache_read"] += cr; tok["cache_creation"] += cc
    tok["total"] = sum(tok.values())
    return {"total_priced_usd": total_priced,
            "total_billed_usd": total_billed or None,
            "per_model": per_model, "tokens": tok}


def demo():
    """Self-check: rate card reproduces the live CLI billed cost."""
    # Live probe (2026-07-05), claude-haiku-4-5, cache prefix at 1h TTL:
    got = price("claude-haiku-4-5-20251001",
                input_tokens=10, output_tokens=57,
                cache_read=17209, cache_creation=13579, cache_ttl="1h")
    billed = 0.029173900000000003
    assert abs(got - billed) < 1e-4, f"priced {got} vs billed {billed}"

    # Substring matching: dated id and generic id both resolve; opus-4-8 wins over opus.
    assert rate_for("claude-opus-4-8") == (5.0, 25.0)
    assert rate_for("claude-fable-5") == (10.0, 50.0)
    assert rate_for("claude-sonnet-5") == (3.0, 15.0)   # CLI bills standard

    # Rollup across two models (seahorse-style: fable advisor + opus builder).
    mu = {
        "claude-fable-5":  {"inputTokens": 1000, "outputTokens": 500,
                            "cacheReadInputTokens": 20000, "cacheCreationInputTokens": 4000,
                            "costUSD": 0.001},
        "claude-opus-4-8": {"inputTokens": 3000, "outputTokens": 2000,
                            "cacheReadInputTokens": 50000, "cacheCreationInputTokens": 8000,
                            "costUSD": 0.002},
    }
    r = price_modelusage(mu)
    assert r["tokens"]["output"] == 2500
    assert set(r["per_model"]) == set(mu)
    assert r["total_priced_usd"] > 0 and r["total_billed_usd"] == 0.003
    print("pricing.py demo OK — priced=%.6f billed=%.6f (haiku probe)" % (got, billed))


if __name__ == "__main__":
    demo()
