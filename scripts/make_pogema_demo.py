#!/usr/bin/env python3
"""Generate the deterministic POGEMA animation embedded in the README."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pogema import GridConfig, pogema_v0

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cmvr.communication import LinkConfig, PSRConfig, ReplicaPolicy
from cmvr.env import PSRClosedLoopRunner, generate_instance
from cmvr.mapping import BeliefMap, CellState
from cmvr.utils.config import ExperimentConfig


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
    instance = generate_instance(ExperimentConfig(
        seed=51, map_size=32, obstacle_density=0.20, num_agents=8,
        observation_radius=3, max_episode_steps=64,
    ))
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
    replica_trace: list[tuple[np.ndarray, np.ndarray]] = []

    def record_replica(
        _step: int, beliefs: tuple[BeliefMap, ...], _positions,
    ) -> None:
        replica_trace.append((
            beliefs[0].occupancy.copy(), beliefs[0].source_ids.copy(),
        ))

    result = PSRClosedLoopRunner(
        policy=ReplicaPolicy.DEADLINE_AWARE_REPAIR,
        config=config,
        step_observer=record_replica,
    ).run(instance)
    return instance, result, replica_trace


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


def render_frame(
    instance, occupancy: np.ndarray, source_ids: np.ndarray, positions,
    label: str, total_steps: int,
) -> Image.Image:
    cell = 12
    margin = 18
    header = 72
    footer = 30
    grid_size = instance.map_size * cell
    image = Image.new(
        "RGB", (grid_size + 2 * margin, grid_size + header + footer), "#FFFFFF",
    )
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    known = occupancy != CellState.UNKNOWN
    remote = known & (source_ids != 0)
    coverage = 100.0 * float(known.mean())
    remote_share = 100.0 * float(remote.sum()) / max(1, int(known.sum()))
    draw.text((margin, 10), "CARE  |  POGEMA  |  30% packet loss", fill="#172033", font=font)
    draw.text((margin, 28), "Robot 1 local map replica (not ground truth)", fill="#172033", font=font)
    draw.text(
        (margin, 46),
        f"{label} / {total_steps:02d}   known {coverage:4.1f}%   received {remote_share:4.1f}%",
        fill="#5A6475", font=font,
    )

    top = header
    for row in range(instance.map_size):
        for column in range(instance.map_size):
            x0 = margin + column * cell
            y0 = top + row * cell
            state = int(occupancy[row, column])
            source = int(source_ids[row, column])
            if state == CellState.UNKNOWN:
                fill = "#B9C1CC"
            elif state == CellState.BLOCKED:
                fill = "#246B9A" if source != 0 else "#273142"
            else:
                fill = "#D9EEFB" if source != 0 else "#F7F8FA"
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

    legend_y = top + grid_size + 9
    legend = (
        ("#B9C1CC", "unknown"), ("#F7F8FA", "seen locally"),
        ("#D9EEFB", "peer data"), ("#273142", "obstacle"),
    )
    legend_x = margin
    for color, text in legend:
        draw.rectangle((legend_x, legend_y, legend_x + 10, legend_y + 10), fill=color, outline="#7A8493")
        draw.text((legend_x + 14, legend_y), text, fill="#465063", font=font)
        legend_x += 96

    return image


def main() -> None:
    args = parse_args()
    instance, result, replica_trace = run_episode()
    positions = replay_positions(instance, result.action_trace)
    unknown = np.full(instance.obstacle_map.shape, CellState.UNKNOWN, dtype=np.int8)
    no_sources = np.full(instance.obstacle_map.shape, -1, dtype=np.int64)
    frame_data = [(unknown, no_sources, positions[0], "initial")]
    frame_data.extend(
        (occupancy, sources, positions[step], f"step {step:02d}")
        for step, (occupancy, sources) in enumerate(replica_trace)
    )
    frame_data.append((*replica_trace[-1], positions[-1], f"step {len(result.action_trace):02d}"))
    frames = [
        render_frame(instance, occupancy, sources, frame_positions, label, len(result.action_trace))
        for occupancy, sources, frame_positions, label in frame_data
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        args.output,
        save_all=True,
        append_images=frames[1:],
        duration=[700] + [160] * (len(frames) - 2) + [700],
        loop=0,
        optimize=True,
    )
    print(
        f"saved {len(frames)} frames to {args.output} "
        f"(CSR={result.completion_success_rate:.3f}, bytes={result.network_summary['attempted_bytes']})"
    )


if __name__ == "__main__":
    main()
