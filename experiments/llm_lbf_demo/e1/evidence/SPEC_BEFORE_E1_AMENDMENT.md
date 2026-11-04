# Policy2Action E1: paired policy-flip experiment

Implementation handoff for Codex | 4 November 2026 | Status: proposed protocol, not experimental results

## 1. Decision and provenance

**Build one experiment: ask for the next joint pickup allocation in an identical world under two opposite operational rules, with valid progress possible under either rule.** The recommendation must change its cooperation pattern to satisfy both. This is a cleaner first test of policy conditioning than varying policy length while navigation and task feasibility also change.

| Origin | Requirement or proposal |
|---|---|
| Supervisor's original emails and latest clarification | Investigate human-written policies, reasonable LLM action recommendations, effects of complexity/language, and task performance separately from compliance. Planner superiority is not required. |
| This handoff's design choice | Opposite-rule pairs, frozen decision snapshots, exact admissible-action enumeration, thresholds, sample counts and tests below. These were not explicitly requested by the supervisor. |
| New hypotheses | H1: the controller reliably changes cooperation decisions when the rule changes. H2: strict paired compliance differs between matched English and Vietnamese policies. Neither is an established finding. |
| Deferred supervisor direction | Complexity/exception scaling follows an interpretable E1 result. E1 does not test logical complexity or establish an exception-handling contribution. |

The existing review found substantial precedents. This is a controlled validation experiment, not a novelty claim, architecture contribution, intentional-cheating test or benchmark release claim. The recovered branch has not been inspected in this request. Codex must reconcile it with this contract; the earlier report alone does not verify its behavior.

## 2. Exact task and policy conditions

One centralized LLM receives fully observed state and recommends a **single pickup allocation**, not primitive moves or a full episode plan. Every non-null target is a commitment to collect that box; null means unassigned for this allocation. The common objective is: make at least one feasible pickup while obeying the policy. Collecting every box is not required.

**R: require joint pickup.** Every selected box must have both robots assigned. A physically possible joint pickup of a light box is allowed.

**F: forbid joint pickup.** Every selected box must have exactly one robot assigned. Distinct solo targets or one solo target plus an unassigned robot are allowed.

Two short English realizations, frozen before test:

- R1: "For every box you select next, assign both robots to that box. Do not select a box for just one robot."
- F1: "For every box you select next, assign exactly one robot to that box. Do not select the same box for both robots."
- R2: "The next pickup must use the two robots together on one box. Individual pickup assignments are forbidden."
- F2: "The next pickup assignments must be individual. Assigning the two robots together to one box is forbidden."

Provisional Vietnamese counterparts, **requiring bilingual semantic review before any live run**:

- R1: "Với mỗi thùng được chọn tiếp theo, hãy phân công cả hai robot cùng thu gom thùng đó. Không được phân công chỉ một robot cho một thùng."
- F1: "Với mỗi thùng được chọn tiếp theo, hãy phân công đúng một robot thu gom thùng đó. Không được phân công cả hai robot cho cùng một thùng."
- R2: "Lần thu gom tiếp theo phải do hai robot cùng thực hiện trên một thùng. Không được phân công thu gom riêng lẻ."
- F2: "Các phân công thu gom tiếp theo phải là phân công riêng lẻ. Không được phân công hai robot cùng thu gom một thùng."

The validated canonical meanings are R/F above, not an LLM translation. Audit permission versus obligation, scope, null/unassigned semantics and capacity. Reject ambiguous realizations before evaluation. Do not adapt them after seeing test outputs. Different surface forms need not be exactly length-matched; log token counts and avoid claims of a pure syntax effect.

### World construction

Use an obstacle-free 8 x 8 grid, two robots and three boxes. No hidden state, colors, special connectors or dynamic tasks. Build 12 development families and 60 held-out families. Each family is a distinct generated world; all language/policy/paraphrase/repeat variants stay in that family. Layouts or relabelings of one underlying world are not additional independent families.

Thirty held-out worlds have three individually liftable boxes; thirty have two individually liftable boxes and one jointly-only box. Vary capacities and relative positions with fixed generation seeds. Require at least two boxes individually liftable by either robot; every box must be jointly liftable. Use non-overlapping interior positions and reachable distinct approach slots. Reject duplicate worlds and development/test overlap before locking the manifest. This gives valid pickup alternatives under both policies; F is never forced to attempt an impossible heavy remainder.

Hand fixture: A at (1,1), B at (6,1), both capacity 1.0; b0 at (2,4), level 0.6; b1 at (5,4), level 0.8; b2 at (4,6), level 1.6. Examples:

