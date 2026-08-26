"""
Properly powered test of how constraint density interacts with the
circulant+rotate+ls advantage over local_search_x10, across guest counts up
to 500. Follow-up to banquet_definitive.png, whose quick 8-repeat, 2-size
ablation gave an inconsistent (sign-flipping) signal between n=60 and n=100
-- not enough power to draw a real conclusion.

Density conventions match smoke_test_bootstrap.py earlier this session:
  none   - constraints=[]
  sparse - n_guests // 10 pairs each direction
  dense  - n_guests // 3 pairs each direction
Both sparse/dense generate must_sit_together across cliques and
must_sit_apart within cliques, so they actually conflict with the tag
clustering rather than being redundant with it.

Uses the actual production functions (_solve_circulant_rotate_ls,
_solve_local_search) and production hyperparameters directly (bypassing
MAX_GUESTS, which is a request-validation limit, not a solver limit) so
n_guests can go well past 120.

Usage: python3 backend/scripts/smoke_test_constraint_density_power.py
"""
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from app.schema import Guest, Constraint, BanquetTable
from app.optimiser import _solve_circulant_rotate_ls, _solve_local_search

GUEST_SIZES = [60, 100, 200, 350, 500]
DENSITIES = {"none": None, "sparse": 10, "dense": 3}
K_REPEATS = 10
CROSS_TAG_POOL = ["interestA", "interestB", "interestC", "interestD"]


def make_scenario(rng, n_guests, density_divisor):
    clique_size = rng.choice([3, 4, 5, 6])
    multi_tag = rng.choice([False, True])
    clique_of = lambda i: i // clique_size

    guests = []
    for i in range(n_guests):
        tags = [f"clique{clique_of(i)}"]
        if multi_tag:
            tags += rng.sample(CROSS_TAG_POOL, rng.randint(0, 2))
        guests.append(Guest(id=i, name=f"g{i}", relation_tags=tags))

    n_tables = max(3, n_guests // rng.choice([15, 20, 25]))
    seats_per_table = -(-n_guests // n_tables)  # ceil
    if rng.choice([True, False]) != bool(seats_per_table % 2):
        seats_per_table += 1  # randomize parity per repeat
    tables = [BanquetTable(id=f"t{i}", num_seats=seats_per_table) for i in range(n_tables)]

    constraints = []
    if density_divisor is not None:
        n_pairs = max(1, n_guests // density_divisor)
        added, attempts = 0, 0
        while added < n_pairs and attempts < n_pairs * 30 and n_guests >= 2:
            a, b = rng.sample(range(n_guests), 2)
            attempts += 1
            if clique_of(a) != clique_of(b):
                constraints.append(Constraint(guest_a_id=a, guest_b_id=b, relationship="must_sit_together"))
                added += 1
        added, attempts = 0, 0
        while added < n_pairs and attempts < n_pairs * 30 and n_guests >= 2:
            a, b = rng.sample(range(n_guests), 2)
            attempts += 1
            if clique_of(a) == clique_of(b):
                constraints.append(Constraint(guest_a_id=a, guest_b_id=b, relationship="must_sit_apart"))
                added += 1

    return guests, tables, constraints


def main():
    total_start = time.time()
    results = {}

    for density_name, divisor in DENSITIES.items():
        rows = []
        for n_guests in GUEST_SIZES:
            wins, ties, losses = 0, 0, 0
            rel_circ, rel_ls = [], []
            for rep in range(K_REPEATS):
                seed = abs(hash((density_name, n_guests, rep))) % 1000000
                rng = random.Random(seed)
                guests, tables, constraints = make_scenario(rng, n_guests, divisor)

                r_circ = _solve_circulant_rotate_ls(guests, tables, constraints)
                r_ls = _solve_local_search(guests, tables, constraints)
                rel_circ.append(r_circ['relation_score'])
                rel_ls.append(r_ls['relation_score'])
                if r_circ['relation_score'] > r_ls['relation_score'] + 1e-9:
                    wins += 1
                elif r_ls['relation_score'] > r_circ['relation_score'] + 1e-9:
                    losses += 1
                else:
                    ties += 1
            rows.append((n_guests, np.mean(rel_circ), np.std(rel_circ), np.mean(rel_ls), np.std(rel_ls), wins, ties, losses))
            print(f"  [{density_name:6s}] n={n_guests:3d} done ({time.time() - total_start:.1f}s elapsed total)")
        results[density_name] = rows

    print()
    for density_name, rows in results.items():
        print(f"--- density={density_name} ({K_REPEATS} repeats per n) ---")
        print(f"{'n':>4s}  {'circ_mean':>10s}  {'circ_std':>9s}  {'ls_mean':>9s}  {'ls_std':>8s}  {'win/tie/loss (circ)'}")
        for n, cm, cs, lm, ls_, w, t, l in rows:
            print(f"{n:4d}  {cm:10.4f}  {cs:9.4f}  {lm:9.4f}  {ls_:8.4f}  {w}/{t}/{l}")
        print()

    print(f"Total runtime: {time.time() - total_start:.1f}s")


if __name__ == "__main__":
    main()
