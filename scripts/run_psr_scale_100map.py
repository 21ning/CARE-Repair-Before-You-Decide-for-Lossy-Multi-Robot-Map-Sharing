#!/usr/bin/env python3
"""Run the causal tiled PSR-UT scaling sweep (100 independent maps)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_psr_suite import run_suite

MAP_SEEDS = list(range(100))
SCALES = (
    (4, 24, 18), (8, 32, 32), (16, 48, 32), (32, 64, 32),
)

def config(agents: int, size: int, steps: int, workers: int) -> dict:
    return {"instance_family":"tiled_cluttered_fork", "seeds":MAP_SEEDS,
        "map_size":size, "obstacle_densities":[.2], "num_agents":agents, "observation_radius":3, "max_episode_steps":steps,
        "data_bytes_per_agent_per_step":4459,"control_bytes_per_agent_per_step":512,"max_digest_peers":1,"repair_interval_steps":1,"sync_interval_steps":8,"corridor_horizon":8,"corridor_radius":1,"digest_base_bytes":16,"digest_entry_bytes":6,"replica_digest_bytes":16,"path_weighted_sigma":1.0,"ack_bytes":8,"patch_base_bytes":4,
        "loss_probabilities":[.3],"delay_steps":[0],"policies":["one_shot_delta","retry_all_arq","mismatch_triggered_full_repair","utility_triggered_repair"],"link_seed":20260808,"workers":workers}

def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument('--output-directory',type=Path,default=Path('results/psr_ut_scale_100map')); p.add_argument('--workers',type=int,default=32); a=p.parse_args()
    if a.output_directory.exists() and any(a.output_directory.iterdir()): raise FileExistsError(a.output_directory)
    a.output_directory.mkdir(parents=True); studies=[]
    for agents,size,steps in SCALES:
        c=config(agents,size,steps,a.workers); r=run_suite(c,a.output_directory/f'agents_{agents}_map_{size}')
        studies.append({'study':f'agents_{agents}_map_{size}','config':c,'rows':r['rows'],'trace_rows':r['trace_rows'],'workers':r['workers']}); print(json.dumps(studies[-1]),flush=True)
    (a.output_directory/'manifest.json').write_text(json.dumps({'design':'100 independent matched maps with one independent network trace per map','map_seeds':MAP_SEEDS,'workers':a.workers,'studies':studies},indent=2)+'\n')

if __name__=='__main__': main()
