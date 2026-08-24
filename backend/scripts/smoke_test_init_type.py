"""
Does init_type='surjective' improve GradSolver over the 'uniform' init used
throughout this session's benchmarking?

'uniform' starts from an exactly symmetric torch.zeros(n, n) logits matrix --
deterministic given the problem instance, no randomness anywhere in it.
'surjective' (regularised_surjective_init) instead starts from a random
near-permutation with a strong margin -- a real prior bias toward *some*
one-to-one seating, already close to a valid assignment before training even
starts. Worth checking directly since raw gradsolver's known failure mode
(collapsing toward score 0 on banquet/theatre at scale, see
benchmark_solvers.py) is exactly the kind of thing a better init might fix.

Sampled over many random problem instances per point (table/clique size and
tag structure vary). Tag structure (single-tag cliques vs. cliques +
cross-cutting tags) is picked randomly per repeat rather than plotted as a
separate line -- splitting every method into single-tag/multi-tag variants
made the previous benchmark plot too dense to read.

Usage: python3 backend/scripts/smoke_test_init_type.py
"""
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import numpy as np
import torch

from app.schema import Guest, CabaretTable, BanquetTable, TheatreSection
from app.solvers import GradSolver, LocalSearchSolver

OUTPUT_DIR = Path(__file__).parent / "outputs"

TRAIN_KWARGS = dict(num_epochs=300, lambda_guest=1, lambda_seat=1, lambda_ce=50,
                     lambda_one_hot=0, keep_history=False, verbose=False)

METHODS = ['gradsolver (uniform)', 'gradsolver+ls (uniform)',
           'gradsolver (surjective)', 'gradsolver+ls (surjective)',
           'local_search_x10']
TABLE_TYPES = ["cabaret", "banquet", "theatre"]
SIZES = [8, 16, 32, 64, 100, 150, 200]
K_REPEATS = 10
CROSS_TAG_POOL = ["interestA", "interestB", "interestC", "interestD"]


def make_scenario(rng, n_guests, table_type):
    clique_size = rng.choice([3, 4, 5, 6])
    target_table_size = rng.choice([6, 8, 10])
    multi_tag = rng.choice([False, True])  # varied per repeat, not plotted separately

    guests = []
    for i in range(n_guests):
        tags = [f"clique{i // clique_size}"]
        if multi_tag:
            tags += rng.sample(CROSS_TAG_POOL, rng.randint(0, 2))
        guests.append(Guest(id=i, name=f"g{i}", relation_tags=tags))

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
    elif table_type == "theatre":
        num_rows = 2
        sizes = [max(s, 4) for s in sizes]  # avoid a 1-seat-per-row table (zero adjacency edges)
        sizes = [((s + num_rows - 1) // num_rows) * num_rows for s in sizes]
        tables = [TheatreSection(id=f"t{i}", num_seats=s, num_rows=num_rows) for i, s in enumerate(sizes)]
    else:
        raise ValueError(table_type)

    return guests, tables


def run_gradsolver(guests, tables, init_type):
    start = time.time()
    model = GradSolver(guest_list=guests, table_list=tables, constraints=[], init_type=init_type)
    model.train(**TRAIN_KWARGS)
    guest_to_seat = model.extract_hard_seating()
    score = model._summarize_assignment(guest_to_seat)['relation_score']
    return score, time.time() - start, guest_to_seat


def run_gradsolver_plus_ls(guests, tables, gradsolver_guest_to_seat):
    start = time.time()
    ls = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=[])
    seat_to_guest = np.argsort(gradsolver_guest_to_seat)
    guest_to_seat = ls.solve(initial=seat_to_guest)
    score = ls._summarize_assignment(guest_to_seat)['relation_score']
    return score, time.time() - start


def run_local_search(guests, tables, num_restarts=10, seed=0):
    start = time.time()
    ls = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=[])
    guest_to_seat = ls.solve(seed=seed, num_restarts=num_restarts)
    score = ls._summarize_assignment(guest_to_seat)['relation_score']
    return score, time.time() - start


