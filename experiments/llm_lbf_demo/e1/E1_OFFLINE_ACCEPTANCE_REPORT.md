# E1 offline acceptance — executor v2 update, 4 November 2026

**Executor regression resolved; all 864 witnesses pass. No live/paid experiments
were run.** Model/provider availability, bilingual approval and real P0 performance
remain explicitly unverified. Previous E1 dry-run results are infrastructure
validation, not model findings.

## Cause and minimal patch

The recorded `test-006` allocation A→b0/B→b2, seed **20261122**, exactly reproduced
the original 40-tick failure, including trace hash. From tick 2, both robots moved
West/East together between [(3,2),(3,3)] and [(2,2),(2,3)]. Each A* plan treated the
other robot's current cell as stationary; concurrent movement across separate
target groups invalidated that assumption and repeatedly reversed the next move.

`e1-motion-2` adds one general arbitration step: at most one directional command
per tick, chosen by stable agent-ID priority. Other directional commands become
explicit `None` waits. LOAD commands—including synchronized joint LOAD—are
preserved. No family/seed/coordinate tests, target substitutions, policy changes,
new planner, task selection, simulator edits or LLM calls were added. The recovered
A* executor remains unchanged; the E1 bridge coordinates its proposed actions.
Every proposed action, executed action and yielded motion is logged.

Version/source hashes bind witness acceptance, replay caches and run metadata.
Old witnesses cannot certify v2; old run journals cannot resume under changed code.

## Verified results

| Check | Before | After |
|---|---:|---:|
| Recorded regression | EXECUTOR, 40 ticks, no pickup | SUCCESS, pickup at tick 7 |
| Witness coverage | 864/864 | 864/864 |
| Successful witnesses | 863/864 | **864/864** |
| Remaining witness failures | 1 | **0** |

All 72 worlds and every allocation/seed are retained. Across the 864 comparisons,
741 first-pickup times are unchanged, 117 are longer and 6 are shorter. This is a
conservative coordination correction, not an optimality or arbitrary-layout
liveness guarantee.

**32 tests pass**, including all nine original tests. Added checks cover LOAD/wait
preservation, proposal immutability, translated/renamed/alternate-seed regressions,
stale witness certificates and stale replay caches. The legacy regression still
reproduces with the old navigator; the new default succeeds.

The 864 witness recommendation labels are identical. All **12,096** historical
fixture responses regrade identically; all **5,760** actual policy-only R/F payload
pairs still pass. Oracle PairPass remains 1; blind/idle/malformed remain 0 in their
preserved historical analyses. No new inference was needed for those checks.
Hash verification confirms **292** historical evidence/frozen files unchanged,
including the manifest, policies, independent oracle, controller and recovered
executor. The previous acceptance report and modified executor sources were
archived before editing.

## Evidence and reproduction

Current artifacts are under `evidence/executor-v2/`:

- `before.json`, `after.json`: exact replay inputs and full traces.
- `motion-coordination.patch`: executor/provenance integration patch.
- `tests-final.txt`: complete 32-test output.
- `witnesses.jsonl`, `witness-summary.json`: all 864 replays, hashes, counts and
  **empty failures list**. This is the current witness certificate; the original
  manifest lock and v1 witness file remain historical evidence.
- `verification.json`, `historical-verification.json`: label, payload, preservation
  and incompatible-resume checks.

From repository root:

```bash
export MPLCONFIGDIR=/private/tmp/policy2action-mpl
experiments/llm_lbf_demo/.venv/bin/python -m unittest discover -s experiments/llm_lbf_demo/tests -v
experiments/llm_lbf_demo/.venv/bin/python experiments/llm_lbf_demo/tests/verify_executor_v2.py
experiments/llm_lbf_demo/.venv/bin/python -m experiments.llm_lbf_demo.e1.worlds --manifest /private/tmp/e1-v2-manifest.jsonl --witnesses /private/tmp/e1-v2-witnesses.jsonl
```

Use fresh output paths. Offline executor readiness is cleared for the frozen
protocol. Live launch still requires human EN/VI approval, configured exact model
snapshots/settings, verified prices, explicit permission and a dollar ceiling.
Provider/model compatibility remains untested; actual P0 thresholds are unknown.
Held-out live E1 still requires a matching passed **real** P0 gate. No approval,
provider availability, model performance or scientific conclusion is inferred
from these deterministic checks.
