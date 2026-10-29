import os
import json
import numpy as np
from dotenv import load_dotenv

from src.reasoning.a_star import a_star_planning
from src.reasoning.levelbased.l1 import build_state, distance

# Load environment variables from .env
load_dotenv()

DEFAULT_POLICY = "Always collect the lightest box first (lowest level). If levels are equal, choose the closest one."

DIRECTION_NAMES = {
    0: "East",
    np.pi: "West",
    np.pi / 2: "North",
    3 * np.pi / 2: "South"
}


def get_direction_name(direction):
    for dir_val, name in DIRECTION_NAMES.items():
        if np.isclose(direction, dir_val):
            return name
    return f"{direction:.2f} rad"


def is_facing_target(agent_pos, agent_direction, target_pos):
    """Check if agent is adjacent to target_pos and facing towards it."""
    if np.isclose(agent_direction, np.pi / 2):      # North
        facing = (agent_pos[0], agent_pos[1] + 1)
    elif np.isclose(agent_direction, 3 * np.pi / 2):  # South
        facing = (agent_pos[0], agent_pos[1] - 1)
    elif np.isclose(agent_direction, 0) or np.isclose(agent_direction, 2 * np.pi):  # East
        facing = (agent_pos[0] + 1, agent_pos[1])
    elif np.isclose(agent_direction, np.pi):       # West
        facing = (agent_pos[0] - 1, agent_pos[1])
    else:
        facing = None
    return facing == tuple(target_pos)


def call_gpt4o_mini_controller(policy_text, agent_info, tasks_info, inter_task_distances, grid_shape, completed_tasks=None):
    """
    Calls OpenAI gpt-4o-mini to act as Semantic Policy Controller & Route Optimizer.
    Selects the next target box from available tasks based on the natural language policy,
    evaluating both semantic constraints and tour path efficiency.
    """
    if completed_tasks is None:
        completed_tasks = []

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    
    # Check if a valid API key exists
    if not api_key or api_key == "your_openai_api_key_here":
        print("\n[LLM Controller] Note: OPENAI_API_KEY not found or using placeholder in .env.")
        print("[LLM Controller] Running offline semantic rule fallback to simulate LLM decision.")
        return fallback_semantic_target(policy_text, agent_info, tasks_info)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        system_prompt = (
            "You are an intelligent Semantic Policy Controller and Route Optimizer for an autonomous robot agent "
            "in a 2D Level-Based Foraging (LBF) grid world.\n"
            "Your job is to read the user's Natural Language Policy, examine the available boxes (tasks), "
            "and decide which box to target next in accordance with the policy.\n"
            "If prioritized tasks matching a condition have already been collected (see completed_tasks), "
            "and remaining available tasks are not explicitly forbidden, select the next available task to continue foraging.\n"
            "When the policy demands path optimization, shortest route, or efficiency (or does not strictly forbid it), "
            "evaluate candidate multi-stop routes (tours) to minimize total travel steps and avoid wasteful back-and-forth detours.\n"
            "Return your decision in valid JSON format only."
        )

        user_content = {
            "grid_size": list(grid_shape),
            "natural_language_policy": policy_text,
            "agent_state": agent_info,
            "available_tasks": tasks_info,
            "completed_tasks": completed_tasks,
            "inter_task_distances": inter_task_distances,
            "instructions": (
                "1. Analyze the natural language policy requirements carefully.\n"
                "2. If the policy specifies strict attribute priorities (e.g., 'heaviest first'), adhere to it and note the detour cost.\n"
                "3. If the policy specifies priority or ordering (e.g. 'prioritize X first before Y'), check completed_tasks: "
                "if all X tasks are completed or none remain, proceed to collect the remaining available tasks.\n"
                "4. If the policy specifies 'shortest path', 'optimal route', or efficiency, evaluate the overall multi-stop tour cost "
                "(agent -> task1 -> task2 -> ...) and choose the sequence that minimizes total travel distance.\n"
                "5. Provide the output as JSON with keys:\n"
                "   - 'reasoning': Step-by-step rationale comparing route options and policy compliance\n"
                "   - 'planned_sequence': List of task IDs in visiting order\n"
                "   - 'selected_task_id': The immediate next task ID to visit (or null if strictly forbidden)\n"
                "   - 'target_position': [x, y] coordinates of the selected task (or null if no task selected)\n"
                "   - 'estimated_total_tour_cost': Estimated total steps for the entire remaining tour\n"
                "   - 'policy_compliance': boolean\n"
                "   - 'compliance_note': brief note"
            )
        }

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_content, indent=2)}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )

        result = json.loads(response.choices[0].message.content)
        
        # Ensure target_position is a tuple of ints if present and valid
        if result.get("target_position") is not None and isinstance(result["target_position"], (list, tuple)):
            result["target_position"] = tuple(result["target_position"])
        elif result.get("selected_task_id") is not None:
            # Match position from tasks_info
            matched = next((t for t in tasks_info if str(t["task_id"]) == str(result["selected_task_id"])), None)
            if matched:
                result["target_position"] = tuple(matched["position"])
            
        return result

    except Exception as e:
        print(f"\n[LLM Controller Error] Failed to call OpenAI API: {e}")
        print("[LLM Controller] Falling back to offline semantic rule matching.")
        return fallback_semantic_target(policy_text, agent_info, tasks_info)


