import sys
import os
import numpy as np
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import random
from tables import Table
from simanneal import Annealer
from seating_plan.exceptions import OptimiserError,InvalidInput
from seating_plan.models import generate_similarity_matrix
from seating_plan.tables import BanquetTable
from seating_plan.validation import is_valid_matrix_id_dict

# This file contains various optimisers for the seating plan problem.

#Simulated Annealing Optimiser
class SimAnnealer(Annealer):
    def __init__(self, initial_state:list, score_matrix, id_dict,score_param=1,**kwargs):
        """
        initial_state: list of table objects representing an initial assignment of guests to all available seats.

        Philosophy: we will allow the case where there are more seats than guests since a genuine use-case of the
        algorithm could be coming up with the right partition of guests into tables 
        (e.g. if we have two tables with 6 seats and 10 guests, how do we split them: 4+6 or 5+5?)
        """
        if not isinstance(initial_state, list):
            if isinstance(initial_state,Table):
                initial_state = [initial_state]
            else:
                raise TypeError("initial_state should be a [list of] Table[s].")
        if not all(isinstance(table, Table) for table in initial_state):
            raise TypeError(f"All elements in initial_state should be instances of {Table}.")
        #we require that there are at least two filled seats.
        if sum(guest is not None for table in initial_state for guest in table.seats.values()) < 2:
            raise InvalidInput(f"The optimiser {self} requires at least two filled seats in the intial state.")
        
        #check that id_dict and score_matrix are compatible with the initial_state
        if not is_valid_matrix_id_dict(score_matrix,id_dict):
            raise InvalidInput(f"The score_matrix and id_dict provided are not valid.")

        super().__init__(initial_state=initial_state, **kwargs)
        self.copy_strategy = 'deepcopy' 
        self.score_matrix = score_matrix
        self.id_dict = id_dict
        self.score_param = score_param
        self.last_guests = (None,None)  # To avoid swapping the same guests repeatedly 

    def move(self):
        """
        Randomly select two tables (with replacement) containing guests swap two guests.
        """
        guest1,guest2 = self.last_guests
        tables = self.state[:]
        non_empty_tables = [table for table in self.state if any(guest is not None for guest in table.seats.values())]
        while set([guest1,guest2]) == set(self.last_guests):
            table1, table2 = random.choice(non_empty_tables), random.choice(tables)
            seat1,guest1 = random.choice([item for item in list(table1.seats.items()) if item[1] is not None])
            seat2,guest2 = random.choice([item for item in list(table2.seats.items()) if item[1]!= guest1])
        
        self.last_guests = (guest1,guest2)
        table1_idx,table2_idx = self.state.index(table1), self.state.index(table2)
        self.state[table1_idx].assign_seat(guest_id=guest2,seat_pos=seat1)
        self.state[table2_idx].assign_seat(guest_id=guest1,seat_pos=seat2)
    
    def energy(self):
        """
        Calculate the total negative score of the seating arrangement.
        """
        total_score = 0
        for table in self.state:
            total_score -= table.compute_score(self.score_matrix, self.id_dict,self.score_param)
        
        return total_score

#rough test
"""data =[
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
data = random.sample(data,len(data))
matrix,id_dict = generate_similarity_matrix(data,relation_key_word='relational_tags',id_key_word='name')
table1 = BanquetTable(num_side_seats=6,head_seat=True,foot_seat=True)
table2 = BanquetTable(num_side_seats=6,head_seat=True,foot_seat=True)
for pos in range(8):
    table1.assign_seat(data[pos]['name'],pos)
    if pos < 7:
        table2.assign_seat(data[pos+8]['name'],pos)
initial_state = [table1,table2]
for score_param in np.arange(0,1.1,0.1):
    annealer = SimAnnealer(initial_state=initial_state, score_matrix=matrix, id_dict=id_dict, score_param=score_param)
    best_state, best_energy = annealer.anneal()
    print(f"Score parameter: {score_param}")
    print(f"Best energy: {best_energy}")
    for table in best_state:
        print(f"Table seats: {table.seats}")
    print("\n")
"""