import numpy as np
import math
from scipy.linalg import block_diag
from scipy.optimize import linear_sum_assignment
import torch

# Small containers (e.g. Railway's default plan) often report more CPUs than
# are actually allocated to them. Torch then spawns a thread per reported CPU
# and those threads spend most of their time contending for a much smaller
# real CPU quota, rather than doing useful work -- for a problem this small,
# single-threaded is both simpler and dramatically faster in that environment.
torch.set_num_threads(1)

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
        self._relation_matrix = self._get_relation_matrix(guest_list)
        self._constraint_matrix = self._get_constraint_matrix(constraints)
        self._table_adjacency = self._get_table_adjacency(table_list)

    def _get_relation_matrix(self, guest_list : List[Guest]) -> np.ndarray:
        # Tags are matched case-insensitively (e.g. "College" and "college"
        # typed for different guests still count as the same group) --
        # normalized locally, without mutating the guests' actual stored tags.
        normalized_tags = [
            {tag.strip().lower() for tag in guest.relation_tags}
            for guest in guest_list
        ]

        cliques = defaultdict(set)
        for guest, tags in zip(guest_list, normalized_tags):
            for tag in tags:
                cliques[tag].add(guest.id)

        n_guests = len(guest_list)
        relation_matrix = np.zeros((n_guests, n_guests))

        for i in range(n_guests):
            for j in range(i + 1, n_guests):
                common_cliques = normalized_tags[i].intersection(normalized_tags[j])
                similarity_score = 0
                for clq in common_cliques:
                    clique_size = len(cliques[clq])
                    if clique_size > 1:
                        similarity_score += 1/(clique_size - 1)


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

    def _summarize_assignment(self, guest_to_seat: np.ndarray) -> dict:
        """
        Turns a guest->seat array into the standard result dict (assignment, avg_score, constraint satisfaction).
        """
        guest_to_seat = guest_to_seat[:self.n_guests]
        T_hard = np.zeros((self.n_guests, self.n_seats))
        T_hard[np.arange(self.n_guests), guest_to_seat] = 1

        relation_score = T_hard.T @ self._relation_matrix @ T_hard
        relation_score = np.sum(relation_score * self._table_adjacency) / self.n_guests if self.n_guests > 0 else 0

        constraint_score = np.sum((T_hard.T @ self._constraint_matrix @ T_hard) * self._table_adjacency)

        result = {'assignment': {g: int(s) for g, s in enumerate(guest_to_seat) if g < self.n_guests and s < self.n_seats},
                  'relation_score': relation_score, 'constraint_score':constraint_score}

        constraint_name = ['must_sit_together', 'could_sit_together', 'must_sit_apart']
        constraint_weight = [1, 0.5, -1]
        constraint_matrix_upper = np.triu(self._constraint_matrix)
        for name, weight in zip(constraint_name, constraint_weight):
            guest_a, guest_b = np.where(constraint_matrix_upper == weight)
            seat_a = guest_to_seat[guest_a]
            seat_b = guest_to_seat[guest_b]
            adjacency = self._table_adjacency[seat_a, seat_b]

            # must_sit_together means genuinely adjacent seats (adjacency == 1),
            # not just "somewhere on the same table" -- the decayed weight given
            # to every other same-table pair doesn't count. could_sit_together is
            # a softer nudge, so any same-table connection satisfies it.
            # must_sit_apart is the opposite of "connected at all": since every
            # same-table pair now has nonzero adjacency, it's satisfied only when
            # the pair is on different tables.
            if name == 'must_sit_together':
                satisfied_mask = (adjacency == 1)
            elif name == 'must_sit_apart':
                satisfied_mask = (adjacency == 0)
            else:
                satisfied_mask = (adjacency > 0)
            result[name] = {"satisfied": int(np.sum(satisfied_mask)), "total": len(guest_a)}

            if name != 'could_sit_together':
                violated_mask = ~satisfied_mask
                result[f'{name}_violations'] = list(zip(
                    guest_a[violated_mask].tolist(), guest_b[violated_mask].tolist()
                ))

        return result

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

        self.constraint_matrix = torch.from_numpy(self._constraint_matrix).float()
        self.relation_matrix = torch.from_numpy(self._relation_matrix).float()
        self.table_adjacency = torch.from_numpy(self._table_adjacency).float()

        n = max(self.n_guests,self.n_seats)
        self.n = n
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

        eps = 1e-8
        ce_loss = -(T_seats.t().detach() * torch.log(T_guest + eps)).sum(dim=1).mean()
        ce_loss += -(T_guest.t().detach() * torch.log(T_seats + eps)).sum(dim=1).mean()

        one_hot_loss = (1 - (T_guest**2).sum(dim=1)).mean() + (1 - (T_seats**2).sum(dim=1)).mean()
        
        return guest_score, seat_score, ce_loss, one_hot_loss

    def train(self, num_epochs=1000, lambda_guest=1, lambda_seat=1, lambda_ce=50, lambda_one_hot=50, keep_history=True, verbose=True):
        optimiser = torch.optim.Adam(self.parameters(),lr=0.01)
        history = {'guest_score':[], 'seat_score':[], 'cross_entropy':[], 'one_hot':[], 'T_guest':[], 'T_seats':[]}
        num_edges = self.table_adjacency.sum()
        for epoch in range(num_epochs):
            optimiser.zero_grad()
            guest_score, seat_score, ce_loss, one_hot_loss = self.forward()
            l_one_hot = 0 if epoch < int(0.8 * num_epochs) else lambda_one_hot
            loss = -(lambda_guest * guest_score + lambda_seat * seat_score)/(num_edges + 1e-8) + lambda_ce * ce_loss  + l_one_hot * one_hot_loss
            loss.backward()
            optimiser.step()

            if keep_history:
                history['guest_score'].append(guest_score.item()/self.n_guests)
                history['seat_score'].append(seat_score.item()/self.n_guests)
                history['cross_entropy'].append(ce_loss.item())
                history['one_hot'].append(one_hot_loss.item())
                history['T_guest'].append(self.get_soft_assignment()[0].cpu().detach().numpy())
                history['T_seats'].append(self.get_soft_assignment()[1].cpu().detach().numpy())
            if epoch%100 == 0 or epoch == num_epochs -1:
                log(f"(Epoch {epoch+1}/{num_epochs}) Guest Score: {guest_score/self.n_guests:.4f}, Seat Score: {seat_score/self.n_guests:.4f}, CE: {ce_loss:.4f}, One Hot: {one_hot_loss:.4f}",verbose=verbose)

        return history

    def extract_hard_seating(self):
        """
        Maps real guests to real seats, via the Hungarian algorithm on the soft assignment probs.
        Also returns average score and constraint satisfaction rate.
        """
        T_guest = self.get_soft_assignment()[0].cpu().detach().numpy()

        #Hungarian algorithm to match real guests to real seats
        T_real = T_guest[:self.n_guests, :self.n_seats]
        row_ind, col_ind = linear_sum_assignment(-T_real)
        guest_to_seat = np.zeros(self.n, dtype=int)
        guest_to_seat[row_ind] = col_ind

        dummy_guests = np.setdiff1d(np.arange(self.n), row_ind)
        empty_seats = np.setdiff1d(np.arange(self.n), col_ind)
        guest_to_seat[dummy_guests] = empty_seats

        return guest_to_seat

    def decimate(self, lambda_guest=1, lambda_seat=1, lambda_ce=50, lambda_one_hot=0,
                 initial_epochs=300, settle_epochs=30, batch_size=1, keep_history=True, verbose=True):
        """
        Iteratively pin the most-confident remaining guest(s) to their
        highest-probability seat, mask those seats out for everyone else, and
        continue training the rest ("settle") before pinning the next batch.

        Produces a valid discrete assignment by construction -- a seat is
        masked out for every other guest the moment it's taken, so there's no
        Hungarian-extraction step needed afterwards, and no way for the mean-
        field marginals to be mis-decoded into a double-booked seat.

        batch_size=1 (pin one guest per round, re-settling after each) gives
        the most adaptive results, but costs O(n) settle-rounds -- for large
        guest lists, pinning several of the most-confident guests per round
        trades a little quality for a roughly batch_size-times speedup.

        Mirrors train()'s interface: returns a history dict with the same
        keys (populated across the initial settle phase and every subsequent
        settle round, as one continuous timeline), and leaves the model's own
        logits in their final state -- here, the fully pinned one-hot
        assignment -- so extract_hard_seating() / _summarize_assignment()
        work unchanged afterwards, exactly as they do after train().
        """
        n = self.guest_logits.shape[0]
        optimiser = torch.optim.Adam(self.parameters(), lr=0.01)
        guest_adjacency = self.rel_weight * self.relation_matrix + self.con_weight * self.constraint_matrix
        num_edges = self.table_adjacency.sum()
        pinned: dict[int, int] = {}
        NEG = -1e4

        history = {'guest_score': [], 'seat_score': [], 'cross_entropy': [], 'one_hot': [], 'T_guest': [], 'T_seats': []}
        epoch = 0

        def masked_soft_assignment():
            g_logits = self.guest_logits.clone()
            s_logits = self.seat_logits.clone()
            if pinned:
                seats = list(pinned.values())
                gs = list(pinned.keys())
                g_logits[:, seats] = NEG
                s_logits[:, gs] = NEG
                for g, s in pinned.items():
                    g_logits[g, :] = NEG
                    g_logits[g, s] = 0.0
                    s_logits[s, :] = NEG
                    s_logits[s, g] = 0.0
            return F.softmax(g_logits, dim=1), F.softmax(s_logits, dim=1)

        def settle(num_epochs):
            nonlocal epoch
            for _ in range(num_epochs):
                optimiser.zero_grad()
                T_guest, T_seats = masked_soft_assignment()
                assignment = T_guest.t()
                guest_score = torch.sum((assignment @ guest_adjacency @ assignment.t()) * self.table_adjacency)
                assignment = T_seats
                seat_score = torch.sum((assignment @ guest_adjacency @ assignment.t()) * self.table_adjacency)
                eps = 1e-8
                ce = -(T_seats.t().detach() * torch.log(T_guest + eps)).sum(dim=1).mean()
                ce += -(T_guest.t().detach() * torch.log(T_seats + eps)).sum(dim=1).mean()
                one_hot = (1 - (T_guest ** 2).sum(dim=1)).mean()
                loss = (-(lambda_guest * guest_score + lambda_seat * seat_score) / (num_edges + 1e-8)
                        + lambda_ce * ce + lambda_one_hot * one_hot)
                loss.backward()
                optimiser.step()

                if keep_history:
                    history['guest_score'].append(guest_score.item()/self.n_guests)
                    history['seat_score'].append(seat_score.item()/self.n_guests)
                    history['cross_entropy'].append(ce.item())
                    history['one_hot'].append(one_hot.item())
                    history['T_guest'].append(T_guest.cpu().detach().numpy())
                    history['T_seats'].append(T_seats.cpu().detach().numpy())
                if epoch % 100 == 0:
                    log(f"(Epoch {epoch+1}) Guest Score: {guest_score/num_edges:.4f}, Seat Score: {seat_score/num_edges:.4f}, "
                        f"CE: {ce:.4f}, One Hot: {one_hot:.4f}, pinned {len(pinned)}/{n}", verbose=verbose)
                epoch += 1

        settle(initial_epochs)
        while len(pinned) < n:
            T_guest, _ = masked_soft_assignment()
            free = [g for g in range(n) if g not in pinned]
            free.sort(key=lambda g: T_guest[g].max().item(), reverse=True)

            # pin the top batch_size most-confident free guests, greedily
            # resolving any within-batch seat collisions by confidence order
            # (all candidates were ranked against the same pre-batch snapshot,
            # so two could nominally want the same seat)
            claimed_this_batch = set()
            for g in free[:batch_size]:
                seat_prefs = torch.argsort(T_guest[g], descending=True)
                s_star = next(int(s) for s in seat_prefs if int(s) not in claimed_this_batch)
                pinned[g] = s_star
                claimed_this_batch.add(s_star)

            settle(settle_epochs)
            log(f"decimation: pinned {len(pinned)}/{n}", verbose=verbose)

        with torch.no_grad():
            for g, s in pinned.items():
                self.guest_logits[g, :] = NEG
                self.guest_logits[g, s] = 0.0
                self.seat_logits[s, :] = NEG
                self.seat_logits[s, g] = 0.0

        return history


