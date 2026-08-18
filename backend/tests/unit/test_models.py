import pytest
import torch

from app.schema import Guest, Constraint, BanquetTable
from app.solvers import GradSolver, regularised_surjective_init


# --- Solver._get_relation_matrix -------------------------------------------
# (exercised through GradSolver, since Solver is abstract; hand-built guest
# lists are used here rather than the random fixture, since these tests check
# exact numeric values and need full control over which guests share tags)

def test_relation_matrix_is_symmetric():
    """relation_matrix[i][j] should always equal relation_matrix[j][i]."""
    guests = [
        Guest(id=0, name="A", relation_tags=["friends"]),
        Guest(id=1, name="B", relation_tags=["friends", "work"]),
        Guest(id=2, name="C", relation_tags=["work"]),
    ]
    tables = [BanquetTable(id="t1", type="banquet", num_seats=4)]
    solver = GradSolver(guest_list=guests, table_list=tables, constraints=[])

    assert torch.allclose(solver.relation_matrix, solver.relation_matrix.T)


def test_relation_matrix_diagonal_is_zero():
    """A guest should have zero relation score with themselves."""
    guests = [Guest(id=i, name=str(i), relation_tags=["shared"]) for i in range(4)]
    tables = [BanquetTable(id="t1", type="banquet", num_seats=4)]
    solver = GradSolver(guest_list=guests, table_list=tables, constraints=[])

    assert torch.allclose(torch.diagonal(solver.relation_matrix), torch.zeros(4))


def test_relation_matrix_zero_for_guests_with_no_shared_tags():
    """Two guests with disjoint relation_tags should score 0."""
    guests = [
        Guest(id=0, name="A", relation_tags=["friends"]),
        Guest(id=1, name="B", relation_tags=["work"]),
    ]
    tables = [BanquetTable(id="t1", type="banquet", num_seats=2)]
    solver = GradSolver(guest_list=guests, table_list=tables, constraints=[])

    assert solver.relation_matrix[0, 1].item() == 0


def test_relation_matrix_weights_shared_tag_by_inverse_clique_size():
    """A tag shared by k guests should contribute 1/k to each pair sharing it."""
    guests = [Guest(id=i, name=str(i), relation_tags=["friends"]) for i in range(3)]
    tables = [BanquetTable(id="t1", type="banquet", num_seats=4)]
    solver = GradSolver(guest_list=guests, table_list=tables, constraints=[])

    expected = 1 / 3
    for i in range(3):
        for j in range(i + 1, 3):
            assert solver.relation_matrix[i, j].item() == pytest.approx(expected)


def test_relation_matrix_sums_contributions_across_multiple_shared_tags():
    """Two guests sharing more than one tag should have their per-tag scores summed."""
    guests = [
        Guest(id=0, name="A", relation_tags=["friends", "work"]),
        Guest(id=1, name="B", relation_tags=["friends", "work"]),
    ]
    tables = [BanquetTable(id="t1", type="banquet", num_seats=2)]
    solver = GradSolver(guest_list=guests, table_list=tables, constraints=[])

    # each tag's clique is just these two guests, so each tag contributes 1/2 -> 1/2 + 1/2 = 1
    assert solver.relation_matrix[0, 1].item() == pytest.approx(1.0)


# --- Solver._get_constraint_matrix ------------------------------------------

def test_constraint_matrix_must_sit_together_sets_one():
    """A 'must_sit_together' constraint should set the corresponding entry to 1."""
    guests = [Guest(id=0, name="A", relation_tags=[]), Guest(id=1, name="B", relation_tags=[])]
    tables = [BanquetTable(id="t1", type="banquet", num_seats=2)]
    constraints = [Constraint(guest_a_id=0, guest_b_id=1, relationship="must_sit_together")]
    solver = GradSolver(guest_list=guests, table_list=tables, constraints=constraints)

    assert solver.constraint_matrix[0, 1].item() == 1


def test_constraint_matrix_could_sit_together_sets_half():
    """A 'could_sit_together' constraint should set the corresponding entry to 0.5."""
    guests = [Guest(id=0, name="A", relation_tags=[]), Guest(id=1, name="B", relation_tags=[])]
    tables = [BanquetTable(id="t1", type="banquet", num_seats=2)]
    constraints = [Constraint(guest_a_id=0, guest_b_id=1, relationship="could_sit_together")]
    solver = GradSolver(guest_list=guests, table_list=tables, constraints=constraints)

    assert solver.constraint_matrix[0, 1].item() == 0.5


def test_constraint_matrix_must_sit_apart_sets_negative_one():
    """A 'must_sit_apart' constraint should set the corresponding entry to -1."""
    guests = [Guest(id=0, name="A", relation_tags=[]), Guest(id=1, name="B", relation_tags=[])]
    tables = [BanquetTable(id="t1", type="banquet", num_seats=2)]
    constraints = [Constraint(guest_a_id=0, guest_b_id=1, relationship="must_sit_apart")]
    solver = GradSolver(guest_list=guests, table_list=tables, constraints=constraints)

    assert solver.constraint_matrix[0, 1].item() == -1


