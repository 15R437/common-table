"""
Checks two live questions against the CURRENT on-disk optimiser.py:

(1) The user manually edited _CircularBanquetSurrogate.adjacency() to make
    offset-3 ("diagonal opposite") connections parity-dependent (only sent
    from even-indexed seats), intending to respect the real banquet table's
    actual left/right geometry instead of a naive pure-distance rule. Does
    this degrade circulant+rotate+ls's performance vs the previously-
    validated pure-distance version (smoke_test_rotate_trick.py numbers:
    n=100 mean=0.1829 8/0/0 vs LS10; n=200 mean=0.0926 8/0/0 vs LS10)?

    Note: unlike the ORIGINAL degree-imbalance bug, this edit is still
    exactly node-degree-regular (verified separately) -- so if it degrades
    anything, it's a subtler vertex-transitivity break, not the same
    catastrophic collapse.

(2) Does a banquet table with head_seat=True (currently falls back to
    training GradSolver directly on the real, non-circulant table -- no
    surrogate, per _circulant_surrogate's documented "unvalidated" case)
    perform reasonably against local_search_x10, or does it break/collapse?

Both tested via the ACTUAL production functions (_solve_circulant_rotate_ls,
_solve_local_search), called directly with use_large_scale_surrogate=True to
exercise the mechanism regardless of guest count.

Usage: python3 backend/scripts/smoke_test_parity_edit_check.py
"""
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from app.schema import Guest, BanquetTable
from app.optimiser import _solve_circulant_rotate_ls, _solve_local_search, _CircularBanquetSurrogate

SIZES = [100, 200]
K_REPEATS = 8


def make_scenario(rng, n_guests, head_seat=False, foot_seat=False):
    n_tables = 5
    clique_size = -(-n_guests // n_tables)  # ceil, matches the validated structure
    guests = [Guest(id=i, name=f"g{i}", relation_tags=[f"clique{i // clique_size}"]) for i in range(n_guests)]
    seats_per_table = clique_size
    tables = [BanquetTable(id=t, num_seats=seats_per_table, head_seat=head_seat, foot_seat=foot_seat)
              for t in range(n_tables)]
    return guests, tables


def run(label, head_seat=False, foot_seat=False):
    print(f"--- {label} ---")
    rng = random.Random(hash(label) & 0xffff)
    for n in SIZES:
        circ_scores, ls_scores = [], []
        wins = ties = losses = 0
        t0 = time.time()
        for rep in range(K_REPEATS):
            guests, tables = make_scenario(rng, n, head_seat=head_seat, foot_seat=foot_seat)
            r_circ = _solve_circulant_rotate_ls(guests, tables, [], use_large_scale_surrogate=True)
            r_ls = _solve_local_search(guests, tables, [])
            circ_scores.append(r_circ['relation_score'])
            ls_scores.append(r_ls['relation_score'])
            circ_key = (r_circ['constraint_score'], r_circ['relation_score'])
            ls_key = (r_ls['constraint_score'], r_ls['relation_score'])
            if circ_key > ls_key:
                wins += 1
            elif circ_key < ls_key:
                losses += 1
            else:
                ties += 1
        print(f"  n={n}: circulant+rotate+ls mean={np.mean(circ_scores):.4f}  "
              f"local_search_x10 mean={np.mean(ls_scores):.4f}  "
              f"win/tie/loss={wins}/{ties}/{losses}  ({time.time()-t0:.1f}s)")
    print()


if __name__ == "__main__":
    n = 8
    m = _CircularBanquetSurrogate(id=0, num_seats=n).adjacency()
    print("--- vertex-transitivity check (current on-disk surrogate, n=8) ---")
    for i in range(n):
        neighbors = sorted((j, round(m[i, j], 2)) for j in range(n) if m[i, j] > 0)
        rel_neighbors = sorted(((j - i) % n, w) for j, w in neighbors)
        print(f"  seat {i} (parity {i%2}): relative-offset/weight pairs = {rel_neighbors}")
    print()

    run("plain banquet (no head/foot)")
    run("banquet WITH head_seat", head_seat=True)
    run("banquet WITH head_seat AND foot_seat", head_seat=True, foot_seat=True)
