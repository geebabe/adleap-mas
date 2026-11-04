# First real P0 gate — proposed, not authorized or run

Prepared 4 November 2026. **Zero paid/provider requests made.** Executor
`e1-motion-2` is frozen at SHA-256
`c2cfbd0e9971c1fda23723b0220173c307d534880201b96c072006373dd531cc`.
`executor.freeze.json` also binds the unchanged recovered navigation source,
pinned upstream and all 864 passing executor witnesses. Any change blocks launch.

## Exact policies for human semantic review

`review/e1_policies.json` is a **byte-identical copy** of the E1 policy file actually
used by the controller. It contains P0 and both R/F paraphrases in EN and VI.
File SHA-256: `49c899c6ae29ab2fd2bba6aaa9d5d4afbbf63b7afe5cad9de883ac8aa4ce4abd`.
Canonical policy hash used by approval guards:
`e697de1da770bdd42cf431c6a205404c1a03fb718bf5c4f726fa1430bb05410d`.

Human approval is **pending**. Review permission versus obligation, all-null
failure, one-target-per-robot semantics, sum of capacities versus individual
capacity, weight inequality and scope. P0 has no require/forbid restriction.
Record approval in a separate `human-approval.json`, based on the template; do
not edit the policy metadata to mark it approved because that changes its hash.
No machine or fake-provider result constitutes bilingual approval.

P0 EN:
> Select at least one box for a feasible pickup. For each selected box, the combined lifting capacity of the assigned robots must be at least its weight. Each robot may be assigned to at most one box; a robot may be unassigned.

P0 VI:
> Hãy chọn ít nhất một thùng để có thể thu gom được. Với mỗi thùng được chọn, tổng sức nâng của các robot được phân công phải ít nhất bằng trọng lượng của thùng. Mỗi robot chỉ được phân công tối đa một thùng; có thể không phân công nhiệm vụ cho một robot.

## Proposed model/settings contract and sources

`live.proposed.json` contains exact snapshots, not moving aliases:

| Role | Snapshot | Input / cached input / output USD per million tokens |
|---|---|---|
| Primary, recovered model family | gpt-4o-mini-2024-07-18 | 0.15 / 0.075 / 0.60 |
| Replication | gpt-4.1-mini-2025-04-14 | 0.40 / 0.10 / 1.60 |

