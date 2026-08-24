"""
Benchmark all the seating-assignment methods discussed this session:

  gradsolver        - single GradSolver training run, Hungarian extraction
  gradsolver+ls      - gradsolver's output, refined by LocalSearchSolver
  decimate           - GradSolver.decimate (pin-most-confident-then-resettle)
  decimate+ls        - decimate's output, refined by LocalSearchSolver
  local_search_x10   - pure LocalSearchSolver, 10 random restarts, no GradSolver at all

Two parts:
  1. Small-scale exact comparison (n <= 9) against true brute-force optimum.
  2. A robust scaling sweep: 3 table types x 2 tag structures (single-tag
     cliques vs. cliques + cross-cutting tags) x guest counts up to 200,
     each point averaged over K_REPEATS independent random instances (varying
     clique size and table size per repeat, not just guest count) --
     GradSolver's uniform init is deterministic given the problem instance,
     so a single instance per point (as an earlier version of this script
     did) isn't a meaningful sample; only varying the instance itself is.

Usage: python3 backend/scripts/benchmark_solvers.py
"""
import itertools
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import numpy as np

from app.schema import Guest, CabaretTable, BanquetTable, TheatreSection
from app.solvers import GradSolver, LocalSearchSolver

OUTPUT_DIR = Path(__file__).parent / "outputs"

DECIMATE_KWARGS = dict(initial_epochs=1000, settle_epochs=10, batch_size=1,
                        lambda_guest=1, lambda_seat=1, lambda_ce=50, lambda_one_hot=0,
                        keep_history=False, verbose=False)
TRAIN_KWARGS = dict(num_epochs=300, lambda_guest=1, lambda_seat=1, lambda_ce=50,
                     lambda_one_hot=0, keep_history=False, verbose=False)

METHODS = ['gradsolver', 'gradsolver+ls', 'decimate', 'decimate+ls', 'local_search_x10']
TABLE_TYPES = ["cabaret", "banquet", "theatre"]
TAG_MODES = [False, True]  # multi_tag
SIZES = [8, 16, 32, 64, 100, 150, 200]
K_REPEATS = 3
CROSS_TAG_POOL = ["interestA", "interestB", "interestC", "interestD"]


def make_scenario(rng, n_guests, table_type, multi_tag, clique_size=None, target_table_size=None):
    # clique_size and target_table_size are randomized per call unless
    # pinned, so "guest count" isn't the only thing varying across repeats --
    # table granularity and clique granularity vary too.
    if clique_size is None:
        clique_size = rng.choice([3, 4, 5, 6])
    if target_table_size is None:
        target_table_size = rng.choice([6, 8, 10])

    guests = []
    for i in range(n_guests):
        tags = [f"clique{i // clique_size}"]
        if multi_tag:
            # cross-cutting tags that ignore clique boundaries, closer to a
            # real guest list where people carry multiple overlapping tags.
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
        num_rows = 2  # num_rows=1 is degenerate (breaks TheatreSection.adjacency())
        sizes = [max(s, 4) for s in sizes]  # avoid a 1-seat-per-row table, which has zero adjacency edges
        sizes = [((s + num_rows - 1) // num_rows) * num_rows for s in sizes]
        tables = [TheatreSection(id=f"t{i}", num_seats=s, num_rows=num_rows) for i, s in enumerate(sizes)]
    else:
        raise ValueError(table_type)

    return guests, tables


def brute_force_optimum(guests, tables):
    ls = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=[])
    n = ls.n
    best = -np.inf
    for perm in itertools.permutations(range(n)):
        s = ls.score(np.array(perm))
        if s > best:
            best = s
    return best / len(guests)


def run_gradsolver(guests, tables):
    start = time.time()
    model = GradSolver(guest_list=guests, table_list=tables, constraints=[], init_type='uniform')
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


def run_decimate(guests, tables):
    start = time.time()
    model = GradSolver(guest_list=guests, table_list=tables, constraints=[], init_type='uniform')
    model.decimate(**DECIMATE_KWARGS)
    guest_to_seat = model.extract_hard_seating()
    score = model._summarize_assignment(guest_to_seat)['relation_score']
    return score, time.time() - start, guest_to_seat


def run_decimate_plus_ls(guests, tables, decimate_guest_to_seat):
    start = time.time()
    ls = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=[])
    seat_to_guest = np.argsort(decimate_guest_to_seat)
    guest_to_seat = ls.solve(initial=seat_to_guest)
    score = ls._summarize_assignment(guest_to_seat)['relation_score']
    return score, time.time() - start


def run_local_search(guests, tables, num_restarts=10, seed=0):
    start = time.time()
    ls = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=[])
    guest_to_seat = ls.solve(seed=seed, num_restarts=num_restarts)
    score = ls._summarize_assignment(guest_to_seat)['relation_score']
    return score, time.time() - start


