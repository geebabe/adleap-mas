"""
Level-Based Foraging (LBF) with LLM Semantic Policy Controller (gpt-4o-mini).
Demonstrates 1 agent on a 10x10 grid executing natural-language policies.
"""
import sys
import os
import time
import argparse
import numpy as np

# Add project root to sys.path
sys.path.append(os.getcwd())

from src.envs.LevelForagingEnv import LevelForagingEnv, Agent, Task
from src.reasoning.levelbased.llm import DEFAULT_POLICY, get_direction_name

PRESET_POLICIES = {
    "lightest": "Always collect the lightest box first (lowest level). If levels are equal, choose the closest one.",
    "heaviest": "Always collect the heaviest box first (highest level) that the agent can lift.",
    "north_first": "Only forage boxes located in the northern half of the grid (y >= 5) before any other boxes.",
    "vietnamese": "Hãy ưu tiên nhặt hộp có trọng lượng nhẹ nhất (level nhỏ nhất) trước. Nếu cùng level, chọn hộp gần nhất."
}


def print_grid(shape, agent, tasks):
    """Prints a clean ASCII representation of the 10x10 grid."""
    grid = [[' . ' for _ in range(shape[0])] for _ in range(shape[1])]
    
    # Place uncompleted tasks
    for t in tasks:
        if not t.completed:
            grid[t.position[1]][t.position[0]] = f'T{t.index}'

    # Place agent
    grid[agent.position[1]][agent.position[0]] = ' A '

    print("   " + "".join([f" {x} " for x in range(shape[0])]))
    for y in reversed(range(shape[1])):
        row = f"{y:2d} " + "".join(grid[y])
        print(row)
    print()


def run_experiment(policy_text=None, display=False, max_episodes=100, step_delay=0.3):
    if policy_text is None:
        policy_text = PRESET_POLICIES["lightest"]

    print("=" * 70)
    print("🚀 Level-Based Foraging (LBF) - 10x10 Proof of Concept")
    print(f"🤖 Controller: LLM Semantic Policy Controller (gpt-4o-mini + A* Planner)")
    print(f"📜 Natural Language Policy:\n   \"{policy_text}\"")
    if display:
        print(f"🖥️  Pygame GUI Display: ENABLED (Step delay: {step_delay}s)")
    print("=" * 70)

    # 1. Setting up 10x10 environment with 1 agent and 3 tasks
    dim = (10, 10)
    agent = Agent(
        index='A',
        atype='llm',
        position=(1, 1),
        direction=np.pi / 2,  # North
        radius=1.0,           # Full vision
        angle=1.0,
        level=1.0
    )
    # Store policy text in agent smart_parameters
    agent.smart_parameters['policy'] = policy_text

    tasks = [
        Task(index='0', position=(2, 7), level=0.3),  # Lightest
        Task(index='1', position=(8, 2), level=0.6),  # Medium
        Task(index='2', position=(7, 8), level=0.9),  # Heaviest
    ]

    components = {
        'agents': [agent],
        'adhoc_agent_index': 'A',
        'tasks': tasks,
        'obstacles': []
    }

    env = LevelForagingEnv(shape=dim, components=components, display=display)
    env.policy = policy_text

    # 2. Reset Environment
    state = env.reset()
    adhoc_agent = env.get_adhoc_agent()
    method = env.import_method(adhoc_agent.type)

    print("\nInitial Environment Grid (10x10):")
    print_grid(dim, adhoc_agent, tasks)
    print(f"Agent A: Position {adhoc_agent.position}, Level: {adhoc_agent.level}")
    for t in tasks:
        print(f"  - Task T{t.index}: Position {t.position}, Level (Weight): {t.level}")

    # 3. Main Loop
    done = False
    total_reward = 0
    start_time = time.time()
    step_history = []

    print("\n" + "-" * 70)
    print("Beginning Execution...")
    print("-" * 70)

    while not done and env.episode < max_episodes:
        # Handle Pygame window events so it doesn't freeze on macOS
        if display:
            import pygame
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    print("\n[Pygame] Window closed by user.")
                    done = True
                    break
            if done:
                break

        step_num = env.episode + 1
        pos_before = adhoc_agent.position
        dir_before = adhoc_agent.direction

        # Planning next action via LLM Semantic Controller
        action, target = method(env, adhoc_agent)
        action_name = env.action_dict.get(action, str(action))

        # Take step
        state, reward, done, info = env.step(action)
        total_reward += reward

        pos_after = adhoc_agent.position
        dir_name = get_direction_name(adhoc_agent.direction)

        # Log step
        log_str = (
            f"Step {step_num:02d} | Agent pos: {pos_before} -> {pos_after} | "
            f"Facing: {dir_name:5s} | Target: {target} | Action: {action_name}"
        )
        if reward > 0:
            log_str += f" | 🎉 REWARD: +{reward} (Task Completed!)"
        print(log_str)

        step_history.append({
            "step": step_num,
            "action": action_name,
            "reward": reward,
            "pos": pos_after
        })

        if display and step_delay > 0:
            time.sleep(step_delay)

    elapsed_time = time.time() - start_time
    if display:
        print("\nDisplaying final state for 2 seconds before closing window...")
        time.sleep(2.0)
    env.close()

    # 4. Summary & Verification
    print("\n" + "=" * 70)
    print("📊 EXPERIMENT SUMMARY")
    print("=" * 70)
    print(f"Status:             {'COMPLETED SUCCESS' if done else 'MAX STEPS REACHED'}")
    print(f"Total Steps Taken:  {env.episode}")
    print(f"Total Reward:       {total_reward} / {len(tasks)}")
    print(f"Execution Time:     {elapsed_time:.2f} seconds")
    print(f"Tasks Completed:    {sum(1 for t in env.components['tasks'] if t.completed)} / {len(env.components['tasks'])}")
    print(f"Final Agent Pos:    {adhoc_agent.position}")
    print("=" * 70)

    return done, total_reward, env.episode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LBF with LLM Semantic Policy Controller")
    parser.add_argument("--policy", type=str, default=None,
                        help="Natural language policy string or preset (lightest, heaviest, north_first, vietnamese)")
    parser.add_argument("--display", action="store_true", default=False,
                        help="Enable pygame graphical window")
    parser.add_argument("--step_delay", type=float, default=0.25,
                        help="Delay in seconds between steps when display is enabled (default: 0.25)")
    parser.add_argument("--max_steps", type=int, default=100,
                        help="Maximum episodes/steps")
    args = parser.parse_args()

    selected_policy = args.policy
    if selected_policy in PRESET_POLICIES:
        selected_policy = PRESET_POLICIES[selected_policy]
    elif selected_policy is None:
        selected_policy = PRESET_POLICIES["lightest"]

    run_experiment(
        policy_text=selected_policy,
        display=args.display,
        max_episodes=args.max_steps,
        step_delay=args.step_delay
    )

