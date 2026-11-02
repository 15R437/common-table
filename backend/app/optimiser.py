import numpy as np
from .schema import SeatingRequest, SeatingResponse, EvaluateRequest, ConstraintViolation, CabaretTable, BanquetTable, TheatreSection
from .solvers import GradSolver, LocalSearchSolver

NUM_EPOCHS = 1000
LAMBDA_GUEST = 1
LAMBDA_SEAT = 1
LAMBDA_CE = 50
LAMBDA_ONE_HOT = 100

MAX_GUESTS = 120
MAX_SEATS = 120

# Cabaret: gradsolver+ls wins unconditionally, at every guest count and tag
# structure tested (including with empty seats) -- no known losing case, so
# it's always used regardless of size. Banquet/theatre: the circulant+rotate
# advantage only shows up at scale, and can lose under realistic multi-tag
# structure at smaller sizes -- plain local_search_x10 is safer below this
# threshold, matching the ~10s wall-clock budget this was chosen against.
LARGE_SCALE_THRESHOLD = 300

# GradSolver's uniform init is deterministic (see solvers.py) -- given the
# same request, the circulant+rotate+ls path produces the exact same result
# every time, unlike local_search_x10's random restarts. The "shuffle" button
# is what gives it any variety at all: GradSolver's raw extraction (after
# rotation, before the final hill-climb) isn't itself a swap-local optimum,
# so a different scan order through that hill-climb can converge to a
# different local optimum (see backend/scripts/smoke_test_shuffle_scan_order.py --
# a shuffled scan order beat the default in 11/40 sampled instances, lost in
# 9/40, tied in 20/40). Trying several shuffles and keeping the best alongside
# the default means the button can only match or improve on the un-shuffled
# result, never regress it.
NUM_SHUFFLE_CANDIDATES = 10