| Recommendation | Physical | R good | F good |
|---|---|---|---|
| A -> b2; B -> b2 | Yes | Yes | No |
| A -> b0; B -> b1 | Yes | No | Yes |
| A -> b0; B -> null | Yes | No | Yes |
| A -> b0; B -> b0 | Yes | Yes | No |
| A -> b2; B -> null | No | No | No |
| A -> null; B -> null | No capacity violation, but no progress | No | No |

R/F good sets are nonempty and disjoint. A deterministic rule-blind allocation cannot pass both members of a pair. This is the decisive control. It avoids the earlier illustrative exception design's overlapping permissions, which could let an unchanged conservative choice satisfy both policies.

## 3. Controller, oracle and executor contract

Preferred normalized output; adapt existing field names losslessly rather than rewrite the controller:

```json
{"targets":{"A":"b0","B":null}}
```

Require exactly the registered agent keys, known unfinished task IDs or null, and no extra fields. No explanation, self-rated compliance or independent cooperation flag is needed. If the recovered controller emits a cooperation flag, record it and flag contradictions with targets; do not silently repair them. Reject unknown IDs, duplicate JSON keys and malformed output. Document any provider envelope extraction. No semantic or LLM-based output repair in the scored path.

Enumerate the 16 target pairs from {b0,b1,b2,null} squared. For each selected box, compute the sum of assigned robots' capacities, with a documented numerical tolerance. Physical validity requires adequate combined capacity, a valid box, and a verified executor witness for that allocation. At least one box must be selected for progress. R requires two assigned robots per selected box; F requires one. Accept all good allocations, including symmetric alternatives. Labels come from independent predicates, never the model's rationale or a single gold trajectory.

Maintain a grader-side **gold** condition and a separately recorded **presented** policy. They normally agree; acceptance tests deliberately mismatch them to expose accidental leakage or label coupling. The policy ID, gold labels, good sets and reference allocation must never enter the model payload. State IDs/keys, objective, schema, role placement and all non-policy text must be byte-identical across a paired R/F call. Do not include derived policy-permission fields.

Before live use, inspect the actual simulator action mapping, observation visibility, wait/stop behavior and randomness. Upstream commit 0874e57fc4974d7e1f8bdd5d39e04119e7053d6f defines 0 as East, not Stay. Do not assume the recovered branch agrees or use action 0 to wait. `info['coop']` records successful joint loading and is insufficient as the grader.

Keep the existing conventional executor fixed. Validate each world's oracle witnesses with offline deterministic replay; no new planner is required. Replay distinct valid returned allocations until first pickup or 40 primitive ticks, with fixed simulator seeds and no further LLM call. Record target assignments, primitive actions and pickup events. If the executor repairs/overrides a proposal, score the original recommendation and record the change. Execution failure is separate from recommendation noncompliance. An unverified waiting mechanism blocks replay acceptance; do not fake it or change world physics.

## 4. Controlled variables and baselines

| Manipulate | Hold fixed or explicitly record |
|---|---|
| R versus F: primary semantic intervention | Exact world/history, objective, action interface and executor |
| EN versus VI: secondary language intervention | JSON keys/IDs/enums, shared English scaffold, response language-neutral schema |
| Two validated within-language paraphrases | Scope/meaning, output budget and role hierarchy |
| Three fresh-context repetitions | Same frozen model/configuration; record provider seed if supported, never assume determinism |

Use two preregistered model snapshots: the recovered controller's primary model and one available replication model. Require exact IDs/configuration at run time; do not invent them or automatically select whichever passes best. Default temperature 0 and output budget 256 tokens if supported by both; otherwise freeze and disclose supported settings before running. All calls are fresh context. Randomize R/F order, interleave languages and record provider version/fingerprint and run time.

Baselines:

1. **P0, game rules only:** no R/F restriction; tests interface/physical reasoning and non-vacuous progress. Used for the development gate.
2. **Scripted policy-aware oracle:** selects a member of the independent good set and replays it. Infrastructure ceiling, not an LLM competitor.
3. **Deterministic rule-blind allocator:** uses only state and a fixed ID tie-break, always emits the same valid allocation for R/F. Pair score must be zero; validates that task competence alone cannot pass.

No MCTS/A* superiority comparison. Reference paths are executor checks, not asserted globally optimal tours.

## 5. Sample, gate and fixed analysis

**Development gate:** 12 worlds x 2 languages x 3 repeats x 2 models = 144 P0 snapshot calls. Per model/language, require parseability >= 98%, physical validity >= 95%, and valid progressive recommendation rate >= 80%. These are proposed engineering thresholds, not supervisor requirements or validated reliability standards. This replaces the earlier illustrative 144-episode gate with a cheaper snapshot gate aligned to E1's unit of analysis. Offline executor tests remain mandatory.

