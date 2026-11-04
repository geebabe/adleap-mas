# Real conditional-policy development pilot

Completed 5 November 2026 using the reviewed EN/VI conditional policy and separately approved USD 0.15 cap. **Exploratory development evidence, not formal E1 or a causal complexity experiment.**

Model: `gpt-4o-mini-2024-07-18`. The exact final capacity clarification, JSON schema/parser, physical predicates and `e1-motion-2` executor were preserved. All original 12 development worlds were retained, with the same worlds in both languages and three fresh-context repetitions. No held-out calls, output repair or target substitution.

## Goodness by branch and language

Each row has 18 calls from six independent worlds. Format/capacity/policy failure flags are reported separately and can overlap; repeated calls are not independent worlds.

| Branch | Language | Strict GOOD | Rate | Format failures | Capacity failures | Geometry failures | Policy failures | Native first pickups | Conditional pickup violations |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| solo_required | EN | 11/18 | 61.1% | 0 | 0 | 0 | 7 | 18 | 7 |
| solo_required | VI | 0/18 | 0.0% | 0 | 0 | 0 | 18 | 18 | 18 |
| joint_required | EN | 15/18 | 83.3% | 0 | 3 | 0 | 3 | 18 | 3 |
| joint_required | VI | 17/18 | 94.4% | 0 | 0 | 0 | 1 | 18 | 1 |

Geometry and progress remain independent of conditional policy compliance. A successful native pickup never changes a failed recommendation label. Infrastructure errors and remaining NOT_RUN slots, if present, are retained in all original denominators.

## Every world and repetition

| World | Branch | EN repetitions 1 / 2 / 3 | VI repetitions 1 / 2 / 3 |
|---|---|---|---|
| development-000 | solo_required | POLICY / GOOD / GOOD | POLICY / POLICY / POLICY |
| development-001 | solo_required | GOOD / GOOD / GOOD | POLICY / POLICY / POLICY |
| development-002 | solo_required | GOOD / GOOD / GOOD | POLICY / POLICY / POLICY |
| development-003 | solo_required | POLICY / POLICY / POLICY | POLICY / POLICY / POLICY |
| development-004 | solo_required | GOOD / GOOD / GOOD | POLICY / POLICY / POLICY |
| development-005 | solo_required | POLICY / POLICY / POLICY | POLICY / POLICY / POLICY |
| development-006 | joint_required | GOOD / GOOD / GOOD | GOOD / GOOD / GOOD |
| development-007 | joint_required | PHYSICS / PHYSICS / PHYSICS | GOOD / GOOD / POLICY |
| development-008 | joint_required | GOOD / GOOD / GOOD | GOOD / GOOD / GOOD |
| development-009 | joint_required | GOOD / GOOD / GOOD | GOOD / GOOD / GOOD |
| development-010 | joint_required | GOOD / GOOD / GOOD | GOOD / GOOD / GOOD |
| development-011 | joint_required | GOOD / GOOD / GOOD | GOOD / GOOD / GOOD |

All 72 individual allocations, raw responses, independent flags, native outcomes, latency and cost are in `world_repetition_results.csv`. Full prompts/envelopes are in `attempts.jsonl`; complete traces and pickup audits are in `results.json`.

## Jointly-only boxes

| Branch | Language | Recommendations selecting a jointly-only box | Actual jointly-only pickups |
|---|---|---:|---:|
| solo_required | EN | 0 | 0 |
| solo_required | VI | 0 | 0 |
| joint_required | EN | 18 | 15 |
| joint_required | VI | 17 | 17 |

The joint branch requires both robots to target a jointly-only, jointly-feasible box; cooperation on a light box alone does not satisfy it. All mixed development worlds have b2 as the unique qualifying box.

## Retained failures

All failures are retained without repair in `FAILURE_EXAMPLES.json`.