NEIGHBOR_MAX_HOP = 3
# Every real Table.adjacency() decays roughly by half per "hop" (see
# schema.py), and is now a COMPLETE graph -- every seat weakly connected to
# every other -- rather than the small fixed-degree graphs this solver was
# originally designed against. A seat only counts as a neighbour if its
# weight is still within NEIGHBOR_MAX_HOP decay-halvings of that seat's own
# strongest connection, which bounds neighbour-list size to a small constant
# regardless of table size -- restoring the O(seat degree) scaling below --
# at the cost of _swap_delta ignoring genuinely negligible contributions from
# very distant seats. This only affects which candidate swaps the hill-climb
# *considers*; score() and the final relation_score/constraint_score always
# use the full, un-thresholded adjacency exactly as given. See
# backend/scripts/FINDINGS.md for the measured wall-clock impact (a single
# 120-seat banquet table went from 30s to a fraction of a second).


class LocalSearchSolver(Solver):
    """
    Pure discrete local search: hill-climb a guest<->seat assignment via
    pairwise swaps, evaluating each candidate swap by its score *delta*
    rather than rescoring the whole arrangement from scratch. A swap between
    seats p and q only changes score terms touching p or q, so the delta only
    needs to sum over p and q's actual table-adjacency neighbors -- which,
    for any real table layout, is a small bounded number regardless of how
    many guests/seats there are in total (see NEIGHBOR_MAX_HOP). That's what
    makes this scale: each candidate-swap check costs O(seat degree), not
    O(n) or O(n^3).

    Usable standalone (random restart + hill-climb, a legitimate simple
    baseline) via solve(), or as a refinement pass on top of another solver's
    output via refine().
    """

    def __init__(self, guest_list: List[Guest], table_list: List[Table], constraints: List[Constraint] = [], rel_weight=1, con_weight=10):
        super().__init__(guest_list, table_list, constraints)
        self.rel_weight = rel_weight
        self.con_weight = con_weight

        relation_matrix = self._get_relation_matrix(guest_list)
        constraint_matrix = self._get_constraint_matrix(constraints)
        table_adjacency = self._get_table_adjacency(table_list)
        guest_adjacency = rel_weight * relation_matrix + con_weight * constraint_matrix

        n = max(self.n_guests, self.n_seats)
        if n > self.n_guests:
            padded = np.zeros((n, n))
            padded[:self.n_guests, :self.n_guests] = guest_adjacency # real guests to real guests
            padded[self.n_guests:, :self.n_guests] = -1e-6 # fake guests to real guests
            padded[:self.n_guests, self.n_guests:] = -1e-6 # real guests to fake guests
            guest_adjacency = padded
        if n > self.n_seats:
            padded = np.zeros((n, n))
            padded[:self.n_seats, :self.n_seats] = table_adjacency
            table_adjacency = padded

        self.n = n
        self.guest_adjacency = guest_adjacency
        self.table_adjacency = table_adjacency
        row_max = table_adjacency.max(axis=1, keepdims=True)
        neighbor_threshold = row_max * (2.0 ** -NEIGHBOR_MAX_HOP)
        self.neighbors = [np.nonzero(table_adjacency[i] > neighbor_threshold[i, 0])[0] for i in range(n)]

    def score(self, seat_to_guest: np.ndarray) -> float:
        P = np.zeros((self.n, self.n))
        P[np.arange(self.n), seat_to_guest] = 1
        return np.sum((P @ self.guest_adjacency @ P.T) * self.table_adjacency)

    def _swap_delta(self, seat_to_guest: np.ndarray, s1: int, s2: int) -> float:
        g1, g2 = seat_to_guest[s1], seat_to_guest[s2]
        G, A = self.guest_adjacency, self.table_adjacency
        total = 0.0
        for k in self.neighbors[s1]:
            if k == s2:
                continue
            gk = seat_to_guest[k]
            total += A[s1, k] * (G[g2, gk] - G[g1, gk])
        for k in self.neighbors[s2]:
            if k == s1:
                continue
            gk = seat_to_guest[k]
            total += A[s2, k] * (G[g1, gk] - G[g2, gk])
        return total

    def refine(self, seat_to_guest: np.ndarray) -> np.ndarray:
        """Hill-climb from a given seat->guest assignment to a swap-local optimum."""
        seat_to_guest = np.array(seat_to_guest, dtype=int).copy()
        improved = True
        while improved:
            improved = False
            for s1 in range(self.n):
                for s2 in range(s1 + 1, self.n):
                    if self._swap_delta(seat_to_guest, s1, s2) > 1e-9:
                        seat_to_guest[s1], seat_to_guest[s2] = seat_to_guest[s2], seat_to_guest[s1]
                        improved = True
        return seat_to_guest

    def refine_shuffled(self, seat_to_guest: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        """Same hill-climb as refine(), but the (s1, s2) scan order is
        reshuffled at the start of every full pass instead of always being
        range(n) x range(n). A first-improvement hill-climb is path-dependent
        -- from a starting point that isn't already a local optimum, a
        different scan order can converge to a different (better or worse)
        local optimum. Once a state IS a local optimum, no scan order can find
        an improving swap that isn't there, so this only matters as a way to
        seed *additional attempts* from a not-yet-converged starting point,
        never as a way to improve an already-refine()'d result."""
        seat_to_guest = np.array(seat_to_guest, dtype=int).copy()
        pairs = [(s1, s2) for s1 in range(self.n) for s2 in range(s1 + 1, self.n)]
        improved = True
        while improved:
            improved = False
            rng.shuffle(pairs)
            for s1, s2 in pairs:
                if self._swap_delta(seat_to_guest, s1, s2) > 1e-9:
                    seat_to_guest[s1], seat_to_guest[s2] = seat_to_guest[s2], seat_to_guest[s1]
                    improved = True
        return seat_to_guest

    def random_assignment(self, seed=None) -> np.ndarray:
        rng = np.random.default_rng(seed)
        return rng.permutation(self.n)

    def solve(self, initial: np.ndarray = None, seed=None, num_restarts: int = 1):
        """
        Refine `initial` if given (single pass). Otherwise run `num_restarts`
        random restarts and keep the best. Returns (guest_of_seat, score).
        """
        if initial is not None:
            seat_to_guest = self.refine(initial)
            guest_to_seat = np.argsort(seat_to_guest)
            return guest_to_seat

        best_assignment, best_score = None, -np.inf
        for i in range(num_restarts):
            start = self.random_assignment(seed=None if seed is None else seed + i)
            candidate = self.refine(start)
            candidate_score = self.score(candidate)
            if candidate_score > best_score:
                best_assignment, best_score = candidate, candidate_score

        guest_to_seat = np.argsort(best_assignment)
        return guest_to_seat


if __name__ == "__main__":
    from .schema import BanquetTable
    #Test
    guest_list = [Guest(id=0,name="Alex",relation_tags=['dyter']), Guest(id=1,name="Danny",relation_tags=["alty_boys","htb"]), Guest(id=2,name="Ezra",relation_tags=["htb"])]
    table_list = [BanquetTable(id='one',type='banquet')]
    constraints = [Constraint()]

    solver = GradSolver(guest_list=guest_list, table_list=table_list, constraints=constraints)
    solver.train(lambda_guest=1,lambda_seat=1, lambda_ce=1)