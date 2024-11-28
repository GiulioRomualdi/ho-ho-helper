import random
import networkx as nx


def secret_santa(participants, constraints):
    """
    Organize a Secret Santa with constraints.

    Parameters:
        participants (list): List of participant names.
        constraints (list of tuple): List of pairs (a, b) where `a` cannot give a gift to `b` and vice versa.

    Returns:
        dict: Secret Santa assignments (participant -> recipient).
    """
    G = nx.DiGraph()
    G.add_nodes_from(participants)

    for giver in participants:
        for receiver in participants:
            if giver != receiver and (giver, receiver) not in constraints:
                G.add_edge(giver, receiver)

    for _ in range(100):  # Retry up to 100 times
        shuffled_participants = random.sample(participants, len(participants))
        assignments = {}
        for giver in shuffled_participants:
            valid_receivers = list(set(G.successors(giver)) - set(assignments.values()))
            if valid_receivers:
                assignments[giver] = random.choice(valid_receivers)
            else:
                break
        if len(assignments) == len(participants):
            return assignments

    raise ValueError(
        "Could not find a valid Secret Santa arrangement with the given constraints."
    )
