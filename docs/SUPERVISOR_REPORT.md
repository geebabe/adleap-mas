# Policy2Action: Research Progress Report
**Project**: Policy2Action — Natural Language Policy Execution in Multi-Agent Systems  
**Simulator**: AdLeap-MAS (Level-Based Foraging Domain)  
**Supervisor**: Prof. Leandro Soriano Marcolino  
**Student**: Nguyen Minh Chi  
**Date**: October 29, 2026  
**Git Branch**: `feature/llm-policy-controller`  

---

## 1. Executive Summary

The goal of **Policy2Action** is to enable autonomous robotic agents in the `adleap-mas` simulator to interpret, reason about, and strictly adhere to policies expressed in natural human language.

Rather than relying on an LLM to blindly generate low-level grid movements (which classical algorithms already solve in sub-milliseconds), we developed and validated a **Hierarchical Hybrid Architecture**:
1. **High-Level Semantic Controller (`gpt-4o-mini`)**: Interprets free-form natural language policies, evaluates semantic priorities (weight attributes, spatial boundaries, cooperative rules, multilingual constraints), and allocates target tasks.
2. **Low-Level Motion Planner ($A^*$ in `adleap-mas`)**: Computes collision-free, optimal grid navigation and handles actuator timing.

We have successfully implemented and benchmarked this system across both **single-agent** and **two-agent collaborative** scenarios, empirically proving:
- **The Policy Cost Trade-off**: Quantitative measurement of travel overhead imposed by semantic constraints (up to $+34.8\%$ detour overhead).
- **Synchronized Multi-Agent Coordination**: Two robots dynamically rendezvousing at a heavy box and executing simultaneous joint lifting.
- **Strict Compliance vs. Cheating**: The controller cleanly terminates when remaining tasks violate policy constraints, rather than cheating to inflate completion scores.

---

## 2. Research Motivation: Why LLM + Classical Planning?

A central question in our lab discussion was: *Why use an LLM when classical planners like MCTS or $A^*$ already exist in `adleap-mas`?*

| Capability | Classical Planners ($A^*$, MCTS) | Pure LLM Action Generation | **Hybrid Policy2Action (Our Method)** |
| :--- | :---: | :---: | :---: |
| **Grid Navigation ($10 \times 10$)** | **Optimal ($< 1$ ms)** | Inefficient, hallucination risk | **Optimal ($A^*$ low-level)** |
| **Semantic Policy Comprehension** | Cannot parse human language | Strong reasoning capability | **Full NLP reasoning (`gpt-4o-mini`)** |
| **Multi-Agent Task Allocation** | Requires rigid heuristic rules | Flexible context-aware matching | **Dynamic semantic assignment** |
| **Multi-Stop Tour Optimization** | Requires hardcoded TSP solver | Evaluates candidate sequences | **Pairwise distance matrix + LLM** |
| **Cross-Lingual Zero-Shot** | Impossible | Multilingual out-of-the-box | **Zero-shot English / Vietnamese** |

> **Scientific Thesis**: The core value of LLMs in multi-agent environments is not in navigating 2D grid coordinates, but in **interpreting unstructured human rules into high-level task allocations and resolving compliance-versus-efficiency trade-offs**.

---

## 3. System Architecture & Workflow

The controller operates on an **event-triggered hierarchical workflow**:

```
[Environment State (Agents & Boxes)] + [Natural Language Policy]
                           │
                           ▼
          ┌───────────────────────────────────┐
          │ High-Level LLM Semantic Controller│
          │          (gpt-4o-mini)            │
          └───────────────────────────────────┘
                           │
       Outputs: Task Allocation & Cooperation Flag (JSON)
                           │
                           ▼
          ┌───────────────────────────────────┐
          │  Low-Level Motion Coordinator     │
          │    - Slot Matching (East/West)    │
          │    - A* Pathfinding               │
          │    - Rendezvous & Handshake       │
          └───────────────────────────────────┘
                           │
                           ▼
            Simultaneous Execution in AdLeap-MAS
```

