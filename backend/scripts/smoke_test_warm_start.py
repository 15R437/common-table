"""
Smoke test, two questions:

(1) Does training GradSolver and extracting a hard seating via the Hungarian
    algorithm give LocalSearchSolver a better warm start than a random
    permutation (the same single-shot budget: one starting point, one
    hill-climb to a swap-local optimum)?

(2) When extracting that hard seating, is running the Hungarian algorithm on
    -(T_guest + T_seats.T) meaningfully better than what
    GradSolver.extract_hard_seating currently does (-T_guest alone)?

Both extraction variants are implemented here as a standalone helper -- this
does not edit GradSolver.extract_hard_seating, it's a throwaway comparison.

Sampled over many random problem instances (guest/tag/table-type structure
varies), not seeds on one fixed instance -- see smoke_test_anchoring.py for
why that matters here (GradSolver's uniform init is deterministic given the
instance).

Usage: python3 backend/scripts/smoke_test_warm_start.py
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from scipy.optimize import linear_sum_assignment

from app.schema import Guest, CabaretTable, BanquetTable
from app.solvers import GradSolver, LocalSearchSolver

TRAIN_KWARGS = dict(num_epochs=300, lambda_guest=1, lambda_seat=1, lambda_ce=50,
                     lambda_one_hot=10, keep_history=False, verbose=False)
N_INSTANCES = 30
LOCAL_SEARCH_RESTARTS = 300  # for the reference optimum
K_RANDOM_DRAWS = 10          # random single-restart draws per instance, for comparison
CROSS_TAG_POOL = ["interestA", "interestB", "interestC", "interestD"]


def random_scenario(rng, table_type="cabaret", multi_tag=False):
    n_cliques = rng.randint(3, 6)
    # BanquetTable.adjacency() has a known bug on odd seat counts.
    clique_size = rng.choice([2, 4]) if table_type == "banquet" else rng.randint(2, 4)
    n = n_cliques * clique_size

    guests = []
    for i in range(n):
        tags = [f"clique{i // clique_size}"]
        if multi_tag:
            tags += rng.sample(CROSS_TAG_POOL, rng.randint(0, 2))
        guests.append(Guest(id=i, name=f"g{i}", relation_tags=tags))

    if table_type == "banquet":
        tables = [BanquetTable(id=t, num_seats=clique_size) for t in range(n_cliques)]
    else:
        tables = [CabaretTable(id=t, num_seats=clique_size) for t in range(n_cliques)]
    return guests, tables


def reference_optimum(ls):
    guest_to_seat = ls.solve(num_restarts=LOCAL_SEARCH_RESTARTS, seed=0)
    return ls._summarize_assignment(guest_to_seat)['relation_score']


def hungarian_seating(T_guest, T_seats, n_guests, n_seats, variant):
    if variant == "guest_only":
        cost = -T_guest[:n_guests, :n_seats]
    elif variant == "combined":
        cost = -(T_guest + T_seats.T)[:n_guests, :n_seats]
    else:
        raise ValueError(variant)
    row_ind, col_ind = linear_sum_assignment(cost)
    guest_to_seat = np.zeros(n_guests, dtype=int)
    guest_to_seat[row_ind] = col_ind
    return guest_to_seat


def run_condition(table_type, multi_tag):
    rng = random.Random(hash((table_type, multi_tag)) & 0xffff)
    ratios = {"grad_guest_only": [], "grad_combined": [], "random_mean": [], "random_best": []}
    record_guest, record_combined = [], []  # (wins, ties, losses) vs the 10 random draws, per instance

    for i in range(N_INSTANCES):
        guests, tables = random_scenario(rng, table_type=table_type, multi_tag=multi_tag)
        ls = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=[])
        optimum = reference_optimum(ls)
        if optimum <= 0:
            continue

        model = GradSolver(guest_list=guests, table_list=tables, constraints=[], init_type='uniform')
        model.train(**TRAIN_KWARGS)
        T_guest, T_seats = model.get_soft_assignment()
        T_guest = T_guest.detach().numpy()
        T_seats = T_seats.detach().numpy()
        n_guests, n_seats = model.n_guests, model.n_seats

        def refined_score(g2s):
            seat_to_guest = np.argsort(g2s)
            guest_to_seat = ls.solve(initial=seat_to_guest)
            return ls._summarize_assignment(guest_to_seat)['relation_score']

        g2s_guest_only = hungarian_seating(T_guest, T_seats, n_guests, n_seats, "guest_only")
        g2s_combined = hungarian_seating(T_guest, T_seats, n_guests, n_seats, "combined")
        score_guest_only = refined_score(g2s_guest_only)
        score_combined = refined_score(g2s_combined)

        random_scores = np.array([
            ls._summarize_assignment(ls.solve(seed=1000 * i + k, num_restarts=1))['relation_score']
            for k in range(K_RANDOM_DRAWS)
        ])

        ratios["grad_guest_only"].append(score_guest_only / optimum)
        ratios["grad_combined"].append(score_combined / optimum)
        ratios["random_mean"].append(random_scores.mean() / optimum)
        ratios["random_best"].append(random_scores.max() / optimum)

        def wtl(score):
            tie = np.isclose(score, random_scores, atol=1e-9)
            win = (score > random_scores) & ~tie
            loss = (score < random_scores) & ~tie
            return win.sum(), tie.sum(), loss.sum()

        record_guest.append(wtl(score_guest_only))
        record_combined.append(wtl(score_combined))

    label = f"table_type={table_type:8s} multi_tag={multi_tag}"
    print(f"--- {label} ({N_INSTANCES} instances, {K_RANDOM_DRAWS} random draws/instance) ---")
    for key in ["grad_guest_only", "grad_combined", "random_mean", "random_best"]:
        arr = np.array(ratios[key])
        print(f"{key:16s}  mean_ratio={arr.mean():.4f}  std={arr.std():.4f}")
    total_draws = N_INSTANCES * K_RANDOM_DRAWS
    for name, record in [("grad_guest_only", record_guest), ("grad_combined", record_combined)]:
        wins, ties, losses = np.array(record).sum(axis=0)
        print(f"{name} vs individual random draws: "
              f"win={wins}/{total_draws} ({wins/total_draws:.1%})  "
              f"tie={ties}/{total_draws} ({ties/total_draws:.1%})  "
              f"loss={losses}/{total_draws} ({losses/total_draws:.1%})")
    print()


def main():
    for table_type in ["cabaret", "banquet"]:
        for multi_tag in [False, True]:
            run_condition(table_type, multi_tag)


if __name__ == "__main__":
    main()
