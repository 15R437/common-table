import pytest
import numpy as np
from itertools import combinations
from faker import Faker
from typing import  List
from app.schema import Guest, Constraint, BanquetTable, CabaretTable, TheatreSection
from app.models import GradSolver

TAGS = ["work_a", "work_b", "uni_a", "uni_b", "family_a", "family_b", "church_a", "church_b", "gym", "school"]

@pytest.fixture
def sample_guests_and_constraints():
    def _sample(num_guests : int = 6, min_tags_per_guest : int = 0, max_tags_per_guest : int = 4, num_constraints: int = 3, seed=None):
        rng = np.random.default_rng(seed=seed)
        fake = Faker()
        names = [fake.name() for _ in range(num_guests)]
        relationships = ["must_sit_together", "could_sit_together", "must_sit_apart"]
        num_tags = rng.integers(low=min_tags_per_guest, high=min(max_tags_per_guest,len(TAGS)), size=num_guests, endpoint=True)

        guest_list = [Guest(id=i, name=name, relation_tags=rng.choice(TAGS,size=n_tags,replace=False))
                    for i, (name, n_tags) in enumerate(zip(names,num_tags))]
        
        pairs = list(combinations(guest_list,2))
        num_constraints = min(max(0,num_constraints),len(pairs))
        chosen_pairs = rng.choice(pairs, size=num_constraints, replace=False)
        chosen_relationships = rng.choice(relationships, size=num_constraints, replace=True)
        constraints = [Constraint(guest_a_id=guest_a.id, guest_b_id=guest_b.id, relationship=rel) 
                    for (guest_a,guest_b),rel in zip(chosen_pairs,chosen_relationships)]

        return {'guest_list':guest_list, 'constraints':constraints}
    return _sample



@pytest.fixture
def sample_banquet_tables():
    def _sample_banquet_tables(num_seats_per_table : List[int], head_seat : bool =False, foot_seat : bool =False) -> List[BanquetTable]:
        table_list = [BanquetTable(id=str(i), num_seats=n_seats, head_seat=head_seat, foot_seat=foot_seat) for i,n_seats in enumerate(num_seats_per_table)]
        return table_list
    return _sample_banquet_tables

@pytest.fixture
def sample_cabaret_tables():
    def _sample_cabaret_tables(num_seats_per_table : List[int], full_circle : bool = False) -> List[CabaretTable]:
        table_list = [CabaretTable(id=str(i), num_seats=n_seats, full_circle=full_circle) for i,n_seats in enumerate(num_seats_per_table)]
        return table_list
    return _sample_cabaret_tables

@pytest.fixture
def sample_theatre_section():
    def _sample_theatre_section(num_seats_per_section: List[int], num_rows_per_section: List[int]) -> List[TheatreSection]:
        assert len(num_seats_per_section) == len(num_rows_per_section), f"num_seats_per_section must have the same length as num_rows_per_section."
        section_list = [TheatreSection(id=str(i), num_seats=n_seats, num_rows=n_rows)
                        for i,n_seats,n_rows in enumerate(zip(num_seats_per_section, num_rows_per_section))]
        return section_list
    return _sample_theatre_section