### Input Payload (Sent to LLM)
When replanning is needed, the current world state is serialized into clean JSON:
```json
{
  "grid_size": [10, 10],
  "natural_language_policy": "Robots must always collaborate to lift heavy boxes (level > 1.0) first. Only after all heavy boxes are cleared should they forage light boxes.",
  "agents": [
    {"id": "A", "position": [1, 1], "direction": "North", "level": 1.0},
    {"id": "B", "position": [8, 1], "direction": "North", "level": 1.0}
  ],
  "available_tasks": [
    {"task_id": "0", "position": [2, 7], "level": 0.6, "requires_coop": false},
    {"task_id": "1", "position": [8, 7], "level": 0.8, "requires_coop": false},
    {"task_id": "2", "position": [5, 5], "level": 1.6, "requires_coop": true}
  ],
  "completed_tasks": []
}
```

### Output Decision (Returned by LLM)
The LLM returns structured JSON specifying task assignments and strategic reasoning:
```json
{
  "reasoning": "Policy mandates collaborative lifting of heavy boxes first. Task 2 (level 1.6) requires both agents. Both Agent A and Agent B are assigned to Task 2.",
  "cooperating_on_heavy": true,
  "agent_A_target_task_id": "2",
  "agent_B_target_task_id": "2",
  "policy_compliance": true,
  "compliance_note": "Cooperating on heavy box as prioritized."
}
```

---

## 4. Two-Agent Collaboration & Synchronized Rendezvous

To test multi-agent collaboration, we formulated a 2-agent scenario on a $10 \times 10$ grid:
- **Agent A**: Position `(1, 1)`, Level `1.0` (Lifting Capacity)
- **Agent B**: Position `(8, 1)`, Level `1.0` (Lifting Capacity)
- **Light Boxes**: Task 0 at `(2, 7)` (Lv 0.6) and Task 1 at `(8, 7)` (Lv 0.8) — liftable by one robot.
- **Heavy Box**: Task 2 at `(5, 5)` (Level `1.6`) — **Exceeds individual capacity** ($1.0 < 1.6$). Both robots must be adjacent and execute `Load` simultaneously ($1.0 + 1.0 = 2.0 \ge 1.6$).

### Low-Level Synchronization Mechanism:
1. **Collision-Free Slot Matching**: The system calculates valid adjacent cells around the box (West, East, South, North) and pairs them to minimize total Manhattan travel:
   $$\min \Big( \text{dist}(\text{Agent A}, \text{Slot}_A) + \text{dist}(\text{Agent B}, \text{Slot}_B) \Big) \quad \text{where } \text{Slot}_A \neq \text{Slot}_B$$
   Agent A approaches West `(4, 5)`, while Agent B approaches East `(6, 5)`.
2. **The Handshake / Rendezvous**:
   - If Agent A arrives earlier, it turns to face the box and **holds position (Action 0 / Stay)**.
   - When Agent B also reaches its slot and turns to face the box, the coordinator detects that both are ready.
   - **Simultaneous Action**: Both robots execute Action 4 (`Load`) at the exact same time-step, lifting the heavy box together (`info['coop'] = 1`).
3. **Transition to Parallel Foraging**: Once the heavy box is cleared, the LLM switches modes, dispatching Agent A to Task 0 and Agent B to Task 1 in parallel.

---

## 5. Empirical Benchmark Results

### Benchmark 1: Single-Agent Policy Trade-Offs (10x10 Grid)
*Baseline scenario: Agent at `(1, 1)`, 3 boxes of weights 0.3, 0.6, 0.9.*

| # | Policy Profile | Constraint Type | Tasks Completed | Policy Compliance | Total Steps | Detour Overhead | Decision Latency |
|---|:---|:---|:---:|:---:|:---:|:---:|:---:|
| **1** | **Unconstrained Optimal** | Path Optimization | **3/3 (100%)** | **100%** | **23** | **0.0% (Baseline)** | 12.06s |
| **2** | **Lightest First** | Attribute Priority | **3/3 (100%)** | **100%** | **26** | **+13.0%** | 7.87s |
| **3** | **Heaviest First** | Attribute Priority | **3/3 (100%)** | **100%** | **31** | **+34.8%** | 8.50s |
| **4** | **Spatial (North First)** | Regional Boundary | **3/3 (100%)** | **100%** | **23** | **+0.0%** | 9.21s |
| **5** | **Multilingual (Vietnamese)**| Cross-Lingual | **3/3 (100%)** | **100%** | **23** | **+0.0%** | 8.82s |

*Data logged from `results/preliminary_benchmark.csv`.*

---

