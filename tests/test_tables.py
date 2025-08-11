from seating_plan.tables import BanquetTable
from seating_plan.validation import is_valid_matrix_id_dict
from seating_plan.exceptions import InvalidInput, TableError
import numpy as np
import random
import pytest

data =[
    {'name':'Anca', 'relational_tags':['htb','st_saviour','acton']},
    {'name':'Madison', 'relational_tags':['htb','acton']},
    {'name':'Tekena', 'relational_tags':['htb','kcl']},
    {'name':'Josh', 'relational_tags':['htb','kcl']},
    {'name':'Melissa', 'relational_tags':['htb']},
    {'name':'Kate', 'relational_tags':['ual']},
    {'name':'Mel', 'relational_tags':['ual']},
    {'name':'Julia', 'relational_tags':['cambridge']},
    {'name':'Alex', 'relational_tags':['cambridge','ags']},
    {'name':'Danny', 'relational_tags':['ags','htb']},
    {'name':'Success', 'relational_tags':['ags','cambridge']},
    {'name':'Judah', 'relational_tags':['htb','st_saviour','acton']},
    {'name':'Amet', 'relational_tags':['htb','st_saviour','acton']},
    {'name':'Judd', 'relational_tags':['htb','acton']},
    {'name':'Hannah', 'relational_tags':['htb','acton']}
]

def test_banquet_table_init():
    table00 = BanquetTable(num_side_seats=6)
    table10 = BanquetTable(num_side_seats=6,head_seat=True)
    table01= BanquetTable(num_side_seats=7)
    table11 = BanquetTable(num_side_seats=6,head_seat=True,foot_seat=True)
    #Check that the number of seats is correct
    assert table00.num_seats == 6
    assert table10.num_seats == 7
    assert table01.num_seats == 7
    assert table11.num_seats == 8
    #Check that the head and foot seats are set correctly
    assert bool(table00.head_seat) == False
    assert bool(table00.foot_seat) == False
    assert bool(table10.head_seat) == True
    assert bool(table10.foot_seat) == False
    assert bool(table01.head_seat) == False
    assert bool(table01.foot_seat) == False
    assert bool(table11.head_seat) == True
    assert bool(table11.foot_seat) == True
    #Check the adjacency matrix shape
    assert table00.adjacency_matrix.shape == (6, 6)
    assert table10.adjacency_matrix.shape == (7, 7)
    assert table01.adjacency_matrix.shape == (7, 7)
    assert table11.adjacency_matrix.shape == (8, 8)
    #Check that the adjacency matrix is symmetric
    assert np.all(table00.adjacency_matrix == table00.adjacency_matrix.T)
    assert np.all(table10.adjacency_matrix == table10.adjacency_matrix.T)
    assert np.all(table01.adjacency_matrix == table01.adjacency_matrix.T)
    assert np.all(table11.adjacency_matrix == table11.adjacency_matrix.T)
    #Check that the adjacency matrix has the right number of edges
    assert np.sum(table00.adjacency_matrix) == 2*7  
    assert np.sum(table10.adjacency_matrix) == 2*9
    assert np.sum(table01.adjacency_matrix) == 2*8
    assert np.sum(table11.adjacency_matrix) == 2*11
    #Check that the adjacency matrix has the right edge connections
    #table00
    assert np.all(table00.adjacency_matrix[0,:] == np.array([0,1,1,0,0,0]))
    assert np.all(table00.adjacency_matrix[1,1:] == np.array([0,0,1,0,0]))
    assert np.all(table00.adjacency_matrix[2,2:] == np.array([0,1,1,0]))
    assert np.all(table00.adjacency_matrix[3,3:] == np.array([0,0,1]))
    assert np.all(table00.adjacency_matrix[4,4:] == np.array([0,1]))
    assert np.all(table00.adjacency_matrix[5,5:] == np.array([0]))
    #table10
    assert np.all(table10.adjacency_matrix[0,:] == np.array([0,1,1,0,0,0,0]))
    assert np.all(table10.adjacency_matrix[1,1:] == np.array([0,1,1,0,0,0]))
    assert np.all(table10.adjacency_matrix[2,2:] == np.array([0,0,1,0,0]))
    assert np.all(table10.adjacency_matrix[3,3:] == np.array([0,1,1,0]))
    assert np.all(table10.adjacency_matrix[4,4:] == np.array([0,0,1]))
    assert np.all(table10.adjacency_matrix[5,5:] == np.array([0,1]))
    assert np.all(table10.adjacency_matrix[6,6:] == np.array([0]))
    #table01
    assert np.all(table01.adjacency_matrix[0,:] == np.array([0,1,1,0,0,0,0]))
    assert np.all(table01.adjacency_matrix[1,1:] == np.array([0,0,1,0,0,0]))
    assert np.all(table01.adjacency_matrix[2,2:] == np.array([0,1,1,0,0]))
    assert np.all(table01.adjacency_matrix[3,3:] == np.array([0,0,1,0]))
    assert np.all(table01.adjacency_matrix[4,4:] == np.array([0,1,1]))
    assert np.all(table01.adjacency_matrix[5,5:] == np.array([0,0]))
    assert np.all(table01.adjacency_matrix[6,6:] == np.array([0]))
    #table11
    assert np.all(table11.adjacency_matrix[0,:] == np.array([0,1,1,0,0,0,0,0]))
    assert np.all(table11.adjacency_matrix[1,1:] == np.array([0,1,1,0,0,0,0]))
    assert np.all(table11.adjacency_matrix[2,2:] == np.array([0,0,1,0,0,0]))
    assert np.all(table11.adjacency_matrix[3,3:] == np.array([0,1,1,0,0]))
    assert np.all(table11.adjacency_matrix[4,4:] == np.array([0,0,1,0]))
    assert np.all(table11.adjacency_matrix[5,5:] == np.array([0,1,1]))
    assert np.all(table11.adjacency_matrix[6,6:] == np.array([0,1]))
    assert np.all(table11.adjacency_matrix[7,7:] == np.array([0]))
    #Check that errors are raised for invalid tables
    with pytest.raises(InvalidInput):
        BanquetTable(num_side_seats=5, head_seat=True, foot_seat=True)
    with pytest.raises(InvalidInput):
        BanquetTable(num_side_seats=6, head_seat=False, foot_seat=True)
    with pytest.raises(InvalidInput):
        BanquetTable(num_side_seats=-1, head_seat=True, foot_seat=False)
    with pytest.raises(InvalidInput):
        BanquetTable(num_side_seats=1, head_seat=False, foot_seat=False)

