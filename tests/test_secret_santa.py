import itertools
import random
from collections import Counter

import pytest
from scipy.stats import chisquare

from ho_ho_helper.secret_santa import (
    NoValidAssignmentError,
    is_single_cycle,
    secret_santa,
)

PARTICIPANTS = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank"]
CONSTRAINTS = {
    ("Alice", "Bob"),
    ("Bob", "Alice"),
    ("Diana", "Eve"),
    ("Eve", "Diana"),
    ("Alice", "Charlie"),
}


def all_valid_assignments(participants, constraints, single_cycle=False):
    """Brute force every valid arrangement, used as ground truth."""
    result = []
    for receivers in itertools.permutations(participants):
        assignment = dict(zip(participants, receivers, strict=True))
        if any(g == r or (g, r) in constraints for g, r in assignment.items()):
            continue
        if single_cycle and not is_single_cycle(assignment):
            continue
        result.append(assignment)
    return result


def freeze(assignment):
    return tuple(sorted(assignment.items()))


def assert_valid(assignment, participants, constraints):
    assert set(assignment) == set(participants)
    assert sorted(assignment.values()) == sorted(participants)
    for giver, receiver in assignment.items():
        assert giver != receiver
        assert (giver, receiver) not in constraints


def assert_uniform(draw, expected, samples_per_outcome=200):
    """Chi-square goodness-of-fit test against the uniform distribution."""
    expected_keys = [freeze(a) for a in expected]
    samples = samples_per_outcome * len(expected)
    counts = Counter(freeze(draw()) for _ in range(samples))
    assert set(counts) == set(expected_keys), "some valid arrangements never occur"
    _, p_value = chisquare([counts[k] for k in expected_keys])
    assert p_value > 1e-3, f"distribution is not uniform (p={p_value:.2g})"


@pytest.mark.parametrize("seed", range(200))
def test_assignments_are_valid(seed):
    result = secret_santa(PARTICIPANTS, CONSTRAINTS, rng=random.Random(seed))
    assert_valid(result, PARTICIPANTS, CONSTRAINTS)


@pytest.mark.parametrize("seed", range(50))
def test_single_cycle_assignments_are_valid(seed):
    result = secret_santa(
        PARTICIPANTS, CONSTRAINTS, single_cycle=True, rng=random.Random(seed)
    )
    assert_valid(result, PARTICIPANTS, CONSTRAINTS)
    assert is_single_cycle(result)


def test_draw_is_uniform():
    expected = all_valid_assignments(PARTICIPANTS, CONSTRAINTS)
    rng = random.Random(2024)
    assert_uniform(lambda: secret_santa(PARTICIPANTS, CONSTRAINTS, rng=rng), expected)


def test_draw_without_constraints_is_uniform():
    participants = ["A", "B", "C", "D", "E"]
    expected = all_valid_assignments(participants, set())
    assert len(expected) == 44  # number of derangements of 5 elements
    rng = random.Random(1)
    assert_uniform(lambda: secret_santa(participants, rng=rng), expected)


def test_single_cycle_draw_is_uniform():
    expected = all_valid_assignments(PARTICIPANTS, CONSTRAINTS, single_cycle=True)
    rng = random.Random(7)
    assert_uniform(
        lambda: secret_santa(PARTICIPANTS, CONSTRAINTS, single_cycle=True, rng=rng),
        expected,
    )


@pytest.mark.parametrize("single_cycle", [False, True])
def test_fallback_enumeration_is_uniform(single_cycle):
    expected = all_valid_assignments(PARTICIPANTS, CONSTRAINTS, single_cycle)
    rng = random.Random(3)
    assert_uniform(
        lambda: secret_santa(
            PARTICIPANTS,
            CONSTRAINTS,
            single_cycle=single_cycle,
            rng=rng,
            max_attempts=0,
        ),
        expected,
        samples_per_outcome=100,
    )


def test_default_rng_is_not_deterministic():
    draws = {freeze(secret_santa(PARTICIPANTS, CONSTRAINTS)) for _ in range(50)}
    assert len(draws) > 1


