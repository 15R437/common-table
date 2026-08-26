"""
Follow-up to the interval-graph/topology investigation (see smoke_test_*.py
and the session's conversation): banquet and theatre both lose to plain
local_search_x10 because their adjacency needs two independent coordinates
(row and position) rather than a single distance-based ordering -- confirmed
by isolating topology from edge-weighting and from raw degree.

This tests the natural fix: keep decaying weight (like the sparse decaying
ring that already confirmed decay-vs-uniform doesn't matter), but only
connect seats within the same row -- removing the cross-row coupling
entirely, so each row is independently a 1D (Robinson/Toeplitz) structure.
Both banquet ("row" = which side of the table, by the same zig-zag parity
real BanquetTable already uses) and theatre (row = literal grid row) are
reinterpreted this way.

Prediction, following everything found so far: gradsolver+ls should win
again, matching the sparse decaying-ring result, since there's no longer any
two-axis coupling to trip up the smooth relaxation.

Sampled over many random problem instances per point (table/clique size and
tag structure vary; tag structure randomized per repeat, not plotted/reported
as a separate line -- see prior feedback on plot density).

Usage: python3 backend/scripts/smoke_test_row_decay.py
"""
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

SIZES = [64, 100, 150, 200]
K_REPEATS = 8
CROSS_TAG_POOL = ["interestA", "interestB", "interestC", "interestD"]


class DecayingRowBanquetTable(CabaretTable):
    """Same zig-zag row assignment real BanquetTable uses (even index = one
    side, odd index = the other), but only same-row seats are connected, with
    weight decaying by within-row distance -- no cross-row edges at all."""
    def adjacency(self):
        n = self.num_seats
        m = np.zeros((n, n))
        for parity in [0, 1]:
            row_seats = [i for i in range(n) if i % 2 == parity]
            for a_pos, i in enumerate(row_seats):
                for b_pos, j in enumerate(row_seats):
                    if i < j:
                        d = b_pos - a_pos
                        w = 0.5 ** (d - 1)
                        m[i, j] = w
                        m[j, i] = w
        return m


class DecayingRowTheatreTable(CabaretTable):
    """Literal grid rows (as in real TheatreSection), only same-row seats
    connected, weight decaying by within-row (column) distance."""
    num_rows: int = 4

    def adjacency(self):
        n = self.num_seats
        rows = self.num_rows
        cols = n // rows
        m = np.zeros((n, n))
        for r in range(rows):
            for c1 in range(cols):
                for c2 in range(c1 + 1, cols):
                    i, j = r * cols + c1, r * cols + c2
                    w = 0.5 ** (c2 - c1 - 1)
                    m[i, j] = w
                    m[j, i] = w
        return m


class BoustrophedonDecayTable(CabaretTable):
    """A single connected interval graph spanning every seat, not several
    disconnected rows: number the grid in a snake/boustrophedon path (row 0
    left-to-right, row 1 right-to-left, row 2 left-to-right, ...) -- every
    consecutive pair in that ordering, including at the turns, is a genuine
    physical grid-neighbor. Weight decays by distance along that single path."""
    num_rows: int = 2

    def adjacency(self):
        n = self.num_seats
        rows = self.num_rows
        cols = n // rows
        # boustrophedon_pos[seat] = this seat's position along the snake path
        boustrophedon_pos = np.zeros(n, dtype=int)
        pos = 0
        for r in range(rows):
            col_order = range(cols) if r % 2 == 0 else range(cols - 1, -1, -1)
            for c in col_order:
                boustrophedon_pos[r * cols + c] = pos
                pos += 1

        m = np.zeros((n, n))
        for i in range(n):
            for j in range(i + 1, n):
                d = abs(boustrophedon_pos[i] - boustrophedon_pos[j])
                w = 0.5 ** (d - 1)
                m[i, j] = w
                m[j, i] = w
        return m


# table_type -> (class, fixed kwargs, minimum divisible-by for seat counts)
TABLE_CONFIGS = {
    "banquet_row_decay": (DecayingRowBanquetTable, {}, 2),
    "theatre_row_decay": (DecayingRowTheatreTable, {"num_rows": 4}, 4),
    "banquet_boustrophedon": (BoustrophedonDecayTable, {"num_rows": 2}, 2),
    "theatre_boustrophedon": (BoustrophedonDecayTable, {"num_rows": 4}, 4),
}


def make_scenario(rng, n_guests, table_type):
    clique_size = rng.choice([3, 4, 5, 6])
    target_table_size = rng.choice([6, 8, 10])
    multi_tag = rng.choice([False, True])

    guests = []
    for i in range(n_guests):
        tags = [f"clique{i // clique_size}"]
        if multi_tag:
            tags += rng.sample(CROSS_TAG_POOL, rng.randint(0, 2))
        guests.append(Guest(id=i, name=f"g{i}", relation_tags=tags))

    table_cls, kwargs, divisor = TABLE_CONFIGS[table_type]
    num_tables = max(1, -(-n_guests // target_table_size))
    base = n_guests // num_tables
    remainder = n_guests % num_tables
    sizes = [base + (1 if i < remainder else 0) for i in range(num_tables)]
    sizes = [max(s, 2 * divisor) for s in sizes]  # need at least 2 seats per row
    sizes = [((s + divisor - 1) // divisor) * divisor for s in sizes]  # round up to a clean grid

    tables = [table_cls(id=f"t{i}", num_seats=s, **kwargs) for i, s in enumerate(sizes)]
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


def run_condition(table_type, seed_offset, total_start):
    rows = []
    for n in SIZES:
        grad_scores, ls_scores, grad_times, ls_times = [], [], [], []
        wins, ties, losses = 0, 0, 0
        for rep in range(K_REPEATS):
            seed = seed_offset + n * 1000 + rep
            rng = random.Random(seed)
            guests, tables = make_scenario(rng, n, table_type)
            grad, t_grad = run_gradsolver_plus_ls(guests, tables, seed)
            ls10, t_ls = run_local_search(guests, tables, seed)
            grad_scores.append(grad); ls_scores.append(ls10)
            grad_times.append(t_grad); ls_times.append(t_ls)
            if grad > ls10 + 1e-9: wins += 1
            elif ls10 > grad + 1e-9: losses += 1
            else: ties += 1
        rows.append((n, np.mean(grad_scores), np.mean(ls_scores),
                     np.mean(grad_times), np.mean(ls_times), wins, ties, losses))
        print(f"  [{table_type}] n={n:3d} done ({time.time() - total_start:.1f}s elapsed total)")
    return rows


def main():
    total_start = time.time()
    for table_type in TABLE_CONFIGS:
        seed_offset = abs(hash(table_type)) % 100000
        rows = run_condition(table_type, seed_offset, total_start)
        print(f"\n--- {table_type} ({K_REPEATS} repeats per n) ---")
        print(f"{'n':>4s}  {'gradsolver+ls':>14s}  {'local_search_x10':>17s}  {'grad_time':>10s}  {'ls_time':>8s}  {'win/tie/loss (grad)'}")
        for n, g, l, tg, tl, w, t, ls_ in rows:
            print(f"{n:4d}  {g:14.4f}  {l:17.4f}  {tg:10.2f}s  {tl:8.2f}s  {w}/{t}/{ls_}")
        print()
    print(f"Total runtime: {time.time() - total_start:.1f}s")


if __name__ == "__main__":
    main()
