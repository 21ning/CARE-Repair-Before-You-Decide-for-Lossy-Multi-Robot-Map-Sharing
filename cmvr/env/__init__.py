"""Instance generation and closed-loop execution for PSR-UT."""

from .instance import (
    CriticalDecisionPair, EpisodeInstance, critical_decision_pairs,
    generate_instance, load_instance, save_instance,
)
from cmvr.communication import PSRConfig, ReplicaPolicy
from .psr_runner import PSRClosedLoopRunner, PSRResult
from .structured_instances import (
    generate_fork_bottleneck_instance, generate_multifork_bottleneck_instance,
    generate_rotated_multifork_bottleneck_instance, generate_multifork_topology_variant_instance,
    generate_cluttered_multifork_instance, generate_tiled_cluttered_fork_instance,
)

__all__ = [
    "EpisodeInstance",
    "CriticalDecisionPair",
    "critical_decision_pairs",
    "PSRClosedLoopRunner",
    "PSRConfig",
    "PSRResult",
    "ReplicaPolicy",
    "generate_fork_bottleneck_instance",
    "generate_multifork_bottleneck_instance",
    "generate_rotated_multifork_bottleneck_instance",
    "generate_multifork_topology_variant_instance",
    "generate_cluttered_multifork_instance",
    "generate_tiled_cluttered_fork_instance",
    "generate_instance",
    "load_instance",
    "save_instance",
]
