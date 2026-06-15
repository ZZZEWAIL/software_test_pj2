import random
from typing import List

from utils.seed import Seed

MAX_SEEDS = 1000


class PowerSchedule:

    def assign_energy(self, population: List[Seed]) -> None:
        """Assigns each seed the same energy"""
        for seed in population:
            seed.energy = 1

    def normalized_energy(self, population: List[Seed]) -> List[float]:
        """Normalize energy"""
        energy = list(map(lambda seed: seed.energy, population))
        sum_energy = sum(energy)  # Add up all values in energy
        assert sum_energy != 0
        norm_energy = list(map(lambda nrg: nrg / sum_energy, energy))
        return norm_energy

    def choose(self, population: List[Seed]) -> Seed:
        """Choose weighted by normalized energy.

        Population size management is handled by GreyBoxFuzzer._try_offload_population()
        which persists low-energy seeds to disk.  This method focuses solely on selection.
        """
        self.assign_energy(population)
        norm_energy = self.normalized_energy(population)
        seed: Seed = random.choices(population, weights=norm_energy)[0]
        return seed
