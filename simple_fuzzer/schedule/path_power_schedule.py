from typing import Dict, Sequence

from schedule.power_schedule import PowerSchedule
from utils.seed import Seed


class PathPowerSchedule(PowerSchedule):

    def __init__(self) -> None:
        super().__init__()
        self.path_frequency: Dict[frozenset, int] = {}

    def assign_energy(self, population: Sequence[Seed]) -> None:
        """Assign exponential energy inversely proportional to path frequency"""
        for seed in population:
            path_id = frozenset(seed.coverage)
            freq = self.path_frequency.get(path_id, 1)
            seed.energy = 1.0 / freq
