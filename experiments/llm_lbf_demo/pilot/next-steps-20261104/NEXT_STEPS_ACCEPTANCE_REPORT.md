# Authorized next steps — completion and acceptance report

Completed 4 November 2026. **Formal P0 completed but FAILED overall. Held-out E1 remains BLOCKED.** No held-out model calls were made.

## Completed requirements

- Recorded the user's explicit approval of all EN/VI meanings and the combined USD 2.55 cap in `USER_APPROVAL.json`; policy bytes remain unchanged. External human/spending records are stored separately.
- Completed the matched Vietnamese exploratory development sweep: 108/108 GOOD, R/F PairPass 36/36, all first-pickup replays successful, zero retries. English remains 33/36 PairPass; the 12 worlds, rather than calls/repetitions, are the independent families.
- Completed four separate development-only compatibility calls: both exact models and both languages accepted the frozen settings and returned the requested snapshot IDs. Smoke is not part of the formal gate.
- Froze the final P0 configuration AFTER real smoke and BEFORE all formal calls. Freeze SHA-256: `fda3e1522e788ed3df20e62b2fd0d6d7a71a64a8b073c05d95b05d677126946b`.
- Completed the entire formal 144-call randomized, language-interleaved P0 schedule. No worlds or failed responses dropped. No retries, fallback model, prompt/threshold changes or recommendation substitutions.
- Independently regraded all 256 new responses. Independently reran 108 VI, 4 smoke and 137 valid formal replays. All replay records match. The seven invalid formal recommendations remain failures in their 36-call denominators and were not executed by the frozen formal runner.
- Verified unchanged frozen source hashes and 864/864 existing executor witness records. These are verification of saved witness evidence, not a newly generated 864-rollout batch.

## Formal P0 result

Each row contains 36 calls. Parseability, geometric validity and progressive goodness are separate measurements. Physical validity requires both capacity and geometry. Thresholds: parseability >=98%, physical validity >=95%, goodness >=80%; with 36 calls, these require 36, 35 and 29 successes respectively.

| Exact snapshot | Language | Parse | Capacity / physical | Geometry | Progressive GOOD | Infra | Cost USD | Result |
|---|---|---:|---:|---:|---:|---:|---:|---|
| gpt-4o-mini-2024-07-18 | EN | 36/36 | 36/36 | 36/36 | 36/36 | 0 | 0.00198000 | PASS |
| gpt-4o-mini-2024-07-18 | VI | 36/36 | 36/36 | 36/36 | 36/36 | 0 | 0.00206820 | PASS |
| gpt-4.1-mini-2025-04-14 | EN | 36/36 | 34/36 | 36/36 | 34/36 | 0 | 0.00528800 | FAIL |
| gpt-4.1-mini-2025-04-14 | VI | 36/36 | 31/36 | 36/36 | 31/36 | 0 | 0.00552480 | FAIL |

Both GPT-4.1-mini conditions fail the physical-validity threshold. All 144 responses were parseable; no infrastructure failures or unknown-cost attempts occurred. Geometry was feasible for all allocations. There were 137 GOOD and 7 PHYSICS outcomes, no POLICY/FORMAT/VACUOUS/SPEC outcomes. All 137 valid replays reached a first pickup; no executor failures or substitutions occurred.

## All seven failures

These are capacity-infeasible recommendations, independently checked against the numeric state, not rollouts that happened to stall. Allocation-only outputs do not reveal whether the internal cause was arithmetic, grounding or interpretation. No simulator/spec defect was found. Every failure and exact prompt/raw response is retained in `../../p0/runs/gate-001/FAILURE_EXAMPLES.json`.

| Model role | Language | World | Repeat (0-based) | Raw response | Insufficient capacity |
|---|---|---|---:|---|---|
| replication | VI | development-006 | 0 | `{"targets":{"A":"b2","B":null}}` | A: 1.0 < 1.2 (b2) |
| replication | VI | development-008 | 2 | `{"targets":{"A":"b2","B":null}}` | A: 1.0 < 1.2 (b2) |
| replication | VI | development-006 | 1 | `{"targets":{"A":"b2","B":null}}` | A: 1.0 < 1.2 (b2) |
| replication | VI | development-011 | 2 | `{"targets":{"A":"b2","B":null}}` | A: 1.4 < 1.6 (b2) |
| replication | EN | development-011 | 2 | `{"targets":{"A":"b2","B":null}}` | A: 1.4 < 1.6 (b2) |
| replication | VI | development-006 | 2 | `{"targets":{"A":"b2","B":null}}` | A: 1.0 < 1.2 (b2) |
| replication | EN | development-011 | 1 | `{"targets":{"A":"b2","B":null}}` | A: 1.4 < 1.6 (b2) |