def fallback_semantic_target(policy_text, agent_info, tasks_info):
    """
    Deterministic rule-based fallback supporting common policy templates:
    optimal path (TSP), lightest, heaviest, closest, northern.
    """
    if not tasks_info:
        return None

    policy_lower = policy_text.lower()
    import itertools

    # 1. Optimal path / Shortest total route
    if any(k in policy_lower for k in ["optimal", "shortest", "ngắn nhất", "tối ưu", "efficiency", "minimum distance"]):
        best_cost = float('inf')
        best_perm = list(tasks_info)
        agent_pos = tuple(agent_info["position"])
        for perm in itertools.permutations(tasks_info):
            curr = agent_pos
            cost = 0
            for t in perm:
                cost += abs(t["position"][0] - curr[0]) + abs(t["position"][1] - curr[1])
                curr = tuple(t["position"])
            if cost < best_cost:
                best_cost = cost
                best_perm = perm
        chosen = best_perm[0]
        seq = [t["task_id"] for t in best_perm]
        return {
            "reasoning": f"[Fallback Engine] Planned optimal tour {seq} with total cost of {best_cost} steps to minimize distance.",
            "planned_sequence": seq,
            "selected_task_id": chosen["task_id"],
            "target_position": tuple(chosen["position"]),
            "estimated_total_tour_cost": best_cost,
            "policy_compliance": True,
            "compliance_note": f"Shortest tour sequence: {seq}"
        }

    # 2. Lightest first (lowest level)
    elif "lightest" in policy_lower or "lowest level" in policy_lower or "nhẹ nhất" in policy_lower or "level thấp nhất" in policy_lower:
        chosen = min(tasks_info, key=lambda t: (t["level"], t["distance"]))
        rule_name = "lightest task (lowest level)"
    # 3. Heaviest first (highest level)
    elif "heaviest" in policy_lower or "highest level" in policy_lower or "nặng nhất" in policy_lower:
        chosen = max(tasks_info, key=lambda t: (t["level"], -t["distance"]))
        rule_name = "heaviest task (highest level)"
    # 4. Northern half first
    elif "north" in policy_lower or "northern" in policy_lower or "phía bắc" in policy_lower:
        north_tasks = [t for t in tasks_info if t["position"][1] >= 5]
        if north_tasks:
            chosen = min(north_tasks, key=lambda t: t["distance"])
            rule_name = "northern task (y >= 5)"
        else:
            chosen = min(tasks_info, key=lambda t: t["distance"])
            rule_name = "closest remaining task"
    # 5. Closest first (default)
    else:
        chosen = min(tasks_info, key=lambda t: t["distance"])
        rule_name = "closest task by distance"

    return {
        "reasoning": f"[Fallback Engine] Selected {chosen['task_id']} as it satisfies the rule '{rule_name}' under policy: '{policy_text}'.",
        "planned_sequence": [chosen["task_id"]],
        "selected_task_id": chosen["task_id"],
        "target_position": tuple(chosen["position"]),
        "policy_compliance": True,
        "compliance_note": f"Matches rule '{rule_name}'."
    }


