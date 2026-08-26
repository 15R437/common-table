"""
Corrected, definitive version of smoke_test_constraint_density_power.py.

Two fixes over that earlier attempt:
1. Scenario generator now matches EXACTLY what the original validated win
   used (smoke_test_rotate_trick.py): clique_size = seats_per_table, n_tables
   fixed, no multi-tag structure. The earlier attempt independently
   randomized clique_size and table size, which is a confound -- it can make
   the clustering problem harder regardless of constraints, and that attempt
   showed circulant losing even at density=none, which contradicts the
   actual validated result. This version isolates constraint density as the
   only thing that varies, holding the validated-clean structure fixed.
2. Win/tie/loss now uses the REAL lexicographic (constraint_score,
   relation_score) comparison production's solve() actually uses, not a
   relation_score-only comparison.

Usage: python3 backend/scripts/smoke_test_constraint_density_definitive.py
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

GUEST_SIZES = [60, 150, 300]
DENSITIES = {"none": None, "sparse": 10, "dense": 3}
K_REPEATS = 10
N_TABLES = 5

COLOR_CIRCULANT = "#2a78d6"
COLOR_LS = "#eb6834"


def make_scenario(rng, n_guests, density_divisor):
    # matches smoke_test_rotate_trick.py's validated structure exactly:
    # clique_size = seats_per_table, no multi-tag.
    clique_size = -(-n_guests // N_TABLES)  # ceil
    clique_of = lambda i: i // clique_size
    guests = [Guest(id=i, name=f"g{i}", relation_tags=[f"clique{clique_of(i)}"]) for i in range(n_guests)]

    seats_per_table = -(-n_guests // N_TABLES)
    if rng.choice([True, False]) != bool(seats_per_table % 2):
        seats_per_table += 1  # randomize parity per repeat -- both validated now
    tables = [BanquetTable(id=f"t{i}", num_seats=seats_per_table) for i in range(N_TABLES)]

    constraints = []
    if density_divisor is not None:
        n_pairs = max(1, n_guests // density_divisor)
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
    data = {}  # (density, metric) -> list of lists-of-values, one per n

    for density_name, divisor in DENSITIES.items():
        per_metric = {"relation": [], "constraint": [], "time_circ": [], "time_ls": [],
                      "relation_ls": [], "constraint_ls": [], "lex_wtl": []}
        for n_guests in GUEST_SIZES:
            rel_c, con_c, t_c, rel_l, con_l, t_l = [], [], [], [], [], []
            wins, ties, losses = 0, 0, 0
            for rep in range(K_REPEATS):
                seed = abs(hash((density_name, n_guests, rep, "definitive"))) % 1000000
                rng = random.Random(seed)
                guests, tables, constraints = make_scenario(rng, n_guests, divisor)

                t0 = time.time()
                r_circ = _solve_circulant_rotate_ls(guests, tables, constraints)
                t_c.append(time.time() - t0)

                t0 = time.time()
                r_ls = _solve_local_search(guests, tables, constraints)
                t_l.append(time.time() - t0)

                rel_c.append(r_circ['relation_score']); con_c.append(r_circ['constraint_score'])
                rel_l.append(r_ls['relation_score']); con_l.append(r_ls['constraint_score'])

                key_circ = (r_circ['constraint_score'], r_circ['relation_score'])
                key_ls = (r_ls['constraint_score'], r_ls['relation_score'])
                if key_circ > key_ls: wins += 1
                elif key_ls > key_circ: losses += 1
                else: ties += 1

            per_metric["relation"].append(rel_c)
            per_metric["constraint"].append(con_c)
            per_metric["time_circ"].append(t_c)
            per_metric["relation_ls"].append(rel_l)
            per_metric["constraint_ls"].append(con_l)
            per_metric["time_ls"].append(t_l)
            per_metric["lex_wtl"].append((wins, ties, losses))
            print(f"  [{density_name:6s}] n={n_guests:3d} done ({time.time() - total_start:.1f}s elapsed total) "
                  f"lex_win/tie/loss(circ)={wins}/{ties}/{losses}")
        data[density_name] = per_metric

    # --- print summary ---
    print()
    for density_name, per_metric in data.items():
        print(f"--- density={density_name} ({K_REPEATS} repeats/n, lexicographic win/tie/loss) ---")
        print(f"{'n':>4s}  {'circ_rel':>9s}  {'ls_rel':>8s}  {'circ_con':>9s}  {'ls_con':>8s}  "
              f"{'circ_t':>7s}  {'ls_t':>7s}  {'win/tie/loss'}")
        for i, n in enumerate(GUEST_SIZES):
            w, t, l = per_metric["lex_wtl"][i]
            print(f"{n:4d}  {np.mean(per_metric['relation'][i]):9.4f}  {np.mean(per_metric['relation_ls'][i]):8.4f}  "
                  f"{np.mean(per_metric['constraint'][i]):9.4f}  {np.mean(per_metric['constraint_ls'][i]):8.4f}  "
                  f"{np.mean(per_metric['time_circ'][i]):7.2f}  {np.mean(per_metric['time_ls'][i]):7.2f}  {w}/{t}/{l}")
        print()

    # --- plot: rows = metric (relation, constraint, time), cols = density ---
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(3, 3, figsize=(15, 11))
    density_names = list(DENSITIES.keys())

    for col, density_name in enumerate(density_names):
        pm = data[density_name]
        # relation_score
        ax = axes[0, col]
        for key, color, label in [("relation", COLOR_CIRCULANT, "circulant+rotate+ls"), ("relation_ls", COLOR_LS, "local_search_x10")]:
            means = [np.mean(v) for v in pm[key]]
            stds = [np.std(v) for v in pm[key]]
            ax.errorbar(GUEST_SIZES, means, yerr=stds, marker='o', color=color, label=label, capsize=3, linewidth=2)
        ax.set_title(f"density={density_name}")
        if col == 0: ax.set_ylabel("relation_score")
        ax.grid(alpha=0.25)

        # constraint_score
        ax = axes[1, col]
        for key, color in [("constraint", COLOR_CIRCULANT), ("constraint_ls", COLOR_LS)]:
            means = [np.mean(v) for v in pm[key]]
            stds = [np.std(v) for v in pm[key]]
            ax.errorbar(GUEST_SIZES, means, yerr=stds, marker='o', color=color, capsize=3, linewidth=2)
        if col == 0: ax.set_ylabel("constraint_score")
        ax.grid(alpha=0.25)

        # runtime
        ax = axes[2, col]
        for key, color in [("time_circ", COLOR_CIRCULANT), ("time_ls", COLOR_LS)]:
            means = [np.mean(v) for v in pm[key]]
            stds = [np.std(v) for v in pm[key]]
            ax.errorbar(GUEST_SIZES, means, yerr=stds, marker='o', color=color, capsize=3, linewidth=2)
        ax.set_xlabel("number of guests")
        if col == 0: ax.set_ylabel("wall-clock time (s)")
        ax.set_yscale("log")
        ax.grid(alpha=0.25)

    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 1.02), ncol=2, fontsize=11, frameon=False)
    fig.suptitle(f"Banquet: circulant+rotate+ls vs local_search_x10, by constraint density "
                 f"({K_REPEATS} repeats/point, lexicographic win metric, error bars = std)", y=1.07, fontsize=12)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "constraint_density_definitive.png", dpi=150, bbox_inches='tight')
    print(f"\nSaved plot: {OUTPUT_DIR / 'constraint_density_definitive.png'}")
    print(f"Total runtime: {time.time() - total_start:.1f}s")


if __name__ == "__main__":
    main()