def test_banquet_table_assign_side_seat():
    table = BanquetTable(num_side_seats=6)
    # Check that assigning a side seat works
    seat_pos = np.random.randint(0, 6)
    guest_id = 'Anca'
    table.assign_side_seat(guest_id='Anca', seat_pos=seat_pos)
    assert table.side_seats[seat_pos] == 'Anca'
    table.assign_side_seat(guest_id='Bobby', seat_pos=seat_pos)
    assert table.side_seats[seat_pos] == 'Bobby'
    # Check that assigning a side seat out of range raises an error
    with pytest.raises(InvalidInput):
        table.assign_side_seat(guest_id=2, seat_pos=6)
    # Check that assigning a side seat with a negative position raises an error
    with pytest.raises(InvalidInput):
        table.assign_side_seat(guest_id=3, seat_pos=-1)

def test_banquet_table_assign_head_seat():
    table = BanquetTable(num_side_seats=6, head_seat=True)
    # Check that assigning a head seat works
    guest_id = 'Anca'
    table.assign_head_seat(guest_id='Anca')
    assert table.head_seat[0] == 'Anca'
    # Check that assigning a head seat when no head seat is available raises an error
    table_no_head = BanquetTable(num_side_seats=6, head_seat=False)
    with pytest.raises(TableError):
        table_no_head.assign_head_seat(guest_id='Bobby')

def test_banquet_table_assign_foot_seat():
    table = BanquetTable(num_side_seats=6, head_seat=True, foot_seat=True)
    # Check that assigning a foot seat works
    guest_id = 'Anca'
    table.assign_foot_seat(guest_id='Anca')
    assert table.foot_seat[0] == 'Anca'
    # Check that assigning a foot seat when no foot seat is available raises an error
    table_no_foot = BanquetTable(num_side_seats=6, head_seat=True, foot_seat=False)
    with pytest.raises(TableError):
        table_no_foot.assign_foot_seat(guest_id='Bobby')

def test_banquet_table_compute_score():
    #mock similarity matrix and id_dict
    id_dict = {data[i]['name']: i for i in range(len(data))}
    matrix = np.random.rand(len(data), len(data))
    matrix = (matrix + matrix.T) / 2  # make it symmetric
    np.fill_diagonal(matrix, 0)  # set diagonal to zero

    #create a BanquetTable and assign seats
    table = BanquetTable(num_side_seats=6, head_seat=True, foot_seat=True)
    shuffle_data = random.sample(data, len(data))
    table.assign_head_seat(guest_id=shuffle_data[0]['name'])
    table.assign_foot_seat(guest_id=shuffle_data[7]['name'])
    for seat_pos in range(6):
        table.assign_side_seat(guest_id=data[seat_pos+1]['name'], seat_pos=seat_pos)

    score = table.compute_score(matrix, id_dict,param=1.0)
    # Check that the score is a non-negative float
    assert isinstance(score, float)
    assert 0 <= score 

    disconnected_table = BanquetTable(num_side_seats=6)
    disconnected_table.assign_side_seat(guest_id=data[0]['name'], seat_pos=0)
    disconnected_table.assign_side_seat(guest_id=data[1]['name'], seat_pos=3)
    disconnected_table.assign_side_seat(guest_id=data[2]['name'], seat_pos=4)
    with pytest.warns(UserWarning):
        disconnected_score = disconnected_table.compute_score(matrix, id_dict)
    # Check that the score is zero for disconnected seats
    assert disconnected_score == 0.0
