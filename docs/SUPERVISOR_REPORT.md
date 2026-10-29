# Policy2Action: Preliminary Progress Report for Supervisor
**Project**: Policy2Action — Semantic Policy Execution in AdLeap-MAS  
**Domain**: Level-Based Foraging (LBF) 10x10 Grid World  
**Supervisor**: Prof. Leandro Soriano Marcolino  
**Student**: Nguyen Minh Chi  
**Date**: October 29, 2026  
**Git Branch**: `feature/llm-policy-controller`  

---

## 1. Executive Summary

The primary objective of **Policy2Action** is to enable autonomous agents to interpret, reason about, and strictly adhere to natural language policies within the `adleap-mas` multi-agent simulator. 

Rather than treating the Large Language Model (LLM) as a simple step-by-step pathfinder—which classical algorithms (A\*, BFS, MCTS) already solve in milliseconds—we formulated and implemented a **Hybrid Semantic Architecture**:
1. **High-Level Semantic Policy Controller (`gpt-4o-mini`)**: Interprets free-form natural language policies (attribute priorities, spatial boundaries, multilingual instructions), resolves global multi-stop tour sequences (TSP), and verifies policy compliance.
2. **Low-Level Motion Planner (A\* in AdLeap-MAS)**: Executes collision-free grid navigation to the target designated by the controller.

We have successfully executed an empirical 5-policy benchmark on a 10x10 LBF environment with 100% task completion and 100% policy compliance, numerically demonstrating the **trade-off between Policy Compliance and Travel Efficiency**.

---

## 2. Theoretical Framing: Why LLM + Classical Planner?

| Capability | Classical Planners (A\*, MCTS) | Pure LLM Action-Generation | **Hybrid Policy2Action (Our Method)** |
| :--- | :--- | :--- | :--- |
| **Grid Navigation (10x10)** | ✅ Optimal (< 1 ms) | ❌ Inefficient, hallucination risk | ✅ **Optimal (A\* low-level)** |
| **Semantic Policy Parsing** | ❌ Cannot parse human language | ✅ Strong reasoning capability | ✅ **Full NLP reasoning (`gpt-4o-mini`)** |
| **Multi-stop Tour Optimization**| ⚠️ Requires hardcoded TSP solver | ⚠️ Prone to back-and-forth detours | ✅ **Pairwise distance matrix + LLM sequencing** |
| **Cross-Lingual Generalization**| ❌ Impossible | ✅ Multilingual out-of-the-box | ✅ **Zero-shot English/Vietnamese/Mixed** |

> **Scientific Thesis**: The value of LLMs in multi-agent environments is not in navigating 2D coordinates, but in **translating unstructured semantic constraints into high-level task allocations and resolving compliance-versus-efficiency trade-offs**.

---

## 3. Empirical Benchmark Results

We evaluated 5 diverse natural-language policy profiles on a standardized 10x10 LBF scenario with 3 foraging tasks of varying weights (levels $0.3, 0.6, 0.9$) and spatial distributions:

| # | Policy Profile | Policy Type | Tasks Completed | Policy Compliance | Total Steps | Detour Overhead | Decision Latency |
|---|:---|:---|:---:|:---:|:---:|:---:|:---:|
| **1** | **Unconstrained Optimal** | Global Optimization | **3/3 (100%)** | **100%** | **23** | **0.0% (Baseline)** | 12.06s |
| **2** | **Lightest First** | Attribute Priority | **3/3 (100%)** | **100%** | **26** | **+13.0%** | 7.87s |
| **3** | **Heaviest First** | Attribute Priority | **3/3 (100%)** | **100%** | **31** | **+34.8%** | 8.50s |
| **4** | **Spatial (North First)** | Regional Constraint | **3/3 (100%)** | **100%** | **23** | **+0.0%** | 9.21s |
| **5** | **Multilingual (Vietnamese)**| Cross-Lingual | **3/3 (100%)** | **100%** | **23** | **+0.0%** | 8.82s |

*Data logged from `results/preliminary_benchmark.csv` on 2026-10-29.*

### Key Quantitative Findings:
1. **The Cost of Policy Compliance**: Under `"Heaviest First"`, the agent intentionally bypasses nearby lighter boxes (dist 7) to collect the heaviest box first (dist 13), resulting in **31 steps (+34.8% detour overhead)** relative to the unconstrained optimal tour (23 steps). This directly provides the numerical metric Prof. Leandro requested.
2. **Global Tour Optimization**: When fed pairwise inter-task distance matrices, `gpt-4o-mini` consistently selects optimal multi-stop sequences (`T0 -> T2 -> T1`) rather than myopic greedy choices, eliminating back-and-forth oscillation.
3. **Multilingual Robustness**: Zero-shot prompt understanding in Vietnamese (`"Hãy ưu tiên nhặt hộp có trọng lượng nhẹ nhất..."`) achieved identical task execution and compliance without translation pre-processing.

