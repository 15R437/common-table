"""
Tests the "pretend it's circulant, then rotate to find the cheapest cut"
trick for banquet tables: train GradSolver+LS on a circulant surrogate
(FullyCyclicBanquetTable, which wins cleanly against local_search_x10), then
for each table independently, search all rotations of that table's resulting
arrangement to find the one that scores best under the REAL (open,
non-circulant) adjacency, then refine with LocalSearchSolver on the real
adjacency. Compared against plain local_search_x10 on the real table
throughout.

Usage: python3 backend/scripts/smoke_test_rotate_trick.py
"""
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import torch

from app.schema import Guest, BanquetTable
from app.solvers import GradSolver, LocalSearchSolver

TRAIN_KWARGS = dict(num_epochs=300, lambda_guest=1, lambda_seat=1, lambda_ce=50,
                     lambda_one_hot=0, keep_history=False, verbose=False)

SIZES = [100, 200]
K_REPEATS = 8


class FullyCyclicBanquetTable(BanquetTable):
    """Real banquet weighting, but every offset wraps modulo n -- the
    circulant surrogate confirmed to win cleanly."""
    def adjacency(self):
        n = self.num_seats
        m = np.zeros((n, n))
        for i in range(n):
            offsets_weights = [(1, 0.75), (2, 1.0), (3, 0.5)] if i % 2 == 0 else [(1, 0.5), (2, 1.0)]
            for off, w in offsets_weights:
                j = (i + off) % n
                m[i, j] = w
                m[j, i] = w
        return m


def make_scenario(n_guests, n_tables=5):
    clique_size = -(-n_guests // n_tables)  # ceil
    guests = [Guest(id=i, name=f"g{i}", relation_tags=[f"clique{i // clique_size}"]) for i in range(n_guests)]
    seats_per_table = -(-n_guests // n_tables)  # ceil, so total seats >= n_guests
    seats_per_table += seats_per_table % 2  # keep even
    real_tables = [BanquetTable(id=f"t{i}", num_seats=seats_per_table) for i in range(n_tables)]
    circulant_tables = [FullyCyclicBanquetTable(id=f"t{i}", num_seats=seats_per_table) for i in range(n_tables)]
    return guests, real_tables, circulant_tables


def table_seat_ranges(table_list):
    ranges, start = [], 0
    for t in table_list:
        ranges.append((start, start + t.num_seats))
        start += t.num_seats
    return ranges


def best_rotation_per_table(guest_to_seat, real_tables, real_relation_matrix, real_table_adjacency, n_guests):
    """For each table independently, try every rotation of that table's
    seating and keep whichever maximizes the score under the REAL adjacency."""
    ranges = table_seat_ranges(real_tables)
    n_total = ranges[-1][1]
    seat_to_guest = np.full(n_total, -1, dtype=int)
    for g in range(n_guests):
        seat_to_guest[guest_to_seat[g]] = g

    new_guest_to_seat = guest_to_seat.copy()
    for lo, hi in ranges:
        size = hi - lo
        local = seat_to_guest[lo:hi]
        sub_adj = real_table_adjacency[lo:hi, lo:hi]
        best_rot, best_score = 0, -np.inf
        for r in range(size):
            rotated = np.roll(local, r)
            mask = rotated != -1
            rel = np.zeros((size, size))
            idx = rotated.copy()
            idx[~mask] = 0
            rel = real_relation_matrix[np.ix_(idx, idx)]
            rel[~mask, :] = 0
            rel[:, ~mask] = 0
            score = np.sum(rel * sub_adj)
            if score > best_score:
                best_score, best_rot = score, r
        rotated_best = np.roll(local, best_rot)
        for s in range(size):
            if rotated_best[s] != -1:
                new_guest_to_seat[rotated_best[s]] = lo + s
    return new_guest_to_seat


def run_circulant_rotate_ls(guests, real_tables, circulant_tables, seed):
    start = time.time()
    torch.manual_seed(seed)
    model = GradSolver(guest_list=guests, table_list=circulant_tables, constraints=[], init_type='uniform')
    model.train(**TRAIN_KWARGS)
    guest_to_seat = model.extract_hard_seating()

    real_model = GradSolver(guest_list=guests, table_list=real_tables, constraints=[], init_type='uniform')
    rotated = best_rotation_per_table(guest_to_seat, real_tables,
                                       real_model._relation_matrix, real_model._table_adjacency, len(guests))

    ls = LocalSearchSolver(guest_list=guests, table_list=real_tables, constraints=[])
    final = ls.solve(initial=np.argsort(rotated))
    score = ls._summarize_assignment(final)['relation_score']
    return score, time.time() - start


def run_gradsolver_plus_ls_real(guests, real_tables, seed):
    start = time.time()
    torch.manual_seed(seed)
    model = GradSolver(guest_list=guests, table_list=real_tables, constraints=[], init_type='uniform')
    model.train(**TRAIN_KWARGS)
    guest_to_seat = model.extract_hard_seating()
    ls = LocalSearchSolver(guest_list=guests, table_list=real_tables, constraints=[])
    final = ls.solve(initial=np.argsort(guest_to_seat))
    score = ls._summarize_assignment(final)['relation_score']
    return score, time.time() - start


def run_local_search(guests, real_tables, seed, num_restarts=10):
    start = time.time()
    ls = LocalSearchSolver(guest_list=guests, table_list=real_tables, constraints=[])
    final = ls.solve(seed=seed, num_restarts=num_restarts)
    score = ls._summarize_assignment(final)['relation_score']
    return score, time.time() - start


def main():
    total_start = time.time()
    for n_guests in SIZES:
        rt_scores, gl_scores, ls_scores = [], [], []
        rt_times, gl_times, ls_times = [], [], []
        rt_vs_ls = [0, 0, 0]  # win, tie, loss
        for rep in range(K_REPEATS):
            seed = 13000 * n_guests + rep
            guests, real_tables, circulant_tables = make_scenario(n_guests)

            rt_score, rt_t = run_circulant_rotate_ls(guests, real_tables, circulant_tables, seed)
            gl_score, gl_t = run_gradsolver_plus_ls_real(guests, real_tables, seed)
            ls_score, ls_t = run_local_search(guests, real_tables, seed)

            rt_scores.append(rt_score); gl_scores.append(gl_score); ls_scores.append(ls_score)
            rt_times.append(rt_t); gl_times.append(gl_t); ls_times.append(ls_t)

            if rt_score > ls_score + 1e-9: rt_vs_ls[0] += 1
            elif ls_score > rt_score + 1e-9: rt_vs_ls[2] += 1
            else: rt_vs_ls[1] += 1

        print(f"--- n={n_guests} ---")
        print(f"  circulant+rotate+ls : mean={np.mean(rt_scores):.4f}  time={np.mean(rt_times):.2f}s")
        print(f"  gradsolver+ls (real): mean={np.mean(gl_scores):.4f}  time={np.mean(gl_times):.2f}s")
        print(f"  local_search_x10    : mean={np.mean(ls_scores):.4f}  time={np.mean(ls_times):.2f}s")
        print(f"  circulant+rotate+ls vs local_search_x10: win/tie/loss = {rt_vs_ls[0]}/{rt_vs_ls[1]}/{rt_vs_ls[2]}")
        print(f"  ({time.time() - total_start:.1f}s elapsed)")

    print(f"\nTotal runtime: {time.time() - total_start:.1f}s")


if __name__ == "__main__":
    main()
