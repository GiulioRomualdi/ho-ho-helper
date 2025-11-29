import toml


def read_toml_file(file_path):
    """
    Reads the participants, constraints, email addresses, and gift settings from a TOML file.

    Parameters:
        file_path (str): Path to the TOML file.

    Returns:
        tuple: (list of participants, list of constraints, dict of emails, dict of gift settings)
    """
    data = toml.load(file_path)
    participants = data["participants"]["names"]
    pairs_constraints = data["constraints"]["couples"]
    direct_constraints = data["constraints"]["direct_constraints"]

    # for each constraint, we have to create two constraints (a, b) and (b, a) since they are mutual by using list comprehension
    constraints = (
        [(a, b) for a, b in pairs_constraints]
        + [(b, a) for a, b in pairs_constraints]
        + [(a, b) for a, b in direct_constraints]
    )

    emails = data["participants"].get("emails", {})
    gift_settings = data.get("gift", {})
    normalized_gift_settings = {
        "max_budget": gift_settings.get("max_budget"),
        "currency": gift_settings.get("currency"),
    }

    return participants, constraints, emails, normalized_gift_settings


def write_toml_file(file_path, assignments):
    """
    Writes the Secret Santa assignments to a TOML file.

    Parameters:
        file_path (str): Path to the output TOML file.
        assignments (dict): Secret Santa assignments.
    """
    data = {"assignments": assignments}
    with open(file_path, "w") as file:
        toml.dump(data, file)