Sources checked read-only on 4 November 2026:
[GPT-4o mini model card](https://developers.openai.com/api/docs/models/gpt-4o-mini),
[GPT-4.1 mini model card](https://developers.openai.com/api/docs/models/gpt-4.1-mini),
[Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create),
[pricing overview](https://developers.openai.com/api/docs/pricing).
`pricing-sources.json` records the extracted facts and URLs. Both model cards mark
these models **deprecated**. Documented listings do not prove account access.
Recheck pricing/deprecation status before spending; unavailable snapshots require
an explicit development-only protocol amendment, never an automatic replacement
or selection using held-out outcomes.

Proposed wire settings: `POST /v1/chat/completions`, temperature 0,
`max_completion_tokens=256`, `response_format={"type":"json_object"}`, n=1,
stream=false, store=false, service_tier=default; no tools, images, provider seed,
reasoning control, prompt changes or full-episode conversations. These settings
follow the official API schema. Exact account/model compatibility remains
**unverified** until authorized smoke requests succeed. JSON mode is retained
rather than changing the frozen prompt/parser to provider-enforced schema output.

## Fixed budget

Reserve **10,000 input + 256 output tokens per attempt**, ignoring cache discounts.
Actual maximum conservative UTF-8 prompt bound in development slots is 1,969.
There are 72 slots/model, 36/model/language. At most two infrastructure retries:
216 attempts/model, **432 total**. Bad model content is not retried.

| Item | Worst-case token cost, USD | Proposed application ceiling |
|---|---:|---:|
| Primary P0, including retries | 0.3571776 | Included below |
| Replication P0, including retries | 0.9524736 | Included below |
| Formal P0: 144 slots | **1.3096512** | **1.50** |
| Separate smoke: 4 slots, up to 12 attempts | **0.0363792** | **0.05** |
| Combined separate phases | **1.3460304** | **1.55** |

No-retry formal token ceiling is USD 0.4365504. These are conservative standard-tier
token estimates, not invoices; taxes/currency conversion are outside this table.
Unknown failed-call usage is reserved at its full bound, never treated as free.
`evidence/preflight-final.json` reproduces the calculation without accessing an API key.
Proposal hash: `ccc8c0699ca4078106fc7398dede3deb7c6e7fe374402b6e398ba2ab03bcc4bb`.
Spending approval template is false and authorizes no phases.

## Exact future launch sequence — DO NOT RUN LIVE YET

From repository root, using the pinned Python 3.12 environment. Set
OPENAI_API_KEY securely in the process environment only after authorization;
no `.env` is loaded. Fill separate human/spending approval records only after
actual approval. Spending authorization must match the proposal hash and allowed
phase/cap. The following commands intentionally fail closed without those records.

1. Authorized development-only compatibility smoke, **separate from the gate**:

```bash
export MPLCONFIGDIR=/private/tmp/policy2action-mpl
experiments/llm_lbf_demo/.venv/bin/python -m experiments.llm_lbf_demo.p0.prepare smoke --live --proposal experiments/llm_lbf_demo/p0/live.proposed.json --spending-approval experiments/llm_lbf_demo/p0/spending-approval.json --human-approval experiments/llm_lbf_demo/p0/human-approval.json --output experiments/llm_lbf_demo/p0/runs/smoke-001
experiments/llm_lbf_demo/.venv/bin/python -m experiments.llm_lbf_demo.p0.prepare report --report-kind smoke --journal experiments/llm_lbf_demo/p0/runs/smoke-001/attempts.jsonl --output experiments/llm_lbf_demo/p0/runs/smoke-001/SMOKE_REPORT.json
```

Exactly one fresh-context P0 call for each model/language, using only
`development-000`, repeat 0. Labels are `smoke`, not formal gate slots. Validate
actual returned snapshot IDs, accepted settings/standard tier and token usage.
Do not use smoke goodness to choose a better-performing model/prompt. Any
compatibility correction requires documented development-only amendment and a
new compatible proposal/smoke, before freezing. Unknown charges require review.

2. Freeze the **final** contract after real smoke and human semantic approval:

```bash
experiments/llm_lbf_demo/.venv/bin/python -m experiments.llm_lbf_demo.p0.prepare freeze --proposal experiments/llm_lbf_demo/p0/live.proposed.json --human-approval experiments/llm_lbf_demo/p0/human-approval.json --smoke-journal experiments/llm_lbf_demo/p0/runs/smoke-001/attempts.jsonl --output experiments/llm_lbf_demo/p0/live.final.freeze.json
```

This creates an immutable-by-hash artifact containing exact configuration,
settings, policy/manifest hashes, all implementation hashes, thresholds, schedule
hash and real smoke evidence hash. It does not authorize spending. Fake smoke
cannot produce a final freeze. This artifact **does not exist yet**, correctly.

3. Only with gate spending authorization, launch the **formal 144-slot P0**:

```bash
experiments/llm_lbf_demo/.venv/bin/python -m experiments.llm_lbf_demo.p0.prepare gate --live --proposal experiments/llm_lbf_demo/p0/live.proposed.json --final-config experiments/llm_lbf_demo/p0/live.final.freeze.json --spending-approval experiments/llm_lbf_demo/p0/spending-approval.json --human-approval experiments/llm_lbf_demo/p0/human-approval.json --output experiments/llm_lbf_demo/p0/runs/gate-001
experiments/llm_lbf_demo/.venv/bin/python -m experiments.llm_lbf_demo.p0.prepare report --report-kind gate --journal experiments/llm_lbf_demo/p0/runs/gate-001/attempts.jsonl --output experiments/llm_lbf_demo/p0/runs/gate-001/P0_REPORT.json
```

Each formal condition is 12 development worlds × 3 fresh-context repetitions =
**36 calls**. Randomized, language-interleaved schedule is unchanged. Use a fresh
output directory after any contract change. Existing compatible requests may
resume; source/config changes or uncertain in-flight requests fail closed.

## Expected artifacts and report

Smoke and formal directories independently contain `attempts.jsonl` (durable
request, response, infrastructure-error and terminal events) and `replays/*.json`
for progressive physically valid outputs. Raw provider envelopes, actual model
IDs, fingerprints, token usage, request parameters and reserved costs are retained.
The explicit report commands add `SMOKE_REPORT.json` / `P0_REPORT.json`.
The freeze artifact is separate and is mandatory for the formal gate.

`P0_REPORT.json` has four rows: primary EN, primary VI, replication EN,
replication VI. Each reports 36 scheduled calls, completed calls, attempts,
parseability, capacity validity, geometric validity, combined physical validity,
progressive goodness, infrastructure failed attempts/exhausted slots, observed
usage-derived USD, unknown-cost attempts, and reserved upper bound. Costs apply
frozen prices to observed token usage, including cached input; invoiced cost is
explicitly unknown. Failed requests without usage are not silently costed at zero.
Malformed and idle outputs remain failures in their original 36-slot denominators.

Thresholds are unchanged: parseability ≥98% (36/36), physical validity ≥95%
(at least 35/36), progressive goodness ≥80% (at least 29/36), per model/language.
Exhausted INFRA makes evidence incomplete. `P0_REPORT_PENDING.json` currently has
four 36-call rows with **null observed metrics/cost**, not fabricated results.

**Held-out E1 stays blocked** until the required matching real P0 gate passes.
The preparer exposes no held-out launch option; smoke cannot qualify as P0, and
existing E1 guards reject absent, fake, failed or incompatible real gate evidence.
No prompt, model or threshold adaptation using held-out outcomes is permitted.
