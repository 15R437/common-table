import numpy as np
from .schema import SeatingRequest, SeatingResponse, ConstraintViolation
from .solvers import GradSolver, LocalSearchSolver

NUM_EPOCHS = 1000
LAMBDA_GUEST = 1
LAMBDA_SEAT = 1
LAMBDA_CE = 50
LAMBDA_ONE_HOT = 100

MAX_GUESTS = 120
MAX_SEATS = 120

def solve(request: SeatingRequest) -> SeatingResponse:
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
            f"{len(guest_list)} guests but only {total_seats} seats available across all tables."
        )

    #NUM_EPOCHS = 100 * len(guest_list)
    model = GradSolver(guest_list=guest_list, table_list=table_list, constraints=constraints, init_type='surjective')
    model.train(lambda_guest=LAMBDA_GUEST, lambda_seat=LAMBDA_SEAT, lambda_ce=LAMBDA_CE, lambda_one_hot=LAMBDA_ONE_HOT, num_epochs=NUM_EPOCHS, keep_history=False, verbose=False)
    guest_to_seat = model.extract_hard_seating()
    local_search = LocalSearchSolver(guest_list=guest_list, table_list=table_list, constraints=constraints)
    seat_to_guest = np.argsort(guest_to_seat)
    guest_to_seat = local_search.solve(initial=seat_to_guest)
    result = model._summarize_assignment(guest_to_seat=guest_to_seat)

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