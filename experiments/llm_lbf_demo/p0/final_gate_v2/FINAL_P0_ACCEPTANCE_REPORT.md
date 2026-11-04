# Second and final formal P0 — acceptance report

Completed 4 November 2026. **All four required P0 conditions passed.**

This is formal attempt 2 using the single previously tested `p0-capacity-grounding-2` clarification. No prompt variant, model, threshold, policy, parser, grader, executor, world or seed was changed in response to these outcomes.

## Verification and execution

- Recorded the user's approval of the exact proposed second/final gate and USD 1.55 cap (smoke USD 0.05; gate USD 1.50), including infrastructure retries.
- Complete offline suite passed: 53 tests, including original recovery/E1/P0 tests and corrected-adapter, fixture, resume, prerequisite and held-out-blocking checks.
- Rechecked official prices on 4 November 2026: [GPT-4o-mini](https://developers.openai.com/api/docs/models/gpt-4o-mini), [GPT-4.1-mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini). Input/output rates remain USD 0.15/0.60 and 0.40/1.60 per million tokens. Budgets reserve uncached input and all allowed retries.
- Four new development-only smoke calls succeeded with exact snapshots/settings. Smoke outcomes remain separate from the formal gate.
- Created a new final freeze after smoke and before formal calls. SHA-256 `f606710ae1b6509bf22ee68d9bc0b75bd34d4f512b1219cb1c7c4411e14c4087`.
- Completed every one of the 144 formal slots: all 12 development worlds, both languages, both models and three fresh-context repetitions. Exact schedule and prompts retained in `REQUEST_SCHEDULE.json`; all responses and failures retained in hash-chained journals.
- Independently regraded all saved responses and reran all applicable executor traces with exact matches. Verified policy-only language comparisons, frozen bindings and 525 historical-file hashes. Existing 864/864 witness evidence is still accepted; this is not a newly generated witness batch.

## Formal results

Each model/language row has 36 calls. Required thresholds: parseability >=98% (36/36), physical validity >=95% (35/36), progressive goodness >=80% (29/36). Capacity and geometry are independent recommendation labels; rollout success never changes them.

| Exact model snapshot | Language | Parse | Capacity | Geometry | Progressive GOOD | Infra attempts | Token cost USD | Result |
|---|---|---:|---:|---:|---:|---:|---:|---|
| gpt-4o-mini-2024-07-18 | EN | 36/36 | 36/36 | 36/36 | 36/36 | 0 | 0.00242700 | PASS |
| gpt-4o-mini-2024-07-18 | VI | 36/36 | 36/36 | 36/36 | 36/36 | 0 | 0.00251640 | PASS |
| gpt-4.1-mini-2025-04-14 | EN | 36/36 | 35/36 | 36/36 | 35/36 | 0 | 0.00647520 | PASS |
| gpt-4.1-mini-2025-04-14 | VI | 36/36 | 36/36 | 36/36 | 36/36 | 0 | 0.00671520 | PASS |

All outcomes remain in their original denominators. The independent unit is the development world (12 families), not the 144 requests. Gate thresholds are engineering floors, not proof of general policy understanding.

## Every remaining recommendation failure

| Model | Language | World | Repeat (0-based) | Raw response | Capacity calculation |
|---|---|---|---:|---|---|
| gpt-4.1-mini-2025-04-14 | EN | development-011 | 0 | `{"targets":{"A":"b2","B":null}}` | A: 1.4 < 1.6 (b2) |

All failures have exact prompts, native states, raw outputs and independent labels in `runs/gate-002/FAILURE_EXAMPLES.json`. Physically invalid recommendations are not replayed by the frozen formal protocol; they remain failures, not missing data.

## First versus second gate

| Model | Language | First physical validity | Second physical validity | Second result |
|---|---|---:|---:|---|
| gpt-4o-mini-2024-07-18 | EN | 36/36 | 36/36 | PASS |
| gpt-4o-mini-2024-07-18 | VI | 36/36 | 36/36 | PASS |
| gpt-4.1-mini-2025-04-14 | EN | 34/36 | 35/36 | PASS |
| gpt-4.1-mini-2025-04-14 | VI | 31/36 | 36/36 | PASS |

These are repeated development evaluations after a documented correction, not held-out causal estimates or a model leaderboard. The failed first gate is preserved.

## Spending and stopping decision

| Phase | Provider attempts | Regraded | Replayed | Token cost USD | Durable reservation USD |
|---|---:|---:|---:|---:|---:|
| smoke | 4 | 4 | 4 | 0.00050325 | 0.0121264 |
| gate | 144 | 144 | 143 | 0.01813380 | 0.4365504 |

Total observed usage-derived cost: **USD 0.01863705**, within the separately authorized USD 1.55 cap; total durable reservation approximately USD 0.4486768. These are token-based costs, not invoices. Unknown-cost failed attempts, if any, are separately reserved and reported rather than treated as free.

All required conditions passed. Held-out E1 has no spending authorization and was not run; prepare its separate finite budget and frozen matching transport contract before launch.

No held-out worlds were sent to a provider. No full-episode controller, new architecture or graphics work was added.

## Artifacts and reproduction

- `live.proposed.json`, `PREREGISTRATION.json`, `spending-approval.json`, `REQUEST_SCHEDULE.json`: unchanged settings, authorization, schedule and exact prompts.
- `live.final.freeze.json`: final corrected binding and successful real smoke evidence.
- `runs/smoke-002/SMOKE_REPORT.json`: separate model/language compatibility results.
- `runs/gate-002/P0_REPORT.json`, `conditions.csv`, `FAILURE_EXAMPLES.json`: all formal outcomes and cost by condition.
- `runs/*/attempts.jsonl` and `replays/*.json`: durable exact wire requests, complete provider envelopes, usage and simulator traces.
- `FINAL_VERIFICATION.json`, `PROTOCOL_STATUS.json`: independent verification and stopping decision.
- `RUNNER_PROVENANCE.json`, `evidence/runner.patch`, `tests-before-live.txt`: versioned adapter integration and complete test evidence.

Actual live commands (completed; compatible resume uses the SAME output directory):

```bash
MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python -m experiments.llm_lbf_demo.p0.final_gate_v2.live smoke --live --proposal experiments/llm_lbf_demo/p0/final_gate_v2/live.proposed.json --spending-approval experiments/llm_lbf_demo/p0/final_gate_v2/spending-approval.json --human-approval experiments/llm_lbf_demo/p0/human-approval.json --output experiments/llm_lbf_demo/p0/final_gate_v2/runs/smoke-002
MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python -m experiments.llm_lbf_demo.p0.final_gate_v2.live gate --live --proposal experiments/llm_lbf_demo/p0/final_gate_v2/live.proposed.json --final-config experiments/llm_lbf_demo/p0/final_gate_v2/live.final.freeze.json --spending-approval experiments/llm_lbf_demo/p0/final_gate_v2/spending-approval.json --human-approval experiments/llm_lbf_demo/p0/human-approval.json --output experiments/llm_lbf_demo/p0/final_gate_v2/runs/gate-002
```

Free offline test command:

```bash
MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python -m unittest discover -s experiments/llm_lbf_demo/tests -v
```
