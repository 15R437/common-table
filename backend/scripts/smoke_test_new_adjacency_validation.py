"""
Re-validates circulant+rotate+ls vs local_search_x10 after ALL THREE real
adjacency functions (BanquetTable, CabaretTable, TheatreSection) were
rewritten in schema.py -- new weight scale (hop-decay, 2**(1-k)), new
structure (banquet: multi-row propagation; cabaret: decaying complete graph
when full_circle=False, decaying ring when True; theatre: within-row
decaying complete graph, no cross-row edges).

Critically, the SURROGATES circulant+rotate+ls trains against
(_CircularBanquetSurrogate, _CircularTheatreSurrogate, and cabaret's
full_circle=True copy) were NOT changed to match -- this checks whether they
still approximate the new real structure well enough to win, or whether the
mismatch between old surrogate assumptions and new real weight scale breaks
the previously-validated advantage.

Uses the ACTUAL production functions (_solve_circulant_rotate_ls,
_solve_local_search) with use_large_scale_surrogate=True forced (so the
mechanism is exercised regardless of guest count), matching the
clique_size=seats_per_table convention validated throughout this session.

Usage: python3 backend/scripts/smoke_test_new_adjacency_validation.py
"""
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from app.schema import Guest, BanquetTable, CabaretTable, TheatreSection
from app.optimiser import _solve_circulant_rotate_ls, _solve_local_search

SIZES = [60, 150]
K_REPEATS = 8
N_TABLES = 5


def make_guests(n_guests, clique_size):
    return [Guest(id=i, name=f"g{i}", relation_tags=[f"clique{i // clique_size}"]) for i in range(n_guests)]


def run_banquet(n, rep_seed, head_seat=False):
    clique_size = -(-n // N_TABLES)
    guests = make_guests(n, clique_size)
    tables = [BanquetTable(id=t, num_seats=clique_size, head_seat=head_seat) for t in range(N_TABLES)]
    return guests, tables


def run_cabaret(n, rep_seed, full_circle):
    clique_size = -(-n // N_TABLES)
    guests = make_guests(n, clique_size)
    tables = [CabaretTable(id=t, num_seats=clique_size, full_circle=full_circle) for t in range(N_TABLES)]
    return guests, tables


def run_theatre(n, rep_seed):
    # one big section, rows sized close to clique_size for comparable structure
    seats_per_row = max(2, -(-n // N_TABLES))
    num_rows = -(-n // seats_per_row)
    total_seats = num_rows * seats_per_row
    clique_size = seats_per_row
    guests = make_guests(n, clique_size)
    tables = [TheatreSection(id=0, num_seats=total_seats, num_rows=num_rows)]
    return guests, tables


def evaluate(label, scenario_fn, **kwargs):
    print(f"--- {label} ---")
    rng_seed = hash(label) & 0xffff
    for n in SIZES:
        wins = ties = losses = 0
        circ_scores, ls_scores = [], []
        t0 = time.time()
        for rep in range(K_REPEATS):
            guests, tables = scenario_fn(n, rng_seed + rep, **kwargs)
            if len(guests) > sum(t.num_seats for t in tables):
                continue
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
    evaluate("banquet (no head/foot)", run_banquet)
    evaluate("cabaret (full_circle=True)", run_cabaret, full_circle=True)
    evaluate("cabaret (full_circle=False)", run_cabaret, full_circle=False)
    evaluate("theatre", run_theatre)
