"""Core Secret Santa drawing algorithm.

The draw is *uniformly random*: every valid arrangement has exactly the same
probability of being picked. This is achieved with rejection sampling: a
uniformly random permutation (or cycle) is drawn and accepted only if it
respects all the constraints. If valid arrangements are so rare that rejection
sampling does not find one quickly, the valid arrangements are enumerated
explicitly and one of them is picked uniformly.
"""

from __future__ import annotations

import random
import warnings
from collections.abc import Iterable, Sequence

Pair = tuple[str, str]

DEFAULT_MAX_ATTEMPTS = 100_000
DEFAULT_ENUMERATION_LIMIT = 100_000
MAX_SEARCH_NODES = 1_000_000


class NoValidAssignmentError(ValueError):
    """Raised when no arrangement satisfies the given constraints."""


def secret_santa(
    participants: Sequence[str],
    constraints: Iterable[Pair] = (),
    *,
    single_cycle: bool = False,
    rng: random.Random | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    enumeration_limit: int = DEFAULT_ENUMERATION_LIMIT,
) -> dict[str, str]:
    """Draw a Secret Santa arrangement.

    Parameters:
        participants: Unique participant names (at least two).
        constraints: Directed pairs ``(giver, receiver)`` that are not allowed.
        single_cycle: If True, the gifts form a single loop through everybody
            (A -> B -> C -> ... -> A) instead of possibly several smaller loops.
        rng: Random generator. Defaults to ``random.SystemRandom`` (OS entropy).
            Pass ``random.Random(seed)`` for a reproducible draw.
        max_attempts: Number of rejection-sampling attempts before falling back
            to explicit enumeration.
        enumeration_limit: Maximum number of arrangements collected by the
            fallback enumeration.

    Returns:
        A mapping ``giver -> receiver``.

    Raises:
        ValueError: If the participants are invalid.
        NoValidAssignmentError: If no arrangement satisfies the constraints.
    """
    participants = list(participants)
    _validate_participants(participants)
    rng = rng if rng is not None else random.SystemRandom()
    forbidden = set(constraints)

    allowed = {
        giver: {r for r in participants if r != giver and (giver, r) not in forbidden}
        for giver in participants
    }
    _check_trivially_infeasible(participants, allowed)
    if not _has_perfect_matching(participants, set(participants), allowed):
        raise NoValidAssignmentError(_NO_SOLUTION_MESSAGE)

    for _ in range(max_attempts):
        candidate = _random_candidate(participants, single_cycle, rng)
        if all(receiver in allowed[giver] for giver, receiver in candidate.items()):
            return candidate

    solutions, exhaustive = _enumerate_solutions(
        participants, allowed, single_cycle, rng, enumeration_limit
    )
    if not solutions:
        raise NoValidAssignmentError(_NO_SOLUTION_MESSAGE)
    if not exhaustive:
        warnings.warn(
            "The constraints are very restrictive: the draw is valid but may not "
            "be perfectly uniform.",
            RuntimeWarning,
            stacklevel=2,
        )
    return rng.choice(solutions)


_NO_SOLUTION_MESSAGE = (
    "Could not find a valid Secret Santa arrangement with the given constraints. "
    "Try removing some constraints."
)


def is_single_cycle(assignments: dict[str, str]) -> bool:
    """Return True if following the gifts from anyone visits every participant."""
    if not assignments:
        return False
    start = next(iter(assignments))
    current, steps = assignments[start], 1
    while current != start:
        current = assignments[current]
        steps += 1
        if steps > len(assignments):
            return False
    return steps == len(assignments)


def _validate_participants(participants: list[str]) -> None:
    if len(participants) < 2:
        raise ValueError("At least two participants are needed for a Secret Santa.")
    duplicates = sorted({p for p in participants if participants.count(p) > 1})
    if duplicates:
        raise ValueError(f"Duplicate participant names: {', '.join(duplicates)}")


