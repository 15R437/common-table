import pytest
import random
import numpy as np
from seating_plan import optimisers
from seating_plan import tables
from seating_plan import exceptions

guests = ['Alice','Bob','Charlie','David','Eve',
         'Frank','Grace','Heidi','Ivan','Judy',
         'Karl','Leo','Mallory','Nina','Oscar',
         'Peggy','Quentin','Rupert','Sybil','Trent']
num_guests = len(guests)
shuffled_guests = random.sample(guests, num_guests)
id_dict = {name:i for i,name in enumerate(shuffled_guests)}

# Generate a random similarity matrix
np.random.seed(42) 
matrix = 2*np.random.rand(num_guests, num_guests)
matrix = (matrix + matrix.T)/2
np.fill_diagonal(matrix, 0)

# Set negative relations in the matrix whilst keeping it symmetric
negative_relations = np.random.choice(num_guests**2, size=5, replace=False)
negative_guest_pairs = []
for i in negative_relations:
    row, col = divmod(i, num_guests)
    if row == col:  # Skip diagonal elements
        continue
    matrix[row, col] = -1
    matrix[col, row] = -1
    negative_guest_pairs.append((shuffled_guests[row], shuffled_guests[col]))



@pytest.fixture
def initial_state():
    """Fixture to create an initial state with two tables."""
    table1 = tables.BanquetTable(num_side_seats=6, head_seat=True, foot_seat=True)
    table2 = tables.BanquetTable(num_side_seats=6, head_seat=True, foot_seat=True)
    table3 = tables.BanquetTable(num_side_seats=6, head_seat=True, foot_seat=True)
    
    # Assign some guests to the tables
    for i in range(8):
        table1.assign_seat(guest_id=shuffled_guests[i], seat_pos=i % 8)
        table2.assign_seat(guest_id=shuffled_guests[i+ 8], seat_pos=i % 8)
        if i <4:
            table3.assign_seat(guest_id=shuffled_guests[i + 16], seat_pos=i % 8)
    
    return [table1, table2, table3]

def test_SimAnnealer_init(initial_state):
    #initial_state is not a [list of] table object[s]
    with pytest.raises(TypeError):
        annealer = optimisers.SimAnnealer(42, matrix, id_dict)
    #initial_state is a list of non-Table objects
    with pytest.raises(TypeError):
        annealer = optimisers.SimAnnealer([42, "string"], matrix, id_dict)
    #initial_state is a Table object but not enough filled seats
    with pytest.raises(exceptions.InvalidInput):
        empty_table = tables.BanquetTable(num_side_seats=4,head_seat=True)
        annealer = optimisers.SimAnnealer(empty_table, matrix, id_dict)
    #invalid score_matrix
    with pytest.raises(exceptions.InvalidInput):
        invalid_matrix = np.array([[1, 2], [3, 4]])
        invalid_id_dict = {0: 0, 1: 1}
        annealer = optimisers.SimAnnealer(initial_state, invalid_matrix, invalid_id_dict)
    #invalid id_dict
    with pytest.raises(exceptions.InvalidInput):
        invalid_matrix = np.array([[1, 2], [3, 4]])
        invalid_id_dict = {0: 0, 1: 2}
        annealer = optimisers.SimAnnealer(initial_state, invalid_matrix, invalid_id_dict)
    #valid initialisation
    annealer = optimisers.SimAnnealer(initial_state, matrix, id_dict)
    assert isinstance(annealer, optimisers.SimAnnealer)
    assert all(annealer.state[i].seats == initial_state[i].seats for i in range(len(initial_state)))
    assert annealer.score_matrix is matrix
    assert annealer.id_dict is id_dict

def test_SimAnnealer_move(initial_state):
    annealer = optimisers.SimAnnealer(initial_state, matrix, id_dict)
    prev_state = [table.seats.copy() for table in annealer.state]
    last_guests = [annealer.last_guests]
    # Perform a move
    for i in range(10):
        annealer.move()
        assert any(table.seats != prev_state[i] for i, table in enumerate(annealer.state))
        prev_state = [table.seats.copy() for table in annealer.state]
        last_guests.append(annealer.last_guests)
        # Check that the last guests swapped are not the same as the previous ones
        assert set(last_guests[-1]) != set(last_guests[-2]) 

def test_SimAnnealer_energy(initial_state):
    annealer = optimisers.SimAnnealer(initial_state, matrix, id_dict)
    # Calculate the energy of the initial state
    initial_energy = annealer.energy()
    assert isinstance(initial_energy, (int, float))
    # Perform a move and check if the energy changes
    annealer.move()
    new_energy = annealer.energy()
    assert isinstance(new_energy, (int, float))
    assert new_energy != initial_energy

def test_SimAnnealer_anneal(initial_state):
    annealer = optimisers.SimAnnealer(initial_state, matrix, id_dict)
    scheduler = annealer.auto(minutes=10)
    best_state,best_energy = annealer.anneal()
    # check that none of the negative guest pairs are sitting together
    for guest_1, guest_2 in negative_guest_pairs:
        guest_1_table = next((table for table in best_state if guest_1 in table.seats.values()), None)
        guest_2_table = next((table for table in best_state if guest_2 in table.seats.values()), None)
        if guest_1_table == guest_2_table:
            adjacency_matrix = guest_1_table.adjacency_matrix
            guest_1_seat = list(guest_1_table.seats.values()).index(guest_1)
            guest_2_seat = list(guest_2_table.seats.values()).index(guest_2)
            # Check that the adjacency matrix entry for these guests is zero
            assert adjacency_matrix[guest_1_seat, guest_2_seat] == 0, \
                f"Guests {guest_1} and {guest_2} are sitting together in the same table."
            