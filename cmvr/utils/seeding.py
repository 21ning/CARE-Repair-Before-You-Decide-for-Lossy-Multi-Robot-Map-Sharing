"""Centralized deterministic seeding without importing optional Torch."""

from __future__ import annotations

import random
import sys

import numpy as np


def seed_everything(seed: int, *, seed_loaded_torch: bool = True) -> None:
    """Seed Python and NumPy, and Torch only when it is already imported."""
    random.seed(seed)
    np.random.seed(seed)
    if seed_loaded_torch and "torch" in sys.modules:
        torch = sys.modules["torch"]
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
