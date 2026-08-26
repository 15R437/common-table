"""
Smoke test for the "shuffle button" proposal.

The literal framing -- "shuffle the guest list, then re-run local search" --
can't do anything: LocalSearchSolver.refine() iterates fixed seat-index pairs
(s1, s2) in range(self.n) order; relabeling which guest sits where doesn't
change which seat-pairs get examined or in what order. What could actually
matter is the *scan order* refine() walks over candidate swaps -- a classic
first-improvement hill-climb is path-dependent, so a different scan order
from the same starting point can converge to a different local optimum.

Two questions, tested separately:

(1) From a NOT-YET-CONVERGED starting point (e.g. GradSolver's raw extracted
    seating, before any local search), does randomizing scan order reliably
    find a different/better local optimum than the fixed default order?
    -- this is the gradsolver+ls shuffle-button case.

(2) From an ALREADY-CONVERGED point (the output of refine() itself, e.g. the
    winning restart of local_search_x10), does re-running refine() with a
    shuffled scan order change anything at all? By construction, refine()
    only stops when no single swap improves the score for *any* pair -- a
    property of the state itself, not the order used to discover it. So this
    is expected to be a hard no: re-scanning an empty neighborhood can't find
    what isn't there. This is tested directly, not just argued.

Usage: python3 backend/scripts/smoke_test_shuffle_scan_order.py
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from app.schema import Guest, CabaretTable, BanquetTable
from app.solvers import GradSolver, LocalSearchSolver

TRAIN_KWARGS = dict(num_epochs=300, lambda_guest=1, lambda_seat=1, lambda_ce=50,
                     lambda_one_hot=10, keep_history=False, verbose=False)
N_INSTANCES = 20
K_SHUFFLES = 10
CROSS_TAG_POOL = ["interestA", "interestB", "interestC", "interestD"]


def random_scenario(rng, table_type="banquet", multi_tag=False):
    n_cliques = rng.randint(3, 6)
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


def refine_shuffled(ls: LocalSearchSolver, seat_to_guest: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Same fixed-point hill-climb as LocalSearchSolver.refine(), but the
    (s1, s2) scan order is freshly shuffled at the start of every full pass,
    instead of always being range(n) x range(n)."""
    seat_to_guest = np.array(seat_to_guest, dtype=int).copy()
    n = ls.n
    pairs = [(s1, s2) for s1 in range(n) for s2 in range(s1 + 1, n)]
    improved = True
    while improved:
        improved = False
        rng.shuffle(pairs)
        for s1, s2 in pairs:
            if ls._swap_delta(seat_to_guest, s1, s2) > 1e-9:
                seat_to_guest[s1], seat_to_guest[s2] = seat_to_guest[s2], seat_to_guest[s1]
                improved = True
    return seat_to_guest


def question_1_not_yet_converged():
    """GradSolver's raw extracted seating -> does shuffled-scan-order refine
    beat/differ from the default fixed-order refine?"""
    rng_py = random.Random(1)
    beats_default = 0
    ties_default = 0
    loses_default = 0
    any_variation = 0
    total = 0

    for table_type in ["banquet", "cabaret"]:
        for i in range(N_INSTANCES):
            guests, tables = random_scenario(rng_py, table_type=table_type, multi_tag=True)
            ls = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=[])

            model = GradSolver(guest_list=guests, table_list=tables, constraints=[], init_type='uniform')
            model.train(**TRAIN_KWARGS)
            raw_guest_to_seat = model.extract_hard_seating()
            raw_seat_to_guest = np.argsort(raw_guest_to_seat)

            default_result = ls.refine(raw_seat_to_guest)
            default_score = ls.score(default_result)

            shuffled_scores = []
            for k in range(K_SHUFFLES):
                rng_np = np.random.default_rng(1000 * i + k)
                shuffled_result = refine_shuffled(ls, raw_seat_to_guest, rng_np)
                shuffled_scores.append(ls.score(shuffled_result))
            shuffled_scores = np.array(shuffled_scores)

            total += 1
            if shuffled_scores.max() > default_score + 1e-9:
                beats_default += 1
            elif np.any(np.abs(shuffled_scores - default_score) > 1e-9):
                loses_default += 1
            else:
                ties_default += 1

            if np.ptp(shuffled_scores) > 1e-9:
                any_variation += 1

    print("--- Q1: shuffled scan order from GradSolver's raw (unrefined) seating ---")
    print(f"instances where best-of-{K_SHUFFLES} shuffles beats default order: {beats_default}/{total}")
    print(f"instances where default order beats all {K_SHUFFLES} shuffles:      {loses_default}/{total}")
    print(f"instances tied (all identical):                                    {ties_default}/{total}")
    print(f"instances where the {K_SHUFFLES} shuffles disagree with EACH OTHER: {any_variation}/{total}")
    print()


def question_2_already_converged():
    """A refine()-converged local optimum -> does re-running with a shuffled
    scan order ever find a further improving swap?"""
    rng_py = random.Random(2)
    changed = 0
    total = 0

    for table_type in ["banquet", "cabaret"]:
        for i in range(N_INSTANCES):
            guests, tables = random_scenario(rng_py, table_type=table_type, multi_tag=True)
            ls = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=[])

            start = ls.random_assignment(seed=i)
            converged = ls.refine(start)
            converged_score = ls.score(converged)

            for k in range(K_SHUFFLES):
                rng_np = np.random.default_rng(2000 * i + k)
                reshuffled = refine_shuffled(ls, converged, rng_np)
                reshuffled_score = ls.score(reshuffled)
                total += 1
                if abs(reshuffled_score - converged_score) > 1e-9:
                    changed += 1

    print("--- Q2: shuffled scan order re-applied to an ALREADY-CONVERGED local optimum ---")
    print(f"re-scans that changed the score at all: {changed}/{total}")
    print("(expected: 0/{} -- a swap-local optimum has no improving swap for ANY pair,".format(total))
    print(" which is a property of the state, not the order used to find it)")
    print()


if __name__ == "__main__":
    question_1_not_yet_converged()
    question_2_already_converged()