def llm_choose_target(env, agent):

    """
    Extracts the current state and invokes the LLM Semantic Policy Controller
    to choose a target task for the agent.
    """
    # 1. Identify active (uncompleted) tasks
    active_tasks = [t for t in env.components['tasks'] if not t.completed]
    if not active_tasks:
        return None, None

    # 2. Extract policy text
    policy = agent.smart_parameters.get('policy', getattr(env, 'policy', DEFAULT_POLICY))

    # 3. Format state for LLM
    agent_info = {
        "agent_id": agent.index,
        "position": list(agent.position),
        "direction": get_direction_name(agent.direction),
        "level": float(agent.level)
    }

    tasks_info = []
    for t in active_tasks:
        d = abs(t.position[0] - agent.position[0]) + abs(t.position[1] - agent.position[1])
        tasks_info.append({
            "task_id": str(t.index),
            "position": list(t.position),
            "level": round(float(t.level), 2),
            "distance_from_agent": d
        })

    # Track completed tasks for temporal reasoning
    completed_tasks = [
        {"task_id": str(t.index), "position": list(t.position), "level": round(float(t.level), 2)}
        for t in env.components.get('tasks', []) if t.completed
    ]

    # Pairwise Manhattan distances between tasks
    inter_task_distances = {}
    for i in range(len(active_tasks)):
        for j in range(i + 1, len(active_tasks)):
            t1, t2 = active_tasks[i], active_tasks[j]
            dist_12 = abs(t1.position[0] - t2.position[0]) + abs(t1.position[1] - t2.position[1])
            inter_task_distances[f"Task_{t1.index}_to_Task_{t2.index}"] = dist_12

    # 4. Query LLM Semantic Controller
    decision = call_gpt4o_mini_controller(
        policy, agent_info, tasks_info, inter_task_distances, env.shape, completed_tasks=completed_tasks
    )

    if decision:
        target_pos = None
        raw_pos = decision.get("target_position")
        if raw_pos is not None:
            target_pos = tuple(raw_pos)
            # Validate target position belongs to an active task
            matching_task = next((t for t in active_tasks if t.position == target_pos), None)
            if matching_task is None:
                # Fallback by matching selected_task_id
                matching_task = next((t for t in active_tasks if str(t.index) == str(decision.get("selected_task_id"))), None)
                if matching_task:
                    target_pos = matching_task.position
                else:
                    target_pos = active_tasks[0].position
        elif decision.get("selected_task_id") is not None:
            matching_task = next((t for t in active_tasks if str(t.index) == str(decision.get("selected_task_id"))), None)
            if matching_task:
                target_pos = matching_task.position

        agent.smart_parameters['last_llm_decision'] = decision
        return target_pos, decision

    return None, None


def llm_planning(env, agent):
    """
    Hybrid LLM Planning Method for Level-Based Foraging (LBF):
    1. High-level (LLM Semantic Policy Controller):
       - If no target is set or the current target task is completed,
         prompts gpt-4o-mini with the natural language policy and active tasks.
       - LLM selects the target task and validates policy compliance.
    2. Low-level (A* Motion Planner):
       - Uses A* to compute the optimal path toward the target.
       - Returns action 4 (Load) when adjacent and facing the target.
    """
    # 1. Build the grid state for pathfinding
    state = build_state(env.shape, env.components)

    # 2. Check current target validity
    if agent.target is not None:
        # Check if task at target is still uncompleted
        active_task = next((t for t in env.components['tasks'] if t.position == agent.target and not t.completed), None)
        if active_task is None:
            agent.target = None

    # 3. If no target, consult the LLM Semantic Policy Controller
    if agent.target is None:
        target_pos, decision = llm_choose_target(env, agent)
        agent.target = target_pos
        if decision:
            print("\n" + "=" * 65)
            print("🤖 [LLM Semantic Policy Controller - gpt-4o-mini]")
            print(f"📋 Policy: \"{agent.smart_parameters.get('policy', getattr(env, 'policy', DEFAULT_POLICY))}\"")
            print(f"🎯 Selected Task: {decision.get('selected_task_id')} at {decision.get('target_position')}")
            print(f"💡 Reasoning: {decision.get('reasoning')}")
            print(f"✅ Compliance: {decision.get('policy_compliance')} ({decision.get('compliance_note', '')})")
            print("=" * 65 + "\n")

    # 4. Check if adjacent and facing target -> execute Load (Action 4)
    if agent.target is not None and is_facing_target(agent.position, agent.direction, agent.target):
        return 4, agent.target

    # 5. Otherwise, use A* pathfinding to step toward target
    if agent.target is not None:
        next_action = a_star_planning(state, env.shape[0], env.shape[1],
                                      env.action_space, agent.position, agent.target)
    else:
        # No target selected (policy complete or restricted) -> Stay in place
        next_action = 0

    return next_action, agent.target


# Alias for compatibility with import_method when agent.type is 'llm_policy'
llm_policy_planning = llm_planning