def test_seed_makes_draw_reproducible():
    first = secret_santa(PARTICIPANTS, CONSTRAINTS, rng=random.Random(42))
    second = secret_santa(PARTICIPANTS, CONSTRAINTS, rng=random.Random(42))
    assert first == second


def test_consecutive_years_never_repeat_when_previous_is_forbidden():
    rng = random.Random(0)
    previous = secret_santa(PARTICIPANTS, CONSTRAINTS, rng=rng)
    for _ in range(200):
        current = secret_santa(
            PARTICIPANTS, CONSTRAINTS | set(previous.items()), rng=rng
        )
        assert not set(current.items()) & set(previous.items())


@pytest.mark.parametrize("single_cycle", [False, True])
def test_restrictive_but_feasible_constraints_are_solved(single_cycle):
    # Everybody can only gift the next or the third next person in a ring:
    # valid arrangements are extremely rare among all the permutations, and
    # the previous greedy algorithm always gave up on this input.
    n = 30
    people = [f"P{i}" for i in range(n)]
    allowed = {(people[i], people[(i + k) % n]) for i in range(n) for k in (1, 3)}
    constraints = {(g, r) for g in people for r in people if (g, r) not in allowed}
    for seed in range(5):
        result = secret_santa(
            people,
            constraints,
            single_cycle=single_cycle,
            rng=random.Random(seed),
            max_attempts=1000,
        )
        assert_valid(result, people, constraints)
        assert not single_cycle or is_single_cycle(result)


@pytest.mark.parametrize("single_cycle", [False, True])
def test_infeasible_constraints_raise(single_cycle):
    # With A and B unable to gift each other, both would have to gift C.
    with pytest.raises(NoValidAssignmentError):
        secret_santa(
            ["A", "B", "C"],
            {("A", "B"), ("B", "A")},
            single_cycle=single_cycle,
            rng=random.Random(0),
            max_attempts=100,
        )


@pytest.mark.parametrize("single_cycle", [False, True])
def test_non_obvious_infeasibility_is_detected_quickly(single_cycle):
    # The last three people can only gift P0 or P1: everybody has some option,
    # but there is no valid arrangement. An unpruned search would take hours.
    people = [f"P{i}" for i in range(16)]
    constraints = {(g, r) for g in people[-3:] for r in people[2:]}
    with pytest.raises(NoValidAssignmentError):
        secret_santa(
            people, constraints, single_cycle=single_cycle, rng=random.Random(0)
        )
    with pytest.raises(NoValidAssignmentError):
        secret_santa(
            people,
            constraints,
            single_cycle=single_cycle,
            rng=random.Random(0),
            max_attempts=0,
        )


def test_single_cycle_can_be_infeasible_when_permutation_is_not():
    people = ["A", "B", "C", "D"]
    # Only A<->B and C<->D swaps are allowed: two loops, but no single loop.
    allowed = {("A", "B"), ("B", "A"), ("C", "D"), ("D", "C")}
    constraints = {(g, r) for g in people for r in people if (g, r) not in allowed}
    assert secret_santa(people, constraints, rng=random.Random(0)) == {
        "A": "B",
        "B": "A",
        "C": "D",
        "D": "C",
    }
    with pytest.raises(NoValidAssignmentError):
        secret_santa(people, constraints, single_cycle=True, rng=random.Random(0))


def test_nobody_to_gift_raises_a_clear_error():
    with pytest.raises(NoValidAssignmentError, match="Alice is not allowed to give"):
        secret_santa(
            ["Alice", "Bob", "Charlie"], {("Alice", "Bob"), ("Alice", "Charlie")}
        )


@pytest.mark.parametrize("participants", [[], ["Alice"]])
def test_too_few_participants_raise(participants):
    with pytest.raises(ValueError, match="At least two"):
        secret_santa(participants)


def test_duplicate_participants_raise():
    with pytest.raises(ValueError, match="Duplicate"):
        secret_santa(["Alice", "Bob", "Alice"])


def test_is_single_cycle():
    assert is_single_cycle({"A": "B", "B": "C", "C": "A"})
    assert not is_single_cycle({"A": "B", "B": "A", "C": "D", "D": "C"})
    assert not is_single_cycle({})
