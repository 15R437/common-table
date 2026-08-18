"""
Fast-iteration exploration tool for GradSolver.

This is NOT a test — nothing here asserts anything. It trains a GradSolver on
a small scenario and dumps the things you'd want to eyeball while iterating on
the model: a training curve per loss term, and a before/after heatmap of the
soft assignment matrix. Rerun it after every change to models.py to see the
effect immediately.

Usage (from anywhere, no PYTHONPATH juggling needed):
    python3 backend/scripts/explore_gradsolver.py
    python3 backend/scripts/explore_gradsolver.py --scenario must_sit_together --num-epochs 500
    python3 backend/scripts/explore_gradsolver.py --scenario random --num-guests 10 --num-seats 10 --show
"""
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import numpy as np
import torch
from scipy.optimize import linear_sum_assignment

from app.schema import Guest, Constraint, BanquetTable, CabaretTable, TheatreSection
from app.solvers import GradSolver
from utils.plots import plot_loss_history, plot_matrix, animate_matrices, plot_seating_chart

OUTPUT_DIR = Path(__file__).parent / "outputs"

guest_list = [Guest(id=0,name="Alex",relation_tags=["alty_boys"]),
                Guest(id=1,name="Success",relation_tags=["alty_boys"]),
                Guest(id=2,name="Danny",relation_tags=["alty_boys"]),
                Guest(id=3,name="Ivy",relation_tags=["sainsburys"],),
                Guest(id=4,name="Adam",relation_tags=["sainsburys"]),
                Guest(id=5,name="Jane",relation_tags=[])]
random.shuffle(guest_list)
constraints = [Constraint(guest_a_id=2,guest_b_id=3,relationship="must_sit_together")]
table_list = [CabaretTable(id=0, num_seats=8,full_circle=False)]


def extract_hard_seating(T_guest):
    """Guest -> seat, via the Hungarian algorithm on the soft assignment probs."""
    row_ind, col_ind = linear_sum_assignment(-T_guest)
    return dict(zip(row_ind, col_ind))

def run_experiment(num_epochs, lambda_guest, lambda_seat, lambda_ce):
    #torch.manual_seed(seed)
    model = GradSolver(guest_list=guest_list, table_list=table_list, constraints=constraints, init_type='uniform')

    T_guest_before, _ = model.get_soft_assignment()
    T_guest_before = T_guest_before.detach().clone()

    start = time.time()
    history = model.train(
        lambda_guest=lambda_guest,
        lambda_seat=lambda_seat,
        lambda_ce=lambda_ce,
        num_epochs=num_epochs,
        keep_history=True,
        verbose=True,
    )
    elapsed = time.time() - start
    print(f"Experiment complete after {elapsed:.4f}s.")

    plot_loss_history(history=history, primary_losses=['guest_score','seat_score'], secondary_losses=['cross_entropy'])
    animate_matrices(matrix_list=history['T_guest'],fig_title='T_guest')
    animate_matrices(matrix_list=history['T_seats'],fig_title='T_seats')

    T_guest_final, T_seats_final = model.get_soft_assignment()
    T_guest_final = T_guest_final.cpu().detach().numpy()
    T_seats_final = T_seats_final.cpu().detach().numpy()
    final_arrangement = model.extract_hard_seating()
    plot_matrix(matrix_list=[T_guest_final, T_seats_final.T], title_list=['Learned T_guest', 'Learned T_seats transpose'], fig_title='Learned Assignment Matrices')
    plot_seating_chart(tables=table_list,guest_list=guest_list,seat_of_guest=final_arrangement)
    

if __name__ == "__main__":
    run_experiment(num_epochs=1000, lambda_guest=1, lambda_seat=1, lambda_ce=50)
