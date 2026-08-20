from pydantic import BaseModel, Field, model_validator, field_validator
from typing import Literal, List, Optional, Union
from typing_extensions import Annotated
from abc import ABC, abstractmethod
import numpy as np

class Guest(BaseModel):
    id: str | int = Field(..., description="Unique identifier for the guest")
    name: str = Field(..., description="Full name of the guest")
    relation_tags: List[str]

class Table(BaseModel, ABC):
    id: str | int = Field(..., description="Unique identifier for the table")
    type: Literal["banquet", "cabaret", "theatre"] = Field(..., description="Type of seating arrangement")
    num_seats: int = Field(..., description="Number of seats available at this table")

    @abstractmethod
    def adjacency(self):
        """Return an adjacency matrix showing the connectivity of seats on this table"""
        pass

class BanquetTable(Table):
    type: Literal["banquet"] = "banquet"
    head_seat: Optional[bool] = Field(False, description="If True, a seat is placed at the head of the table")
    foot_seat: Optional[bool] = Field(False, description="If True a seat is placed at the foot of the table")

    def adjacency(self,adj_score=1,opp_score=0.75,diag_opp_score=0.5):
        """
        Computes the adjacency matrix for the Banquet Table seating arrangement. Element (i,j) is 1 iff
        seat i and j are adjacent, directly opposite or diagonally opposite each other. Otherwise element (i,j) is 0.
        """
        num_side_seats = self.num_seats - int(self.head_seat) - int(self.foot_seat)
        adjacency_matrix = np.zeros((self.num_seats,self.num_seats))
        offset = int(self.head_seat)

        # head seat to the first row of side seats -- normally two (one on
        # each side), but there may only be one, or none, on a small table.
        if self.head_seat:
            for idx in range(offset, offset + min(2, num_side_seats)):
                adjacency_matrix[0,idx] = 1
            if num_side_seats == 0 and self.foot_seat:
                # head and foot are the table's only two seats
                adjacency_matrix[0,offset] = 1

        #side seats to adjacent and opposite side seats
        for i in range(num_side_seats-2):
            idx = i+offset
            if i%2 == 0:
                adjacency_matrix[idx,idx+1] = opp_score #directly opposite
                adjacency_matrix[idx,idx+2] = adj_score #adjacent
                # the "diagonal opposite" seat is the far seat of the *next*
                # row -- only wire it up if that next row is complete. With
                # an odd number of side seats, the final row has no left-hand
                # seat, so this would otherwise index past the end of the
                # matrix (see the dangling-seat handling below instead).
                if i+3 < num_side_seats:
                    adjacency_matrix[idx,idx+3] = diag_opp_score #diagonal opposite
            else:
                adjacency_matrix[idx,idx+1] = diag_opp_score #diagonal opposite
                adjacency_matrix[idx,idx+2] = adj_score #adjacent


        #penultimate side seat to last side seat
        if num_side_seats >= 2:
            idx = num_side_seats-2+offset
            if num_side_seats % 2 == 0:
                adjacency_matrix[idx,idx+1] = 1 #last row's own pair are directly opposite
            else:
                # odd number of side seats: the last seat has no partner in its
                # own row, so it has no "directly opposite" connection at all --
                # instead it's diagonally opposite the previous row's other-side
                # seat, mirroring the diagonal relationship every other row-pair
                # gets from the loop above.
                adjacency_matrix[idx,idx+1] = diag_opp_score

        # foot seat to the last row of side seats -- normally two, but may be
        # one or none on a small table (the head/foot-only case is handled above).
        if self.foot_seat:
            foot_idx = num_side_seats+offset
            for idx in range(foot_idx - min(2, num_side_seats), foot_idx):
                adjacency_matrix[foot_idx,idx] = 1

        return adjacency_matrix + adjacency_matrix.T
   
class CabaretTable(Table):
    type: Literal["cabaret"] = "cabaret"
    full_circle: Optional[bool] = Field(False, description="Are seats aranged all the around the table?")

    def adjacency(self):
        adjacency_matrix = np.zeros((self.num_seats,self.num_seats))
        rows = np.arange(self.num_seats - 1)
        cols = np.arange(1, self.num_seats)
        adjacency_matrix[rows, cols] = 1
        if self.full_circle:
            adjacency_matrix[self.num_seats-1,0] = 1
        
        return adjacency_matrix + adjacency_matrix.T
    
class TheatreSection(Table):
    type: Literal["theatre"] = "theatre"
    num_rows: int = Field(..., description="Number of rows.")

    @model_validator(mode='after')
    def check_divisibility(cls,model):
        if model.num_seats % model.num_rows != 0:
            raise ValueError(f"Number of rows must divide number of seats.")
        return model
    
    def adjacency(self):
        """
        Seats are numbered from left to right going down the rows.
        """
        adjacency_matrix = np.zeros((self.num_seats,self.num_seats))
        n = self.num_seats // self.num_rows # number of seats per row

        # down, right and (down and right) relations
        seats = np.array([i + row * n for row in range(self.num_rows - 1) for i in range(n-1)])
        seats_right = seats + 1
        seats_down = seats + n
        seats_down_right = seats + n + 1
        adjacency_matrix[seats, seats_right] = 1
        adjacency_matrix[seats, seats_down] = 1
        adjacency_matrix[seats, seats_down_right] = 1

        # (up and right) relations
        seats = np.array([i + row * n for row in range(1, self.num_rows) for i in range(n-1)])
        seats_up_right = seats - n + 1
        adjacency_matrix[seats, seats_up_right] = 1

        return adjacency_matrix + adjacency_matrix.T


TableType = Annotated[
    Union[BanquetTable, CabaretTable, TheatreSection], 
    Field(discriminator="type")
]

class Constraint(BaseModel):
    guest_a_id: str | int = Field(..., description="ID of the first guest")
    guest_b_id: str | int = Field(..., description="ID of the second guest")
    relationship: Literal["must_sit_together", "could_sit_together", "must_sit_apart"] = Field(
        ..., 
        description="Provides a hard or soft preference for two guest to sit together or a hard preference for them to sit apart"
    )

class SeatingRequest(BaseModel):
    guests: List[Guest]
    tables: List[TableType]
    constraints: List[Constraint]

class ConstraintViolation(BaseModel):
    guest_a: Guest
    guest_b: Guest

class SeatingResponse(BaseModel):
    table_assignments: dict[str | int, dict[int,Guest]]
    avg_score: float = Field(..., description="The score for this seating arrangement.")
    must_sit_together: dict[str, int]
    could_sit_together: dict[str,int]
    must_sit_apart: dict[str, int]
    must_sit_together_violations: List[ConstraintViolation] = Field(
        default_factory=list, description="Guest pairs that should sit together but don't."
    )
    must_sit_apart_violations: List[ConstraintViolation] = Field(
        default_factory=list, description="Guest pairs that should sit apart but don't."
    )