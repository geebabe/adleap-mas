"""
Level-Based Foraging (LBF) - 2-Agent Collaborative Experiment.
Demonstrates centralized Multi-Agent LLM Semantic Policy Control in AdLeap-MAS:
- Agent A (level 1.0) and Agent B (level 1.0)
- Light boxes (level <= 1.0) for individual foraging
- Heavy box (level 1.6 > 1.0) requiring synchronized joint collaboration
"""
import sys
import os
import time
import argparse
import numpy as np

sys.path.append(os.getcwd())

from src.envs.LevelForagingEnv import LevelForagingEnv, Agent, Task
from src.reasoning.levelbased.llm_multiagent import (
    multiagent_plan_step,
    DEFAULT_MULTIAGENT_POLICY,
    get_direction_name
)

MULTIAGENT_POLICY_PRESETS = {
    "cooperative": "Robots must always collaborate to lift heavy boxes (level > 1.0) first. Only after all heavy boxes are cleared should they forage light boxes.",
    "independent": "Each robot should only forage light boxes that it can lift alone (level <= 1.0). Never attempt heavy boxes.",
    "optimal": "Collect all boxes in the minimum total time. Allocate tasks between Robot A and Robot B to minimize latency, cooperating on heavy boxes when required.",
    "vietnamese": "Hai robot phải cùng nhau hợp tác nâng các hộp có trọng lượng lớn hơn 1.0 trước, sau đó mới chia nhau nhặt các hộp nhẹ còn lại."
}


def build_two_agent_env(display=False, vision_radius=1.0, vision_angle=1.0):
    """
    Creates standardized 10x10 environment with 2 agents and 3 boxes (2 light, 1 heavy).
    """
    agent_A = Agent(
        index='A',
        atype='llm_policy',
        position=(1, 1),
        direction=np.pi / 2,
        radius=vision_radius,
        angle=vision_angle,
        level=1.0
    )
    agent_B = Agent(
        index='B',
        atype='llm_policy',
        position=(8, 1),
        direction=np.pi / 2,
        radius=vision_radius,
        angle=vision_angle,
        level=1.0
    )

    agent_A.smart_parameters['ntasks'] = 3
    agent_B.smart_parameters['ntasks'] = 3

    # Tasks: 2 light boxes, 1 heavy box
    tasks = [
        Task(index='0', position=(2, 7), level=0.6),  # Light (Liftable by A or B)
        Task(index='1', position=(8, 7), level=0.8),  # Light (Liftable by A or B)
        Task(index='2', position=(5, 5), level=1.6),  # Heavy (Requires BOTH A and B!)
    ]

    components = {
        'agents': [agent_A, agent_B],
        'tasks': tasks,
        'obstacles': [],
        'adhoc_agent_index': 'A'
    }

    env = LevelForagingEnv(
        shape=(10, 10),
        components=components,
        display=display,
        type_knowledge=True,
        parameter_knowledge=True,
        vision_block=False
    )
    return env


def print_env_grid(env):
    grid = [["." for _ in range(env.shape[0])] for _ in range(env.shape[1])]
    for task in env.components['tasks']:
        if not task.completed:
            x, y = task.position
            grid[y][x] = f"T{task.index}"

    for ag in env.components['agents']:
        x, y = ag.position
        grid[y][x] = str(ag.index)

    print("\nInitial Environment Grid (10x10):")
    header = "   " + " ".join(f"{x:2d}" for x in range(env.shape[0]))
    print(header)
    for y in reversed(range(env.shape[1])):
        row_str = " ".join(f"{grid[y][x]:>2s}" for x in range(env.shape[0]))
        print(f"{y:2d} {row_str}")
    print()