def test_constraint_matrix_unconstrained_pairs_are_zero():
    """Guest pairs with no constraint between them should be 0."""
    guests = [Guest(id=i, name=str(i), relation_tags=[]) for i in range(3)]
    tables = [BanquetTable(id="t1", type="banquet", num_seats=4)]
    constraints = [Constraint(guest_a_id=0, guest_b_id=1, relationship="must_sit_together")]
    solver = GradSolver(guest_list=guests, table_list=tables, constraints=constraints)

    assert solver.constraint_matrix[0, 2].item() == 0
    assert solver.constraint_matrix[1, 2].item() == 0


def test_constraint_matrix_is_symmetric():
    """
    Constraints are inherently bidirectional (a "must sit apart" between A and B
    is the same fact regardless of which guest is "a" and which is "b"), so
    constraint_matrix should be symmetric like relation_matrix is. Regression
    test for a bug where only constraint_matrix[idx1, idx2] was written, never
    the [idx2, idx1] entry, so the constraint only applied in one direction.
    """
    guests = [Guest(id=0, name="A", relation_tags=[]), Guest(id=1, name="B", relation_tags=[])]
    tables = [BanquetTable(id="t1", type="banquet", num_seats=2)]
    constraints = [Constraint(guest_a_id=0, guest_b_id=1, relationship="must_sit_together")]
    solver = GradSolver(guest_list=guests, table_list=tables, constraints=constraints)

    assert solver.constraint_matrix[0, 1].item() == solver.constraint_matrix[1, 0].item()


# --- Solver._get_table_adjacency --------------------------------------------

def test_table_adjacency_shape_matches_total_seats(sample_banquet_tables):
    """Adjacency matrix should be (n_seats, n_seats) for the combined table list."""
    tables = sample_banquet_tables(num_seats_per_table=[4, 6])
    guests = [Guest(id=i, name=str(i), relation_tags=[]) for i in range(10)]
    solver = GradSolver(guest_list=guests, table_list=tables, constraints=[])

    assert solver.table_adjacency.shape == (10, 10)


def test_table_adjacency_no_edges_between_different_tables(sample_banquet_tables):
    """Seats at different tables should never be adjacent to each other."""
    tables = sample_banquet_tables(num_seats_per_table=[4, 4])
    guests = [Guest(id=i, name=str(i), relation_tags=[]) for i in range(8)]
    solver = GradSolver(guest_list=guests, table_list=tables, constraints=[])

    cross_block = solver.table_adjacency[:4, 4:]
    assert torch.all(cross_block == 0)


def test_table_adjacency_matches_each_table_own_adjacency(sample_banquet_tables):
    """The block for a given table should equal that table's own .adjacency() output."""
    tables = sample_banquet_tables(num_seats_per_table=[4, 4])
    guests = [Guest(id=i, name=str(i), relation_tags=[]) for i in range(8)]
    solver = GradSolver(guest_list=guests, table_list=tables, constraints=[])

    first_table_block = solver.table_adjacency[:4, :4]
    expected = torch.from_numpy(tables[0].adjacency()).float()
    assert torch.allclose(first_table_block, expected)


# --- regularised_surjective_init --------------------------------------------

def test_regularised_surjective_init_output_shape():
    """Output should be shape (n_low, n_high)."""
    logits = regularised_surjective_init(n_low=5, n_high=8)
    assert logits.shape == (5, 8)


def test_regularised_surjective_init_is_surjective_when_n_low_ge_n_high():
    """When n_low >= n_high, every column index should be some row's argmax."""
    n_low, n_high = 10, 4
    logits = regularised_surjective_init(n_low, n_high)
    argmax_per_row = logits.argmax(dim=1)

    assert set(argmax_per_row.tolist()) == set(range(n_high))


def test_regularised_surjective_init_margin_makes_target_the_argmax():
    """For each row, the designated target column should stand out clearly
    above the rest of that row (the noise alone can't explain the gap)."""
    n_low, n_high, noise_std = 20, 5, 0.1
    logits = regularised_surjective_init(n_low, n_high, noise_std=noise_std)

    for row in logits:
        sorted_row, _ = torch.sort(row, descending=True)
        gap = sorted_row[0] - sorted_row[1]
        assert gap > 5 * noise_std


def test_regularised_surjective_init_handles_n_low_less_than_n_high():
    """When n_low < n_high, function should not error and should still return correct shape."""
    logits = regularised_surjective_init(n_low=3, n_high=10)
    assert logits.shape == (3, 10)


# --- GradSolver.__init__ -----------------------------------------------------