## Costs and remaining blockers

| New phase | Requests | Observed token cost USD | Authorized phase cap USD |
|---|---:|---:|---:|
| Vietnamese development | 108 | 0.00590340 | 1.00 |
| Separate compatibility smoke | 4 | 0.00041195 | 0.05 |
| Formal P0 | 144 | 0.01486100 | 1.50 |
| Total under this authorization | 256 | **0.02117635** | **2.55** |

Costs apply the frozen verified prices to actual token usage; they are not invoices. No retries. Total durable reservation was approximately USD 0.6272656. All caps included permitted retries; none were needed. Official price sources: [GPT-4o-mini](https://developers.openai.com/api/docs/models/gpt-4o-mini), [GPT-4.1-mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini).

Human semantic review and account-level provider compatibility are now verified for this configuration. Overall real P0 performance is verified **below the required floor** because the replication model fails in both languages. The primary model passed both conditions, but this does not authorize removing the replication conditions from the frozen protocol.

Held-out E1 remains blocked by the failed required P0 gate and has no spending authorization. No prompt, model or threshold was changed after results. The full-episode extension remains deferred.

The next permissible research step is a documented, separately versioned development-only interface correction if warranted by the capacity errors, followed by a new frozen P0 gate. The specification allows one such correction; this report does not perform it, assert that it will fix the model, or authorize another paid run. Retain this failed gate as evidence.

## Artifacts and reproduction

- `FINAL_VERIFICATION.json`: independent grades/replays, counts, costs, unchanged bindings and blocked held-out status.
- `../../p0/live.final.freeze.json`: final immutable-by-hash settings and smoke binding.
- `../../p0/runs/smoke-001/SMOKE_REPORT.json`: separate compatibility report.
- `../../p0/runs/gate-001/P0_REPORT.json` and `GATE_ACCEPTANCE.json`: formal four-condition results and matching gate binding.
- `../../p0/runs/gate-001/attempts.jsonl`: hash-chained exact prompts, all raw provider envelopes, usage and terminal labels.
- `../vietnamese-development-sweep-20261104-01/`: all 108 raw responses, allocations, grades, traces, CSV and matched EN/VI analysis.
- `tests-final.txt`: complete offline test suite output (41 tests).

Executed commands from repository root (do not rerun paid phases in a new directory to repeat them):

```bash
MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python experiments/llm_lbf_demo/pilot/next-steps-20261104/run_vietnamese_sweep.py --approval experiments/llm_lbf_demo/pilot/next-steps-20261104/vietnamese-approval.json
MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python experiments/llm_lbf_demo/pilot/next-steps-20261104/analyze_vietnamese_sweep.py
MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python experiments/llm_lbf_demo/pilot/next-steps-20261104/execute_p0_authorized.py smoke --output experiments/llm_lbf_demo/p0/runs/smoke-001
MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python -m experiments.llm_lbf_demo.p0.prepare freeze --human-approval experiments/llm_lbf_demo/p0/human-approval.json --smoke-journal experiments/llm_lbf_demo/p0/runs/smoke-001/attempts.jsonl --output experiments/llm_lbf_demo/p0/live.final.freeze.json
MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python experiments/llm_lbf_demo/pilot/next-steps-20261104/execute_p0_authorized.py gate --final-config experiments/llm_lbf_demo/p0/live.final.freeze.json --output experiments/llm_lbf_demo/p0/runs/gate-001
```

Free offline suite command:

```bash
MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python -m unittest discover -s experiments/llm_lbf_demo/tests -v
```

The verifier/analyzers use exclusive creation for their report outputs. Preserve existing outputs; for a fresh audit, direct them to copies rather than deleting evidence. Configured credentials were loaded privately and never written to artifacts.
