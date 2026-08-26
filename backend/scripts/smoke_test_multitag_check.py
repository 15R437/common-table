"""
Does the corrected circulant+rotate+ls constraint-free advantage
(constraint_density_definitive.png, density=none column) survive realistic
multi-tag guest structure, or was it an artifact of the single-tag-only
scenario used to isolate the earlier clique/table-size confound?

Same scenario generator as smoke_test_constraint_density_definitive.py
(clique_size = seats_per_table, matching the originally validated
structure), constraints=[] throughout (the only condition circulant has ever
won), with multi_tag added back as a per-instance randomized factor (not a
separate plotted line).

Usage: python3 backend/scripts/smoke_test_multitag_check.py
"""
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from app.schema import Guest, BanquetTable
from app.optimiser import _solve_circulant_rotate_ls, _solve_local_search

GUEST_SIZES = [60, 150, 300]
K_REPEATS = 10
N_TABLES = 5
CROSS_TAG_POOL = ["interestA", "interestB", "interestC", "interestD"]


def make_scenario(rng, n_guests):
    clique_size = -(-n_guests // N_TABLES)  # ceil, matches the validated structure
    clique_of = lambda i: i // clique_size
    multi_tag = rng.choice([False, True])

    guests = []
    for i in range(n_guests):
        tags = [f"clique{clique_of(i)}"]
        if multi_tag:
            tags += rng.sample(CROSS_TAG_POOL, rng.randint(0, 2))
        guests.append(Guest(id=i, name=f"g{i}", relation_tags=tags))

    seats_per_table = -(-n_guests // N_TABLES)
    if rng.choice([True, False]) != bool(seats_per_table % 2):
        seats_per_table += 1  # randomize parity per repeat, as before
    tables = [BanquetTable(id=f"t{i}", num_seats=seats_per_table) for i in range(N_TABLES)]

    return guests, tables, multi_tag


def main():
    total_start = time.time()
    print(f"{'n':>4s}  {'circ_rel':>9s}  {'ls_rel':>8s}  {'circ_t':>7s}  {'ls_t':>7s}  {'win/tie/loss'}  {'multi_tag split'}")
    for n_guests in GUEST_SIZES:
        rel_c, rel_l, t_c, t_l = [], [], [], []
        wins, ties, losses = 0, 0, 0
        multi_tag_flags = []
        for rep in range(K_REPEATS):
            seed = abs(hash((n_guests, rep, "multitag_check"))) % 1000000
            rng = random.Random(seed)
            guests, tables, multi_tag = make_scenario(rng, n_guests)
            multi_tag_flags.append(multi_tag)

            t0 = time.time()
            r_circ = _solve_circulant_rotate_ls(guests, tables, [])
            t_c.append(time.time() - t0)

            t0 = time.time()
            r_ls = _solve_local_search(guests, tables, [])
            t_l.append(time.time() - t0)

            rel_c.append(r_circ['relation_score']); rel_l.append(r_ls['relation_score'])

            key_circ = (r_circ['constraint_score'], r_circ['relation_score'])
            key_ls = (r_ls['constraint_score'], r_ls['relation_score'])
            if key_circ > key_ls: wins += 1
            elif key_ls > key_circ: losses += 1
            else: ties += 1

        n_multi = sum(multi_tag_flags)
        print(f"{n_guests:4d}  {np.mean(rel_c):9.4f}  {np.mean(rel_l):8.4f}  {np.mean(t_c):7.2f}  {np.mean(t_l):7.2f}  "
              f"{wins}/{ties}/{losses}  ({n_multi} multi-tag / {K_REPEATS - n_multi} single-tag)")
        print(f"      ({time.time() - total_start:.1f}s elapsed total)")

    print(f"\nTotal runtime: {time.time() - total_start:.1f}s")


if __name__ == "__main__":
    main()
