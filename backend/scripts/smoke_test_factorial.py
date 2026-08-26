"""
Full 2x2x2 factorial to pin down which of three candidate properties
actually determines whether gradsolver+ls beats local_search_x10:

  circulant   -- wraps around ((i+d) % n) vs open path (i+d, capped at n-1)
  monotonic   -- weight strictly decays with distance vs a zigzag
                 (alternating up/down) weight function
  contiguous  -- every distance 1..k is connected vs a gapped connection
                 set ({1, 2, k}, skipping the middle)

Every prior test changed more than one of these at once and drew a
conclusion from it -- this isolates all three independently, at consistent
guest counts, to settle which one(s) actually matter.

Usage: python3 backend/scripts/smoke_test_factorial.py
"""
import itertools
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import torch

from app.schema import Guest, CabaretTable
from app.solvers import GradSolver, LocalSearchSolver

TRAIN_KWARGS = dict(num_epochs=300, lambda_guest=1, lambda_seat=1, lambda_ce=50,
                     lambda_one_hot=0, keep_history=False, verbose=False)

SIZES = [100, 200]
K_REPEATS = 8
K_CUTOFF = 8


class FactorialTable(CabaretTable):
    circulant: bool = True
    monotonic: bool = True
    contiguous: bool = True
    k: int = K_CUTOFF

    def _weight(self, d):
        if self.monotonic:
            return 0.5 ** (d - 1)
        return 0.5 ** (d // 2 - 1) if d % 2 == 0 else 0.8 * (0.5 ** ((d - 1) // 2))

    def adjacency(self):
        n = self.num_seats
        m = np.zeros((n, n))
        offsets = list(range(1, self.k + 1)) if self.contiguous else [1, 2, self.k]
        for i in range(n):
            for d in offsets:
                if self.circulant:
                    j = (i + d) % n
                    if i == j:
                        continue
                else:
                    j = i + d
                    if j >= n:
                        continue
                w = self._weight(d)
                m[i, j] = w
                m[j, i] = w
        return m


def make_scenario(n_guests, flags, n_tables=5):
    clique_size = -(-n_guests // n_tables)  # ceil, avoid clique_size=0
    guests = [Guest(id=i, name=f"g{i}", relation_tags=[f"clique{i // clique_size}"]) for i in range(n_guests)]
    seats_per_table = -(-n_guests // n_tables)  # ceil, so total seats >= n_guests
    tables = [FactorialTable(id=f"t{i}", num_seats=seats_per_table, **flags) for i in range(n_tables)]
    return guests, tables


def run_gradsolver_plus_ls(guests, tables, seed):
    start = time.time()
    torch.manual_seed(seed)
    model = GradSolver(guest_list=guests, table_list=tables, constraints=[], init_type='uniform')
    model.train(**TRAIN_KWARGS)
    guest_to_seat = model.extract_hard_seating()
    ls = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=[])
    final = ls.solve(initial=np.argsort(guest_to_seat))
    score = ls._summarize_assignment(final)['relation_score']
    return score, time.time() - start


def run_local_search(guests, tables, seed, num_restarts=10):
    start = time.time()
    ls = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=[])
    final = ls.solve(seed=seed, num_restarts=num_restarts)
    score = ls._summarize_assignment(final)['relation_score']
    return score, time.time() - start


def main():
    total_start = time.time()
    combos = list(itertools.product([True, False], repeat=3))  # (circulant, monotonic, contiguous)
    results = {}

    for circulant, monotonic, contiguous in combos:
        flags = dict(circulant=circulant, monotonic=monotonic, contiguous=contiguous)
        label = f"circulant={circulant!s:5s} monotonic={monotonic!s:5s} contiguous={contiguous!s:5s}"
        per_n = {}
        for n in SIZES:
            wins, ties, losses = 0, 0, 0
            for rep in range(K_REPEATS):
                seed = abs(hash((circulant, monotonic, contiguous, n, rep))) % 1000000
                guests, tables = make_scenario(n, flags)
                grad, _ = run_gradsolver_plus_ls(guests, tables, seed)
                ls10, _ = run_local_search(guests, tables, seed)
                if grad > ls10 + 1e-9: wins += 1
                elif ls10 > grad + 1e-9: losses += 1
                else: ties += 1
            per_n[n] = (wins, ties, losses)
        results[(circulant, monotonic, contiguous)] = per_n
        print(f"{label}  " + "  ".join(f"n={n}: {w}/{t}/{l}" for n, (w, t, l) in per_n.items()) +
              f"   ({time.time() - total_start:.1f}s elapsed)")

    print(f"\nTotal runtime: {time.time() - total_start:.1f}s")
    print("\nformat: wins/ties/losses (gradsolver+ls) out of 8 repeats\n")


if __name__ == "__main__":
    main()
