import random
from typing import List

from utils.seed import Seed

MAX_SEEDS = 1000


class PowerSchedule:

    def assign_energy(self, population: List[Seed]) -> None:
        """为每个种子分配相同的能量"""
        for seed in population:
            seed.energy = 1

    def normalized_energy(self, population: List[Seed]) -> List[float]:
        """归一化能量，使总和为 1"""
        energy = list(map(lambda seed: seed.energy, population))
        sum_energy = sum(energy)
        assert sum_energy != 0
        norm_energy = list(map(lambda nrg: nrg / sum_energy, energy))
        return norm_energy

    def choose(self, population: List[Seed]) -> Seed:
        """按归一化能量加权随机选择种子"""
        self.assign_energy(population)
        norm_energy = self.normalized_energy(population)
        seed: Seed = random.choices(population, weights=norm_energy)[0]
        return seed
