import pytest

from ho_ho_helper.config import (
    ConfigError,
    GiftSettings,
    load_config,
    parse_config,
    read_assignments,
    write_assignments,
)


def test_load_example_file(repo_root):
    config = load_config(repo_root / "participants.toml")
    assert config.participants == ["Alice", "Bob", "Charlie", "Diana", "Eve"]
    assert config.constraints == {
        ("Alice", "Bob"),
        ("Bob", "Alice"),
        ("Diana", "Eve"),
        ("Eve", "Diana"),
        ("Alice", "Charlie"),
    }
    assert config.emails["Alice"] == "alice@example.com"
    assert config.gift == GiftSettings(max_budget=10, currency="EUR")


def test_optional_sections_can_be_omitted():
    config = parse_config({"participants": {"names": ["A", "B"]}})
    assert config.constraints == set()
    assert config.emails == {}
    assert config.gift == GiftSettings()


def test_constraints_without_direct_constraints():
    config = parse_config(
        {"participants": {"names": ["A", "B", "C"]}, "constraints": {"couples": []}}
    )
    assert config.constraints == set()


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({}, "Missing \\[participants\\]"),
        ({"participants": {"names": "Alice"}}, "list of names"),
        ({"participants": {"names": ["A", "A"]}}, "Duplicate"),
        ({"participants": {"names": ["A", " "]}}, "empty"),
        (
            {
                "participants": {"names": ["Alice", "Bob"]},
                "constraints": {"couples": [["Alice", "bob"]]},
            },
            "Unknown participant.*bob",
        ),
        (
            {
                "participants": {"names": ["Alice", "Bob"]},
                "constraints": {"direct_constraints": [["Alice", "Carol"]]},
            },
            "Unknown participant.*Carol",
        ),
        (
            {
                "participants": {"names": ["A", "B", "C"]},
                "constraints": {"couples": [["A", "B", "C"]]},
            },
            "pair of names",
        ),
        (
            {
                "participants": {"names": ["A", "B"], "emails": {"Carol": "c@x.org"}},
            },
            "Unknown participant.*Carol",
        ),
        (
            {"participants": {"names": ["A", "B"]}, "gift": {"max_budget": "ten"}},
            "max_budget",
        ),
    ],
)
def test_invalid_config_raises(data, message):
    with pytest.raises(ConfigError, match=message):
        parse_config(data)


def test_assignments_round_trip(tmp_path):
    assignments = {"Mary Jane": "Bob", "Bob": "Zoë", "Zoë": "Mary Jane"}
    path = tmp_path / "assignments.toml"
    write_assignments(path, assignments)
    assert read_assignments(path) == assignments


def test_read_invalid_assignments(tmp_path):
    path = tmp_path / "participants.toml"
    path.write_text('[participants]\nnames = ["A"]\n')
    with pytest.raises(ConfigError, match="assignments"):
        read_assignments(path)