If a language fails, report its floor and do not interpret R/F differences there as evidence of higher-policy difficulty. One documented interface correction may be made using development data, followed by a new frozen gate. A second failure blocks that model/language's confirmatory E1; retain the failed gate in the report. Do not substitute another model using test scores.

**Held-out E1 ceiling:** 60 families x 2 policies x 2 languages x 2 paraphrases x 3 repeats x 2 models = **2,880 calls**. Gate plus E1 = **3,024 planned calls**, excluding infrastructure-error retries. This is a fixed precision-oriented scope, not a claim of power for an unknown effect. Do not increase the sample after inspecting test effects. A clearly labeled dry run on fixtures is not scientific evidence.

For family i and matched language/paraphrase/repeat/model, let yR and yF be strict binary goodness indicators. **PairPass = yR * yF.** Invalid or non-progressive outputs are failures, not missing values. Average six pair scores within each family; aggregate over 60 families. The preregistered primary estimate is English PairPass for the primary model. Report the replication model separately. The paired VI-minus-EN difference is secondary; compare with within-language paraphrase/repeat variability. It is not a universal language ranking or a complexity interaction.

Use a seeded, 10,000-resample cluster bootstrap over families, retaining every condition inside each sampled family; report 95% intervals and all marginal rates. Stratify descriptive results by light-only versus mixed worlds. Repeats and paraphrases do not multiply the number of independent worlds. Flag boundary/degenerate bootstrap intervals; if all 60 families pass every pair, additionally report an exact binomial interval for that all-variants family-pass event, explicitly a different estimand. Do not imply zero errors proves perfect reliability.

Additional metrics: per-policy strict goodness, parse/physical validity, policy violation conditional on physical validity alongside unconditional rates, false idle/stop, and probability of a joint assignment. On replay, separately report successful pickup, forbidden joint-load attempts, forbidden successful pickups, executor substitutions and latency/ticks. Do not require identical task IDs across languages when both allocations are good. No efficiency-optimality claim in E1.

## 6. Failure taxonomy and falsification

Assign the first applicable machine-checkable outcome below; retain additional independent flags. Root causes require separate evidence.

| Code | Observable outcome |
|---|---|
| INFRA | API timeout/service error; retained, never silently scored as a model refusal |
| FORMAT | Bad JSON/schema, unknown IDs, conflicting legacy flag or translated ID |
| PHYSICS | Parsed allocation lacks required capacity or valid executable assignment |
| VACUOUS | No pickup selected despite a known good alternative |
| POLICY | Physically valid progressive recommendation violates R/F assignment rule |
| GOOD | Parsed, physically valid, progressive and policy-compliant |
| EXECUTOR | Replay stalls/changes allocation/fails after an otherwise good recommendation; separate execution axis |
| SPEC | Translation, oracle or simulator-semantic defect; invalidates affected comparison rather than blaming the LLM |

H1's proposed operational target is PairPass >= 0.80. An upper 95% bound below 0.80 contradicts that target; a lower bound >= 0.80 supports it within this testbed; overlap is inconclusive. The value 0.80 is a design target, not a novelty or publication criterion. Nearly unchanged cooperation patterns plus low PairPass support failure of effective policy conditioning; they do not establish intentional rule-breaking or a unique internal cause.

For secondary language effects, predeclare 10 percentage points as the practical margin. If the paired 95% interval is entirely within [-0.10, +0.10], a difference of that size is not supported in E1; an interval crossing the margins is inconclusive. A 10-point disadvantage is supported only if the whole interval lies beyond that boundary. These decisions may remain underpowered at 60 families; report that rather than equating non-significance with equivalence. This does not test whether code-switching or complex policies are harder.

**Protocol falsifiers:** empty/overlapping good sets; infeasible compliant alternatives; policy metadata leaked to the model; a deterministic rule-blind baseline passing a pair; schema repairs counted as original success; scorer and prompt labels coupled; or an unreconciled wait/stop interface. Any such defect blocks scientific interpretation until corrected on development data. Do not call it a model finding.

## 7. Codex deliverables and acceptance tests

Use repository-native module conventions. The names below are proposed outputs, not claims that files already exist: one controller adapter; `e1_manifest.jsonl`; `e1_policies.json`; independent `e1_oracle.py`; `run_e1.py`; `analyze_e1.py`; focused `test_e1.py`; and a short README. Keep state and raw provider response in append-only JSONL with hashes/IDs for family, split, state, prompt, presented policy, grader policy, model, paraphrase, repeat, parser version, oracle version, seeds, timestamps, status, normalized allocation and replay trace. Resume only exact matching records; never mix runs after prompt/model changes.