def test_gradsolver_guest_logits_shape(sample_guests_and_constraints, sample_banquet_tables):
    """guest_logits should be square (max(n_guests, n_seats) each way), padded with dummy rows/cols."""
    data = sample_guests_and_constraints(num_guests=5, num_constraints=2, seed=1)
    tables = sample_banquet_tables(num_seats_per_table=[8])
    solver = GradSolver(guest_list=data["guest_list"], table_list=tables, constraints=data["constraints"])

    assert solver.guest_logits.shape == (8, 8)


def test_gradsolver_seat_logits_shape(sample_guests_and_constraints, sample_banquet_tables):
    """seat_logits should be square (max(n_guests, n_seats) each way), padded with dummy rows/cols."""
    data = sample_guests_and_constraints(num_guests=5, num_constraints=2, seed=1)
    tables = sample_banquet_tables(num_seats_per_table=[8])
    solver = GradSolver(guest_list=data["guest_list"], table_list=tables, constraints=data["constraints"])

    assert solver.seat_logits.shape == (8, 8)


def test_gradsolver_parameters_are_registered(sample_guests_and_constraints, sample_banquet_tables):
    """guest_logits and seat_logits should show up in model.parameters() (nn.Module wiring)."""
    data = sample_guests_and_constraints(num_guests=4, num_constraints=1, seed=2)
    tables = sample_banquet_tables(num_seats_per_table=[4])
    solver = GradSolver(guest_list=data["guest_list"], table_list=tables, constraints=data["constraints"])

    param_names = {name for name, _ in solver.named_parameters()}
    assert param_names == {"guest_logits", "seat_logits"}


# --- GradSolver.get_soft_assignment ------------------------------------------

def test_get_soft_assignment_rows_sum_to_one(sample_guests_and_constraints, sample_banquet_tables):
    """T_guest and T_seats should each be valid probability distributions per row (softmax)."""
    data = sample_guests_and_constraints(num_guests=5, num_constraints=2, seed=3)
    tables = sample_banquet_tables(num_seats_per_table=[6])
    solver = GradSolver(guest_list=data["guest_list"], table_list=tables, constraints=data["constraints"])

    T_guest, T_seats = solver.get_soft_assignment()

    assert torch.allclose(T_guest.sum(dim=1), torch.ones(T_guest.shape[0]), atol=1e-5)
    assert torch.allclose(T_seats.sum(dim=1), torch.ones(T_seats.shape[0]), atol=1e-5)


def test_get_soft_assignment_lower_temperature_sharpens_distribution(sample_guests_and_constraints, sample_banquet_tables):
    """A smaller temp should push probabilities closer to one-hot than a higher temp."""
    data = sample_guests_and_constraints(num_guests=5, num_constraints=2, seed=4)
    tables = sample_banquet_tables(num_seats_per_table=[6])
    solver = GradSolver(guest_list=data["guest_list"], table_list=tables, constraints=data["constraints"])

    T_guest_high_temp, _ = solver.get_soft_assignment(temp=5)
    T_guest_low_temp, _ = solver.get_soft_assignment(temp=0.1)

    max_prob_high_temp = T_guest_high_temp.max(dim=1).values.mean()
    max_prob_low_temp = T_guest_low_temp.max(dim=1).values.mean()

    assert max_prob_low_temp > max_prob_high_temp


# --- GradSolver.forward -------------------------------------------------------

def test_forward_returns_three_scalars(sample_guests_and_constraints, sample_banquet_tables):
    """guest_score, seat_score, ce_loss should each be 0-dimensional tensors."""
    data = sample_guests_and_constraints(num_guests=5, num_constraints=2, seed=5)
    tables = sample_banquet_tables(num_seats_per_table=[6])
    solver = GradSolver(guest_list=data["guest_list"], table_list=tables, constraints=data["constraints"])

    guest_score, seat_score, ce_loss = solver.forward()

    assert guest_score.dim() == 0
    assert seat_score.dim() == 0
    assert ce_loss.dim() == 0


def test_forward_ce_loss_is_nonnegative(sample_guests_and_constraints, sample_banquet_tables):
    """Cross-entropy losses should never be negative."""
    data = sample_guests_and_constraints(num_guests=5, num_constraints=2, seed=6)
    tables = sample_banquet_tables(num_seats_per_table=[6])
    solver = GradSolver(guest_list=data["guest_list"], table_list=tables, constraints=data["constraints"])

    _, _, ce_loss = solver.forward()

    assert ce_loss.item() >= 0


