"""
Definitive validation plot for the production circulant+rotate+ls pipeline
on banquet tables, after fixing _CircularBanquetSurrogate to a pure-distance
weight rule (see the session's parity/degree-imbalance investigation).

Uses the ACTUAL production functions (_solve_circulant_rotate_ls,
_solve_local_search) and ACTUAL production hyperparameters, across guest
counts, with real must_sit_together/must_sit_apart constraints (so
constraint_score is meaningful) and randomized tag structure and seat parity
per repeat (not plotted as separate lines/methods -- see prior feedback on
plot density).

Usage: python3 backend/scripts/smoke_test_banquet_definitive.py
"""
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import numpy as np

from app.schema import Guest, Constraint, BanquetTable
from app.optimiser import _solve_circulant_rotate_ls, _solve_local_search

OUTPUT_DIR = Path(__file__).parent / "outputs"

GUEST_SIZES = [20, 40, 60, 80, 100, 120]
K_REPEATS = 8
CROSS_TAG_POOL = ["interestA", "interestB", "interestC", "interestD"]

COLOR_CIRCULANT = "#2a78d6"  # validated categorical slot 1 (blue)
COLOR_LS = "#eb6834"         # validated categorical slot 2 (orange)


def make_scenario(rng, n_guests):
    clique_size = rng.choice([3, 4, 5, 6])
    multi_tag = rng.choice([False, True])

    guests = []
    for i in range(n_guests):
        tags = [f"clique{i // clique_size}"]
        if multi_tag:
            tags += rng.sample(CROSS_TAG_POOL, rng.randint(0, 2))
        guests.append(Guest(id=i, name=f"g{i}", relation_tags=tags))

    n_tables = rng.choice([3, 4, 5])
    seats_per_table = -(-n_guests // n_tables)  # ceil
    # randomize seat parity per repeat -- both are now expected to work after
    # the pure-distance-function fix, and this is exactly the dimension that
    # broke before, so covering it here is part of what makes this "definitive"
    if rng.choice([True, False]) != bool(seats_per_table % 2):
        seats_per_table += 1
    tables = [BanquetTable(id=f"t{i}", num_seats=seats_per_table) for i in range(n_tables)]

    # real must-together/apart constraints, some crossing clique boundaries so
    # they actually conflict with the tag clustering
    clique_of = lambda i: i // clique_size
    n_pairs = max(1, n_guests // 8)
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

    return guests, tables, constraints


def main():
    total_start = time.time()
    data = {"circulant": {"relation": [], "constraint": [], "time": []},
            "ls": {"relation": [], "constraint": [], "time": []}}
    ns = []

    for n_guests in GUEST_SIZES:
        per = {"circulant": {"relation": [], "constraint": [], "time": []},
               "ls": {"relation": [], "constraint": [], "time": []}}
        for rep in range(K_REPEATS):
            seed = abs(hash((n_guests, rep))) % 100000
            rng = random.Random(seed)
            guests, tables, constraints = make_scenario(rng, n_guests)

            t0 = time.time()
            r_circ = _solve_circulant_rotate_ls(guests, tables, constraints)
            t_circ = time.time() - t0

            t0 = time.time()
            r_ls = _solve_local_search(guests, tables, constraints)
            t_ls = time.time() - t0

            per["circulant"]["relation"].append(r_circ["relation_score"])
            per["circulant"]["constraint"].append(r_circ["constraint_score"])
            per["circulant"]["time"].append(t_circ)
            per["ls"]["relation"].append(r_ls["relation_score"])
            per["ls"]["constraint"].append(r_ls["constraint_score"])
            per["ls"]["time"].append(t_ls)

        ns.append(n_guests)
        for method in ["circulant", "ls"]:
            for metric in ["relation", "constraint", "time"]:
                data[method][metric].append(per[method][metric])
        print(f"  n={n_guests:3d} done ({time.time() - total_start:.1f}s elapsed total)")

    # --- print summary table ---
    print(f"\n{'n':>4s}  {'circ_relation':>14s}  {'ls_relation':>12s}  {'circ_constraint':>16s}  "
          f"{'ls_constraint':>14s}  {'circ_time':>10s}  {'ls_time':>8s}")
    for i, n in enumerate(ns):
        print(f"{n:4d}  {np.mean(data['circulant']['relation'][i]):14.4f}  {np.mean(data['ls']['relation'][i]):12.4f}  "
              f"{np.mean(data['circulant']['constraint'][i]):16.4f}  {np.mean(data['ls']['constraint'][i]):14.4f}  "
              f"{np.mean(data['circulant']['time'][i]):10.2f}s  {np.mean(data['ls']['time'][i]):8.2f}s")

    # --- plot: one row per metric (relation, constraint, time), single axis each ---
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
    metrics = [("relation", "relation_score (mean)"), ("constraint", "constraint_score (mean)"), ("time", "wall-clock time (s)")]

    for ax, (metric, ylabel) in zip(axes, metrics):
        for method, color, label in [("circulant", COLOR_CIRCULANT, "circulant+rotate+ls"),
                                      ("ls", COLOR_LS, "local_search_x10")]:
            means = [np.mean(vals) for vals in data[method][metric]]
            stds = [np.std(vals) for vals in data[method][metric]]
            ax.errorbar(ns, means, yerr=stds, marker='o', color=color, label=label, capsize=3, linewidth=2)
        ax.set_xlabel("number of guests")
        ax.set_ylabel(ylabel)
        ax.set_title(ylabel.split(" (")[0].replace("_", " "))
        ax.grid(alpha=0.25)
        if metric == "time":
            ax.set_yscale("log")

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 1.06), ncol=2, fontsize=10, frameon=False)
    fig.suptitle(f"Banquet table: circulant+rotate+ls vs local_search_x10 ({K_REPEATS} repeats/point, error bars = std)",
                 y=1.14, fontsize=12)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "banquet_definitive.png", dpi=150, bbox_inches='tight')
    print(f"\nSaved plot: {OUTPUT_DIR / 'banquet_definitive.png'}")
    print(f"Total runtime: {time.time() - total_start:.1f}s")


if __name__ == "__main__":
    main()
