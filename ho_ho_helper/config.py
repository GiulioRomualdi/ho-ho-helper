"""Reading and writing of the TOML files used by ho-ho-helper."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomli_w

Pair = tuple[str, str]


class ConfigError(ValueError):
    """Raised when the participants file is invalid."""


@dataclass(frozen=True)
class GiftSettings:
    max_budget: int | float | None = None
    currency: str | None = None


@dataclass(frozen=True)
class Config:
    participants: list[str]
    constraints: set[Pair] = field(default_factory=set)
    emails: dict[str, str] = field(default_factory=dict)
    gift: GiftSettings = field(default_factory=GiftSettings)


def load_config(path: str | Path) -> Config:
    """Read and validate a participants file.

    Couples are expanded to two directed constraints (nobody in a couple gives
    a gift to the other), direct constraints are kept as they are
    (``[a, b]`` means that ``a`` cannot give a gift to ``b``).
    """
    with open(path, "rb") as file:
        data = tomllib.load(file)
    return parse_config(data)


def parse_config(data: dict[str, Any]) -> Config:
    participants_section = _table(data, "participants")
    names = participants_section.get("names")
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise ConfigError("'participants.names' must be a list of names.")
    names = [n.strip() for n in names]
    if any(not n for n in names):
        raise ConfigError("Participant names cannot be empty.")
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise ConfigError(f"Duplicate participant names: {', '.join(duplicates)}")
    known = set(names)

    constraints_section = _table(data, "constraints", required=False)
    couples = _pairs(constraints_section, "couples", known)
    direct = _pairs(constraints_section, "direct_constraints", known)
    constraints = {(a, b) for a, b in couples} | {(b, a) for a, b in couples}
    constraints |= set(direct)

    emails = participants_section.get("emails", {})
    if not isinstance(emails, dict) or not all(
        isinstance(v, str) for v in emails.values()
    ):
        raise ConfigError("'participants.emails' must map names to email addresses.")
    _check_known(emails, known, "participants.emails")

    gift_section = _table(data, "gift", required=False)
    max_budget = gift_section.get("max_budget")
    if max_budget is not None and (
        isinstance(max_budget, bool) or not isinstance(max_budget, int | float)
    ):
        raise ConfigError("'gift.max_budget' must be a number.")
    currency = gift_section.get("currency")
    if currency is not None and not isinstance(currency, str):
        raise ConfigError("'gift.currency' must be a string.")

    return Config(
        participants=names,
        constraints=constraints,
        emails=dict(emails),
        gift=GiftSettings(max_budget=max_budget, currency=currency),
    )


def read_assignments(path: str | Path) -> dict[str, str]:
    """Read an assignments file previously written by :func:`write_assignments`."""
    with open(path, "rb") as file:
        data = tomllib.load(file)
    assignments = data.get("assignments")
    if not isinstance(assignments, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in assignments.items()
    ):
        raise ConfigError(f"{path} does not contain a valid [assignments] table.")
    return assignments


def write_assignments(path: str | Path, assignments: dict[str, str]) -> None:
    """Write the Secret Santa assignments to a TOML file."""
    with open(path, "wb") as file:
        tomli_w.dump({"assignments": dict(sorted(assignments.items()))}, file)


def _table(data: dict[str, Any], key: str, required: bool = True) -> dict[str, Any]:
    value = data.get(key)
    if value is None:
        if required:
            raise ConfigError(f"Missing [{key}] section.")
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"'{key}' must be a table.")
    return value


def _pairs(section: dict[str, Any], key: str, known: set[str]) -> list[Pair]:
    raw = section.get(key, [])
    if not isinstance(raw, list):
        raise ConfigError(f"'constraints.{key}' must be a list of pairs.")
    pairs: list[Pair] = []
    for item in raw:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not all(isinstance(n, str) for n in item)
        ):
            raise ConfigError(
                f"Every entry of 'constraints.{key}' must be a pair of names, "
                f"got {item!r}."
            )
        a, b = (n.strip() for n in item)
        if a == b:
            raise ConfigError(f"Invalid pair in 'constraints.{key}': {item!r}.")
        pairs.append((a, b))
    _check_known([n for pair in pairs for n in pair], known, f"constraints.{key}")
    return pairs


def _check_known(names: Any, known: set[str], where: str) -> None:
    unknown = sorted(set(names) - known)
    if unknown:
        raise ConfigError(
            f"Unknown participant(s) in '{where}': {', '.join(unknown)}. "
            "Check for typos: names must match 'participants.names' exactly."
        )
