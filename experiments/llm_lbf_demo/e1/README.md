# E1 offline harness

E1 measures one controlled policy-conditioned pickup recommendation from a frozen
world. All supplied results are **scripted infrastructure validation**, not model
findings. No paid experiments were run. The recovered executor and its nine tests
remain unchanged.

Use Python 3.12 and the existing parent `requirements.lock` / `bootstrap.py` setup.
All commands below run from the repository root:

```bash
export MPLCONFIGDIR=/private/tmp/policy2action-mpl
experiments/llm_lbf_demo/.venv/bin/python -m unittest discover -s experiments/llm_lbf_demo/tests -v
experiments/llm_lbf_demo/.venv/bin/python -m experiments.llm_lbf_demo.e1.run_e1 --dry-run --fixture oracle --output /private/tmp/e1-oracle
experiments/llm_lbf_demo/.venv/bin/python -m experiments.llm_lbf_demo.e1.analyze_e1 /private/tmp/e1-oracle/attempts.jsonl --output /private/tmp/e1-oracle/analysis.json
```

Repeat with `--fixture blind`, `idle`, and `malformed` using fresh directories.
Each complete run contains 144 P0 slots and 2,880 E1 slots. Model roles use clearly
fake IDs. `--stage gate` runs only the P0 slots; `--stage e1` only held-out slots.
Reusing the same output directory resumes only an exactly compatible run; completed
requests are never repeated. Analysis outputs refuse overwrite.

To reproduce world generation and all executor witnesses without overwriting the
frozen artifacts:

```bash
experiments/llm_lbf_demo/.venv/bin/python -m experiments.llm_lbf_demo.e1.worlds --manifest /private/tmp/e1-manifest.jsonl --witnesses /private/tmp/e1-witnesses.jsonl
experiments/llm_lbf_demo/.venv/bin/python experiments/llm_lbf_demo/tests/verify_e1_evidence.py
```

The generator fixes 12 development and 60 held-out families (30 light, 30 mixed
held-out). Agent/task IDs, translations/reflections/rotations of coordinates, and
common translations do not create additional families. Every variant remains
within its family. Capacity values and positions vary; directions are fixed East.
Geometric predicates enumerate joint-position reachability independently of the
recovered A*. Task cells stay blocked and an unassigned robot is stationary.
The numerical capacity tolerance is 1e-9; a tolerance-only success that differs
from upstream's exact comparison is flagged SPEC, not credited to a model.

`e1_policies.json` contains R/F's two paraphrases in each language and P0's physical
rules/progress statement. All translations await human semantic approval. The
controller sends exactly objective, world state and policy text in an otherwise
fixed English scaffold. Gold conditions and presented policies are separately
recorded outside the payload. There is no solo preference or inferred rule enum.
The fixture provider's exact-text lookup exists only in `providers.py` for tests;
it is not a language-understanding method. The strict parser does not repair
responses, extract fenced substrings, coerce IDs, or accept legacy flags.

Recommendation status is FORMAT, PHYSICS, VACUOUS, POLICY, or GOOD, with capacity
and geometry recorded separately. Known specification defects are SPEC and
invalidate comparison. EXECUTOR is a separate rollout axis. An executor stall
never changes a recommendation's capacity, geometry or policy label. Replay stops
after first pickup or 40 ticks without another controller call. Trace files
retain all primitive actions and attempted loads, including unsuccessful attempts.

The original executor regression and its complete v1 evidence are retained. The
versioned `e1-motion-2` bridge now serializes directional commands across all task
groups by stable agent-ID priority, while retaining simultaneous LOAD and actual
None waits. This repairs the stationary-obstacle assumption used by recovered A*;
it changes neither allocation nor task selection. Every yield is explicit in
`proposed_actions`, `actions` and `motion_yields`. The original recovered code and
upstream physics remain unchanged.

On the recorded `test-006` allocation/seed, v1 reproduces a 40-tick oscillation;
v2 picks up in 7 ticks. All 864 v2 witnesses now succeed; none are dropped. Across
witnesses, 117 first pickups take longer, 6 take fewer ticks, and 741 are unchanged.
This conservative fix is not a global optimality or general liveness guarantee.
New witnesses and before/after traces are under `evidence/executor-v2/`; the original
`evidence/e1_witnesses.jsonl`, manifest lock and dry-run records are preserved.
The current witness gate requires matching executor version and source hash.
Replay caches include both; historical runs are rejected for resume under v2,
not rewritten. Use fresh output directories for new runs. Recommendation labels
and all existing policy-only payload comparisons have been reverified unchanged.

`attempts.jsonl` is hash-chained, process-locked and fsynced after request-start,
raw-response and terminal events. Each attempt records state/prompt/family hashes,
model, presented policy, grader condition, versions, timestamps, raw envelope,
usage and replay references. Responses are durable before grading/replay. On a
crash after a response, resume reuses that response. A started request with no
recorded response/error is uncertain: automatic resend is blocked until explicit
provider reconciliation. Torn tails and integrity failures are rejected rather
than silently truncated. Run code/config hashes prevent mixing changed prompts,
models, policies or manifests. POSIX file locking is used (verified on macOS).

`analyze_e1.py` keeps malformed/idle responses in strict denominators, computes
six pair scores per family/language/model, and resamples the 60 family rows
10,000 times with seed 4103, retaining EN/VI together. It reports per-policy
marginals, strata, joint-assignment probability, false idle, execution outcomes,
paired language differences, degenerate/boundary intervals, and the separate
all-variants family-pass exact interval when every family passes. INFRA/SPEC
leave the report incomplete and cannot certify confirmatory results. Repetitions
and paraphrases never increase the number of independent worlds.

## Future live gate (not executed)

The explicit `--live --stage gate` entry point requires a real configuration and
an external human approval record matching the policy hash. The example files
intentionally fail closed. Configure exact primary/replication snapshot IDs,
frozen settings, verified prices, token bounds, explicit approval and a finite
dollar ceiling. No `.env` is loaded. Live gate and held-out E1 are separate runs.

Preflight reserves the worst-case configured input/output cost for three attempts
per slot, including two infrastructure retries, before starting. Every attempted
request reserves its bound durably; failed/unknown usage is never assumed free.
This is a conservative estimate, not verified billing. Infrastructure errors may
retry at most twice; malformed/refusal content never retries. Exhaustion leaves
the run incomplete. A fake gate cannot authorize E1. The held-out entry point
re-analyzes the original real gate journal and requires matching manifest, policy,
prompt, code and model bindings plus all four model/language thresholds. This
implementation conservatively blocks a full confirmatory launch if any gate
condition fails; it never substitutes models/worlds.

The executor witness blocker is cleared for the frozen worlds. Human bilingual
approval, exact real-model/provider compatibility, configured budget/permission,
and real P0 performance remain unverified. No live or paid experiments were run.
The optional HTTP transport has only been exercised through local mocks.

To verify the v2 patch and preservation checks:

```bash
experiments/llm_lbf_demo/.venv/bin/python experiments/llm_lbf_demo/tests/verify_executor_v2.py
```

See `E1_OFFLINE_ACCEPTANCE_REPORT.md` and `evidence/executor-v2/witness-summary.json`.
The earlier manifest lock describes v1 historical acceptance; the versioned
witness summary records the current acceptance and source/data hashes.