Provide `--dry-run` with a fake provider and zero network calls. Live mode requires an explicit flag, configured model IDs, bilingual approval, passed gate and a configured dollar ceiling; estimate cost and reject a budget overrun before starting. Reserve retry allowance within that ceiling. Retry infrastructure errors at most twice with request IDs logged; do not retry bad model content. After exhausted infrastructure errors, mark the report incomplete rather than select replacement test worlds or hide unmatched pairs. Do not run paid calls merely to verify this handoff.

Acceptance tests, all offline unless explicitly marked:

1. Enumerate the hand fixture and verify every table row in section 2. Assert nonempty, disjoint R/F good sets for every locked world; the all-null pair fails both.
2. Accept all alternative good allocations, including agent swaps; reject solo-heavy loading, unknown/completed boxes and unexpected output fields.
3. Reuse exactly the same deterministic rule-blind output in both arms: PairPass = 0. Scripted policy-aware oracle: PairPass = 1.
4. Swap presented R/F text while keeping the grader label fixed; an oracle-following fake provider's former successes become failures. Catch accidental scorer relabeling.
5. Payload diff test: for a matched pair, only policy text differs. Reject leakage of gold condition, permissions or witness actions. No forbidden regex policy shortcut in the controller adapter.
6. Strict parser rejects duplicate keys, translated IDs and contradictory legacy flags; no silent coercion/semantic repair. All-null is schema-valid but the scorer classifies it VACUOUS, never GOOD.
7. Verify native action 0/wait/Load meanings and record actual branch hash. Replay oracle solo and joint assignments without mistaking a movement for waiting. Monitor attempted joint Load even when pickup fails; successful-pickup counter alone must fail this test.
8. Seeded generation reproduces manifest hashes; no development/test duplicate or relabeling leakage; 60 independent test families with the declared 30/30 strata.
9. Dry run produces exactly 144 gate slots and 2,880 E1 slots, with 720 R/F pairs per model and 360 per model/language. These are slots, not independent worlds. No network access in dry run.
10. Analysis fixtures: perfect oracle -> PairPass 1; deterministic rule-blind -> 0; always idle -> 0; malformed response stays in the strict denominator. Permuting task/agent IDs preserves labels; changing a necessary capacity changes physical labels.
11. Resume/retry tests prevent duplicate successful requests, retain every attempt and reject incompatible manifest/prompt/model hashes. An exhausted API failure makes the run incomplete.
12. Bilingual review and P0 thresholds are **live-run prerequisites**, not fabricated offline pass results. A failing gate blocks the corresponding confirmatory condition and remains visible in the report.

**Definition of done:** offline tests pass; dry-run outputs and analysis reproduce expected scores; action/stop semantics and bilingual sign-off are documented; live-call estimate and caps are reviewable. Actual live results are a separate execution stage. Acceptance tests above are specified, not claimed to have been run against the recovered prototype.

## 8. Do not implement

No new LLM architecture, decentralized debate, memory/RAG/graph system, fine-tuning, RL, LTL synthesis, shield that silently fixes policy failures, PDDL translation, learned judge, new simulator physics, visualization redesign, colors/connectors, additional languages/code-switching, exception tiers, large-team/partial-observability scaling, adversarial pressure experiments or broad prompt sweeps. No planner leaderboard, claims of global optimality, intentional cheating or novel benchmark. Do not reconstruct missing experimental outcomes from the old report. Implement the E1 harness and its measurement contract only.

## Evidence anchors

This spec narrows the existing [research direction brief](https://chatgpt.com/library?file_id=libfile_f2512c8845f881919026dfc7d7e94441&account_id=personal), sections 4-7, and [deep literature review](https://chatgpt.com/library?file_id=libfile_286a08de91788191b218bf4b1e103b78&account_id=personal), sections 3 and 7-9. It replaces their illustrative full-factorial counts for E1, without rewriting their longer-term research agenda. Independent procedural grading has precedent in [SOPBench](https://aclanthology.org/2026.emnlp-main.936/); language/interface controls in [MLCL](https://aclanthology.org/2026.acl-long.2039/); language-by-constraint evaluation in [XIFBench](https://doi.org/10.52202/085713-0584); and controlled workflow complexity in [CC-Gen](https://aclanthology.org/2026.acl-long.767/). These references are reused from the validated review, not newly reviewed claims of absence.
