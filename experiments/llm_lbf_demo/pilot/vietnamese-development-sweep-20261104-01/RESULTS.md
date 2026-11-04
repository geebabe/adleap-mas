# Matched Vietnamese development sweep — exploratory evidence

Completed 4 November 2026 after explicit human semantic and spending approval. Same model snapshot, prompt scaffold, parser, grader, executor and worlds as the English sweep; only the policy field changes language. No prompt tuning.

Model: `gpt-4o-mini-2024-07-18`. Executor: `e1-motion-2`. Twelve independent development families, three fresh-context repetitions per policy. No held-out calls.

| Policy | Strict GOOD | Parseable | Capacity valid | Geometry valid | First pickup | Token cost USD |
|---|---:|---:|---:|---:|---:|---:|
| P0 | 36/36 | 36/36 | 36/36 | 36/36 | 36/36 | 0.00206820 |
| R | 36/36 | 36/36 | 36/36 | 36/36 | 36/36 | 0.00192780 |
| F | 36/36 | 36/36 | 36/36 | 36/36 | 36/36 | 0.00190740 |

R/F PairPass: **36/36** versus English **33/36**. All Vietnamese world/repetition cells are GOOD/GOOD/GOOD (P0/R/F). The entire observed difference is development-007: EN 0/3 paired passes, VI 3/3. Other worlds are 3/3 in both languages.

The paired family bootstrap interval for VI minus EN is [0, 0.25], using 12 families and 10,000 resamples (seed 20261104). This does not establish a general language advantage. Collection was sequential by language rather than randomized across languages. The VI-only bootstrap [1,1] is degenerate; it is not evidence of certainty. As a separate boundary summary, 12/12 worlds passed all three R/F pairs; a two-sided exact binomial interval for that family event is [0.735352, 1].

No recommendation selected a jointly-only box. These successes do not demonstrate cooperative collection of boxes that require combined capacity. No malformed responses, idle allocations, capacity failures, infrastructure failures, executor stalls, substitutions or SPEC defects were observed in this VI sweep.

| Policy | Selected box levels (box counted once per recommendation) |
|---|---|
| P0 | 0.4: 21, 0.6: 12, 0.9: 3 |
| R | 0.4: 16, 0.6: 18, 1.0: 2 |
| F | 0.4: 25, 0.6: 13 |

Actual token usage: 34020 input, 1334 output, 0 cached input. Usage-derived cost **USD 0.00590340**, not an invoice. Exactly 108 requests, zero retries; durable reservation USD 0.1785888 under the USD 1 cap.

All raw envelopes, prompts and per-call grades/replays are retained. See `results.json`, `analysis.json`, `EN_VI_COMPARISON.json` and `world_repetition_results.csv`. This is not a formal E1 gate result.
