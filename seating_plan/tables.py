import numpy as np
import warnings

class BanquetTable:
    def __init__(self,num_side_seats,head_seat=False,foot_seat=False):
        if not head_seat and foot_seat:
            raise ValueError("If foot seat is present, head seat must also be present.")
        if head_seat and foot_seat and num_side_seats%2:
            raise ValueError("If both head and foot seats are present, num_side_seats must be even.")
        
        self.head_seat = {i:None for i in range(int(head_seat))}
        self.foot_seat = {i:None for i in range(int(foot_seat))}

        if self.is_non_neg_int(num_side_seats,'num_side_seats'):
            if num_side_seats < 2:
               warnings.warn(f"num_side_seats ({num_side_seats}) should be at least 2. Setting it to 2.")
               num_side_seats = 2
               
            self.side_seats = {i:None for i in range(num_side_seats)} #zig-zag numbering
                
        self.num_seats = num_side_seats+len(self.head_seat)+len(self.foot_seat)
        adjacency_matrix = np.zeros((self.num_seats,self.num_seats))
        offset = 0

        #head seats to first two side seats
        if self.head_seat:
            adjacency_matrix[0,1] = 1
            adjacency_matrix[0,2] = 1
            offset = 1  

        #side seats to adjacent and opposite side seats
        for i in range(num_side_seats-2):
            i = i+offset
            adjacency_matrix[i,i+1] = (1+i-offset)%2 #1 only if we are at an even side seat
            adjacency_matrix[i,i+2] = 1

        #last two side seats
        i = num_side_seats-2+offset
        adjacency_matrix[i,i+1] = (1+num_side_seats)%2 #1 only if even number of side seats

        #foot seat to last two side seats
        if self.foot_seat:
            i = num_side_seats+offset
            adjacency_matrix[i,i-1] = 1
            adjacency_matrix[i,i-2] = 1
        
        self.adjacency_matrix = adjacency_matrix + adjacency_matrix.T 

    def is_non_neg_int(self,num,variable:str):
        try:
            assert type(num) == int
            assert num >= 0
            return True
        except:
            raise ValueError(f"Expected a non-negative integer for {variable} but got {num}.")
            
        
    def assign_side_seat(self,guest_id,seat_pos):
        if self.is_non_neg_int(seat_pos,'pos'):
            num_side_seats = self.num_seats - len(self.head_seat) - len(self.foot_seat)
            if seat_pos < num_side_seats :
                self.side_seats[seat_pos] = guest_id
            else:
                raise ValueError(f"seat_pos ({seat_pos}) should be between 0 and {num_side_seats-1} inclusive.")
            
    def assign_head_seat(self,guest_id):
        if self.head_seat:
            self.head_seat[0] = guest_id
        else:
            raise ValueError("No head seat available to assign.")

    def assign_foot_seat(self,guest_id):
        if self.foot_seat:
            self.foot_seat[0] = guest_id
        else:
            raise ValueError("No foot seat available to assign.")
        
    def compute_score(self,matrix,id_dict):
        "Root-Mean_Square of the edges (given by matrix) in the arrangement"
        seating_order = [id_dict[self.head_seat[i]] if self.head_seat[i] is not None else None for i in self.head_seat.keys()]
        seating_order += [id_dict[self.side_seats[i]] if self.side_seats[i] is not None else None for i in self.side_seats.keys()]
        seating_order += [id_dict[self.foot_seat[i]] if self.foot_seat[i] is not None else None for i in self.foot_seat.keys()]
        filled_seats = np.where(np.array(seating_order) != None)[0]
        seating_order = [i for i in seating_order if i is not None]

        ordered_matrix = matrix[seating_order][:,seating_order]
        adjacency_matrix = self.adjacency_matrix[filled_seats][:,filled_seats]
       
        edge_scores = np.matmul(adjacency_matrix,ordered_matrix**2)
        if adjacency_matrix.shape[0] == 1:
            edge_scores = edge_scores[0,0]
        elif np.sum(adjacency_matrix)==0:
            edge_scores = 0.
        else:
            edge_scores = np.sqrt(2*np.sum(edge_scores)/np.sum(adjacency_matrix)) #root-mean-square

        return edge_scores
    
    def get_seating_arrangement(self):
        """
        Returns a dictionary with the seating arrangement.
        Keys are seat positions and values are guest IDs.
        """
        arrangement = {
            'head_seat': self.head_seat,
            'side_seats': self.side_seats,
            'foot_seat': self.foot_seat
        }
        return arrangement
    def __str__(self):
        return f"BanquetTable with {len(self.head_seat)} head seat(s), {len(self.foot_seat)} foot seat(s) and {len(self.side_seats)} side seats."