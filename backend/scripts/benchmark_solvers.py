"""
Benchmark all the seating-assignment methods discussed this session:

  gradsolver        - single GradSolver training run, Hungarian extraction
  gradsolver+ls      - gradsolver's output, refined by LocalSearchSolver
  decimate           - GradSolver.decimate (pin-most-confident-then-resettle)
  decimate+ls        - decimate's output, refined by LocalSearchSolver
  local_search_x10   - pure LocalSearchSolver, 10 random restarts, no GradSolver at all
  brute_force        - exact optimum (only computed for small guest counts)

Two parts:
  1. Small-scale exact comparison (n <= 9) against true brute-force optimum.
  2. Large-scale sweep (n up to 200) without ground truth (infeasible to
     brute-force), comparing score and wall-clock time across methods.

Usage: python3 backend/scripts/benchmark_solvers.py
"""
import itertools
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import numpy as np

from app.schema import Guest, CabaretTable, BanquetTable, TheatreSection
from app.solvers import GradSolver, LocalSearchSolver

OUTPUT_DIR = Path(__file__).parent / "outputs"

DECIMATE_KWARGS = dict(initial_epochs=200, settle_epochs=15, batch_size=1,
                        lambda_guest=1, lambda_seat=1, lambda_ce=50, lambda_one_hot=0)
TRAIN_KWARGS = dict(num_epochs=300, lambda_guest=1, lambda_seat=1, lambda_ce=50,
                     lambda_one_hot=0, keep_history=False, verbose=False)


