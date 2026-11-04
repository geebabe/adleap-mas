# Conditional-policy development pilot — review before live execution

Prepared 5 November 2026. **Implemented and offline verified. No new real LLM calls. Awaiting human semantic review and pilot spending approval.** This pilot is separate from formal E1 and the recovered older conditional episode scenario.

## Exact bilingual policy

EN: If any remaining box cannot be lifted by either robot alone but can be lifted by both together, assign both robots to one such box. Otherwise, make physically feasible solo assignments that produce progress.

VI: Nếu có bất kỳ thùng nào chưa được thu gom mà không robot nào trong hai robot có thể tự nâng một mình, nhưng cả hai robot có thể cùng nâng được, hãy phân công cả hai robot cho một thùng như vậy. Nếu không, hãy đưa ra các phân công thu gom riêng lẻ khả thi về mặt vật lý để tạo ra tiến triển.

Both texts describe the same condition: an unfinished box has weight strictly above each robot's capacity, but no greater than their combined capacity. In that branch, select one such box and assign both robots to it. Otherwise, selected boxes must each have exactly one sufficiently capable robot, with at least one active assignment. A robot may remain unassigned. Every selected assignment must also pass the unchanged independent geometric-feasibility check. Human confirmation of these new translations is still required.

## Existing development-world coverage

No worlds changed or generated. All 12 original development worlds have at least one geometrically and physically feasible compliant allocation.

| World | Capacity A / B | Weights b0 / b1 / b2 | Required branch | Jointly-only and feasible boxes |
|---|---|---|---|---|
| development-000 | 1.0 / 1.4 | 0.4 / 0.6 / 0.8 | solo_required | none |
| development-001 | 0.8 / 1.4 | 0.4 / 0.6 / 0.6 | solo_required | none |
| development-002 | 1.2 / 1.2 | 0.4 / 0.6 / 0.9 | solo_required | none |
| development-003 | 1.4 / 1.4 | 0.4 / 0.6 / 1.0 | solo_required | none |
| development-004 | 1.4 / 1.0 | 0.4 / 0.6 / 0.8 | solo_required | none |
| development-005 | 1.4 / 0.8 | 0.4 / 0.6 / 0.6 | solo_required | none |
| development-006 | 1.0 / 1.0 | 0.4 / 0.6 / 1.2 | joint_required | b2 |
| development-007 | 1.2 / 1.4 | 0.4 / 0.6 / 1.6 | joint_required | b2 |
| development-008 | 1.0 / 0.8 | 0.4 / 0.6 / 1.2 | joint_required | b2 |
| development-009 | 1.2 / 1.2 | 0.4 / 0.6 / 1.4 | joint_required | b2 |
| development-010 | 0.8 / 1.2 | 0.4 / 0.6 / 1.4 | joint_required | b2 |
| development-011 | 1.4 / 0.8 | 0.4 / 0.6 / 1.6 | joint_required | b2 |

Coverage: **six independent worlds per branch**, no missing branch, no ineligible world. The joint branch coincides with mixed-world layouts and the solo branch with light-world layouts. Branch contrasts are descriptive; neither complexity nor geometry is causally isolated.

## Representative states and independent accepted/rejected allocations

Full native snapshots, including positions/directions, are in `REVIEW_EXAMPLES.json`. Both representative boards are 8×8 with no obstacles; no state has been altered.

### development-000 — solo_required

```json
{
  "agents": [
    {
      "direction": 0.0,
      "id": "A",
      "level": 1.0,
      "position": [
        3,
        2
      ]
    },
    {
      "direction": 0.0,
      "id": "B",
      "level": 1.4,
      "position": [
        4,
        3
      ]
    }
  ],
  "obstacles": [],
  "shape": [
    8,
    8
  ],
  "tasks": [
    {
      "completed": false,
      "id": "b0",
      "level": 0.4,
      "position": [
        4,
        6
      ]
    },
    {
      "completed": false,
      "id": "b1",
      "level": 0.6,
      "position": [
        6,
        2
      ]
    },
    {
      "completed": false,
      "id": "b2",
      "level": 0.8,
      "position": [
        1,
        2
      ]
    }
  ]
}
```

