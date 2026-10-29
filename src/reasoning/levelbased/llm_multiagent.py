"""
Centralized Multi-Agent LLM Semantic Policy Controller for Level-Based Foraging (LBF).
Coordinates two robot agents (Agent A and Agent B) to interpret natural-language policies,
dynamically allocate tasks, synchronize joint rendezvous on heavy boxes, and forage in parallel.
"""
import os
import json
import numpy as np
from src.reasoning.a_star import a_star_planning
from src.reasoning.levelbased.l1 import build_state
from src.envs.LevelForagingEnv import do_action, there_is_task

DEFAULT_MULTIAGENT_POLICY = (
    "Robots must always collaborate to lift heavy boxes (level > 1.0) first. "
    "Only after all heavy boxes are cleared should they forage light boxes."
)

DIRECTION_NAMES = {
    0.0: "East",
    round(np.pi, 2): "West",
    round(np.pi / 2, 2): "North",
    round(3 * np.pi / 2, 2): "South"
}


def get_direction_name(direction_rad):
    r = round(float(direction_rad), 2)
    return DIRECTION_NAMES.get(r, f"{r:.2f} rad")


def get_adjacent_interaction_slots(task_pos, grid_shape, obstacles=None):
    """
    Returns valid adjacent grid cells around task_pos and the required
    facing direction and turn action to face and load the task.
    """
    if obstacles is None:
        obstacles = set()
    x, y = task_pos
    w, h = grid_shape
    candidates = [
        {"slot": (x - 1, y), "required_dir": 0.0, "face_action": 0, "name": "West"},       # Action 0: East
        {"slot": (x + 1, y), "required_dir": np.pi, "face_action": 1, "name": "East"},     # Action 1: West
        {"slot": (x, y - 1), "required_dir": np.pi / 2, "face_action": 2, "name": "South"}, # Action 2: North
        {"slot": (x, y + 1), "required_dir": 3 * np.pi / 2, "face_action": 3, "name": "North"} # Action 3: South
    ]
    valid = []
    for c in candidates:
        sx, sy = c["slot"]
        if 0 <= sx < w and 0 <= sy < h and (sx, sy) not in obstacles:
            valid.append(c)
    return valid


def assign_cooperative_slots(task_pos, pos_A, pos_B, grid_shape, obstacles=None):
    """
    Assigns distinct adjacent interaction slots to Agent A and Agent B
    around a shared heavy box to minimize total Manhattan travel distance.
    """
    valid_slots = get_adjacent_interaction_slots(task_pos, grid_shape, obstacles)
    if len(valid_slots) < 2:
        # Fallback if crowded
        sA = valid_slots[0] if valid_slots else {"slot": pos_A, "required_dir": 0.0, "face_action": 0}
        sB = valid_slots[1] if len(valid_slots) > 1 else {"slot": pos_B, "required_dir": np.pi, "face_action": 1}
        return sA, sB

    best_dist = float('inf')
    best_pair = (valid_slots[0], valid_slots[1])

    for i in range(len(valid_slots)):
        for j in range(len(valid_slots)):
            if i == j:
                continue
            s1, s2 = valid_slots[i], valid_slots[j]
            d1 = abs(pos_A[0] - s1["slot"][0]) + abs(pos_A[1] - s1["slot"][1])
            d2 = abs(pos_B[0] - s2["slot"][0]) + abs(pos_B[1] - s2["slot"][1])
            total_d = d1 + d2
            if total_d < best_dist:
                best_dist = total_d
                best_pair = (s1, s2)

    return best_pair[0], best_pair[1]


def is_facing(agent_pos, agent_dir, target_pos):
    dx, dy = 0, 0
    if abs(agent_dir - np.pi / 2) < 0.1:  # North
        dy = 1
    elif abs(agent_dir - 3 * np.pi / 2) < 0.1:  # South
        dy = -1
    elif abs(agent_dir - 0.0) < 0.1 or abs(agent_dir - 2 * np.pi) < 0.1:  # East
        dx = 1
    elif abs(agent_dir - np.pi) < 0.1:  # West
        dx = -1

    facing_pos = (agent_pos[0] + dx, agent_pos[1] + dy)
    return facing_pos == tuple(target_pos)


