# Policy review and next-step launch packet

Prepared 4 November 2026. No new API calls made by preparation. Original policies, prompts, worlds and executor unchanged.

Approval of the work plan is recorded in the conversation. Human semantic confirmation and phase spending amounts are requested separately; no approval is inferred or fabricated.

## Exact policy texts

### P0, realization 1

EN: Select at least one box for a feasible pickup. For each selected box, the combined lifting capacity of the assigned robots must be at least its weight. Each robot may be assigned to at most one box; a robot may be unassigned.

VI: Hãy chọn ít nhất một thùng để có thể thu gom được. Với mỗi thùng được chọn, tổng sức nâng của các robot được phân công phải ít nhất bằng trọng lượng của thùng. Mỗi robot chỉ được phân công tối đa một thùng; có thể không phân công nhiệm vụ cho một robot.

### R, realization 1

EN: For every box you select next, assign both robots to that box. Do not select a box for just one robot.

VI: Với mỗi thùng được chọn tiếp theo, hãy phân công cả hai robot cùng thu gom thùng đó. Không được phân công chỉ một robot cho một thùng.

### R, realization 2

EN: The next pickup must use the two robots together on one box. Individual pickup assignments are forbidden.

VI: Lần thu gom tiếp theo phải do hai robot cùng thực hiện trên một thùng. Không được phân công thu gom riêng lẻ.

### F, realization 1

EN: For every box you select next, assign exactly one robot to that box. Do not select the same box for both robots.

VI: Với mỗi thùng được chọn tiếp theo, hãy phân công đúng một robot thu gom thùng đó. Không được phân công cả hai robot cho cùng một thùng.

### F, realization 2

EN: The next pickup assignments must be individual. Assigning the two robots together to one box is forbidden.

VI: Các phân công thu gom tiếp theo phải là phân công riêng lẻ. Không được phân công hai robot cùng thu gom một thùng.

## Paid phases awaiting confirmation

- Matched Vietnamese development: 108 calls, no retries, cap USD 1, conservative token reservation USD 0.1785888.
- Separate development-only compatibility smoke: 4 slots, up to 12 attempts, cap USD 0.05, worst-case USD 0.0363792.
- Formal P0 gate after successful smoke and configuration freeze: 144 slots, up to 432 attempts, cap USD 1.50, worst-case USD 1.3096512.
- Combined requested ceiling: USD 2.55. No held-out E1 spending included.
- Malformed outputs are not retried. Failed attempts retain their reservations; all responses/failures are logged.
- Held-out E1 remains blocked until the real matching P0 gate passes and its separate finite budget is authorized.

## Reproduce preparation

```bash
MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python experiments/llm_lbf_demo/pilot/next-steps-20261104/run_vietnamese_sweep.py --preflight
```

Live Vietnamese command (fails closed without genuine matching approval):

```bash
MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python experiments/llm_lbf_demo/pilot/next-steps-20261104/run_vietnamese_sweep.py --approval experiments/llm_lbf_demo/pilot/next-steps-20261104/vietnamese-approval.json
```

P0 smoke/freeze/gate commands are unchanged in ../../p0/P0_LAUNCH_READINESS.md. No final freeze is created before real smoke.

Source prices rechecked against official model pages on 4 November 2026: https://developers.openai.com/api/docs/models/gpt-4o-mini and https://developers.openai.com/api/docs/models/gpt-4.1-mini.