def run_all_methods(guests, tables):
    results = {}

    score, t, guest_to_seat = run_gradsolver(guests, tables)
    results['gradsolver'] = (score, t)

    score2, t2 = run_gradsolver_plus_ls(guests, tables, guest_to_seat)
    results['gradsolver+ls'] = (score2, t + t2)

    score, t, guest_to_seat = run_decimate(guests, tables)
    results['decimate'] = (score, t)

    score2, t2 = run_decimate_plus_ls(guests, tables, guest_to_seat)
    results['decimate+ls'] = (score2, t + t2)

    score, t = run_local_search(guests, tables, num_restarts=10)
    results['local_search_x10'] = (score, t)

    return results


def run_condition(table_type, multi_tag, seed_offset, total_start):
    data = {method: {'n': [], 'score_mean': [], 'score_std': [], 'time_mean': [], 'time_std': []}
            for method in METHODS}
    for n in SIZES:
        per_score = {m: [] for m in METHODS}
        per_time = {m: [] for m in METHODS}
        for rep in range(K_REPEATS):
            rng = random.Random(seed_offset + n * 1000 + rep)
            guests, tables = make_scenario(rng, n, table_type, multi_tag)
            results = run_all_methods(guests, tables)
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
        print(f"  [{table_type:8s} multi_tag={multi_tag}] n={n:3d} done "
              f"({time.time() - total_start:.1f}s elapsed total)")
    return data


def print_table(rows, headers):
    widths = [max(len(str(r[i])) for r in rows + [headers]) for i in range(len(headers))]
    def fmt_row(r):
        return "  ".join(str(v).ljust(w) for v, w in zip(r, widths))
    print(fmt_row(headers))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print(fmt_row(r))


if __name__ == "__main__":
    total_start = time.time()

    print("=" * 70)
    print("PART 1: small-scale exact comparison against brute-force optimum")
    print("=" * 70)
    small_rows = []
    for n in [6, 8, 9]:
        rng = random.Random(n)
        guests, tables = make_scenario(rng, n, table_type="cabaret", multi_tag=False,
                                        clique_size=3, target_table_size=6)
        opt = brute_force_optimum(guests, tables)
        results = run_all_methods(guests, tables)
        for method, (score, t) in results.items():
            gap = opt - score
            small_rows.append([n, method, f"{score:.4f}", f"{opt:.4f}", f"{gap:.4f}", f"{t:.2f}s"])
        small_rows.append([n, "brute_force (optimum)", f"{opt:.4f}", f"{opt:.4f}", "0.0000", "-"])
    print_table(small_rows, ["n_guests", "method", "score", "optimum", "gap", "time"])

    print()
    print("=" * 70)
    print(f"PART 2: robust sweep -- {len(TABLE_TYPES)} table types x {len(TAG_MODES)} tag modes x "
          f"{len(SIZES)} guest counts x {K_REPEATS} repeats each (clique size and table size also "
          f"randomized per repeat)")
    print("=" * 70)
    all_data = {}
    for table_type in TABLE_TYPES:
        for multi_tag in TAG_MODES:
            key = (table_type, multi_tag)
            seed_offset = abs(hash(key)) % 100000
            all_data[key] = run_condition(table_type, multi_tag, seed_offset, total_start)

    # --- plots: one row per table type, columns = score / time, tag modes distinguished by linestyle ---
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    colors = {'gradsolver': '#888', 'gradsolver+ls': '#4c72b0', 'decimate': '#dd8452',
              'decimate+ls': '#c44e52', 'local_search_x10': '#55a868'}
    fig, axes = plt.subplots(len(TABLE_TYPES), 2, figsize=(14, 5 * len(TABLE_TYPES)))
    for row, table_type in enumerate(TABLE_TYPES):
        ax_score, ax_time = axes[row]
        for multi_tag in TAG_MODES:
            data = all_data[(table_type, multi_tag)]
            linestyle = '-' if not multi_tag else '--'
            tag_label = 'single-tag' if not multi_tag else 'multi-tag'
            for method in METHODS:
                d = data[method]
                label = f"{method} ({tag_label})" if row == 0 else None
                ax_score.errorbar(d['n'], d['score_mean'], yerr=d['score_std'], marker='o',
                                   linestyle=linestyle, color=colors[method], label=label,
                                   capsize=3, alpha=0.85)
                ax_time.errorbar(d['n'], d['time_mean'], yerr=d['time_std'], marker='o',
                                  linestyle=linestyle, color=colors[method], capsize=3, alpha=0.85)
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
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 1.0), ncol=5, fontsize=8)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(OUTPUT_DIR / "benchmark_solvers.png", dpi=150)
    print(f"\nSaved plot: {OUTPUT_DIR / 'benchmark_solvers.png'}")
    print(f"Total runtime: {time.time() - total_start:.1f}s")
