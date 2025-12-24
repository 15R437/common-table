import numpy as np
import warnings
from seating_plan.exceptions import InvalidInput,TableError
from seating_plan import validation

class Table:
    def __init__(self,num_seats):
        self.num_seats = num_seats
        self.seats = {i:None for i in range(num_seats)}
        self.adjacency_matrix = np.zeros((num_seats,num_seats))
    
    def assign_seat(self,guest_id,seat_pos):
        if validation.is_integer_at_least_n(seat_pos,0) and seat_pos < self.num_seats:
            self.seats[seat_pos] = guest_id
        else:
            raise InvalidInput(f"seat_pos ({seat_pos}) should be an integer between 0 and {self.num_seats-1} inclusive.")

    def compute_score(self,matrix,id_dict,param=1):
        """
        Computes a weighted average between Mean Scores and Min-Max Scores.
        Mean Scores are the average of all scores between connected pairs of guests sitting at the table.
        Min-Max Scores are the minimum of the maximum scores for each guest at the table.
        """
        if not validation.is_valid_matrix_id_dict(matrix, id_dict):
            raise InvalidInput("Invalid matrix and id_dict combination.")
        if not 0 <= param <= 1:
            raise InvalidInput("param should be between 0 and 1 inclusive.")
        if len([guest for guest in self.seats.values() if guest is not None]) < 2:
            warnings.warn("Less than 2 filled seats. Returning 0 score.")
            return 0.
        seating_order = [id_dict[self.seats[i]] if self.seats[i] is not None else None for i in range(self.num_seats)]
        filled_seats = np.where(np.array(seating_order) != None)[0]
        seating_order = [i for i in seating_order if i is not None]

        ordered_matrix = matrix[seating_order][:,seating_order]
        adjacency_matrix = self.adjacency_matrix[filled_seats][:,filled_seats]
       
        edge_scores = adjacency_matrix*ordered_matrix
        if np.sum(adjacency_matrix)==0:
            warnings.warn("There are no edges in the adjacency matrix that connect the filled seats. Returning 0 score.")
            return 0.
        else:
            mean_scores = np.sum(edge_scores)/np.sum(adjacency_matrix)
            max_scores = np.max(edge_scores, axis=1)
            min_max_scores = np.min(max_scores)

        return param*mean_scores + (1-param)*min_max_scores

class BanquetTable(Table):
    def __init__(self,num_side_seats,head_seat=False,foot_seat=False):
        if not isinstance(head_seat, bool) or not isinstance(foot_seat, bool):
            raise InvalidInput("head_seat and foot_seat should be boolean values.")
        if not head_seat and foot_seat:
            raise InvalidInput("If foot seat is present, head seat must also be present.")
        if head_seat and foot_seat and num_side_seats%2:
            raise InvalidInput("If both head and foot seats are present, num_side_seats must be even.")
        if not validation.is_integer_at_least_n(num_side_seats,2):
            raise InvalidInput(f"num_side_seats ({num_side_seats}) should be an integer greater than or equal to 2.")

        super().__init__(num_seats=num_side_seats+int(head_seat)+int(foot_seat))
        self.head_seat = {i:None for i in range(int(head_seat))}
        self.foot_seat = {i:None for i in range(int(foot_seat))}      
        self.side_seats = {i:None for i in range(num_side_seats)} #zig-zag numbering
        self.num_side_seats = num_side_seats
        self.compute_adjacency_matrix()
    
    def compute_adjacency_matrix(self):
        """
        Computes the adjacency matrix for the Banquet Table seating arrangement. Element (i,j) is 1 iff
        seat i and j are adjacent or directly opposite each other. Otherwise element (i,j) is 0.
        """
        num_side_seats = len(self.side_seats)
        adjacency_matrix = np.zeros((self.num_seats,self.num_seats))
        offset = 0

        #head seats to first two side seats
        if self.head_seat:
            adjacency_matrix[0,1] = 1
            adjacency_matrix[0,2] = 1
            offset = 1  

        #side seats to adjacent and opposite side seats
        for i in range(self.num_side_seats-2):
            i = i+offset
            adjacency_matrix[i,i+1] = (1+i-offset)%2 #1 only if we are at an even side seat
            adjacency_matrix[i,i+2] = 1

        #penulitmate side seat to last side seat
        i = self.num_side_seats-2+offset
        adjacency_matrix[i,i+1] = (1+self.num_side_seats)%2 #1 only if even number of side seats

        #foot seat to last two side seats
        if self.foot_seat:
            i = num_side_seats+offset
            adjacency_matrix[i,i-1] = 1
            adjacency_matrix[i,i-2] = 1
        
        self.adjacency_matrix = adjacency_matrix + adjacency_matrix.T 
            
        
    def assign_side_seat(self,guest_id,seat_pos):
        if validation.is_integer_at_least_n(seat_pos,0) and seat_pos < len(self.side_seats):
            self.side_seats[seat_pos] = guest_id
            self.seats[bool(self.head_seat)+seat_pos] = guest_id
        else:
            raise InvalidInput(f"seat_pos ({seat_pos}) should be an integer between 0 and {self.num_side_seats-1} inclusive.")
            
    def assign_head_seat(self,guest_id):
        if self.head_seat:
            self.head_seat[0] = guest_id
            self.seats[0] = guest_id
        else:
            raise TableError("No head seat available on this table.")

    def assign_foot_seat(self,guest_id):
        if self.foot_seat:
            self.foot_seat[0] = guest_id
            self.seats[self.num_seats-1] = guest_id
        else:
            raise TableError("No foot seat available on this table.")
    
    def __str__(self):
        return f"BanquetTable with {len(self.head_seat)} head seat(s), {len(self.foot_seat)} foot seat(s) and {len(self.side_seats)} side seats."