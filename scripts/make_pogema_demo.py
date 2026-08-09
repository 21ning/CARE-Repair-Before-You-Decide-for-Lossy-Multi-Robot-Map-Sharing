#!/usr/bin/env python3
"""Generate the deterministic POGEMA animation embedded in the README."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pogema import GridConfig, pogema_v0

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cmvr.communication import LinkConfig, PSRConfig, ReplicaPolicy
from cmvr.env import PSRClosedLoopRunner, generate_cluttered_multifork_instance


COLORS = (
    "#0072B2", "#D55E00", "#009E73", "#CC79A7",
    "#E69F00", "#56B4E9", "#F0E442", "#6A3D9A",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "assets" / "pogema_demo.gif",
        help="GIF destination (default: assets/pogema_demo.gif)",
    )
    return parser.parse_args()


def run_episode():
    instance = generate_cluttered_multifork_instance(
        seed=0, obstacle_density=0.20, map_size=32, num_agents=8,
        observation_radius=3, max_episode_steps=25,
    )
    config = PSRConfig(
        data_bytes_per_agent_per_step=4459,
        control_bytes_per_agent_per_step=512,
        repair_interval_steps=1,
        sync_interval_steps=4,
        corridor_horizon=8,
        corridor_radius=1,
        max_digest_peers=1,
        link=LinkConfig(loss_probability=0.30, delay_steps=0, seed=20260808),
    )
    result = PSRClosedLoopRunner(
        policy=ReplicaPolicy.UTILITY_TRIGGERED_REPAIR, config=config,
    ).run(instance)
    return instance, result


def replay_positions(instance, action_trace):
    environment = pogema_v0(grid_config=GridConfig(
        seed=instance.generation_seed,
        size=instance.map_size,
        map=instance.obstacle_map.astype(int).tolist(),
        agents_xy=[list(point) for point in instance.starts],
        targets_xy=[list(point) for point in instance.goals],
        num_agents=instance.num_agents,
        obs_radius=instance.observation_radius,
        max_episode_steps=instance.max_episode_steps,
        collision_system=instance.collision_system,
    ))
    environment.reset()
    positions = [tuple(instance.starts)]
    for actions in action_trace:
        environment.step(actions)
        positions.append(tuple(
            tuple(map(int, point))
            for point in environment.grid.get_agents_xy(ignore_borders=True)
        ))
    return positions


def render_frame(instance, positions, step: int, total_steps: int) -> Image.Image:
    cell = 12
    margin = 18
    header = 54
    grid_size = instance.map_size * cell
    image = Image.new("RGB", (grid_size + 2 * margin, grid_size + header + margin), "#FFFFFF")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    draw.text((margin, 12), "CARE / PSR-UT  |  POGEMA  |  30% packet loss", fill="#172033", font=font)
    draw.text((margin, 30), f"step {step:02d} / {total_steps:02d}", fill="#5A6475", font=font)

    top = header
    for row in range(instance.map_size):
        for column in range(instance.map_size):
            x0 = margin + column * cell
            y0 = top + row * cell
            fill = "#273142" if instance.obstacle_map[row, column] else "#F4F6F8"
            draw.rectangle((x0, y0, x0 + cell - 1, y0 + cell - 1), fill=fill)

    for agent, (row, column) in enumerate(instance.goals):
        x0 = margin + column * cell + 2
        y0 = top + row * cell + 2
        draw.rectangle((x0, y0, x0 + cell - 5, y0 + cell - 5), outline=COLORS[agent], width=2)

    for agent, (row, column) in enumerate(positions):
        x0 = margin + column * cell + 1
        y0 = top + row * cell + 1
        draw.ellipse((x0, y0, x0 + cell - 3, y0 + cell - 3), fill=COLORS[agent], outline="#FFFFFF")
        label = str(agent + 1)
        draw.text((x0 + 3, y0 + 1), label, fill="#FFFFFF" if agent != 6 else "#172033", font=font)

    return image


def main() -> None:
    args = parse_args()
    instance, result = run_episode()
    positions = replay_positions(instance, result.action_trace)
    frames = [
        render_frame(instance, frame_positions, step, len(positions) - 1)
        for step, frame_positions in enumerate(positions)
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        args.output,
        save_all=True,
        append_images=frames[1:],
        duration=260,
        loop=0,
        optimize=True,
    )
    print(
        f"saved {len(frames)} frames to {args.output} "
        f"(CSR={result.completion_success_rate:.3f}, bytes={result.network_summary['attempted_bytes']})"
    )


if __name__ == "__main__":
    main()
