"""
Final validation of the production circulant+rotate+ls pipeline
(backend/app/optimiser.py) after switching _CircularBanquetSurrogate to a
pure-distance-function weight rule (no dependence on seat parity), which
fixed the degree-imbalance collapse found at odd num_seats.

Uses the ACTUAL production functions (_solve_circulant_rotate_ls,
_solve_local_search) and ACTUAL production hyperparameters (NUM_EPOCHS=1000,
LAMBDA_ONE_HOT=100) -- not the lighter smoke-test settings used earlier in
the investigation -- across guest counts, table type, and explicit parity
(the dimension that caused the original collapse), plus the usual randomized
tag structure per repeat.

Usage: python3 backend/scripts/smoke_test_production_validation.py
"""
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from app.schema import Guest, BanquetTable, CabaretTable
from app.optimiser import _solve_circulant_rotate_ls, _solve_local_search

GUEST_SIZES = [20, 40, 60, 80, 100, 120]
TABLE_TYPES = ["banquet", "cabaret"]
PARITIES = ["even", "odd"]
K_REPEATS = 6
CROSS_TAG_POOL = ["interestA", "interestB", "interestC", "interestD"]


def make_scenario(rng, n_guests, table_type, parity):
    clique_size = rng.choice([3, 4, 5, 6])
    multi_tag = rng.choice([False, True])

    guests = []
    for i in range(n_guests):
        tags = [f"clique{i // clique_size}"]
        if multi_tag:
            tags += rng.sample(CROSS_TAG_POOL, rng.randint(0, 2))
        guests.append(Guest(id=i, name=f"g{i}", relation_tags=tags))

    # pick a table count that gives the requested seats-per-table parity,
    # keeping every table the same size and total capacity >= n_guests
    n_tables = rng.choice([3, 4, 5])
    seats_per_table = -(-n_guests // n_tables)  # ceil
    if parity == "even" and seats_per_table % 2:
        seats_per_table += 1
    elif parity == "odd" and seats_per_table % 2 == 0:
        seats_per_table += 1

    if table_type == "banquet":
        tables = [BanquetTable(id=f"t{i}", num_seats=seats_per_table) for i in range(n_tables)]
    else:
        tables = [CabaretTable(id=f"t{i}", num_seats=seats_per_table, full_circle=False) for i in range(n_tables)]
    return guests, tables


def run_condition(table_type, parity, total_start):
    rows = []
    for n_guests in GUEST_SIZES:
        wins, ties, losses = 0, 0, 0
        circ_scores, ls_scores = [], []
        for rep in range(K_REPEATS):
            seed = abs(hash((table_type, parity, n_guests, rep))) % 100000
            rng = random.Random(seed)
            guests, tables = make_scenario(rng, n_guests, table_type, parity)

            r_circ = _solve_circulant_rotate_ls(guests, tables, [])
            r_ls = _solve_local_search(guests, tables, [])
            circ_scores.append(r_circ['relation_score'])
            ls_scores.append(r_ls['relation_score'])
            if r_circ['relation_score'] > r_ls['relation_score'] + 1e-9:
                wins += 1
            elif r_ls['relation_score'] > r_circ['relation_score'] + 1e-9:
                losses += 1
            else:
                ties += 1
        rows.append((n_guests, np.mean(circ_scores), np.mean(ls_scores), wins, ties, losses))
        print(f"  [{table_type:8s} {parity:4s}] n={n_guests:3d} done ({time.time() - total_start:.1f}s elapsed total)")
    return rows


def main():
    total_start = time.time()
    for table_type in TABLE_TYPES:
        for parity in PARITIES:
            rows = run_condition(table_type, parity, total_start)
            print(f"\n--- {table_type} / {parity} seats-per-table ({K_REPEATS} repeats per n) ---")
            print(f"{'n':>4s}  {'circulant+rotate+ls':>20s}  {'local_search_x10':>17s}  {'win/tie/loss (circ)'}")
            for n, c, l, w, t, ls_ in rows:
                print(f"{n:4d}  {c:20.4f}  {l:17.4f}  {w}/{t}/{ls_}")
            print()
    print(f"Total runtime: {time.time() - total_start:.1f}s")


if __name__ == "__main__":
    main()
