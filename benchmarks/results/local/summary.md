| condition | stratum | n | check-pass | mean priced $ | mean billed $ | mean tokens | mean wall | models used |
|---|---|---|---|---|---|---|---|---|
| fable | short | 1 | 100% | $0.6062 | $0.6062 | 103,699 | 20.7s | fable-5 |
| fable | long | 1 | 100% | $0.8127 | $0.8127 | 112,947 | 51.2s | fable-5 |
| fable | all | 2 | 100% | $0.7095 | $0.7095 | 108,323 | 36.0s | fable-5 |
| opus | short | 1 | 100% | $0.2899 | $0.2899 | 100,162 | 14.4s | opus-4-8 |
| opus | long | 1 | 100% | $0.3378 | $0.3378 | 104,175 | 39.3s | opus-4-8 |
| opus | all | 2 | 100% | $0.3139 | $0.3139 | 102,168 | 26.8s | opus-4-8 |
| sonnet | short | 1 | 100% | $0.1819 | $0.1819 | 135,930 | 15.1s | sonnet-5 |
| sonnet | long | 1 | 100% | $0.3194 | $0.3194 | 342,292 | 49.8s | sonnet-5 |
| sonnet | all | 2 | 100% | $0.2507 | $0.2507 | 239,111 | 32.4s | sonnet-5 |
| seahorse | short | 1 | 100% | $0.8237 | $0.7911 | 154,482 | 61.8s | fable-5, sonnet-5 |
| seahorse | long | 1 | 100% | $1.3946 | $1.3526 | 375,657 | 106.8s | fable-5, sonnet-5 |
| seahorse | all | 2 | 100% | $1.1091 | $1.0719 | 265,070 | 84.3s | fable-5, sonnet-5 |

priced $ = tokens x public rate card (pricing.py). billed $ = the CLI's own total_cost_usd (ground-truth cross-check). Both roll up subagent models via `modelUsage`, so the seahorse row includes builder-subagent tokens.