---

## 4. Multi-Agent Collaboration Benchmark (2-Agent Coordination)

To directly realize the multi-agent cooperative vision from Prof. Leandro's emails, we formulated a 2-agent cooperative environment:
- **Robots**: Agent A (level 1.0, initial pos `(1, 1)`) and Agent B (level 1.0, initial pos `(8, 1)`).
- **Boxes**: 
  - Light Box T0 at `(2, 7)` (Level 0.6) — Liftable by either robot alone.
  - Light Box T1 at `(8, 7)` (Level 0.8) — Liftable by either robot alone.
  - **Heavy Box T2 at `(5, 5)` (Level 1.6)** — **Exceeds individual capacity (1.6 > 1.0)**; requires synchronized joint loading from adjacent cells by BOTH robots simultaneously.

| # | Policy Profile | Policy Type | Tasks Completed | Coop Tasks | Policy Compliance | Total Steps | Latency |
|---|:---|:---|:---:|:---:|:---:|:---:|:---:|
| **1** | **Cooperative Priority** | Cooperative Priority | **3/3** | **1 Heavy Lift** | **100%** | **13** | 8.49s |
| **2** | **Independent (Light Only)** | Non-Cooperative | **2/3** | **0 Heavy Lifts** | **100%** | **9** | 9.83s |
| **3** | **Parallel Optimization** | Optimization | **3/3** | **1 Heavy Lift** | **100%** | **19** | 7.62s |
| **4** | **Multilingual (Vietnamese)** | Cross-Lingual Coop | **3/3** | **1 Heavy Lift** | **100%** | **13** | 7.04s |

*Data logged from `results/multiagent_preliminary_benchmark.csv` on 2026-10-29.*

### Key Multi-Agent Insights:
1. **Dynamic Rendezvous & Synchronized Loading**: Under `"Cooperative Priority"`, both agents converge on Heavy Box T2 from distinct non-overlapping adjacent cells (Agent A approaches West `(4, 5)`, Agent B approaches East `(6, 5)`). If one robot arrives earlier, it holds position until its teammate arrives, at which point **both execute Action 4 (Load) in the identical time step (Step 8)** to lift the box (`info['coop'] = 1`).
2. **Parallel Division of Labor**: Once the heavy box is cleared, the controller shifts from cooperative to parallel mode, dispatching Agent A to Task 0 and Agent B to Task 1 simultaneously, clearing the remaining grid in only 5 additional steps.
3. **Strict Compliance vs. Task Completion**: Under `"Independent (Light Only)"`, the agents forage both light boxes in 8 steps, and then **strictly stop** at Step 9 without attempting the heavy box, achieving 100% policy compliance (demonstrating that the LLM controller does not cheat when rules restrict collaboration).

---

## 5. Visual Simulation & Simulator Overhaul

In addition to the planning algorithm, we modernized `src/envs/LevelForagingEnv.py` Pygame visualizer:
- **Multi-Agent Shared Fog of War**: Smooth 120-segment cone carving for all agents simultaneously, illuminating the fog dynamically as robots move.
- **Differentiated Agent Aesthetics**: Agent A rendered in DeepSkyBlue, Agent B rendered in Coral, with clear direction orientation and index labels.
- **Unified Multi-Agent HUD**: Real-time telemetry displaying actions and targets for both agents simultaneously (`[A]: East->(5,5) | [B]: West->(5,5)`).

---

## 6. Agenda & Concrete Discussion Points for Meeting with Prof. Leandro

1. **Demonstrate 1-Agent and 2-Agent Benchmarks**:
   - Present the Hybrid Architecture (LLM high-level controller + A\* planner) and empirical results across both single-agent path trade-offs and 2-agent cooperative synchronization.
2. **Testing "Policy Cheating" & Dilemma Scenarios**:
   - Construct deliberate scenarios where strictly following the policy causes a $2\times$ detour penalty, and measure the threshold where agents or prompting strategies succumb to "cheating" to maximize task reward.
3. **Color / Connector Constraints**:
   - Add box and robot color tags as suggested in the initial email discussions (modeling handle/connector compatibilities in real robotic systems).

---

## 7. How to Reproduce

```bash
# 1. Activate conda environment
conda activate policy2action

# 2. Interactive Pygame demonstrations
python examples/levelforaging_llm.py --display --policy optimal              # 1-Agent
python examples/levelforaging_multiagent_llm.py --display --policy cooperative # 2-Agent

# 3. Run complete benchmark suites
python examples/run_benchmark.py             # Single-Agent Benchmark
python examples/run_multiagent_benchmark.py  # 2-Agent Collaboration Benchmark
```
