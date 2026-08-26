"""
Quick test of a three-stage "bootstrap" pipeline for constraint-heavy
scenarios (this is the first test this session to actually use hard
must_sit_together / must_sit_apart constraints -- everything before this
used constraints=[], where relation-only and full-score are the same thing):

  1. LocalSearchSolver, but scored on the relation matrix only (no
     constraints) -- a clean, unconstrained clustering to start from.
  2. GradSolver, warm-started toward that clustering (instead of a random
     permutation, the way 'surjective' init biases toward one) and trained
     on the FULL score (relation + constraints).
  3. LocalSearchSolver again, this time on the full score, to polish.

Compared against:
  - gradsolver+ls: the established default (uniform init, full score
    throughout, no bootstrapping).
  - relation_ls_then_full_ls: an ablation -- stage 1 into stage 3 directly,
    skipping GradSolver entirely. Isolates whether GradSolver's pass is
    actually contributing anything beyond the relation-only starting point.
  - local_search_x10: pure random-restart baseline, full score, no GradSolver.

Constraints are generated to actually conflict with the tag clustering
(must_sit_together across different cliques, must_sit_apart within the same
clique) -- otherwise there's no tension for a bootstrap to help resolve.

Usage: python3 backend/scripts/smoke_test_bootstrap.py
"""
import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import torch

from app.schema import Guest, Constraint, CabaretTable, BanquetTable
from app.solvers import GradSolver, LocalSearchSolver

TRAIN_KWARGS = dict(num_epochs=300, lambda_guest=1, lambda_seat=1, lambda_ce=50,
                     lambda_one_hot=0, keep_history=False, verbose=False)

METHODS = ['gradsolver+ls', 'bootstrap', 'relation_ls_then_full_ls', 'local_search_x10']
TABLE_TYPES = ["cabaret", "banquet"]
SIZES = [16, 32, 64, 100]
K_REPEATS = 5


def make_scenario(rng, n_guests, table_type):
    clique_size = rng.choice([3, 4, 5, 6])
    target_table_size = rng.choice([6, 8, 10])
    clique_of = lambda i: i // clique_size

    guests = [Guest(id=i, name=f"g{i}", relation_tags=[f"clique{clique_of(i)}"]) for i in range(n_guests)]

    # n_guests // 10 turned out too sparse -- every method hit ~100%
    # satisfaction trivially, no differentiation. // 3 actually stresses it.
    n_pairs = max(1, n_guests // 3)
    constraints = []

    added, attempts = 0, 0
    while added < n_pairs and attempts < n_pairs * 30 and n_guests >= 2:
        a, b = rng.sample(range(n_guests), 2)
        attempts += 1
        if clique_of(a) != clique_of(b):  # must-together across cliques -- fights the clustering
            constraints.append(Constraint(guest_a_id=a, guest_b_id=b, relationship="must_sit_together"))
            added += 1

    added, attempts = 0, 0
    while added < n_pairs and attempts < n_pairs * 30 and n_guests >= 2:
        a, b = rng.sample(range(n_guests), 2)
        attempts += 1
        if clique_of(a) == clique_of(b):  # must-apart within a clique -- also fights the clustering
            constraints.append(Constraint(guest_a_id=a, guest_b_id=b, relationship="must_sit_apart"))
            added += 1

    num_tables = max(1, -(-n_guests // target_table_size))  # ceil
    base = n_guests // num_tables
    remainder = n_guests % num_tables
    sizes = [base + (1 if i < remainder else 0) for i in range(num_tables)]
    sizes = [max(s, 2) for s in sizes]

    if table_type == "cabaret":
        tables = [CabaretTable(id=f"t{i}", num_seats=s, full_circle=True) for i, s in enumerate(sizes)]
    elif table_type == "banquet":
        sizes = [s + (s % 2) for s in sizes]  # BanquetTable.adjacency() has a known bug on odd seat counts
        tables = [BanquetTable(id=f"t{i}", num_seats=s) for i, s in enumerate(sizes)]
    else:
        raise ValueError(table_type)

    return guests, tables, constraints


def constraint_satisfaction(result):
    total = result['must_sit_together']['total'] + result['must_sit_apart']['total']
    satisfied = result['must_sit_together']['satisfied'] + result['must_sit_apart']['satisfied']
    return satisfied / total if total > 0 else 1.0


def warm_start_from_assignment(model, guest_to_seat, noise_std=0.1, seed=0):
    """Bias guest_logits/seat_logits toward a known discrete assignment,
    with the same margin formula regularised_surjective_init uses -- just
    pointed at a data-driven starting point instead of a random permutation."""
    gen = torch.Generator().manual_seed(seed)
    n = model.guest_logits.shape[0]
    margin = math.log(max(1, n - 1)) + 5 * noise_std + 0.1
    with torch.no_grad():
        model.guest_logits.copy_(torch.randn(n, n, generator=gen) * noise_std)
        model.seat_logits.copy_(torch.randn(n, n, generator=gen) * noise_std)
        for g, s in enumerate(guest_to_seat):
            model.guest_logits[g, s] += margin
            model.seat_logits[s, g] += margin


def run_gradsolver_plus_ls(guests, tables, constraints, seed):
    start = time.time()
    torch.manual_seed(seed)
    model = GradSolver(guest_list=guests, table_list=tables, constraints=constraints, init_type='uniform')
    model.train(**TRAIN_KWARGS)
    guest_to_seat = model.extract_hard_seating()

    ls_full = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=constraints)
    final = ls_full.solve(initial=np.argsort(guest_to_seat))
    return ls_full._summarize_assignment(final), time.time() - start


def run_bootstrap(guests, tables, constraints, seed):
    start = time.time()
    ls_relation_only = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=[])
    stage1 = ls_relation_only.solve(seed=seed, num_restarts=1)

    model = GradSolver(guest_list=guests, table_list=tables, constraints=constraints, init_type='uniform')
    warm_start_from_assignment(model, stage1, seed=seed)
    model.train(**TRAIN_KWARGS)
    guest_to_seat = model.extract_hard_seating()

    ls_full = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=constraints)
    final = ls_full.solve(initial=np.argsort(guest_to_seat))
    return ls_full._summarize_assignment(final), time.time() - start


