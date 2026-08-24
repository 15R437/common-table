"""
Smoke test: does anchoring one guest break enough symmetry to help GradSolver
find better optima on symmetric-clustering problems (no hard constraints,
several identical tables -- the "prone to local optima" case from prior
testing)?

GradSolver's uniform init is torch.zeros(n, n) -- deterministic given the
problem instance, with nothing else stochastic in training -- so there is no
meaningful "random restart" of a single fixed instance to sample over.
Instead this samples over many random problem instances (guest lists,
relation structure, table counts all vary) and runs each mode once per
instance, paired.

Anchoring is implemented externally via gradient hooks on guest_logits /
seat_logits, so it does NOT touch solvers.py -- this is a throwaway
experiment, not a product change. Three configs:

  baseline      - no anchoring at all
  table_anchor  - guest 0's logits masked to table 0's seat columns only
                  (free to learn *which* seat within that table)
  seat_anchor   - guest 0 hard-pinned to table 0, seat 0 (fully frozen)

Usage: python3 backend/scripts/smoke_test_anchoring.py
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import torch

from app.schema import Guest, CabaretTable, BanquetTable
from app.solvers import GradSolver, LocalSearchSolver

TRAIN_KWARGS = dict(num_epochs=300, lambda_guest=1, lambda_seat=1, lambda_ce=50,
                     lambda_one_hot=10, keep_history=False, verbose=False)
N_INSTANCES = 40
LOCAL_SEARCH_RESTARTS = 300
CROSS_TAG_POOL = ["interestA", "interestB", "interestC", "interestD"]


def random_scenario(rng, table_type="cabaret", multi_tag=False):
    # N_CLIQUES identical-sized tag-cliques seated at that many identical
    # tables sized to match -- true optimum groups each clique at its own
    # table, but the tables are interchangeable, so the objective has an
    # N_CLIQUES!-sized table-swap symmetry group whose size varies by instance.
    n_cliques = rng.randint(3, 6)
    # BanquetTable.adjacency() has a known bug on odd seat counts (see
    # benchmark_solvers.py's make_scenario) -- stick to even sizes for it.
    clique_size = rng.choice([2, 4]) if table_type == "banquet" else rng.randint(2, 4)
    n = n_cliques * clique_size

    guests = []
    for i in range(n):
        tags = [f"clique{i // clique_size}"]
        if multi_tag:
            # cross-cutting tags that ignore clique boundaries, closer to a
            # real guest list where people carry multiple overlapping tags.
            tags += rng.sample(CROSS_TAG_POOL, rng.randint(0, 2))
        guests.append(Guest(id=i, name=f"g{i}", relation_tags=tags))

    if table_type == "banquet":
        tables = [BanquetTable(id=t, num_seats=clique_size) for t in range(n_cliques)]
    else:
        tables = [CabaretTable(id=t, num_seats=clique_size) for t in range(n_cliques)]
    return guests, tables


def table_seat_slices(table_list):
    slices, start = [], 0
    for t in table_list:
        slices.append(slice(start, start + t.num_seats))
        start += t.num_seats
    return slices


def reference_optimum(guests, tables, num_restarts=LOCAL_SEARCH_RESTARTS, seed=0):
    ls = LocalSearchSolver(guest_list=guests, table_list=tables, constraints=[])
    guest_to_seat = ls.solve(num_restarts=num_restarts, seed=seed)
    result = ls._summarize_assignment(guest_to_seat)
    return result['relation_score']


def anchor_guest(model, guest_row, allowed_cols, exact_col=None, init_scale=0.1, seed=0):
    """Restrict guest_row's row of guest_logits (and the matching column of
    seat_logits) to allowed_cols. If exact_col is given, pin hard (no learning
    at all for that guest); otherwise the guest is free to move within
    allowed_cols only."""
    gen = torch.Generator().manual_seed(seed)
    n = model.guest_logits.shape[0]

    with torch.no_grad():
        model.guest_logits[guest_row, :] = -1e4
        model.seat_logits[:, guest_row] = -1e4
        if exact_col is not None:
            model.guest_logits[guest_row, exact_col] = 1e4
            model.seat_logits[exact_col, :] = -1e4
            model.seat_logits[exact_col, guest_row] = 1e4
        else:
            model.guest_logits[guest_row, allowed_cols] = torch.randn(len(allowed_cols), generator=gen) * init_scale
            model.seat_logits[allowed_cols, guest_row] = torch.randn(len(allowed_cols), generator=gen) * init_scale

    guest_mask = torch.zeros(n)
    seat_mask = torch.zeros(n)
    if exact_col is None:
        guest_mask[list(allowed_cols)] = 1
        seat_mask[list(allowed_cols)] = 1

    def guest_hook(grad):
        grad = grad.clone()
        grad[guest_row] = grad[guest_row] * guest_mask
        return grad

    def seat_hook(grad):
        grad = grad.clone()
        grad[:, guest_row] = grad[:, guest_row] * seat_mask
        if exact_col is not None:
            grad[exact_col, :] = 0
        return grad

    model.guest_logits.register_hook(guest_hook)
    model.seat_logits.register_hook(seat_hook)


def run_instance(guests, tables, mode, seed):
    model = GradSolver(guest_list=guests, table_list=tables, constraints=[], init_type='uniform')

    if mode == "table_anchor":
        slices = table_seat_slices(tables)
        anchor_guest(model, guest_row=0, allowed_cols=range(slices[0].start, slices[0].stop), seed=seed)
    elif mode == "seat_anchor":
        anchor_guest(model, guest_row=0, allowed_cols=None, exact_col=0, seed=seed)
    elif mode != "baseline":
        raise ValueError(mode)

    model.train(**TRAIN_KWARGS)
    guest_to_seat = model.extract_hard_seating()
    result = model._summarize_assignment(guest_to_seat)
    return result['relation_score']


def run_sweep(table_type, multi_tag, seed_offset):
    rng = random.Random(seed_offset)
    modes = ["baseline", "table_anchor", "seat_anchor"]
    ratios = {mode: [] for mode in modes}

    for i in range(N_INSTANCES):
        seed = seed_offset + i
        guests, tables = random_scenario(rng, table_type=table_type, multi_tag=multi_tag)
        optimum = reference_optimum(guests, tables, seed=seed)
        for mode in modes:
            score = run_instance(guests, tables, mode, seed=seed)
            ratios[mode].append(score / optimum if optimum > 0 else np.nan)

    baseline = np.array(ratios["baseline"])
    label = f"table_type={table_type:8s} multi_tag={multi_tag}"
    print(f"--- {label} ---")
    for mode in modes:
        arr = np.array(ratios[mode])
        hits = (arr >= 0.999).sum()
        line = f"{mode:14s}  mean_ratio={arr.mean():.4f}  std={arr.std():.4f}  hit_optimum={hits}/{N_INSTANCES}"
        if mode != "baseline":
            delta = arr - baseline
            wins = (delta > 1e-9).sum()
            losses = (delta < -1e-9).sum()
            ties = N_INSTANCES - wins - losses
            line += f"  vs baseline: mean_delta={delta.mean():+.4f}  wins={wins}  losses={losses}  ties={ties}"
        print(line)
    print()


def main():
    # seed_offset keeps each sweep's instances distinct rather than replaying
    # the same 40 problems under a different table_type/multi_tag setting.
    run_sweep(table_type="cabaret", multi_tag=False, seed_offset=0)
    run_sweep(table_type="cabaret", multi_tag=True, seed_offset=1000)
    run_sweep(table_type="banquet", multi_tag=False, seed_offset=2000)
    run_sweep(table_type="banquet", multi_tag=True, seed_offset=3000)


if __name__ == "__main__":
    main()
