# Recovery report — 4 November 2026

## What survived

The workspace was not empty. At inspection its HEAD was
`cb6cc53b016d212a62e8496e76b4f6f3c98381b9`; origin points to the
`geebabe/adleap-mas` fork. The existing worktree had no tracked modifications.

Recovered in place, without editing or moving originals:

- `docs/emails.txt`: supervisor discussion plus later recollections. It contains
  the recommendation to measure policy compliance separately from completion,
  and mentions PROJECT_CONTEXT.md and meeting slides. Recollections embedded in
  this file are provenance, not proof those referenced files survived.
- `docs/SUPERVISOR_REPORT.md`: prior claims, architecture, prompts, commands and
  numerical tables. Claims are unverified, including optimality, cross-language
  robustness, compliance percentages and reported timings.
- `src/reasoning/levelbased/llm.py`, `llm_multiagent.py`: recovered controller code.
- `examples/levelforaging_llm.py`, `levelforaging_multiagent_llm.py`,
  `run_benchmark.py`, `run_multiagent_benchmark.py`: demos and benchmark drivers.
- Four preliminary CSV/Markdown files under `results/`; three rendered images
  under `tmp/`; framework PDF under `docs/`; compiled Python caches.
- Git history includes `42b979d` (preliminary benchmark), `17bb4d5` (two-agent
  controller) and `cb6cc53` (supervisor report). These are recovery anchors.

SHA-256 hashes and sizes of the principal artifacts are recorded in
`evidence/recovery-manifest.json`. The emails are not copied into new reports.
Existing `.env` was neither read nor used. Old scripts were not executed because
they may call paid services. No historical measurement has been reproduced.

## Gaps

No standalone `PROJECT_CONTEXT.md` or `meeting_slides.md` was found among workspace
files or in the available Git path history. No named backup archive or alternate
source recovery bundle was found in the workspace. This is a bounded workspace
inspection, not a forensic search of personal storage or remote email accounts.
Full historical prompts, provider response provenance, exact model versions,
original environments and the laptop's lost version cannot be authenticated from
these artifacts. Whether the surviving implementation exactly matches the lost
prototype is unknown. CSV tables alone cannot establish compliance.

## Upstream and integration

Cloned `https://github.com/lsmcolab/adleap-mas.git` into the experiment's ignored
`vendor/adleap-mas` and detached at
`0874e57fc4974d7e1f8bdd5d39e04119e7053d6f`.
`upstream.lock.json` and `bootstrap.py` reproduce this pin. Source location,
commit and `src/` cleanliness are checked on process startup. Parent and vendor
`src/` remain unchanged.

Actual APIs inspected and exercised: `Agent`, `Task`, `LevelForagingEnv`,
`there_is_task`, `do_action`, `new_position_given_action`, `action2direction`,
and the ad hoc transition dispatch. The central adapter deliberately uses
`do_action`, the framework's existing simultaneous physical transition;
`env.step` would replace teammate commands by ad hoc reasoning. Thus this is
real LBF integration rather than a Gym wrapper-equivalence claim.

Two recovered integration defects were resolved locally:

1. The older two-agent code/report calls action 0 “Stay.” Upstream action 0 is
   East and changes direction/position. The adapter uses `next_action=None`,
   explicitly supported by `do_action`, and tests it against the real environment.
2. Pinned upstream initializes `smart_parameters['ntasks']=None` then subtracts
   completed tasks without guarding None. `make_env` initializes this field to
   the actual task count. No simulator patch is needed.

Task cells block movement and allow facing changes via attempted movement into
an occupied task cell. LOAD acts on the immediately facing task. Cooperative
capacity only combines within the same tick. Distinct slots, conservative
occupied-cell blocking and synchronized LOAD are tested. This coordinator does
not solve arbitrary multi-agent pathfinding.

Upstream imports `TradeStockEnv` eagerly, which imports Matplotlib even for
headless LBF. A clean Python 3.12 venv with the complete 15-package lock was
installed and tested. Initial shell network access required a sandbox network
escalation for clone/package installation; both succeeded. An initial run exposed
the ntasks defect; its adapter fix was verified. A later test fixture still used
a light scenario after scenario pairing was corrected; it was changed to the
explicit heavy fixture and the final tests pass. Earlier generated evidence is
kept locally in ignored superseded directories, not used as final results.

## Current status

The isolated minimal research testbed is implemented and verified with free
controllers and scripted model outputs. The optional real LLM backend is
implemented but untested against a provider. No paid API calls, GPU work,
multilingual evaluation or historical result reproduction was performed. See
RESULTS.md for current evidence and EXPERIMENT_PLAN.md for what it can establish.
