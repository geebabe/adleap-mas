# Exploratory English development sweep — 4 November 2026

108 real fresh-context calls; 12 existing development families × P0/R/F × three repetitions. Exact pilot snapshot `gpt-4o-mini-2024-07-18`, scaffold, paraphrase 0, settings, strict parser, independent grader and executor `e1-motion-2` were preserved. No prompt/model tuning or core source edits.

**Exploratory development evidence, not a passed formal P0/E1 gate. Held-out E1 remains closed.**

## Policy results

| Policy | Strict GOOD | Rate | Parseable | Physical validity | Cooperation-pattern compliance | First pickup | Token-based USD |
|---|---:|---:|---:|---:|---:|---:|---:|
| P0 | 36/36 | 100.00% | 36/36 | 36/36 | 36/36 | 36/36 | $0.00198120 |
| R | 36/36 | 100.00% | 36/36 | 36/36 | 36/36 | 36/36 | $0.00186840 |
| F | 33/36 | 91.67% | 36/36 | 33/36 | 36/36 | 36/36 | $0.00187380 |

**R/F PairPass: 33/36 = 91.67%.** Independent units are 12 world families, not 108 calls or 36 independent pairs. All three failed pairs belong to one family. A seeded 10,000-resample family-cluster bootstrap gives an exploratory 95% interval [75%, 100%].

Overall: 105/108 strict GOOD; 3 PHYSICS; no FORMAT, VACUOUS, POLICY or INFRA outcomes. All 108 allocations are geometrically feasible. No responses were retried, repaired or discarded.

## World and repetition results

Cell order is P0 / R / F. G = GOOD; PH = PHYSICS (insufficient capacity). Full allocations, raw responses, selected levels and timing for every condition are in `world_repetition_results.csv` and individual JSON files.

| World | Stratum | Rep 1 | Rep 2 | Rep 3 | R/F pairs passed |
|---|---|---|---|---|---:|
| development-000 | light | G / G / G | G / G / G | G / G / G | 3/3 |
| development-001 | light | G / G / G | G / G / G | G / G / G | 3/3 |
| development-002 | light | G / G / G | G / G / G | G / G / G | 3/3 |
| development-003 | light | G / G / G | G / G / G | G / G / G | 3/3 |
| development-004 | light | G / G / G | G / G / G | G / G / G | 3/3 |
| development-005 | light | G / G / G | G / G / G | G / G / G | 3/3 |
| development-006 | mixed | G / G / G | G / G / G | G / G / G | 3/3 |
| development-007 | mixed | G / G / PH | G / G / PH | G / G / PH | 0/3 |
| development-008 | mixed | G / G / G | G / G / G | G / G / G | 3/3 |
| development-009 | mixed | G / G / G | G / G / G | G / G / G | 3/3 |
| development-010 | mixed | G / G / G | G / G / G | G / G / G | 3/3 |
| development-011 | mixed | G / G / G | G / G / G | G / G / G | 3/3 |

## Observed distinct failure

There is **one observed failure type**, repeated three times, not three independent failure types. In `development-007`, F at repetitions 1, 2 and 3 returns the identical raw response:

```json
{"targets":{"A":"b1","B":"b2"}}
```

A has capacity 1.2 and targets b1 (level 0.6); B has capacity 1.4 and targets b2 (level 1.6). b2 is jointly-only because 1.6 exceeds both individual capacities. Assigning only B is insufficient.

Independent flags: format valid=true, capacity feasible=false, geometry feasible=true, progressive=true, F cooperation-pattern compliant=true, strict GOOD=false, status=PHYSICS. Raw responses and complete labels are preserved in conditions 066, 069 and 072.

**Why replay success does not erase this error:** A collects b1 at tick 2, so the first-pickup executor succeeds and stops before resolving B’s infeasible commitment. All 108 replays reach a first pickup, but that does not validate every selected target. Original recommendation labels stay PHYSICS. No substitutions occurred.

## Selected levels and jointly-only coverage

Counts below count each selected box once per recommendation, not once per assigned agent. Level is the simulator’s capacity/weight scale; jointly-only depends on actual agent capacities, not a fixed level-1 threshold.

| Policy | Selected level frequencies | Jointly-only selected | Valid joint-only allocations / pickups |
|---|---|---:|---:|
| P0 | 0.4 × 24; 0.6 × 18; 0.9 × 2 | 0 | 0 / 0 |
| R | 0.4 × 18; 0.6 × 16; 1.0 × 2 | 0 | 0 / 0 |
| F | 0.4 × 33; 0.6 × 36; 1.6 × 3 | 3 | 0 / 0 |

**No recommendation successfully assigns a jointly-only box to both robots, and no jointly-only box is picked up.** The only jointly-only selections are the three invalid solo assignments above. R’s successful cooperation is exclusively on individually liftable boxes; this sweep does not demonstrate competent heavy-box allocation.

## Costs, executor and preservation checks

108 requests, zero retries, no infrastructure errors. Actual usage: **32,652 input tokens, zero cached input tokens, 1,376 output tokens**. At the unchanged configured prices ($0.15/M input, $0.075/M cached input, $0.60/M output), token-derived cost is **$0.00572340**. This is not an invoice. Every attempt reserved at most 10,000 input and 256 output tokens before sending; total reserved upper bound **$0.1785888**, below the hard **$1** cap. No extra smoke, fallback-model, retry or analysis API calls were made.

Executor: 108 first-pickup SUCCESS, zero stalls, zero specification defects, zero substitutions. Each replay was repeated offline and matched its original trace exactly. All source hashes, frozen prompt bytes on overlapping pilot worlds, paired policy-only payload differences and journal integrity were verified. Only the 12 development states were sent to the model; the held-out manifest and all core sources remain unchanged.

Artifacts: `configuration.json`, hash-chained `attempts.jsonl`, all 108 response envelopes and result/replay JSON files, `results.json`, `analysis.json`, `world_repetition_results.csv`, and `VI_POLICIES_FOR_REVIEW.json`. The Vietnamese file preserves exactly the corresponding P0/R1/F1 texts and remains awaiting human semantic approval. No Vietnamese calls were made. Any future tuning requires a separately versioned development experiment.