def _check_trivially_infeasible(
    participants: list[str], allowed: dict[str, set[str]]
) -> None:
    for giver in participants:
        if not allowed[giver]:
            raise NoValidAssignmentError(
                f"{giver} is not allowed to give a gift to anybody."
            )
    for receiver in participants:
        if not any(receiver in allowed[giver] for giver in participants):
            raise NoValidAssignmentError(
                f"{receiver} is not allowed to receive a gift from anybody."
            )


def _random_candidate(
    participants: list[str], single_cycle: bool, rng: random.Random
) -> dict[str, str]:
    order = participants.copy()
    rng.shuffle(order)
    if single_cycle:
        # Every n-cycle corresponds to exactly n rotations of a random ordering,
        # so linking each person to the next one gives a uniform random cycle.
        return {giver: order[(i + 1) % len(order)] for i, giver in enumerate(order)}
    return dict(zip(participants, order, strict=True))


def _has_perfect_matching(
    givers: Iterable[str], receivers: set[str], allowed: dict[str, set[str]]
) -> bool:
    """Check whether every giver can get a distinct allowed receiver.

    This is a necessary condition for any valid arrangement, checked in
    polynomial time with augmenting paths (Kuhn's algorithm).
    """
    givers = list(givers)
    if len(givers) != len(receivers):
        return False
    owner: dict[str, str] = {}

    def augment(giver: str, visited: set[str]) -> bool:
        for receiver in allowed[giver] & receivers:
            if receiver in visited:
                continue
            visited.add(receiver)
            if receiver not in owner or augment(owner[receiver], visited):
                owner[receiver] = giver
                return True
        return False

    return all(augment(giver, set()) for giver in givers)


def _enumerate_solutions(
    participants: list[str],
    allowed: dict[str, set[str]],
    single_cycle: bool,
    rng: random.Random,
    limit: int,
) -> tuple[list[dict[str, str]], bool]:
    """Enumerate valid arrangements via depth-first search.

    Branches are pruned as soon as the remaining givers cannot be matched with
    the remaining receivers, so in the permutation mode every branch leads to
    at least one solution. Finding a single cycle is NP-hard in general, hence
    the search also stops after ``MAX_SEARCH_NODES`` nodes.

    Returns the solutions found and whether the enumeration was exhaustive.
    """
    solutions: list[dict[str, str]] = []
    assignment: dict[str, str] = {}
    used: set[str] = set()
    nodes = 0

    def candidates(giver: str) -> list[str]:
        # Sorted before shuffling so that a seeded rng gives reproducible results.
        options = sorted(r for r in allowed[giver] if r not in used)
        rng.shuffle(options)
        return options

    def search_permutation(index: int) -> bool:
        nonlocal nodes
        nodes += 1
        if nodes > MAX_SEARCH_NODES:
            return False
        if index == len(participants):
            solutions.append(assignment.copy())
            return len(solutions) < limit
        giver = participants[index]
        remaining_givers = participants[index + 1 :]
        for receiver in candidates(giver):
            used.add(receiver)
            if _has_perfect_matching(
                remaining_givers, set(participants) - used, allowed
            ):
                assignment[giver] = receiver
                keep_going = search_permutation(index + 1)
                del assignment[giver]
            else:
                keep_going = True
            used.discard(receiver)
            if not keep_going:
                return False
        return True

    start = participants[0]

    def search_cycle(giver: str) -> bool:
        nonlocal nodes
        nodes += 1
        if nodes > MAX_SEARCH_NODES:
            return False
        if len(assignment) == len(participants) - 1:
            if start in allowed[giver]:
                assignment[giver] = start
                solutions.append(assignment.copy())
                del assignment[giver]
            return len(solutions) < limit
        for receiver in candidates(giver):
            used.add(receiver)
            # The receiver becomes the next giver; the loop must close on start.
            unvisited = set(participants) - used
            if _has_perfect_matching(
                [receiver, *unvisited], unvisited | {start}, allowed
            ):
                assignment[giver] = receiver
                keep_going = search_cycle(receiver)
                del assignment[giver]
            else:
                keep_going = True
            used.discard(receiver)
            if not keep_going:
                return False
        return True

    if single_cycle:
        used.add(start)
        exhaustive = search_cycle(start)
    else:
        exhaustive = search_permutation(0)
    return solutions, exhaustive