def run_relation_ls_then_full_ls(guests, tables, constraints, seed):
    start = time.time()
    ls_relation_only = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=[])
    stage1 = ls_relation_only.solve(seed=seed, num_restarts=1)

    ls_full = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=constraints)
    final = ls_full.solve(initial=np.argsort(stage1))
    return ls_full._summarize_assignment(final), time.time() - start


def run_local_search(guests, tables, constraints, seed, num_restarts=10):
    start = time.time()
    ls_full = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=constraints)
    guest_to_seat = ls_full.solve(seed=seed, num_restarts=num_restarts)
    return ls_full._summarize_assignment(guest_to_seat), time.time() - start


RUNNERS = {
    'gradsolver+ls': run_gradsolver_plus_ls,
    'bootstrap': run_bootstrap,
    'relation_ls_then_full_ls': run_relation_ls_then_full_ls,
    'local_search_x10': run_local_search,
}


def run_condition(table_type, seed_offset, total_start):
    data = {method: {'n': [], 'satisfaction_mean': [], 'satisfaction_std': [],
                      'relation_mean': [], 'relation_std': [], 'time_mean': [], 'time_std': []}
            for method in METHODS}
    for n in SIZES:
        per = {m: {'sat': [], 'rel': [], 'time': []} for m in METHODS}
        for rep in range(K_REPEATS):
            seed = seed_offset + n * 1000 + rep
            rng = random.Random(seed)
            guests, tables, constraints = make_scenario(rng, n, table_type)
            for method in METHODS:
                result, t = RUNNERS[method](guests, tables, constraints, seed)
                per[method]['sat'].append(constraint_satisfaction(result))
                per[method]['rel'].append(result['relation_score'])
                per[method]['time'].append(t)
        for method in METHODS:
            sat = np.array(per[method]['sat'])
            rel = np.array(per[method]['rel'])
            tim = np.array(per[method]['time'])
            data[method]['n'].append(n)
            data[method]['satisfaction_mean'].append(sat.mean())
            data[method]['satisfaction_std'].append(sat.std())
            data[method]['relation_mean'].append(rel.mean())
            data[method]['relation_std'].append(rel.std())
            data[method]['time_mean'].append(tim.mean())
            data[method]['time_std'].append(tim.std())
        print(f"  [{table_type:8s}] n={n:3d} done ({time.time() - total_start:.1f}s elapsed total)")
    return data


def print_condition(table_type, data):
    print(f"\n--- {table_type} ---")
    header = f"{'method':26s} {'n':>4s}  {'satisfaction':>16s}  {'relation_score':>16s}  {'time':>8s}"
    print(header)
    print("-" * len(header))
    for method in METHODS:
        d = data[method]
        for i, n in enumerate(d['n']):
            print(f"{method:26s} {n:4d}  "
                  f"{d['satisfaction_mean'][i]:.3f}±{d['satisfaction_std'][i]:.3f}      "
                  f"{d['relation_mean'][i]:6.3f}±{d['relation_std'][i]:.3f}       "
                  f"{d['time_mean'][i]:.2f}s")


def main():
    total_start = time.time()
    all_data = {}
    for table_type in TABLE_TYPES:
        seed_offset = abs(hash(table_type)) % 100000
        all_data[table_type] = run_condition(table_type, seed_offset, total_start)

    for table_type in TABLE_TYPES:
        print_condition(table_type, all_data[table_type])

    print(f"\nTotal runtime: {time.time() - total_start:.1f}s")


if __name__ == "__main__":
    main()
