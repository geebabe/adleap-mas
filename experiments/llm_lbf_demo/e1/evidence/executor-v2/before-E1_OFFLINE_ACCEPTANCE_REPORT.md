# E1 offline acceptance — 4 November 2026

**Offline harness implemented and verified; live launch blocked.** These are
scripted infrastructure results, not model findings. No paid/live calls were made.

## Completed requirements

- Amended the local E1 spec: EN/VI P0 physical rules and progress requirement;
  independent capacity/geometric labels; separate executor outcomes; restricted
  scientific claims. Original spec preserved in `evidence/SPEC_BEFORE_E1_AMENDMENT.md`.
- Strict parser, independent 16-allocation oracle, targets-only snapshot adapter,
  separate presented/gold policies and identical non-policy scaffold. No solo
  preference, hidden grader fields, rationale grading or output repair.
- Frozen seed 20261104: **12 development + 60 held-out families**, test strata
  **30 light / 30 mixed**. Reproduction, split integrity, ID/symmetry/translation
  duplicate rejection and nonempty/disjoint good sets verified.
- **28 tests pass: 19 new E1 + all 9 preserved recovery tests.** They cover parser,
  physics/geometry, alternative allocations, native action/wait/LOAD semantics,
  failed joint attempts, label/payload controls, stalls, retries, durable responses,
  compatible resume, integrity failures, gate thresholds and live/cost safeguards.
- Hash-chained, fsynced attempt/response/terminal logging; raw responses survive
  grading crashes. Completed requests are not repeated; uncertain in-flight calls
  require reconciliation. Infrastructure retries are bounded; bad content never retries.
- PairPass, strict denominators, per-policy marginals, strata and paired VI−EN
  analysis; **10,000 family-cluster bootstrap resamples** with boundary flags and
  a separate exact all-variants family-pass interval. INFRA/SPEC leave reports incomplete.

## Complete dry runs

Each fixture finished **144 P0 + 2,880 E1 = 3,024 slots**. Total: **12,096 fake
requests; zero API calls**. Each has 1,440 R/F pairs: 720 per model role and 360
per role/language, over 60 independent held-out families.

| Fixture | PairPass, both model roles | Terminal outcomes |
|---|---:|---|
| Policy-aware oracle | 1 | 3,024 GOOD |
| Unchanged deterministic blind | 0 | 1,584 GOOD; 1,440 POLICY |
| Idle | 0 | 3,024 VACUOUS |
| Malformed | 0 | 3,024 FORMAT |

All actual paired payloads passed policy-only difference checks. Holding gold
fixed while reversing it relative to oracle responses yielded **2,880 POLICY
rejections**. Every full run resumed without changing journal bytes or calling
its provider. Fake P0 gates cannot authorize real E1. Degenerate fixture intervals
are flagged; the oracle's distinct all-variants family event has exact 95% interval
[0.9404, 1]. This is not evidence of model reliability or language equivalence.

Evidence: `evidence/tests-final.txt`, `offline-verification-final.json`, and
`dry-*/analysis.json`, journals and replay traces, all under `evidence/`.

## Remaining blockers and P0 readiness

**Executor witnesses: 864/864 covered, 863/864 successful.** On `test-006`, A→b0,
B→b2, simulator seed 20261122, the unchanged executor cycles between positions
[(3,2),(3,3)] and [(2,2),(2,3)] without pickup in 40 ticks. The recommendation
remains capacity-feasible, geometrically feasible and GOOD under F; replay is
EXECUTOR separately. The world is retained and the failure regression-tested.
All nine progressive, feasible hand-fixture allocations replay successfully.

A future paid P0 gate is **not ready** until the conventional executor regression
is resolved and witnesses revalidated, a human approves the frozen EN/VI policies,
and exact model snapshots/settings, verified prices, explicit permission and a
finite dollar ceiling are configured. The recovered executor was preserved as
requested. Live preflight blocks on its known failure. Real transport/model
availability and actual P0 thresholds remain unverified.

Live safeguards reserve worst-case tokens plus two infrastructure retries per
slot and enforce durable cost bounds. Held-out E1 additionally requires a matching
passed **real** gate journal; this implementation conservatively blocks the full
confirmatory launch if any model/language gate fails. No model/world substitution.

## Reproduce

From repository root after the parent README's pinned setup:

```bash
export MPLCONFIGDIR=/private/tmp/policy2action-mpl
experiments/llm_lbf_demo/.venv/bin/python -m unittest discover -s experiments/llm_lbf_demo/tests -v
experiments/llm_lbf_demo/.venv/bin/python experiments/llm_lbf_demo/tests/verify_e1_evidence.py
```

See README.md for fresh full dry-run, analysis and witness-generation commands.
Upstream `src/`, recovered implementation and historical evidence remain unchanged.
