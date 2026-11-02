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

    def adjacency(self, adj_score=1, opp_score=0.75, diag_opp_score=0.5):
        """
        Computes the weighted adjacency matrix for the Banquet Table seating arrangement.
        Row distance dy = 0 represents directly opposite seats in the same row.
        Row distance dy >= 1 represents steps down the length of the table.
        """
        num_side_seats = self.num_seats - int(self.head_seat) - int(self.foot_seat)
        adjacency_matrix = np.zeros((self.num_seats, self.num_seats))
        offset = int(self.head_seat)

        total_rows = (num_side_seats + 1) // 2

        # 1. Directly opposite seats in the same row (dy = 0)
        num_full_pairs = num_side_seats // 2
        if num_full_pairs > 0:
            even_same_row = offset + 2 * np.arange(num_full_pairs)
            adjacency_matrix[even_same_row, even_same_row + 1] = opp_score

        # 2. Side seats propagation across row distances (dy >= 1)
        for dy in range(1, total_rows):
            # Same-side seats (Left-to-Left and Right-to-Right)
            seats_same = offset + np.arange(num_side_seats - 2 * dy)
            adjacency_matrix[seats_same, seats_same + 2 * dy] = adj_score * (2 ** (1 - dy))

            # Cross-side diagonal seats (Left-to-Right)
            left_seats = offset + 2 * np.arange((num_side_seats - (2 * dy + 1)) // 2 + 1)
            target_right = left_seats + (2 * dy + 1)
            valid_lr = target_right < (offset + num_side_seats)
            adjacency_matrix[left_seats[valid_lr], target_right[valid_lr]] = opp_score * (2 ** (-dy))

            # Cross-side diagonal seats (Right-to-Left)
            right_seats = offset + 2 * np.arange((num_side_seats - 2 * dy) // 2) + 1
            target_left = right_seats + (2 * dy - 1)
            valid_rl = target_left < (offset + num_side_seats)
            adjacency_matrix[right_seats[valid_rl], target_left[valid_rl]] = opp_score * (2 ** (-dy))

        # 3. Head seat connections
        if self.head_seat:
            for dy in range(total_rows):
                weight = adj_score * (2 ** (-dy))
                left_idx = offset + 2 * dy
                right_idx = offset + 2 * dy + 1
                
                if left_idx < offset + num_side_seats:
                    adjacency_matrix[0, left_idx] = weight
                if right_idx < offset + num_side_seats:
                    adjacency_matrix[0, right_idx] = weight

        # 4. Foot seat connections
        if self.foot_seat:
            foot_idx = self.num_seats - 1
            for dy in range(total_rows):
                weight = adj_score * (2 ** (-dy))
                # Work backwards from the last row
                row_idx = total_rows - 1 - dy
                left_idx = offset + 2 * row_idx
                right_idx = offset + 2 * row_idx + 1

                if left_idx < offset + num_side_seats:
                    adjacency_matrix[left_idx, foot_idx] = weight
                if right_idx < offset + num_side_seats:
                    adjacency_matrix[right_idx, foot_idx] = weight

            if self.head_seat:
                adjacency_matrix[0, foot_idx] = adj_score * (2 ** (-total_rows))

        return adjacency_matrix + adjacency_matrix.T
   
class CabaretTable(Table):
    type: Literal["cabaret"] = "cabaret"
    full_circle: Optional[bool] = Field(False, description="Are seats aranged all the around the table?")

    def adjacency(self):
        adjacency_matrix = np.zeros((self.num_seats, self.num_seats))
        
        if self.full_circle:
            seats = np.arange(self.num_seats)
            max_hop = self.num_seats // 2

            for k_hop in range(1, max_hop + 1):
                weight = 2 ** (1 - k_hop)
                adjacency_matrix[seats, (seats + k_hop) % self.num_seats] = weight
                
                if not (self.num_seats % 2 == 0 and k_hop == max_hop):
                    adjacency_matrix[seats, (seats - k_hop) % self.num_seats] = weight
        else:
            for k_hop in range(1, self.num_seats):
                weight = 2 ** (1 - k_hop)

                rows = np.arange(self.num_seats - k_hop)
                cols = rows + k_hop
                adjacency_matrix[rows, cols] = weight
                adjacency_matrix[cols, rows] = weight
                
        return adjacency_matrix
    
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
        for k_hop in range(1,n):
            seats = np.array([i + row * n for row in range(self.num_rows) for i in range(n-k_hop)])
            adjacency_matrix[seats, seats+k_hop] = 2**(1-k_hop)

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

class EvaluateRequest(SeatingRequest):
    """Score a seating arrangement the user has edited by hand.

    The frontend lets guests be swapped between seats after optimisation. It
    cannot recompute the constraint counts itself: must_sit_together is only
    satisfied by genuinely adjacent seats, which depends on each table type's
    adjacency matrix (see Table.adjacency) rather than on "same table". Rather
    than reimplement that in TypeScript and have the two drift, the edited
    arrangement comes back here to be scored by the same code that produced it.
    """
    assignment: dict[str | int, dict[int, str | int]] = Field(
        ...,
        description="table id -> seat index -> guest id, mirroring SeatingResponse.table_assignments",
    )

class FeedbackRequest(BaseModel):
    verdict: Literal["up", "down"] = Field(..., description="Whether the plan was useful")
    message: Optional[str] = Field(None, max_length=2000, description="Optional free-text comment")
    guest_count: Optional[int] = Field(None, ge=0)
    table_count: Optional[int] = Field(None, ge=0)
    constraint_count: Optional[int] = Field(None, ge=0)

class ConstraintViolation(BaseModel):
    guest_a: Guest
    guest_b: Guest

class SeatingResponse(BaseModel):
    table_assignments: dict[str | int, dict[int,Guest]]
    relation_score: float = Field(..., description="The average relation score for this seating arrangement.")
    constraint_score: float = Field(..., description="The total constraint score for this seating arrangement.")
    must_sit_together: dict[str, int]
    could_sit_together: dict[str,int]
    must_sit_apart: dict[str, int]
    must_sit_together_violations: List[ConstraintViolation] = Field(
        default_factory=list, description="Guest pairs that should sit together but don't."
    )
    must_sit_apart_violations: List[ConstraintViolation] = Field(
        default_factory=list, description="Guest pairs that should sit apart but don't."
    )