| Case | Exact output | Label | Capacity valid | Policy compliant |
|---|---|---|---|---|
| accepted two solo | `{"targets":{"A":"b0","B":"b1"}}` | GOOD | True | True |
| accepted one solo | `{"targets":{"A":"b0","B":null}}` | GOOD | True | True |
| rejected cooperation | `{"targets":{"A":"b0","B":"b0"}}` | POLICY | True | False |
| rejected idle | `{"targets":{"A":null,"B":null}}` | VACUOUS | True | False |

### development-006 — joint_required

```json
{
  "agents": [
    {
      "direction": 0.0,
      "id": "A",
      "level": 1.0,
      "position": [
        6,
        3
      ]
    },
    {
      "direction": 0.0,
      "id": "B",
      "level": 1.0,
      "position": [
        4,
        5
      ]
    }
  ],
  "obstacles": [],
  "shape": [
    8,
    8
  ],
  "tasks": [
    {
      "completed": false,
      "id": "b0",
      "level": 0.4,
      "position": [
        6,
        2
      ]
    },
    {
      "completed": false,
      "id": "b1",
      "level": 0.6,
      "position": [
        5,
        1
      ]
    },
    {
      "completed": false,
      "id": "b2",
      "level": 1.2,
      "position": [
        5,
        4
      ]
    }
  ]
}
```

| Case | Exact output | Label | Capacity valid | Policy compliant |
|---|---|---|---|---|
| accepted joint-only | `{"targets":{"A":"b2","B":"b2"}}` | GOOD | True | True |
| rejected light cooperation | `{"targets":{"A":"b0","B":"b0"}}` | POLICY | True | False |
| rejected solo light progress | `{"targets":{"A":"b0","B":"b1"}}` | POLICY | True | False |
| rejected insufficient capacity | `{"targets":{"A":"b2","B":null}}` | PHYSICS | False | False |

## Implementation and scoring

- `grader.py`: independently selects the branch from capacities/unfinished weights and checks the formal conditional predicate. It imports no controller, provider or executor. The unchanged strict parser and independent physical checks are reused through the existing P0 grader.
- Exact JSON remains `{"targets":{"A":"box_id_or_null","B":"box_id_or_null"}}` (use JSON null rather than the placeholder string). No explanation/branch field or output repair is accepted.
- The exact final `p0-capacity-grounding-2` system scaffold and `e1-motion-2` executor are reused. Only the user policy field changes; EN/VI prompts otherwise match.
- GOOD requires valid format, capacity, geometry, active progress and conditional compliance. Each parsed recommendation retains separate failure flags for format, capacity, geometry, progress, policy and specification. Failure flags can overlap; the primary status retains the original precedence FORMAT / PHYSICS / VACUOUS / POLICY / GOOD (SPEC for explicit defects).
- Every parsed recommendation is replayed, including infeasible/noncompliant recommendations. Native replay uses P0 audit mode to avoid incorrectly treating this conditional policy as a fixed R/F rule; a separate conditional pickup-event audit checks the realized loading agents and collected box. Neither replay nor pickup success changes recommendation labels.
- Joint policy compliance concerns target choice as well as cooperation: collecting a light box jointly while b2 triggers the condition is rejected even if the pickup succeeds.
- The pilot saves the full provider envelope and actual wire request before independent grading and replay. No LLM judge, hidden feasibility list, policy classifier or target substitution is added.

## Proposed real pilot and one finite budget

- Model: **gpt-4o-mini-2024-07-18**. No moving alias or fallback.
- All 12 eligible development worlds × EN/VI × three fresh-context repetitions = **72 calls**. Each branch/language condition has 18 calls from six independent worlds.
- Seed 51105 randomizes world/repetition blocks and interleaves paired languages. The same worlds and repetitions occur in both languages.
- Existing settings: temperature 0, JSON mode, n=1, max_completion_tokens=256, stream=false, store=false, service_tier=default. No added smoke calls.

