# Real capacity-grounding diagnostic results

Exploratory, post-hoc development evidence. Three independent worlds; 24 fresh-context calls, zero retries. Same exact models, settings, parser, grader, policies and executor; only the common system clarification changes between arms.

| Model role | Language | Scaffold | Parse | Capacity | Geometry | Strict GOOD | Executor outcomes |
|---|---|---|---:|---:|---:|---:|---|
| primary | EN | original | 3/3 | 3/3 | 3/3 | 3/3 | {'SUCCESS': 3} |
| primary | EN | clarified | 3/3 | 3/3 | 3/3 | 3/3 | {'SUCCESS': 3} |
| primary | VI | original | 3/3 | 3/3 | 3/3 | 3/3 | {'SUCCESS': 3} |
| primary | VI | clarified | 3/3 | 3/3 | 3/3 | 3/3 | {'SUCCESS': 3} |
| replication | EN | original | 3/3 | 2/3 | 3/3 | 2/3 | {'EXECUTOR': 1, 'SUCCESS': 2} |
| replication | EN | clarified | 3/3 | 2/3 | 3/3 | 2/3 | {'EXECUTOR': 1, 'SUCCESS': 2} |
| replication | VI | original | 3/3 | 0/3 | 3/3 | 0/3 | {'EXECUTOR': 3} |
| replication | VI | clarified | 3/3 | 3/3 | 3/3 | 3/3 | {'SUCCESS': 3} |

Matched original→clarified outcomes: {'unchanged': 9, 'improved': 3} across 12 matched conditions nested in three worlds.

| World | Model | Language | Original | Clarified |
|---|---|---|---|---|
| development-006 | primary | EN | GOOD | GOOD |
| development-006 | primary | VI | GOOD | GOOD |
| development-006 | replication | EN | GOOD | GOOD |
| development-006 | replication | VI | PHYSICS | GOOD |
| development-008 | primary | EN | GOOD | GOOD |
| development-008 | primary | VI | GOOD | GOOD |
| development-008 | replication | EN | GOOD | GOOD |
| development-008 | replication | VI | PHYSICS | GOOD |
| development-011 | primary | EN | GOOD | GOOD |
| development-011 | primary | VI | GOOD | GOOD |
| development-011 | replication | EN | PHYSICS | PHYSICS |
| development-011 | replication | VI | PHYSICS | GOOD |

Usage-derived cost: **USD 0.00275160**, not an invoice. Input tokens 8832; output tokens 293; cached input 0. Conservative reservation USD 0.0727584; hard cap USD 0.10.

All 24 saved responses independently regraded and 24 saved executor traces independently rerun with identical results. Failed recommendations remain failures irrespective of replay success. Raw envelopes, actual IDs, prompts and usage are in `attempts.jsonl`; every verdict and trace is in `results.json`.

The first formal P0 remains failed. This diagnostic cannot pass a formal gate, unlock held-out E1 or establish general policy understanding, language superiority or planner superiority. Any new formal gate needs a new frozen binding and separate authorization; no such calls were made.

## Limitations

- Only three post-hoc failure-selected development worlds; not a generalization sample.
- One fresh-context call per arm/condition; repeats may vary even at temperature 0.
- Same single correction was frozen before these new calls; no further prompt selection.
- No R/F conditions were tested here, and this is not a new 144-call P0 gate.