def run_multiagent_experiment(policy_text=None, display=False, step_delay=0.25, max_episodes=50):
    if policy_text is None:
        policy_text = DEFAULT_MULTIAGENT_POLICY

    env = build_two_agent_env(display=display)

    print("=" * 75)
    print("🚀 Level-Based Foraging (LBF) - 2-Agent Collaborative Experiment")
    print("🤖 Controller: Centralized Multi-Agent LLM Controller (gpt-4o-mini + A*)")
    print(f"📍 Agent A: (1, 1) [Level 1.0] | Agent B: (8, 1) [Level 1.0]")
    print(f"📦 Boxes: T0(2, 7)[Lv 0.6], T1(8, 7)[Lv 0.8], T2(5, 5)[Lv 1.6 - HEAVY!]")
    print(f"📜 Multi-Agent Policy:\n   \"{policy_text}\"")
    print("=" * 75)

    print_env_grid(env)

    start_time = time.time()
    total_reward = 0
    coop_count = 0
    step_num = 0
    done = False

    if display:
        import pygame
        env.reset_renderer()
        env.render()

    print("-" * 75)
    print("Beginning Multi-Agent Execution...")
    print("-" * 75)

    while step_num < max_episodes and not done:
        step_num += 1

        if display:
            import pygame
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    print("\n[Pygame] Window closed by user.")
                    done = True
                    break
            if done:
                break

        ag_A = next(a for a in env.components['agents'] if str(a.index) == 'A')
        ag_B = next(a for a in env.components['agents'] if str(a.index) == 'B')

        posA_before, dirA_before = ag_A.position, get_direction_name(ag_A.direction)
        posB_before, dirB_before = ag_B.position, get_direction_name(ag_B.direction)

        # Step multi-agent controller
        env, info, done = multiagent_plan_step(env, policy_text)

        actA = env.action_dict.get(ag_A.next_action, "None")
        actB = env.action_dict.get(ag_B.next_action, "None")

        reward = info.get('action reward', 0)
        coop = info.get('coop', 0)
        total_reward += reward
        coop_count += coop

        posA_after = ag_A.position
        posB_after = ag_B.position

        log_str = (
            f"Step {step_num:02d} | "
            f"A: {posA_before}->{posA_after} ({actA:5s}) -> tgt {ag_A.target} | "
            f"B: {posB_before}->{posB_after} ({actB:5s}) -> tgt {ag_B.target}"
        )
        if reward > 0:
            if coop > 0:
                log_str += f" | 🤝 COOP REWARD: +{reward} (Heavy Box Completed by Both Robots!)"
            else:
                log_str += f" | 🎉 SOLO REWARD: +{reward} (Light Box Completed!)"
        print(log_str)

        if display:
            env.episode = step_num
            env.render()
            if step_delay > 0:
                time.sleep(step_delay)

        # Early break if LLM deliberately completed policy or stopped due to restrictions
        last_decision = ag_A.smart_parameters.get('last_llm_decision', {})
        if (ag_A.target is None and ag_B.target is None and
                last_decision.get('agent_A_target_task_id') is None and
                last_decision.get('agent_B_target_task_id') is None):
            print(f"\n[Multi-Agent Controller] Policy objective completed or remaining boxes restricted at step {step_num}.")
            done = True
            break

    elapsed = time.time() - start_time
    if display:
        print("\nDisplaying final state for 2 seconds...")
        time.sleep(2.0)
        env.close()

    print("\n" + "=" * 75)
    print("📊 MULTI-AGENT EXPERIMENT SUMMARY")
    print("=" * 75)
    status_str = "COMPLETED SUCCESS" if total_reward == 3 else f"PARTIAL ({total_reward}/3 Tasks)"
    print(f"Status:                 {status_str}")
    print(f"Total Steps Taken:      {step_num}")
    print(f"Total Reward:           {total_reward} / 3")
    print(f"Cooperative Tasks Done: {coop_count} (Heavy Box Synchronized Lifts)")
    print(f"Execution Time:         {elapsed:.2f} seconds")
    print("=" * 75 + "\n")

    return done, total_reward, coop_count, step_num


def main():
    parser = argparse.ArgumentParser(description="2-Agent Collaboration with LLM Policy Controller")
    parser.add_argument("--policy", type=str, default="cooperative",
                        help="Policy preset: 'cooperative', 'independent', 'optimal', 'vietnamese' or custom text.")
    parser.add_argument("--display", action="store_true", help="Display real-time Pygame window")
    parser.add_argument("--step_delay", type=float, default=0.25, help="Delay between steps in seconds")
    parser.add_argument("--max_episodes", type=int, default=50, help="Max steps per episode")

    args = parser.parse_args()

    policy_text = MULTIAGENT_POLICY_PRESETS.get(args.policy.lower(), args.policy)
    run_multiagent_experiment(
        policy_text=policy_text,
        display=args.display,
        step_delay=args.step_delay,
        max_episodes=args.max_episodes
    )


if __name__ == "__main__":
    main()