def run_all_methods(guests, tables, seed):
    results = {}
    for init_type in ['uniform', 'surjective']:
        score, t, g2s = run_gradsolver(guests, tables, init_type)
        results[f'gradsolver ({init_type})'] = (score, t)
        score2, t2 = run_gradsolver_plus_ls(guests, tables, g2s)
        results[f'gradsolver+ls ({init_type})'] = (score2, t + t2)
    score, t = run_local_search(guests, tables, num_restarts=10, seed=seed)
    results['local_search_x10'] = (score, t)
    return results


def run_condition(table_type, seed_offset, total_start):
    data = {method: {'n': [], 'score_mean': [], 'score_std': [], 'time_mean': [], 'time_std': []}
            for method in METHODS}
    for n in SIZES:
        per_score = {m: [] for m in METHODS}
        per_time = {m: [] for m in METHODS}
        for rep in range(K_REPEATS):
            seed = seed_offset + n * 1000 + rep
            rng = random.Random(seed)
            guests, tables = make_scenario(rng, n, table_type)
            # 'surjective' init draws from torch's global RNG -- seed it per
            # repeat so results are reproducible run-to-run.
            torch.manual_seed(seed)
            results = run_all_methods(guests, tables, seed=rep)
            for method, (score, t) in results.items():
                per_score[method].append(score)
                per_time[method].append(t)
        for method in METHODS:
            scores = np.array(per_score[method])
            times = np.array(per_time[method])
            data[method]['n'].append(n)
            data[method]['score_mean'].append(scores.mean())
            data[method]['score_std'].append(scores.std())
            data[method]['time_mean'].append(times.mean())
            data[method]['time_std'].append(times.std())
        print(f"  [{table_type:8s}] n={n:3d} done ({time.time() - total_start:.1f}s elapsed total)")
    return data


def main():
    total_start = time.time()
    all_data = {}
    for table_type in TABLE_TYPES:
        seed_offset = abs(hash(table_type)) % 100000
        all_data[table_type] = run_condition(table_type, seed_offset, total_start)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    colors = {'gradsolver (uniform)': '#888', 'gradsolver+ls (uniform)': '#4c72b0',
              'gradsolver (surjective)': '#dd8452', 'gradsolver+ls (surjective)': '#c44e52',
              'local_search_x10': '#55a868'}
    fig, axes = plt.subplots(len(TABLE_TYPES), 2, figsize=(14, 5 * len(TABLE_TYPES)))
    for row, table_type in enumerate(TABLE_TYPES):
        ax_score, ax_time = axes[row]
        data = all_data[table_type]
        for method in METHODS:
            d = data[method]
            label = method if row == 0 else None
            ax_score.errorbar(d['n'], d['score_mean'], yerr=d['score_std'], marker='o',
                               color=colors[method], label=label, capsize=3, alpha=0.85)
            ax_time.errorbar(d['n'], d['time_mean'], yerr=d['time_std'], marker='o',
                              color=colors[method], capsize=3, alpha=0.85)
        ax_score.set_xlabel("number of guests")
        ax_score.set_ylabel("score (relation_score)")
        ax_score.set_title(f"Score vs. guest count -- {table_type}")
        ax_score.grid(alpha=0.3)
        ax_time.set_xlabel("number of guests")
        ax_time.set_ylabel("wall-clock time (s)")
        ax_time.set_yscale("log")
        ax_time.set_title(f"Time vs. guest count (log scale) -- {table_type}")
        ax_time.grid(alpha=0.3)

    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 1.0), ncol=5, fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(OUTPUT_DIR / "init_type_comparison.png", dpi=150)
    print(f"\nSaved plot: {OUTPUT_DIR / 'init_type_comparison.png'}")
    print(f"Total runtime: {time.time() - total_start:.1f}s")


if __name__ == "__main__":
    main()