def make_scenario(n_guests, clique_size=5, table_type="cabaret", seats_per_table=8):
    guests = [
        Guest(id=i, name=f"g{i}", relation_tags=[f"clique{i // clique_size}"])
        for i in range(n_guests)
    ]
    num_tables = max(1, -(-n_guests // seats_per_table))  # ceil
    base = n_guests // num_tables
    remainder = n_guests % num_tables
    sizes = [base + (1 if i < remainder else 0) for i in range(num_tables)]
    sizes = [max(s, 2) for s in sizes]

    if table_type == "cabaret":
        tables = [CabaretTable(id=f"t{i}", type="cabaret", num_seats=s, full_circle=True)
                  for i, s in enumerate(sizes)]
    elif table_type == "banquet":
        sizes = [s + (s % 2) for s in sizes]  # keep even (avoids the odd-seat adjacency bug)
        tables = [BanquetTable(id=f"t{i}", type="banquet", num_seats=s) for i, s in enumerate(sizes)]
    elif table_type == "theatre":
        num_rows = 2  # num_rows=1 is a degenerate case that breaks TheatreSection.adjacency()
        sizes = [((s + num_rows - 1) // num_rows) * num_rows for s in sizes]  # round up to a multiple of num_rows
        tables = [TheatreSection(id=f"t{i}", type="theatre", num_seats=s, num_rows=num_rows) for i, s in enumerate(sizes)]
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
    result = model.extract_hard_seating()
    return result['avg_score'], time.time() - start, result['assignment']


def run_gradsolver_plus_ls(guests, tables, gradsolver_assignment):
    start = time.time()
    ls = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=[])
    guest_of_seat = np.zeros(ls.n, dtype=int)
    for g, s in gradsolver_assignment.items():
        guest_of_seat[s] = g
    _, score = ls.solve(initial=guest_of_seat)
    return score / len(guests), time.time() - start


def run_decimate(guests, tables):
    start = time.time()
    model = GradSolver(guest_list=guests, table_list=tables, constraints=[], init_type='uniform')
    result = model.decimate(**DECIMATE_KWARGS)
    return result['avg_score'], time.time() - start, result['assignment']


def run_decimate_plus_ls(guests, tables, decimate_assignment):
    start = time.time()
    ls = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=[])
    guest_of_seat = np.zeros(ls.n, dtype=int)
    for g, s in decimate_assignment.items():
        guest_of_seat[s] = g
    _, score = ls.solve(initial=guest_of_seat)
    return score / len(guests), time.time() - start


def run_local_search(guests, tables, num_restarts=10, seed=0):
    start = time.time()
    ls = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=[])
    _, score = ls.solve(seed=seed, num_restarts=num_restarts)
    return score / len(guests), time.time() - start


def run_all_methods(guests, tables):
    results = {}

    score, t, assignment = run_gradsolver(guests, tables)
    results['gradsolver'] = (score, t)

    score2, t2 = run_gradsolver_plus_ls(guests, tables, assignment)
    results['gradsolver+ls'] = (score2, t + t2)

    score, t, assignment = run_decimate(guests, tables)
    results['decimate'] = (score, t)

    score2, t2 = run_decimate_plus_ls(guests, tables, assignment)
    results['decimate+ls'] = (score2, t + t2)

    score, t = run_local_search(guests, tables, num_restarts=10)
    results['local_search_x10'] = (score, t)

    return results


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
        guests, tables = make_scenario(n, clique_size=3, table_type="cabaret", seats_per_table=6)
        opt = brute_force_optimum(guests, tables)
        results = run_all_methods(guests, tables)
        for method, (score, t) in results.items():
            gap = opt - score
            small_rows.append([n, method, f"{score:.4f}", f"{opt:.4f}", f"{gap:.4f}", f"{t:.2f}s"])
        small_rows.append([n, "brute_force (optimum)", f"{opt:.4f}", f"{opt:.4f}", "0.0000", "-"])
    print_table(small_rows, ["n_guests", "method", "score", "optimum", "gap", "time"])

    print()
    print("=" * 70)
    print("PART 2: scaling sweep, n up to 200 (cabaret, full_circle=True, ~8 seats/table)")
    print("=" * 70)
    sizes = [8, 16, 32, 64, 100, 150, 200]
    large_rows = []
    sweep_data = {method: {'n': [], 'score': [], 'time': []} for method in
                  ['gradsolver', 'gradsolver+ls', 'decimate', 'decimate+ls', 'local_search_x10']}
    for n in sizes:
        guests, tables = make_scenario(n, clique_size=5, table_type="cabaret", seats_per_table=8)
        results = run_all_methods(guests, tables)
        for method, (score, t) in results.items():
            large_rows.append([n, method, f"{score:.4f}", f"{t:.2f}s"])
            sweep_data[method]['n'].append(n)
            sweep_data[method]['score'].append(score)
            sweep_data[method]['time'].append(t)
        print(f"  n={n} done ({time.time()-total_start:.1f}s elapsed total)")
    print_table(large_rows, ["n_guests", "method", "score", "time"])

    print()
    print("=" * 70)
    print("PART 3: table type comparison at fixed n=40")
    print("=" * 70)
    type_rows = []
    for table_type in ["banquet", "cabaret", "theatre"]:
        guests, tables = make_scenario(40, clique_size=5, table_type=table_type, seats_per_table=8)
        results = run_all_methods(guests, tables)
        for method, (score, t) in results.items():
            type_rows.append([table_type, method, f"{score:.4f}", f"{t:.2f}s"])
    print_table(type_rows, ["table_type", "method", "score", "time"])

    # --- plots ---
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    colors = {'gradsolver': '#888', 'gradsolver+ls': '#4c72b0', 'decimate': '#dd8452',
              'decimate+ls': '#c44e52', 'local_search_x10': '#55a868'}
    for method, data in sweep_data.items():
        ax1.plot(data['n'], data['score'], marker='o', label=method, color=colors.get(method))
        ax2.plot(data['n'], data['time'], marker='o', label=method, color=colors.get(method))
    ax1.set_xlabel("number of guests")
    ax1.set_ylabel("score (avg_score)")
    ax1.set_title("Score vs. guest count")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.3)
    ax2.set_xlabel("number of guests")
    ax2.set_ylabel("wall-clock time (s)")
    ax2.set_yscale("log")
    ax2.set_title("Time vs. guest count (log scale)")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "benchmark_solvers.png", dpi=150)
    print(f"\nSaved plot: {OUTPUT_DIR / 'benchmark_solvers.png'}")
    print(f"Total runtime: {time.time()-total_start:.1f}s")
