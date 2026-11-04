# Capacity diagnostic acceptance report

Completed 4 November 2026. **The clarification did not eliminate capacity errors. The original formal P0 remains failed and held-out E1 remains blocked.**

## Completed work

- Regraded all 144 first-gate responses, verified every state through manifest → wire prompt → native environment, and checked the native LOAD capacity inequality. No serialization, grader or simulator defect was found.
- Reproduced the bad allocation on all three affected original worlds: no pickup in 40 ticks. Verified six explicitly counterfactual compliant alternatives with successful real-simulator pickups; no recorded recommendation was replaced.
- Added one separately versioned common-scaffold clarification (`p0-capacity-grounding-2`) defining `agents[].level` as capacity, `tasks[].level` as weight, and the per-box capacity inequality. All original user-message bytes, policies, parser, grader, executor and exact model/settings contracts are unchanged.
- Froze 24 matched diagnostic prompts before new calls. Recorded the user's separate USD 0.10 authorization. Completed all 24 real requests with fresh context and zero retries.

| Exact model | Language | Original GOOD | Clarified GOOD |
|---|---|---:|---:|
| gpt-4o-mini-2024-07-18 | EN | 3/3 | 3/3 |
| gpt-4o-mini-2024-07-18 | VI | 3/3 | 3/3 |
| gpt-4.1-mini-2025-04-14 | EN | 2/3 | 2/3 |
| gpt-4.1-mini-2025-04-14 | VI | 0/3 | 3/3 |

All 24 responses were parseable and geometrically feasible. Capacity errors account for all five failures; original arm 4 failures, clarified arm 1 failure. Native execution succeeded for all 19 GOOD outputs and failed to collect for all 5 capacity-infeasible outputs. Independent recommendation labels were not derived from these rollout outcomes. There were no infrastructure failures, substitutions or SPEC defects.

The clarified replication/English failure remains `{"targets":{"A":"b2","B":null}}` on development-011: A has capacity 1.4 and b2 requires 1.6. This still violates the explicit instruction. The internal reason cannot be inferred from an allocation-only response.

The three improved matched conditions were replication/VI on worlds 006, 008 and 011. They now selected light boxes (solo b0, solo b1, or joint b1), so this does not demonstrate competence at jointly-only heavy-box collection.

## Evidence and scientific limits

- Three independent worlds, selected post-hoc because they failed the first gate; the 24 calls are not 24 independent families.
- One fresh-context observation per arm/model/language/world. The matched baseline reruns help expose repetition variability, but this small diagnostic establishes neither general reliability nor language superiority.
- No further prompt variant was selected or tuned using these results. The original first-gate failures and all historical evidence remain intact.
- All 24 responses independently regraded and 24 traces independently rerun with identical results. All 47 offline tests pass. 1,152 label-invariance checks and 108 policy-only payload checks passed; 525 historical files hash-verified unchanged.
- Fake oracle/idle/malformed runs remain explicitly infrastructure-only (24 GOOD / 24 VACUOUS / 24 FORMAT). They are not real-model evidence.

## Spending and status

New diagnostic cost: **USD 0.00275160** at actual token usage (8,832 input; 293 output; no cached input). Conservative reservation USD 0.0727584, within the separately authorized USD 0.10 cap. This is a token-based estimate, not an invoice.

No second formal gate and no held-out calls were run. This diagnostic does not replace P0 or relax its thresholds. The primary model's prior formal pass remains recorded, but the required replication conditions still block the complete protocol.

Remaining decision: whether to spend the permitted second formal P0 attempt on this unchanged clarification, despite the persistent English failure, or explicitly amend the research protocol. Do not silently remove a model, weaken the physical-validity threshold, or continue broad prompt search. Any new formal attempt needs a new frozen binding and explicit phase budget; a second formal failure blocks that model/language under the existing specification.

## Artifacts

- `protocol.frozen.json`: exact 24 prompts, randomized schedule, model settings and source hashes.
- `approval.json`: actual new diagnostic spending approval.
- `evidence/audit-001/AUDIT.json`: complete state/label audit and native counterfactual traces.
- `evidence/live-001/attempts.jsonl`: all exact wire requests, raw envelopes, actual model IDs, usage and latency.
- `evidence/live-001/results.json`: all independent labels and full executor traces.
- `evidence/live-001/ANALYSIS.json`, `conditions.csv`, `RESULTS.md`: per-world and matched-arm findings, including all failure examples.
- `evidence/live-001/VERIFICATION.json`: independent verification, cost and blocked-gate status.
- `tests-final.txt`: complete 47-test output.

Protocol hash: `cff1f7eb9e83a5109e2067434273d0916b9b2a45df6266ef2e6eb71a15761234`. The original v1 final freeze remains valid and unchanged.
