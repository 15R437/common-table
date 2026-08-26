"""
Correction of smoke_test_banquet_cutoff_decay.py, which tested the wrong
structure (two *disconnected* row groups by parity) instead of what was
actually proposed: banquet's zig-zag seat ordering treated as ONE connected
1D sequence (raw index i, not "position within a same-parity subgroup"),
with weight w(i,j) = f(|i-j|) -- the original decaying-weight proposal from
earlier in the session -- now with an explicit cutoff added (the original
test of this exact weight function had no cutoff at all, giving a complete
graph, which produced ties for an unrelated reason: density making the
landscape easier for both methods, not the interval-graph property).

f(d) for even d: 1, 0.5, 0.25, ... (d=2,4,6,...)
f(d) for odd d:  0.8, 0.4, 0.2, ... (d=1,3,5,...)
f(d) = 0 for d > k (the cutoff)

This is a genuine single connected Toeplitz structure (translation-invariant,
bounded), the same class as the sparse decaying ring that won cleanly --
just with this specific two-branch decay function instead of a single smooth
exponential.

Usage: python3 backend/scripts/smoke_test_zigzag_cutoff_decay.py
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


class ZigZagDecayCutoffTable(CabaretTable):
    """Single connected sequence, weight a pure function of raw index
    distance (even/odd branches per the original proposal), cut off to zero
    beyond distance k."""
    k: int = 8

    def adjacency(self):
        n = self.num_seats
        m = np.zeros((n, n))
        for i in range(n):
            for j in range(i + 1, min(i + self.k + 1, n)):
                d = j - i
                w = 0.5 ** (d // 2 - 1) if d % 2 == 0 else 0.8 * (0.5 ** ((d - 1) // 2))
                m[i, j] = w
                m[j, i] = w
        return m


def make_scenario(rng, n_guests, k):
    clique_size = rng.choice([3, 4, 5, 6])
    target_table_size = rng.choice([6, 8, 10])
    multi_tag = rng.choice([False, True])

    guests = []
    for i in range(n_guests):
        tags = [f"clique{i // clique_size}"]
        if multi_tag:
            tags += rng.sample(CROSS_TAG_POOL, rng.randint(0, 2))
        guests.append(Guest(id=i, name=f"g{i}", relation_tags=tags))

    num_tables = max(1, -(-n_guests // target_table_size))
    base = n_guests // num_tables
    remainder = n_guests % num_tables
    sizes = [base + (1 if i < remainder else 0) for i in range(num_tables)]
    sizes = [max(s, 2) for s in sizes]

    tables = [ZigZagDecayCutoffTable(id=f"t{i}", num_seats=s, k=k) for i, s in enumerate(sizes)]
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
    for k in [4, 8]:
        seed_offset = abs(hash(("zigzag_cutoff_decay", k))) % 100000
        rows = []
        for n in SIZES:
            grad_scores, ls_scores, grad_times, ls_times = [], [], [], []
            wins, ties, losses = 0, 0, 0
            for rep in range(K_REPEATS):
                seed = seed_offset + n * 1000 + rep
                rng = random.Random(seed)
                guests, tables = make_scenario(rng, n, k)
                grad, t_grad = run_gradsolver_plus_ls(guests, tables, seed)
                ls10, t_ls = run_local_search(guests, tables, seed)
                grad_scores.append(grad); ls_scores.append(ls10)
                grad_times.append(t_grad); ls_times.append(t_ls)
                if grad > ls10 + 1e-9: wins += 1
                elif ls10 > grad + 1e-9: losses += 1
                else: ties += 1
            rows.append((n, np.mean(grad_scores), np.mean(ls_scores),
                         np.mean(grad_times), np.mean(ls_times), wins, ties, losses))
            print(f"  [k={k}] n={n:3d} done ({time.time() - total_start:.1f}s elapsed total)")

        print(f"\n--- ZigZagDecayCutoffTable, k={k} ({K_REPEATS} repeats per n) ---")
        print(f"{'n':>4s}  {'gradsolver+ls':>14s}  {'local_search_x10':>17s}  {'grad_time':>10s}  {'ls_time':>8s}  {'win/tie/loss (grad)'}")
        for n, g, l, tg, tl, w, t, ls_ in rows:
            print(f"{n:4d}  {g:14.4f}  {l:17.4f}  {tg:10.2f}s  {tl:8.2f}s  {w}/{t}/{ls_}")
        print()
    print(f"Total runtime: {time.time() - total_start:.1f}s")


if __name__ == "__main__":
    main()
