import numpy as np
import math
from scipy.linalg import block_diag
from scipy.optimize import linear_sum_assignment
import torch
import torch.nn.functional as F
import torch.nn as nn
from typing import List, Literal
from collections import defaultdict
from abc import ABC, abstractmethod
from app.schema import Guest, Constraint, Table

def log(msg:str, verbose : bool = False):
    if verbose:
        print(msg)

class Solver(ABC):
    def __init__(self, guest_list: List[Guest], table_list: List[Table], constraints: List[Constraint] = []):
        super().__init__()
        self.id_dict = {guest.id: idx for idx, guest in enumerate(guest_list)}
        self.n_guests = len(guest_list)
        self.n_seats = sum((table.num_seats for table in table_list))

    def _get_relation_matrix(self, guest_list : List[Guest]) -> np.ndarray:
        cliques = defaultdict(set)

        for guest in guest_list:
            for tag in guest.relation_tags:
                cliques[tag].add(guest.id)

        n_guests = len(guest_list)
        relation_matrix = np.zeros((n_guests, n_guests))

        for i in range(n_guests):
            for j in range(i + 1, n_guests):
                guest_i = guest_list[i]
                guest_j = guest_list[j]
                common_cliques = set(guest_i.relation_tags).intersection(set(guest_j.relation_tags))
                similarity_score = 0
                for clq in common_cliques:
                    similarity_score += 1/len(cliques[clq])
                        
            
                relation_matrix[i][j] = similarity_score
                relation_matrix[j][i] = similarity_score

        return relation_matrix

    def _get_constraint_matrix(self, constraints : List[Constraint]) -> np.ndarray:
        constraint_matrix = np.zeros((self.n_guests, self.n_guests))

        for con in constraints:
            idx1 = self.id_dict[con.guest_a_id]
            idx2 = self.id_dict[con.guest_b_id]
            if con.relationship == "must_sit_together":
                constraint_matrix[idx1,idx2] = 1
                constraint_matrix[idx2,idx1] = 1
            elif con.relationship == "could_sit_together":
                constraint_matrix[idx1,idx2] = 0.5
                constraint_matrix[idx2,idx1] = 0.5
            else:
                constraint_matrix[idx1,idx2] = -1
                constraint_matrix[idx2,idx1] = -1

        return constraint_matrix

    def _get_table_adjacency(self, table_list : List[Table]) -> np.ndarray:
        matrices = []
        for table in table_list:
            matrices.append(table.adjacency())

        return block_diag(*matrices)
        
def regularised_surjective_init(n_low, n_high, noise_std=0.1):   
    # 1. Start with a baseline of low-variance random noise
    logits = torch.randn(n_low, n_high) * noise_std
    rand_indices = torch.randperm(n_high)

    targets = torch.zeros(n_low, dtype=torch.long)
    targets[:min(n_low,n_high)] = rand_indices[:min(n_low,n_high)]
    
    # Fill any remaining rows with random column assignments
    if n_low > n_high:
        targets[n_high:] = torch.randint(0, n_high, (n_low - n_high,))
    
    # Shuffle row assignments so the guaranteed coverage isn't locked to the top rows
    targets = targets[torch.randperm(n_low)]

    min_margin = math.log(max(1, n_high - 1)) 

    margin = min_margin + (5 * noise_std) + 0.1
    
    # 4. Inject the margin into the targeted positions
    logits[torch.arange(n_low), targets] += margin
    
    return logits         
            

   