def call_gpt4o_mini_multiagent_controller(policy_text, agents_info, tasks_info, grid_shape, completed_tasks=None):
    """
    Calls OpenAI gpt-4o-mini to act as Centralized Multi-Agent Semantic Controller.
    Assigns target tasks to Agent A and Agent B, identifying whether to collaborate
    on a heavy box or divide and conquer light boxes.
    """
    if completed_tasks is None:
        completed_tasks = []

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or api_key == "your_openai_api_key_here":
        print("\n[Multi-Agent LLM] Running offline rule fallback (no OPENAI_API_KEY).")
        return fallback_multiagent_controller(policy_text, agents_info, tasks_info, completed_tasks)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        system_prompt = (
            "You are a Centralized Multi-Agent Policy Controller for two autonomous robot agents "
            "(Agent A and Agent B) in a 2D Level-Based Foraging (LBF) grid world.\n"
            "Robots have lifting capacities (levels). Boxes (tasks) have weights (levels).\n"
            "- A box with level <= 1.0 can be lifted by a SINGLE robot alone.\n"
            "- A heavy box with level > 1.0 CANNOT be lifted alone; it REQUIRES BOTH robots to collaborate "
            "and lift simultaneously from adjacent cells.\n"
            "Your job is to read the Natural Language Policy and assign target tasks to Agent A and Agent B.\n"
            "If the policy demands cooperation or heavy-first, assign BOTH agents to the same heavy box.\n"
            "If only light boxes remain, or policy demands independent foraging, assign different light boxes "
            "to Agent A and Agent B in parallel to maximize throughput.\n"
            "If a policy strictly forbids certain boxes (e.g., non-cooperative policy forbidding heavy boxes), "
            "set the agent's target to null once permitted boxes are exhausted.\n"
            "Return valid JSON only."
        )

        user_content = {
            "grid_size": list(grid_shape),
            "natural_language_policy": policy_text,
            "agents": agents_info,
            "available_tasks": tasks_info,
            "completed_tasks": completed_tasks,
            "instructions": (
                "1. Analyze the natural language policy requirements.\n"
                "2. If heavy boxes (level > 1.0) must be prioritized, set cooperating_on_heavy=true "
                "and assign both agent_A_target_task_id and agent_B_target_task_id to the heavy task ID.\n"
                "3. Sequential progression: If a policy states 'after all heavy boxes are cleared, forage light boxes' (or similar), "
                "check completed_tasks: if all heavy boxes are already completed (or none remain in available_tasks), "
                "the condition is satisfied! You MUST allocate the remaining light boxes to Agent A and Agent B in parallel.\n"
                "4. When allocating light boxes, assign different tasks to A and B based on proximity "
                "to minimize travel distance (cooperating_on_heavy=false).\n"
                "5. If a policy strictly forbids heavy boxes (non-cooperative), only forage light boxes and set targets to null "
                "once light boxes are exhausted.\n"
                "6. Output JSON with keys:\n"
                "   - 'reasoning': Step-by-step rationale\n"
                "   - 'cooperating_on_heavy': boolean\n"
                "   - 'agent_A_target_task_id': task ID string or null\n"
                "   - 'agent_B_target_task_id': task ID string or null\n"
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
        return result

    except Exception as e:
        print(f"\n[Multi-Agent LLM Error] OpenAI API call failed: {e}")
        return fallback_multiagent_controller(policy_text, agents_info, tasks_info, completed_tasks)


def fallback_multiagent_controller(policy_text, agents_info, tasks_info, completed_tasks=None):
    """
    Deterministic rule-based fallback for multi-agent coordination.
    """
    if not tasks_info:
        return {
            "reasoning": "[Fallback] No tasks remaining.",
            "cooperating_on_heavy": False,
            "agent_A_target_task_id": None,
            "agent_B_target_task_id": None,
            "policy_compliance": True,
            "compliance_note": "Mission complete."
        }

    policy_lower = policy_text.lower()
    heavy_tasks = [t for t in tasks_info if t["level"] > 1.0]
    light_tasks = [t for t in tasks_info if t["level"] <= 1.0]

    # Non-cooperative policy
    if any(k in policy_lower for k in ["independent", "không hợp tác", "alone", "never attempt heavy"]):
        if light_tasks:
            tA = light_tasks[0]["task_id"]
            tB = light_tasks[1]["task_id"] if len(light_tasks) > 1 else light_tasks[0]["task_id"]
            return {
                "reasoning": "[Fallback] Independent policy: allocated light tasks to agents without collaboration.",
                "cooperating_on_heavy": False,
                "agent_A_target_task_id": tA,
                "agent_B_target_task_id": tB,
                "policy_compliance": True,
                "compliance_note": "Complied with non-cooperative constraint."
            }
        else:
            return {
                "reasoning": "[Fallback] Independent policy: only heavy tasks remain, strictly forbidden to collaborate.",
                "cooperating_on_heavy": False,
                "agent_A_target_task_id": None,
                "agent_B_target_task_id": None,
                "policy_compliance": True,
                "compliance_note": "Stopped cleanly without violating non-cooperation rule."
            }

    # Cooperative Priority (Default)
    if heavy_tasks:
        h = heavy_tasks[0]
        return {
            "reasoning": f"[Fallback] Cooperative policy: both agents assigned to heavy task {h['task_id']} (level {h['level']}).",
            "cooperating_on_heavy": True,
            "agent_A_target_task_id": h["task_id"],
            "agent_B_target_task_id": h["task_id"],
            "policy_compliance": True,
            "compliance_note": "Cooperating on heavy box."
        }
    else:
        # Split light tasks
        tA = light_tasks[0]["task_id"] if len(light_tasks) > 0 else None
        tB = light_tasks[1]["task_id"] if len(light_tasks) > 1 else tA
        return {
            "reasoning": "[Fallback] Heavy tasks cleared: splitting remaining light tasks in parallel.",
            "cooperating_on_heavy": False,
            "agent_A_target_task_id": tA,
            "agent_B_target_task_id": tB,
            "policy_compliance": True,
            "compliance_note": "Parallel foraging."
        }


def multiagent_plan_step(env, policy_text):
    """
    Centralized coordinator for Agent A and Agent B:
    1. Evaluates environment state & policy.
    2. Calls LLM Controller to assign targets.
    3. Handles rendezvous and simultaneous joint loading for heavy boxes.
    4. Executes collision-free low-level A* motion.
    """
    agents = env.components['agents']
    tasks = env.components['tasks']
    active_tasks = [t for t in tasks if not t.completed]

    if not active_tasks:
        for ag in agents:
            ag.next_action = 0
            ag.target = None
        return env, {'action reward': 0, 'just_finished_tasks': [], 'coop': 0}, True

    ag_A = next(a for a in agents if str(a.index) == 'A')
    ag_B = next(a for a in agents if str(a.index) == 'B')

    # Re-evaluate targets if either agent has no target or target task was completed
    need_replan = (
        ag_A.target is None or ag_B.target is None or
        not any(t.position == ag_A.target and not t.completed for t in active_tasks) or
        not any(t.position == ag_B.target and not t.completed for t in active_tasks)
    )

    if need_replan:
        agents_info = [
            {"id": "A", "position": list(ag_A.position), "direction": get_direction_name(ag_A.direction), "level": float(ag_A.level)},
            {"id": "B", "position": list(ag_B.position), "direction": get_direction_name(ag_B.direction), "level": float(ag_B.level)}
        ]
        tasks_info = [
            {
                "task_id": str(t.index),
                "position": list(t.position),
                "level": round(float(t.level), 2),
                "requires_coop": bool(t.level > 1.0)
            }
            for t in active_tasks
        ]
        completed_info = [
            {"task_id": str(t.index), "position": list(t.position), "level": round(float(t.level), 2)}
            for t in tasks if t.completed
        ]

        decision = call_gpt4o_mini_multiagent_controller(
            policy_text, agents_info, tasks_info, env.shape, completed_info
        )

        ag_A.smart_parameters['last_llm_decision'] = decision

        tA_id = decision.get("agent_A_target_task_id")
        tB_id = decision.get("agent_B_target_task_id")

        matched_A = next((t for t in active_tasks if str(t.index) == str(tA_id)), None)
        matched_B = next((t for t in active_tasks if str(t.index) == str(tB_id)), None)

        ag_A.target = matched_A.position if matched_A else None
        ag_B.target = matched_B.position if matched_B else None

        print("\n" + "=" * 70)
        print("🤖 [Centralized Multi-Agent LLM Controller - gpt-4o-mini]")
        print(f"📋 Policy: \"{policy_text}\"")
        print(f"🎯 Target A: {tA_id} ({ag_A.target}) | Target B: {tB_id} ({ag_B.target})")
        print(f"🤝 Cooperating on Heavy: {decision.get('cooperating_on_heavy', False)}")
        print(f"💡 Reasoning: {decision.get('reasoning')}")
        print(f"✅ Compliance: {decision.get('policy_compliance')} ({decision.get('compliance_note', '')})")
        print("=" * 70 + "\n")

    # If both targets are None (policy restriction or done)
    if ag_A.target is None and ag_B.target is None:
        ag_A.next_action = 0
        ag_B.next_action = 0
        return env, {'action reward': 0, 'just_finished_tasks': [], 'coop': 0}, True

    # Compute action for each agent
    state = build_state(env.shape, env.components)
    obstacles = set(env.components.get('obstacles', []))
    for t in active_tasks:
        obstacles.add(t.position)

    # CASE 1: Cooperating on the SAME heavy box
    if ag_A.target is not None and ag_A.target == ag_B.target:
        box_pos = ag_A.target
        slot_A, slot_B = assign_cooperative_slots(box_pos, ag_A.position, ag_B.position, env.shape, obstacles)

        # Check Agent A status
        at_slot_A = (ag_A.position == slot_A["slot"])
        facing_A = is_facing(ag_A.position, ag_A.direction, box_pos)

        # Check Agent B status
        at_slot_B = (ag_B.position == slot_B["slot"])
        facing_B = is_facing(ag_B.position, ag_B.direction, box_pos)

        # If both are in position and facing box -> Synchronized Joint Load!
        if at_slot_A and facing_A and at_slot_B and facing_B:
            ag_A.next_action = 4  # Load
            ag_B.next_action = 4  # Load
        else:
            # Action for Agent A
            if not at_slot_A:
                ag_A.next_action = a_star_planning(state, env.shape[0], env.shape[1],
                                                   env.action_space, ag_A.position, slot_A["slot"])
            elif not facing_A:
                ag_A.next_action = slot_A["face_action"]
            else:
                # Agent A is ready at slot and facing, waiting for Agent B
                ag_A.next_action = 0

            # Action for Agent B
            if not at_slot_B:
                ag_B.next_action = a_star_planning(state, env.shape[0], env.shape[1],
                                                   env.action_space, ag_B.position, slot_B["slot"])
            elif not facing_B:
                ag_B.next_action = slot_B["face_action"]
            else:
                # Agent B is ready at slot and facing, waiting for Agent A
                ag_B.next_action = 0

    # CASE 2: Parallel foraging on DIFFERENT boxes (or solo)
    else:
        for ag in [ag_A, ag_B]:
            if ag.target is None:
                ag.next_action = 0
                continue

            slots = get_adjacent_interaction_slots(ag.target, env.shape, obstacles)
            if not slots:
                ag.next_action = 0
                continue

            # Pick closest slot
            best_slot = min(slots, key=lambda s: abs(ag.position[0] - s["slot"][0]) + abs(ag.position[1] - s["slot"][1]))
            at_slot = (ag.position == best_slot["slot"])
            facing = is_facing(ag.position, ag.direction, ag.target)

            if at_slot and facing:
                ag.next_action = 4  # Load
            elif at_slot and not facing:
                ag.next_action = best_slot["face_action"]
            else:
                ag.next_action = a_star_planning(state, env.shape[0], env.shape[1],
                                                 env.action_space, ag.position, best_slot["slot"])

    # Step environment
    next_env, info = do_action(env)
    next_active = [t for t in next_env.components['tasks'] if not t.completed]
    done = (len(next_active) == 0)

    return next_env, info, done