### Benchmark 2: Two-Agent Collaboration (`MAS_DUO`)
*Scenario: 2 Agents at `(1, 1)` and `(8, 1)`, 2 light boxes and 1 heavy box (Level 1.6).*

| # | Policy Profile | Policy Type | Tasks Completed | Coop Heavy Lifts | Policy Compliance | Total Steps | Execution Time |
|---|:---|:---|:---:|:---:|:---:|:---:|:---:|
| **1** | **Cooperative Priority** | Collaborative First | **3/3** | **1 Lift** | **100%** | **13** | 8.49s |
| **2** | **Independent (Light Only)** | Non-Cooperative | **2/3** | **0 Lifts** | **100%** | **9** | 9.83s |
| **3** | **Parallel Optimization** | Throughput Optimal | **3/3** | **1 Lift** | **100%** | **19** | 7.62s |
| **4** | **Multilingual (Vietnamese)** | Cross-Lingual Coop | **3/3** | **1 Lift** | **100%** | **13** | 7.04s |

*Data logged from `results/multiagent_preliminary_benchmark.csv`.*

---

## 6. Key Scientific Insights

1. **Quantifying the "Policy Compliance vs. Efficiency" Trade-off**:
   - In Single-Agent testing, enforcing `"Heaviest First"` caused the agent to intentionally bypass a box at distance 7 to reach a box at distance 13, incurring **$+34.8\%$ travel overhead** relative to the optimal tour.
   - This provides the exact empirical metric Prof. Leandro requested: measuring the numerical penalty of human policy adherence.

2. **Compliance vs. Cheating (The Non-Cooperative Test)**:
   - Under `"Independent (Light Only)"`, the agents collected the two light boxes in 8 steps.
   - At Step 9, with only the heavy box remaining, the LLM controller recognized that lifting it would violate the non-cooperative constraint and **cleanly halted execution**.
   - Result: Completion rate $2/3$, but **Policy Compliance $100\%$**. The agent refused to "cheat" to maximize task reward.

3. **Multi-Agent Efficiency Through Division of Labor**:
   - Clearing all 3 boxes took only **13 steps** with two agents, compared to 23 steps with one agent, demonstrating effective parallel foraging after cooperative rendezvous.

4. **Zero-Shot Cross-Lingual Robustness**:
   - Prompts given in Vietnamese (`"Hai robot phải cùng nhau hợp tác..."`) achieved identical coordination without requiring translation layers.

---

## 7. Simulator & Visual Upgrades in AdLeap-MAS

We enhanced the Pygame visualization engine in `src/envs/LevelForagingEnv.py`:
- **Smooth 120-Segment Fog-of-War**: Atmospheric lighting cone carved with sub-surface alpha blending (`BLEND_RGBA_SUB`).
- **Multi-Agent Dual Vision**: Simultaneous vision cone rendering for all active agents.
- **Differentiated Robot Styling**: Agent A in DeepSkyBlue, Agent B in Coral, with clear orientation arrows and numeric levels.
- **Unified Telemetry HUD**: Displays real-time status and targets for all agents (`[A]: East->(5,5) | [B]: West->(5,5)`).

---

## 8. Proposed Discussion Points for Supervisor Meeting

1. **Review Preliminary Empirical Findings**:
   - Present the single-agent and 2-agent benchmark results demonstrating the compliance vs. detour trade-off curve.
2. **Formalizing "Strategic Dilemma" / Cheating Experiments**:
   - Construct benchmark scenarios where violating the policy offers a massive efficiency gain (e.g., $3\times$ faster completion), and test whether prompting modifications or temperature settings induce the agent to cheat.
3. **Adding Connector / Color Attributes**:
   - Extend robot and box metadata with connector types or colors (as suggested in early emails), requiring specific agent-box compatibility.

---

## 9. Quick Reproduction Commands

```bash
# 1. Activate conda environment
conda activate policy2action

# 2. Interactive Pygame visual demonstrations
python examples/levelforaging_llm.py --display --policy optimal              # 1-Agent
python examples/levelforaging_multiagent_llm.py --display --policy cooperative # 2-Agent

# 3. Automated benchmark suites (generates CSV & Markdown summaries)
python examples/run_benchmark.py             # Single-Agent Benchmark
python examples/run_multiagent_benchmark.py  # 2-Agent Collaboration Benchmark
```