**Single hard pilot ceiling: USD 0.15**, with **zero retries** and at most 72 API requests. Every attempt is reserved before sending. Using the configured bound of 10,000 uncached input and 256 output tokens per attempt:

```text
72 × ((10,000 × $0.15 + 256 × $0.60) / 1,000,000)
= $0.1190592 conservative worst-case token reservation
```

Prices reverified 5 November 2026 using the [official GPT-4o-mini model card](https://developers.openai.com/api/docs/models/gpt-4o-mini). Actual usage-based costs will be reported separately from reservations and are not invoices. Failed attempts with unknown usage retain the full reservation. No malformed response is retried. A transport/model/token-contract failure stops further calls and retains NOT_RUN rows for remaining slots.

Prior spending and bilingual approvals do not authorize this new conditional policy. The live guard requires a new external record matching the exact policy and protocol hashes. `approval.template.json` is false.

## Verified offline results

- **62 tests pass**: all 53 existing tests plus nine new conditional/integration tests. Tests cover actual branches, solo/joint equality boundaries, completed/impossible boxes, multiple candidates, renamed IDs, malformed/duplicate/extra fields, geometric impossibility, no-progress outputs and approval guards.
- All **78 compliant allocations across all 12 original worlds** executed successfully under the unchanged native executor, with zero conditional pickup violations. All witnesses retained in `evidence/executor-witnesses.jsonl`.
- Durable fake runs, 72 slots each: oracle 72 GOOD; wrong-branch 72 POLICY; idle 72 VACUOUS; malformed 72 FORMAT. All reports mark infrastructure validation and zero API calls. Wrong-branch fixtures reach a native pickup while remaining policy failures, explicitly exercising the scoring/execution separation.
- 1141 prior source/evidence files hash-verified unchanged. All pre-existing gate results, conditional episode results and diagnostic artifacts are preserved.
- Real conditional ability remains **unverified**. Real branch/language rates are null in `REAL_RESULTS_PENDING.json`. Nothing is claimed about novelty, general policy understanding, causal complexity effects or whole-episode control.

## Exact commands and artifacts

From repository root. Free tests:

```bash
MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python -m unittest discover -s experiments/llm_lbf_demo/tests -v
```

A new offline oracle replay (choose a fresh output path; existing files are never overwritten):

```bash
MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python -m experiments.llm_lbf_demo.conditional_pilot.pilot run --dry-run --fixture oracle --output /private/tmp/p2a-conditional-oracle-001
MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python -m experiments.llm_lbf_demo.conditional_pilot.pilot report --output /private/tmp/p2a-conditional-oracle-001
```

Real launch only after actual new semantic/spending approval is recorded in `approval.json`:

```bash
MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python -m experiments.llm_lbf_demo.conditional_pilot.pilot run --live --approval experiments/llm_lbf_demo/conditional_pilot/approval.json --output experiments/llm_lbf_demo/conditional_pilot/evidence/live-001
MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python -m experiments.llm_lbf_demo.conditional_pilot.pilot report --output experiments/llm_lbf_demo/conditional_pilot/evidence/live-001
```

Expected artifacts: frozen `configuration.json` with every exact prompt and source hash; fsync/hash-chained `attempts.jsonl` containing attempts, raw provider envelopes and terminal rows; `results.json` with allocations, independent flags/labels, complete native replay traces, conditional pickup audits, token usage, latency and cost; `ANALYSIS.json` with four branch/language rates, world/repetition outcomes and every failure example.

Protocol hash: `7ec1a673f6354746fc8d5e506ef5a2b6ed2289bef2a9a8d603a4ac8f94d4324d`. No held-out worlds or full-episode loop are part of this pilot.