def test_forward_is_differentiable(sample_guests_and_constraints, sample_banquet_tables):
    """
    Calling backward() on the combined loss should populate .grad on both
    guest_logits and seat_logits without raising. (This is the kind of test
    that would have caught the earlier sparse/dense autograd bug immediately.)
    """
    data = sample_guests_and_constraints(num_guests=5, num_constraints=2, seed=7)
    tables = sample_banquet_tables(num_seats_per_table=[6])
    solver = GradSolver(guest_list=data["guest_list"], table_list=tables, constraints=data["constraints"])

    guest_score, seat_score, ce_loss = solver.forward()
    loss = guest_score + seat_score + ce_loss
    loss.backward()

    assert solver.guest_logits.grad is not None
    assert solver.seat_logits.grad is not None
    assert torch.any(solver.guest_logits.grad != 0)


# --- GradSolver.train ----------------------------------------------------------

def test_train_history_has_expected_keys(sample_guests_and_constraints, sample_banquet_tables):
    """Returned history dict should contain 'guest_score', 'seat_score', 'ce', 'T_guest', 'T_seats'."""
    data = sample_guests_and_constraints(num_guests=4, num_constraints=1, seed=8)
    tables = sample_banquet_tables(num_seats_per_table=[4])
    solver = GradSolver(guest_list=data["guest_list"], table_list=tables, constraints=data["constraints"])

    history = solver.train(lambda_guest=1, lambda_seat=1, lambda_ce=0.1, num_epochs=3, verbose=False)

    assert set(history.keys()) == {"guest_score", "seat_score", "cross_entropy", "T_guest", "T_seats"}


def test_train_history_length_matches_num_epochs(sample_guests_and_constraints, sample_banquet_tables):
    """Each history list should have exactly num_epochs entries when keep_history=True."""
    data = sample_guests_and_constraints(num_guests=4, num_constraints=1, seed=9)
    tables = sample_banquet_tables(num_seats_per_table=[4])
    solver = GradSolver(guest_list=data["guest_list"], table_list=tables, constraints=data["constraints"])

    num_epochs = 5
    history = solver.train(lambda_guest=1, lambda_seat=1, lambda_ce=0.1, num_epochs=num_epochs, verbose=False)

    assert len(history["guest_score"]) == num_epochs
    assert len(history["seat_score"]) == num_epochs
    assert len(history["cross_entropy"]) == num_epochs


def test_train_keep_history_false_returns_empty_lists(sample_guests_and_constraints, sample_banquet_tables):
    """With keep_history=False, history lists should stay empty."""
    data = sample_guests_and_constraints(num_guests=4, num_constraints=1, seed=10)
    tables = sample_banquet_tables(num_seats_per_table=[4])
    solver = GradSolver(guest_list=data["guest_list"], table_list=tables, constraints=data["constraints"])

    history = solver.train(lambda_guest=1, lambda_seat=1, lambda_ce=0.1, num_epochs=5, keep_history=False, verbose=False)

    assert history["guest_score"] == []
    assert history["seat_score"] == []
    assert history["cross_entropy"] == []


def test_train_gradients_do_not_accumulate_across_epochs(sample_guests_and_constraints, sample_banquet_tables, monkeypatch):
    """
    train() should call optimiser.zero_grad() once per epoch. This is a direct
    regression test for a bug found earlier this session: without zero_grad(),
    gradients silently accumulate across epochs instead of being reset.
    """
    data = sample_guests_and_constraints(num_guests=4, num_constraints=1, seed=11)
    tables = sample_banquet_tables(num_seats_per_table=[4])
    solver = GradSolver(guest_list=data["guest_list"], table_list=tables, constraints=data["constraints"])

    zero_grad_calls = []
    original_zero_grad = torch.optim.Adam.zero_grad

    def spy_zero_grad(self, *args, **kwargs):
        zero_grad_calls.append(1)
        return original_zero_grad(self, *args, **kwargs)

    monkeypatch.setattr(torch.optim.Adam, "zero_grad", spy_zero_grad)

    num_epochs = 5
    solver.train(lambda_guest=1, lambda_seat=1, lambda_ce=0.1, num_epochs=num_epochs, verbose=False)

    assert len(zero_grad_calls) == num_epochs


def test_train_improves_score_on_a_simple_case():
    """On an easy, well-separated scenario, guest_score after training should be
    higher than guest_score before training (sanity check that learning is happening)."""
    torch.manual_seed(0)
    guests = (
        [Guest(id=i, name=f"friend{i}", relation_tags=["friends"]) for i in range(3)]
        + [Guest(id=i, name=f"family{i}", relation_tags=["family"]) for i in range(3, 6)]
    )
    tables = [BanquetTable(id="t1", type="banquet", num_seats=6)]
    solver = GradSolver(guest_list=guests, table_list=tables, constraints=[])

    guest_score_before, _, _ = solver.forward()
    solver.train(lambda_guest=1, lambda_seat=1, lambda_ce=0.1, num_epochs=300, verbose=False)
    guest_score_after, _, _ = solver.forward()

    assert guest_score_after.item() > guest_score_before.item()