1. development-000, EN, repetition 1: `{"targets":{"A":"b1","B":"b1"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
2. development-000, VI, repetition 1: `{"targets":{"A":"b1","B":"b1"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
3. development-004, VI, repetition 2: `{"targets":{"A":"b1","B":"b1"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
4. development-003, VI, repetition 1: `{"targets":{"A":"b2","B":"b2"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
5. development-003, EN, repetition 1: `{"targets":{"A":"b2","B":"b2"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
6. development-000, VI, repetition 2: `{"targets":{"A":"b1","B":"b1"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
7. development-003, VI, repetition 3: `{"targets":{"A":"b2","B":"b2"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
8. development-003, EN, repetition 3: `{"targets":{"A":"b2","B":"b2"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
9. development-002, VI, repetition 3: `{"targets":{"A":"b1","B":"b1"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
10. development-005, VI, repetition 3: `{"targets":{"A":"b2","B":"b2"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
11. development-005, EN, repetition 3: `{"targets":{"A":"b2","B":"b2"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
12. development-007, EN, repetition 1: `{"targets":{"A":"b1","B":"b2"}}`; label `PHYSICS`; failure flags `{'format': False, 'capacity': True, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
13. development-001, VI, repetition 3: `{"targets":{"A":"b0","B":"b0"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
14. development-002, VI, repetition 1: `{"targets":{"A":"b1","B":"b1"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
15. development-004, VI, repetition 1: `{"targets":{"A":"b1","B":"b1"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
16. development-001, VI, repetition 2: `{"targets":{"A":"b0","B":"b0"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
17. development-002, VI, repetition 2: `{"targets":{"A":"b1","B":"b1"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
18. development-005, EN, repetition 1: `{"targets":{"A":"b2","B":"b2"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
19. development-005, VI, repetition 1: `{"targets":{"A":"b2","B":"b2"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
20. development-007, EN, repetition 2: `{"targets":{"A":"b1","B":"b2"}}`; label `PHYSICS`; failure flags `{'format': False, 'capacity': True, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
21. development-001, VI, repetition 1: `{"targets":{"A":"b0","B":"b0"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
22. development-003, VI, repetition 2: `{"targets":{"A":"b2","B":"b2"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
23. development-003, EN, repetition 2: `{"targets":{"A":"b2","B":"b2"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
24. development-000, VI, repetition 3: `{"targets":{"A":"b1","B":"b1"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
25. development-004, VI, repetition 3: `{"targets":{"A":"b1","B":"b1"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
26. development-007, EN, repetition 3: `{"targets":{"A":"b1","B":"b2"}}`; label `PHYSICS`; failure flags `{'format': False, 'capacity': True, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
27. development-007, VI, repetition 3: `{"targets":{"A":"b1","B":"b1"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
28. development-005, VI, repetition 2: `{"targets":{"A":"b2","B":"b2"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.
29. development-005, EN, repetition 2: `{"targets":{"A":"b2","B":"b2"}}`; label `POLICY`; failure flags `{'format': False, 'capacity': False, 'geometry': False, 'progress': False, 'policy': True, 'specification': False}`.

## Verification and spending

Exactly 72 API requests, 72 responses and 72 terminal slots; zero retries. All 72 saved responses were independently regraded; 72 saved simulator traces and conditional pickup audits independently rerun with identical results. A separate arithmetic/pattern check verified 72 branch labels and 72 policy labels. All 1141 historical files still match their preservation hashes. The unchanged source passed all 62 tests before live execution.

Actual token usage: 29448 input, 936 output, 0 cached input. Usage-derived cost: **USD 0.00497880**, not an invoice. Conservative reservation: **USD 0.1190592**, below the **USD 0.15** hard cap. Unknown-cost attempts: 0. Exact model/settings matched the approved frozen protocol.

## Interpretation limits

- Twelve independent development worlds; six per branch. Three repetitions do not multiply the independent sample size.
- Joint-branch worlds are the mixed group and solo-branch worlds are the light group. Branch comparisons confound layout/weights with the required branch.
- This pilot tests conditional-policy application. It does not isolate a causal complexity effect, establish general policy understanding or novelty, or compare planners.
- No held-out E1 or full-episode controller was run. The conditional pilot does not replace the original formal P0/E1 protocol.

## Executed commands

```bash
MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python -m experiments.llm_lbf_demo.conditional_pilot.pilot run --live --approval experiments/llm_lbf_demo/conditional_pilot/approval.json --output experiments/llm_lbf_demo/conditional_pilot/evidence/live-001
MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python -m experiments.llm_lbf_demo.conditional_pilot.pilot report --output experiments/llm_lbf_demo/conditional_pilot/evidence/live-001
```

These commands completed; existing output is preserved and the runner refuses to repeat it. Regrading/replay requires no API calls.
