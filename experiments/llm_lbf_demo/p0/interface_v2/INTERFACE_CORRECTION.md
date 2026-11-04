# Capacity-grounding interface correction v2

Prepared 4 November 2026. Status: offline audit and fixtures verified; real-model effect unverified. Original failed P0 gate, model snapshots, policy texts and executor are preserved. This is the single proposed development-only interface correction permitted by the E1 specification, not E2 or a new architecture.

## What the evidence establishes

All 144 formal P0 responses were independently regraded. All seven failures returned `{"targets":{"A":"b2","B":null}}`. They occur in three development families: 006, 008 and 011. In each failure, A's capacity is below b2's weight.

The 144 prompt states exactly match the manifest, actual wire requests and reconstructed native environment snapshots. No state serialization error, grading error or simulator defect was found. Upstream `LevelForagingEnv.py`, lines 435–450, sums the capacities of agents issuing LOAD to a task and compares that sum with the task level using `>=`. The independent labels agree.

| Development world | Original bad allocation | Joint-heavy alternative | Solo-light alternative |
|---|---|---|---|
| development-006 | PHYSICS; no pickup in 40 ticks | A/B→b2, pickup in 5 ticks | A→b0, pickup in 2 ticks |
| development-008 | PHYSICS; no pickup in 40 ticks | A/B→b2, pickup in 14 ticks | A→b0, pickup in 5 ticks |
| development-011 | PHYSICS; no pickup in 40 ticks | A/B→b2, pickup in 7 ticks | A→b0, pickup in 5 ticks |

These alternatives are explicitly separate native counterfactual witnesses; they do not replace any recorded model recommendation. All original worlds, seeds, allocations and labels remain intact. The recommendation is already independently capacity-infeasible before its rollout is inspected.

## One narrowly defined correction

Hypothesis: the original scaffold does not explicitly identify `agents[].level` as lifting capacity and `tasks[].level` as required weight. That field ambiguity may contribute to capacity errors. Allocation-only responses cannot identify the internal cause; the audit does not establish that this is the cause.

Version: `p0-capacity-grounding-2`. Append exactly this single common-scaffold clarification to the original system message:

> Numeric field meanings: state.agents[].level is that robot's lifting capacity, and state.tasks[].level is that box's required lifting weight. For every selected box, sum the level values of only the robots assigned to that same box. This sum must be greater than or equal to the box's level. Robots assigned elsewhere or unassigned contribute nothing to that box. These physical rules apply under every supplied policy.

Every original user-message byte is unchanged. The same clarification applies to P0/R/F and both languages. There is no preferred box, ID, solo preference, answer example, feasibility table, hidden label, output repair or action shield. The parser, independent grader, policy texts, upstream environment, model IDs, settings, token budgets and `e1-motion-2` executor are unchanged.

## Frozen diagnostic experiment

- Three worlds: all development families with first-gate capacity errors; this is explicitly post-hoc selection.
- Both original model snapshots, EN and VI P0, original versus clarified scaffold, one fresh-context call per condition.
- 3 worlds × 2 models × 2 languages × 2 scaffold arms = **24 requests**, zero retries.
- Randomized paired arm order and language/model block order, seed 4206. No conversation history.
- Exact models: `gpt-4o-mini-2024-07-18` and `gpt-4.1-mini-2025-04-14`; temperature 0, JSON mode, output limit 256 and standard tier unchanged.
- Hard spending cap **USD 0.10**; conservative reservation for all 24 requests **USD 0.0727584**, assuming up to 10,000 uncached input and 256 output tokens each. No retry costs can occur because retries are disabled.
- Exact prompts, schedule, source hashes and model prices are in `protocol.frozen.json`; protocol hash `cff1f7eb9e83a5109e2067434273d0916b9b2a45df6266ef2e6eb71a15761234`.
- Compare per-box capacity validity and strict goodness for matched scaffold arms; report each model/language separately, with 3 worlds as the independent families. Report all failures, raw responses and native executor diagnoses.
- No formal gate inference, no language ranking, no confidence claim from 24 calls or selection of a best prompt among multiple candidates. This diagnoses a single preregistered clarification.
- Retain all raw responses/failures before scoring. Stop on transport/model-ID/token-contract failure; never silently retry or replace a recommendation.
- No held-out access. Even a successful diagnostic cannot qualify as P0. A subsequent formal gate must use all 12 development worlds and unchanged thresholds, with a new frozen contract and spending authorization. A second formal failure blocks that model/language as specified.

## Offline verification

- Complete suite: **47 tests pass**, including the original 41.
- 1,152 all-allocation label comparisons unchanged; 108 policy-only payload comparisons pass.
- The original final freeze still matches the current v1 source binding; 525 historical files hash-verified unchanged.
- Native original-state replay: three recorded bad allocations fail; all six explicitly counterfactual alternatives succeed.
- Durable fake fixtures: oracle 24 GOOD, idle 24 VACUOUS, malformed 24 FORMAT. These are infrastructure validation only, not model improvements.
- New real LLM calls: **0**. The first formal P0 remains failed; held-out E1 remains blocked.

## Authorization and commands

The earlier approval bound spending to the matched Vietnamese sweep, compatibility smoke and first formal gate. Those phases are complete. It does not authorize this newly versioned 24-call diagnostic. `approval.template.json` is false; old spending approval fails the new guard. After explicit new authorization, record approval matching this exact protocol hash.

From the repository root:

```bash
# Offline tests only
MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python -m unittest discover -s experiments/llm_lbf_demo/tests -v

# Live diagnostic only after matching new approval; fresh output directory
MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python -m experiments.llm_lbf_demo.p0.interface_v2.experiment run --live --approval experiments/llm_lbf_demo/p0/interface_v2/approval.json --output experiments/llm_lbf_demo/p0/interface_v2/evidence/live-001
```

Expected output: `configuration.json`, hash-chained `attempts.jsonl` with exact requests and full provider responses, and `results.json` with independent grades, complete executor traces, actual snapshots, token costs and failures. Credentials are loaded privately from the existing configured environment/.env and never logged.

Pricing sources retained from the verified 4 November configuration: [GPT-4o-mini](https://developers.openai.com/api/docs/models/gpt-4o-mini), [GPT-4.1-mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini). Primary rates are USD 0.15/0.60 per million input/output tokens; replication USD 0.40/1.60. Budget ignores cache discounts. Actual token-based costs are not invoices.
