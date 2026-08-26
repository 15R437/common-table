"""
Does tuning con_weight (relative to the fixed rel_weight=1) change which
method wins, or is local_search_x10's win in smoke_test_bootstrap.py robust
regardless of tuning? And does the answer depend on how many hard
constraints the guest list actually has?

Sweeps con_weight (used identically inside GradSolver's training loss and
LocalSearchSolver's swap evaluation -- same value passed to both, matching
how a real pipeline would use one consistent weight throughout) across two
constraint densities: 'sparse' (few must-together/apart pairs, closer to a
typical real guest list) and 'dense' (the stress-test level from
smoke_test_bootstrap.py, deliberately conflicting with the tag clustering).

Fixed to cabaret, n=64 -- a single representative condition, kept small
specifically so the sweep (5 con_weights x 2 densities) stays quick.

Usage: python3 backend/scripts/smoke_test_weight_sweep.py
"""
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import torch

from app.schema import Guest, Constraint, CabaretTable
from app.solvers import GradSolver, LocalSearchSolver
from smoke_test_bootstrap import warm_start_from_assignment, constraint_satisfaction

TRAIN_KWARGS = dict(num_epochs=300, lambda_guest=1, lambda_seat=1, lambda_ce=50,
                     lambda_one_hot=0, keep_history=False, verbose=False)

N_GUESTS = 64
TABLE_TYPE = "cabaret"
CON_WEIGHTS = [2, 5, 10, 20, 40]
DENSITIES = {'sparse': lambda n: max(1, n // 10), 'dense': lambda n: max(1, n // 3)}
METHODS = ['gradsolver+ls', 'bootstrap', 'relation_ls_then_full_ls', 'local_search_x10']
K_REPEATS = 8


def make_scenario(rng, n_guests, density):
    clique_size = rng.choice([3, 4, 5, 6])
    target_table_size = rng.choice([6, 8, 10])
    clique_of = lambda i: i // clique_size

    guests = [Guest(id=i, name=f"g{i}", relation_tags=[f"clique{clique_of(i)}"]) for i in range(n_guests)]

    n_pairs = DENSITIES[density](n_guests)
    constraints = []
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

    num_tables = max(1, -(-n_guests // target_table_size))
    base = n_guests // num_tables
    remainder = n_guests % num_tables
    sizes = [base + (1 if i < remainder else 0) for i in range(num_tables)]
    sizes = [max(s, 2) for s in sizes]
    tables = [CabaretTable(id=f"t{i}", num_seats=s, full_circle=True) for i, s in enumerate(sizes)]

    return guests, tables, constraints


def run_gradsolver_plus_ls(guests, tables, constraints, seed, con_weight):
    start = time.time()
    torch.manual_seed(seed)
    model = GradSolver(guest_list=guests, table_list=tables, constraints=constraints,
                        init_type='uniform', con_weight=con_weight)
    model.train(**TRAIN_KWARGS)
    guest_to_seat = model.extract_hard_seating()

    ls_full = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=constraints, con_weight=con_weight)
    final = ls_full.solve(initial=np.argsort(guest_to_seat))
    return ls_full._summarize_assignment(final), time.time() - start


def run_bootstrap(guests, tables, constraints, seed, con_weight):
    start = time.time()
    ls_relation_only = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=[], con_weight=con_weight)
    stage1 = ls_relation_only.solve(seed=seed, num_restarts=1)

    model = GradSolver(guest_list=guests, table_list=tables, constraints=constraints,
                        init_type='uniform', con_weight=con_weight)
    warm_start_from_assignment(model, stage1, seed=seed)
    model.train(**TRAIN_KWARGS)
    guest_to_seat = model.extract_hard_seating()

    ls_full = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=constraints, con_weight=con_weight)
    final = ls_full.solve(initial=np.argsort(guest_to_seat))
    return ls_full._summarize_assignment(final), time.time() - start


def run_relation_ls_then_full_ls(guests, tables, constraints, seed, con_weight):
    start = time.time()
    ls_relation_only = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=[], con_weight=con_weight)
    stage1 = ls_relation_only.solve(seed=seed, num_restarts=1)

    ls_full = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=constraints, con_weight=con_weight)
    final = ls_full.solve(initial=np.argsort(stage1))
    return ls_full._summarize_assignment(final), time.time() - start


def run_local_search(guests, tables, constraints, seed, con_weight, num_restarts=10):
    start = time.time()
    ls_full = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=constraints, con_weight=con_weight)
    guest_to_seat = ls_full.solve(seed=seed, num_restarts=num_restarts)
    return ls_full._summarize_assignment(guest_to_seat), time.time() - start


RUNNERS = {
    'gradsolver+ls': run_gradsolver_plus_ls,
    'bootstrap': run_bootstrap,
    'relation_ls_then_full_ls': run_relation_ls_then_full_ls,
    'local_search_x10': run_local_search,
}


def main():
    total_start = time.time()
    print(f"{'density':8s} {'con_weight':>10s}  " + "  ".join(f"{m:26s}" for m in METHODS))
    print("-" * (20 + 28 * len(METHODS)))

    for density in DENSITIES:
        for con_weight in CON_WEIGHTS:
            per = {m: {'sat': [], 'rel': []} for m in METHODS}
            for rep in range(K_REPEATS):
                seed = abs(hash((density, con_weight, rep))) % 100000
                rng = random.Random(seed)
                guests, tables, constraints = make_scenario(rng, N_GUESTS, density)
                for method in METHODS:
                    result, _ = RUNNERS[method](guests, tables, constraints, seed, con_weight)
                    per[method]['sat'].append(constraint_satisfaction(result))
                    per[method]['rel'].append(result['relation_score'])

            cells = []
            for method in METHODS:
                sat = np.array(per[method]['sat'])
                rel = np.array(per[method]['rel'])
                cells.append(f"sat={sat.mean():.3f} rel={rel.mean():.3f}")
            print(f"{density:8s} {con_weight:10d}  " + "  ".join(f"{c:26s}" for c in cells))

    print(f"\nTotal runtime: {time.time() - total_start:.1f}s")


if __name__ == "__main__":
    main()
