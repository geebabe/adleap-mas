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

## 4. Visual Simulation & Simulator Overhaul

In addition to the planning algorithm, we modernized `src/envs/LevelForagingEnv.py` Pygame visualizer:
- **Atmospheric Fog of War**: Replaced coarse 100-ray lines with a smooth 120-segment filled field-of-view cone using sub-surface alpha blending (`BLEND_RGBA_SUB`).
- **HUD & Status Telemetry**: Integrated real-time policy display, active target indicator, and agent level telemetry.
- **Headless & Display Modes**: Verified across macOS Pygame windows and headless rendering pipelines.

---

## 5. Agenda & Concrete Discussion Points for Meeting with Prof. Leandro

1. **Confirm Scope & Direction**:
   - Present the Hybrid Architecture (LLM high-level controller + A\* planner) and benchmark results demonstrating the compliance vs. detour cost curve.
2. **Next Milestone: Multi-Agent Collaboration (`MAS_DUO`)**:
   - Introduce heavy boxes (e.g. weight $1.5$) that require two level $1.0$ agents to rendezvous and lift simultaneously.
   - Test policies such as: *"Agent 1 must always assist Agent 2 with heavy boxes before foraging solo"* vs. non-cooperative solo policies.
3. **Testing "Policy Cheating" & Dilemma Scenarios**:
   - Construct deliberate scenarios where strictly following the policy causes a $2\times$ detour penalty, and measure the threshold where agents or prompting strategies succumb to "cheating" to maximize task reward.
4. **Color / Connector Constraints**:
   - Add box and robot color tags as suggested in the initial email discussions (modeling handle/connector compatibilities in real robotic systems).

---

## 6. How to Reproduce

```bash
# 1. Activate conda environment
conda activate policy2action

# 2. Run the interactive Pygame demonstration
python examples/levelforaging_llm.py --display --policy optimal

# 3. Run the complete 5-policy benchmark suite
python examples/run_benchmark.py
```