class GradSolver(Solver, nn.Module):
    def __init__(self, guest_list: List[Guest], table_list: List[Table], constraints: List[Constraint] = [], init_type : Literal['surjective','uniform'] = 'surjective', rel_weight=1, con_weight=10):
        super().__init__(guest_list, table_list, constraints)
        self.rel_weight = rel_weight
        self.con_weight = con_weight

        self.relation_matrix = torch.from_numpy(self._get_relation_matrix(guest_list)).float()
        self.constraint_matrix = torch.from_numpy(self._get_constraint_matrix(constraints)).float()
        self.table_adjacency = torch.from_numpy(self._get_table_adjacency(table_list)).float()

        n = max(self.n_guests,self.n_seats)
        if n > self.n_guests:
            # dummy guests
            n_extra = n - self.n_guests
            self.constraint_matrix = F.pad(self.constraint_matrix,(0,n_extra,0,n_extra),mode='constant')
            self.relation_matrix = F.pad(self.relation_matrix,(0,n_extra,0,n_extra),mode='constant')
        elif n > self.n_seats:
            # dummy seats
            n_extra = n - self.n_seats
            self.table_adjacency = F.pad(self.table_adjacency,(0,n_extra,0,n_extra),mode='constant')


        if init_type == 'surjective':
            self.guest_logits = nn.Parameter(regularised_surjective_init(n, n))
            self.seat_logits = nn.Parameter(regularised_surjective_init(n, n))
        elif init_type == 'uniform':
            self.guest_logits = nn.Parameter(torch.zeros(n, n))
            self.seat_logits = nn.Parameter(torch.zeros(n, n))

    def get_soft_assignment(self, temp=1):
        T_guest = F.softmax(self.guest_logits/temp, dim=1) # probability ditribution over seats per guest
        T_seats = F.softmax(self.seat_logits/temp, dim=1) # probability distribution over guests per seat

        return T_guest, T_seats
        

    def forward(self):
        T_guest, T_seats = self.get_soft_assignment()
        guest_adjacency = self.rel_weight * self.relation_matrix + self.con_weight * self.constraint_matrix

        # for T_guest
        assignment = T_guest.t() # (n_seats, n_guests)
        score_matrix = assignment @ guest_adjacency @ assignment.t()
        edge_scores = score_matrix * self.table_adjacency
        
        guest_score = torch.sum(edge_scores)

        # for T_seats
        assignment = T_seats # (n_seats, n_guests)
        score_matrix = assignment @ guest_adjacency @ assignment.t()
        edge_scores = score_matrix * self.table_adjacency
        
        seat_score = torch.sum(edge_scores)

        # consistency loss: T_guest[i, j] and T_seats[j, i] both estimate
        # "probability guest i sits at seat j", so they should agree. Cross-entropy
        # of one against the other (held fixed as a target) pulls them together,
        # since -sum_j p_j log q_j is minimized over the simplex exactly when q is
        # proportional to p -- this holds even though T_seats.t()'s rows (and
        # T_guest.t()'s rows) don't themselves sum to 1, unlike the softmax rows
        # they're being compared against.
        eps = 1e-8
        ce_loss = -(T_seats.t().detach() * torch.log(T_guest + eps)).sum(dim=1).mean()
        ce_loss += -(T_guest.t().detach() * torch.log(T_seats + eps)).sum(dim=1).mean()
        
        return guest_score, seat_score, ce_loss

    def train(self, num_epochs=1000, lambda_guest=1, lambda_seat=1, lambda_ce=50, keep_history=True, verbose=True):
        optimiser = torch.optim.Adam(self.parameters(),lr=0.01)
        history = {'guest_score':[], 'seat_score':[], 'cross_entropy':[], 'T_guest':[], 'T_seats':[]}
        num_edges = self.table_adjacency.sum()
        for epoch in range(num_epochs):
            optimiser.zero_grad()
            guest_score, seat_score, ce_loss = self.forward()
            loss = -(lambda_guest * guest_score + lambda_seat * seat_score)/(num_edges + 1e-8) + lambda_ce * ce_loss
            loss.backward()
            optimiser.step()

            if keep_history:
                history['guest_score'].append(guest_score.item())
                history['seat_score'].append(seat_score.item())
                history['cross_entropy'].append(ce_loss.item())
                history['T_guest'].append(self.get_soft_assignment()[0].cpu().detach().numpy())
                history['T_seats'].append(self.get_soft_assignment()[1].cpu().detach().numpy())
            if epoch%100 == 0 or epoch == num_epochs -1:
                log(f"(Epoch {epoch+1}/{num_epochs}) Guest Score: {guest_score/num_edges:.4f}, Seat Score: {seat_score/num_edges:.4f}, CE: {ce_loss:.4f}",verbose=verbose)

        return history

    def extract_hard_seating(self):
        """
        Maps real guests to real seats, via the Hungarian algorithm on the soft assignment probs.
        Also returns average score and constraint satisfaction rate.
        """

        #Convert to NumPy
        relation_matrix = self.relation_matrix.cpu().detach().numpy()
        constraint_matrix = self.constraint_matrix.cpu().detach().numpy()
        table_adjacency = self.table_adjacency.cpu().detach().numpy()
        T_guest = self.get_soft_assignment()[0].cpu().detach().numpy()

        #Hungarian algorithm to match real guests to real seats
        T_real = T_guest[:self.n_guests, :self.n_seats]
        row_ind, col_ind = linear_sum_assignment(-T_real)
        assignment = dict(zip(row_ind, col_ind))

        guest_to_seat = np.zeros(self.n_guests, dtype=int)
        guest_to_seat[row_ind] = col_ind
        T_hard = np.zeros((self.n_guests,self.n_seats))
        T_hard[row_ind,col_ind] = 1

        #Compute average score of assignment
        guest_adjacency = self.rel_weight * relation_matrix + self.con_weight * constraint_matrix
        score_matrix = T_hard.T @ guest_adjacency @ T_hard
        table_adj_sum = np.sum(table_adjacency)
        avg_score = 2*np.sum(score_matrix * table_adjacency) / table_adj_sum if table_adj_sum > 0 else 0
 
        result = {'assignment':assignment, 'avg_score':avg_score}
        
        
        constraint_name = ['must_sit_together','could_sit_together','must_sit_apart']
        constraint_weight = [1,0.5,-1]
        constraint_matrix_upper = np.triu(constraint_matrix)
        for name, weight in zip(constraint_name,constraint_weight):
            guest_a, guest_b = np.where(constraint_matrix_upper == weight)
            seat_a = guest_to_seat[guest_a]
            seat_b = guest_to_seat[guest_b]

            satisfied = np.sum(table_adjacency[seat_a,seat_b])
            count = len(guest_a)
            result[name] = (satisfied,count)


        return result




if __name__ == "__main__":
    from .schema import BanquetTable
    #Test
    guest_list = [Guest(id=0,name="Alex",relation_tags=['dyter']), Guest(id=1,name="Danny",relation_tags=["alty_boys","htb"]), Guest(id=2,name="Ezra",relation_tags=["htb"])]
    table_list = [BanquetTable(id='one',type='banquet')]
    constraints = [Constraint()]

    solver = GradSolver(guest_list=guest_list, table_list=table_list, constraints=constraints)
    solver.train(lambda_guest=1,lambda_seat=1, lambda_ce=1)