class _CircularBanquetSurrogate(BanquetTable):
    """Circulant surrogate for a head/foot-free BanquetTable, matching the
    real BanquetTable.adjacency()'s hop-decay weight-by-offset shape (see
    backend/scripts/FINDINGS.md §6's postscript for how this was derived
    empirically from the real formula) but wrapped modulo num_seats and made
    a pure function of offset alone (no parity dependence): even offsets get
    adj_score * 2**(1 - d/2), odd offsets get opp_score * 2**(-(d-1)/2) --
    the real formula's own EVEN-seat branch, which is the stronger of its two
    parity variants. Dropping the parity split here is deliberate: the
    surrogate only needs to be a good enough training target for GradSolver
    (see _solve_circulant_rotate_ls) -- the final rotate+refine step always
    scores against the REAL adjacency, parity and all -- so a pure-distance
    function keeps this provably circulant (see the vertex-transitivity
    discussion in FINDINGS.md §2) rather than risking a subtle asymmetry
    from trying to also replicate the parity split across a wraparound where
    "which seat is closer" becomes ambiguous.
    """
    def adjacency(self):
        n = self.num_seats
        adj_score, opp_score = 1.0, 0.75
        m = np.zeros((n, n))
        for d in range(1, n // 2 + 1):
            w = adj_score * 2 ** (1 - d / 2) if d % 2 == 0 else opp_score * 2 ** (-(d - 1) / 2)
            for i in range(n):
                j = (i + d) % n
                if i != j:
                    m[i, j] = w
                    m[j, i] = w
        return m


class _CircularTheatreSurrogate(TheatreSection):
    """Circulant surrogate for TheatreSection: each row treated as its own
    independent ring (first and last seat of the row joined), matching the
    real TheatreSection.adjacency()'s within-row hop-decay weight exactly
    (weight = 2**(1-k_hop) per hop, same formula as CabaretTable's own
    full_circle branch) -- no cross-row edges. Unlike the banquet case, the
    real theatre formula has no parity dependence at all, so this is an exact
    circular match, not an approximation.
    """
    def adjacency(self):
        n = self.num_seats
        rows = self.num_rows
        row_len = n // rows
        m = np.zeros((n, n))
        for r in range(rows):
            base = r * row_len
            for hop in range(1, row_len // 2 + 1):
                weight = 2 ** (1 - hop)
                for i in range(row_len):
                    seat_i = base + i
                    seat_j = base + (i + hop) % row_len
                    if seat_i != seat_j:
                        m[seat_i, seat_j] = weight
                        m[seat_j, seat_i] = weight
        return m


def _circulant_surrogate(table, use_large_scale_surrogate):
    """A table to train GradSolver against in place of `table`, using a
    validated circulant (boundary-free) construction where one exists, or
    None if `table` should be used as-is. Cabaret always gets one (no known
    losing case). Banquet/theatre only get one when `use_large_scale_surrogate`
    is set (see LARGE_SCALE_THRESHOLD) -- their circulant advantage is
    conditional on scale, unlike cabaret's. BanquetTable with a head/foot seat
    has no validated circulant construction and always returns None."""
    if isinstance(table, CabaretTable) and not table.full_circle:
        return CabaretTable(id=table.id, num_seats=table.num_seats, full_circle=True)
    if not use_large_scale_surrogate:
        return None
    if isinstance(table, BanquetTable) and not table.head_seat and not table.foot_seat:
        return _CircularBanquetSurrogate(id=table.id, num_seats=table.num_seats)
    if isinstance(table, TheatreSection):
        return _CircularTheatreSurrogate(id=table.id, num_seats=table.num_seats, num_rows=table.num_rows)
    return None


def _rotate_tables_to_best_fit(seat_to_guest, table_list, surrogate_mask, guest_adjacency, table_adjacency):
    """For each table trained against a circulant surrogate, try every
    rotation of that table's seat_to_guest sub-array (including empty seats,
    represented the same way LocalSearchSolver already represents them --
    dummy guest indices >= n_guests) and keep whichever scores best under the
    REAL adjacency. Tables that trained directly on their real structure
    (surrogate_mask[i] is False) are left untouched."""
    seat_to_guest = seat_to_guest.copy()
    start = 0
    for table, use_surrogate in zip(table_list, surrogate_mask):
        size = table.num_seats
        lo, hi = start, start + size
        if use_surrogate:
            local = seat_to_guest[lo:hi]
            sub_table_adj = table_adjacency[lo:hi, lo:hi]
            best_rot, best_score = 0, -np.inf
            for r in range(size):
                rotated = np.roll(local, r)
                score = np.sum(guest_adjacency[np.ix_(rotated, rotated)] * sub_table_adj)
                if score > best_score:
                    best_score, best_rot = score, r
            seat_to_guest[lo:hi] = np.roll(local, best_rot)
        start += size
    return seat_to_guest


def _solve_circulant_rotate_ls(guest_list, table_list, constraints, use_large_scale_surrogate, shuffle=False):
    """Train against a circulant surrogate per table where one is validated
    (see _circulant_surrogate) -- GradSolver loses to plain local search on
    real open banquet/theatre tables, but wins cleanly once the table has no
    boundary. Then search each surrogate-trained table's rotations against
    the REAL adjacency to find the cheapest place to "cut" it back open, and
    finish with the usual LocalSearchSolver refine on the real tables
    throughout.

    If `shuffle` is set, also try NUM_SHUFFLE_CANDIDATES additional hill-climbs
    with a randomised scan order (see LocalSearchSolver.refine_shuffled) from
    the same post-rotation starting point, and keep whichever candidate --
    including the default-order one -- scores best. This is what the
    "shuffle" button uses to get a different result from an otherwise fully
    deterministic pipeline."""
    surrogates = [_circulant_surrogate(table, use_large_scale_surrogate) for table in table_list]
    surrogate_mask = [s is not None for s in surrogates]
    surrogate_table_list = [s if s is not None else table for s, table in zip(surrogates, table_list)]

    model = GradSolver(guest_list=guest_list, table_list=surrogate_table_list, constraints=constraints, init_type='uniform')
    model.train(lambda_guest=LAMBDA_GUEST, lambda_seat=LAMBDA_SEAT, lambda_ce=LAMBDA_CE,
                lambda_one_hot=LAMBDA_ONE_HOT, num_epochs=NUM_EPOCHS, keep_history=False, verbose=False)
    guest_to_seat = model.extract_hard_seating()

    real_solver = LocalSearchSolver(guest_list=guest_list, table_list=table_list, constraints=constraints)
    seat_to_guest = np.argsort(guest_to_seat)
    seat_to_guest = _rotate_tables_to_best_fit(seat_to_guest, table_list, surrogate_mask,
                                                real_solver.guest_adjacency, real_solver.table_adjacency)

    if shuffle:
        rng = np.random.default_rng()
        candidates = [real_solver.refine(seat_to_guest)]
        candidates += [real_solver.refine_shuffled(seat_to_guest, rng) for _ in range(NUM_SHUFFLE_CANDIDATES)]
        best = max(candidates, key=real_solver.score)
        guest_to_seat = np.argsort(best)
    else:
        guest_to_seat = real_solver.solve(initial=seat_to_guest)
    return real_solver._summarize_assignment(guest_to_seat=guest_to_seat)


def _solve_local_search(guest_list, table_list, constraints, num_restarts=10):
    local_search = LocalSearchSolver(guest_list=guest_list, table_list=table_list, constraints=constraints)
    guest_to_seat = local_search.solve(num_restarts=num_restarts)
    return local_search._summarize_assignment(guest_to_seat=guest_to_seat)


def solve(request: SeatingRequest, shuffle: bool = False) -> SeatingResponse:
    guest_list = request.guests
    table_list = request.tables
    constraints = request.constraints

    if len(guest_list) > MAX_GUESTS:
        raise ValueError(f"Guest list cannot exceed {MAX_GUESTS} guests.")

    total_seats = sum(table.num_seats for table in table_list)
    if total_seats > MAX_SEATS:
        raise ValueError(f"Total seats cannot exceed {MAX_SEATS}.")

    if len(guest_list) > total_seats:
        raise ValueError(
            f"{len(guest_list)} guests but only {total_seats} seats available in total."
        )

    # Cabaret always wins with gradsolver+ls (no losing case found, including
    # with empty seats), so its presence alone is enough to use the circulant
    # pipeline. Banquet/theatre only get a circulant surrogate -- and only
    # earn the pipeline on their own -- once the guest count clears
    # LARGE_SCALE_THRESHOLD, where their circulant advantage was validated;
    # below that, plain local_search_x10 is safer (see the multi-tag/
    # constraint investigation in backend/scripts/smoke_test_*.py). Only one
    # method actually runs -- no sequential fallback -- since each branch's
    # winning conditions are now understood well enough to commit to it.
    has_cabaret = any(isinstance(table, CabaretTable) for table in table_list)
    use_large_scale_surrogate = len(guest_list) >= LARGE_SCALE_THRESHOLD
    if has_cabaret or use_large_scale_surrogate:
        result = _solve_circulant_rotate_ls(guest_list, table_list, constraints, use_large_scale_surrogate, shuffle=shuffle)
    else:
        # Already non-deterministic (random restarts with no fixed seed), so
        # calling this again already gives a fresh attempt -- no separate
        # shuffle mechanism needed on this path.
        result = _solve_local_search(guest_list, table_list, constraints)

    table_capacity = [table.num_seats for table in table_list]
    table_cumulative_capacity = np.cumsum(table_capacity)

    table_assignments = {table.id: {} for table in table_list}
    global_assignments = result['assignment']

    for guest_idx, global_seat_idx in global_assignments.items():
        table_idx = int(np.searchsorted(table_cumulative_capacity, global_seat_idx, side='right'))
        table_start_seat = 0 if table_idx == 0 else table_cumulative_capacity[table_idx - 1]
        local_seat_idx = int(global_seat_idx - table_start_seat)

        target_table_id = table_list[table_idx].id
        guest = guest_list[guest_idx]
        table_assignments[target_table_id][local_seat_idx] = guest

    return _build_response(result, table_assignments, guest_list)


def _build_response(result, table_assignments, guest_list) -> SeatingResponse:
    def to_violations(index_pairs):
        return [
            ConstraintViolation(guest_a=guest_list[a], guest_b=guest_list[b])
            for a, b in index_pairs
        ]

    return SeatingResponse(table_assignments=table_assignments,
                           relation_score=result['relation_score'],
                           constraint_score=result['constraint_score'],
                           must_sit_together=result['must_sit_together'],
                           could_sit_together=result['could_sit_together'],
                           must_sit_apart=result['must_sit_apart'],
                           must_sit_together_violations=to_violations(result['must_sit_together_violations']),
                           must_sit_apart_violations=to_violations(result['must_sit_apart_violations']))


def evaluate(request: EvaluateRequest) -> SeatingResponse:
    """Re-score a hand-edited arrangement without re-optimising it.

    Guests keep the seats the user put them in; only the scores and violation
    lists are recomputed, by the same solver code that scores an optimiser run.
    """
    guest_list = request.guests
    table_list = request.tables

    total_seats = sum(table.num_seats for table in table_list)
    if len(guest_list) > total_seats:
        raise ValueError(
            f"{len(guest_list)} guests but only {total_seats} seats available in total."
        )

    guest_index_by_id = {guest.id: index for index, guest in enumerate(guest_list)}
    table_index_by_id = {table.id: index for index, table in enumerate(table_list)}

    # Global seat indices are laid out table after table, matching how solve()
    # splits them back apart via the cumulative capacities.
    table_capacity = [table.num_seats for table in table_list]
    table_cumulative_capacity = np.cumsum(table_capacity)
    table_start_seat = [0, *table_cumulative_capacity[:-1].tolist()]

    guest_to_seat = np.full(len(guest_list), -1, dtype=int)
    seen_seats = set()

    for raw_table_id, seats in request.assignment.items():
        table_index = table_index_by_id.get(raw_table_id)
        # JSON object keys are always strings, so a table or guest id that is an
        # int on the Python side arrives as its string form.
        if table_index is None:
            table_index = table_index_by_id.get(str(raw_table_id))
        if table_index is None:
            try:
                table_index = table_index_by_id.get(int(raw_table_id))
            except (TypeError, ValueError):
                table_index = None
        if table_index is None:
            raise ValueError(f"Unknown table id {raw_table_id!r} in assignment.")

        for seat_index, guest_id in seats.items():
            if not 0 <= seat_index < table_capacity[table_index]:
                raise ValueError(
                    f"Seat {seat_index} is out of range for table {raw_table_id!r}."
                )

            guest_index = guest_index_by_id.get(guest_id)
            if guest_index is None:
                guest_index = guest_index_by_id.get(str(guest_id))
            if guest_index is None:
                try:
                    guest_index = guest_index_by_id.get(int(guest_id))
                except (TypeError, ValueError):
                    guest_index = None
            if guest_index is None:
                raise ValueError(f"Unknown guest id {guest_id!r} in assignment.")

            global_seat = table_start_seat[table_index] + seat_index
            if global_seat in seen_seats:
                raise ValueError(f"Seat {seat_index} of table {raw_table_id!r} is assigned twice.")
            seen_seats.add(global_seat)

            if guest_to_seat[guest_index] != -1:
                raise ValueError(
                    f"Guest {guest_list[guest_index].name!r} is assigned to more than one seat."
                )
            guest_to_seat[guest_index] = global_seat

    unseated = np.flatnonzero(guest_to_seat == -1)
    if unseated.size:
        names = ", ".join(guest_list[i].name for i in unseated[:5])
        raise ValueError(f"These guests have no seat: {names}.")

    # LocalSearchSolver is used purely as a scorer here -- constructing it builds
    # the relation, constraint and adjacency matrices, and _summarize_assignment
    # reads the arrangement off them without any search running.
    scorer = LocalSearchSolver(guest_list, table_list, request.constraints)
    result = scorer._summarize_assignment(guest_to_seat)

    table_assignments = {table.id: {} for table in table_list}
    for guest_index, global_seat_idx in result['assignment'].items():
        table_idx = int(np.searchsorted(table_cumulative_capacity, global_seat_idx, side='right'))
        local_seat_idx = int(global_seat_idx - table_start_seat[table_idx])
        table_assignments[table_list[table_idx].id][local_seat_idx] = guest_list[guest_index]

    return _build_response(result, table_assignments, guest_list)