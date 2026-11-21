import smtplib

import pytest

from ho_ho_helper.config import read_assignments, write_assignments
from ho_ho_helper.main import main

PARTICIPANTS_TOML = """\
[participants]
names = ["Alice", "Bob", "Charlie", "Diana", "Eve"]

[participants.emails]
Alice = "alice@example.com"
Bob = "bob@example.com"
Charlie = "charlie@example.com"
Diana = "diana@example.com"
Eve = "eve@example.com"

[gift]
max_budget = 10
currency = "EUR"

[constraints]
couples = [["Alice", "Bob"], ["Diana", "Eve"]]
direct_constraints = [["Alice", "Charlie"]]
"""


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "participants.toml").write_text(PARTICIPANTS_TOML)
    return tmp_path


def test_draw_and_save(workdir):
    assert main(["--yes"]) == 0
    assignments = read_assignments(workdir / "assignments.toml")
    assert sorted(assignments) == ["Alice", "Bob", "Charlie", "Diana", "Eve"]
    assert assignments["Alice"] not in {"Alice", "Bob", "Charlie"}


def test_output_is_not_overwritten_without_force(workdir, capsys):
    write_assignments(workdir / "assignments.toml", {"Alice": "Eve"})
    assert main(["--yes"]) == 1
    assert "already exists" in capsys.readouterr().err
    assert read_assignments(workdir / "assignments.toml") == {"Alice": "Eve"}

    assert main(["--yes", "--force"]) == 0
    assert len(read_assignments(workdir / "assignments.toml")) == 5


def test_previous_assignments_are_avoided(workdir):
    assert main(["--yes", "-o", "2025.toml", "--seed", "0"]) == 0
    last_year = read_assignments(workdir / "2025.toml")
    for seed in range(30):
        output = f"2026-{seed}.toml"
        args = ["--yes", "-o", output, "-p", "2025.toml", "--seed", str(seed)]
        assert main(args) == 0
        this_year = read_assignments(workdir / output)
        assert not set(this_year.items()) & set(last_year.items())


def test_too_many_previous_files_give_a_helpful_error(workdir, capsys):
    previous = []
    # Keep forbidding last year's pairs until the draw becomes impossible.
    for year in range(10):
        output = f"{year}.toml"
        previous_args = [arg for p in previous for arg in ("-p", p)]
        code = main(["--yes", "-o", output, *previous_args])
        if code != 0:
            assert "fewer --previous" in capsys.readouterr().err
            return
        previous.append(output)
    pytest.fail("the draw never became impossible")


def test_single_cycle_option(workdir):
    from ho_ho_helper.secret_santa import is_single_cycle

    assert main(["--yes", "--single-cycle"]) == 0
    assert is_single_cycle(read_assignments(workdir / "assignments.toml"))


def test_end_of_input_at_prompt_aborts_cleanly(workdir, monkeypatch, capsys):
    def eof(prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    assert main([]) == 130
    assert "Aborted" in capsys.readouterr().err
    assert not (workdir / "assignments.toml").exists()


def test_missing_file_returns_error(workdir, capsys):
    assert main(["--yes", "-f", "nope.toml"]) == 1
    assert "File not found: nope.toml" in capsys.readouterr().err
    assert not (workdir / "assignments.toml").exists()


def test_invalid_config_returns_error(workdir, capsys):
    (workdir / "participants.toml").write_text(
        '[participants]\nnames = ["Alice", "Bob"]\n'
        '[constraints]\ncouples = [["Alice", "Bobby"]]\n'
    )
    assert main(["--yes"]) == 1
    assert "Bobby" in capsys.readouterr().err


def test_email_requires_every_address(workdir, capsys):
    (workdir / "participants.toml").write_text(
        '[participants]\nnames = ["Alice", "Bob"]\n'
        '[participants.emails]\nAlice = "a@x.org"\n'
    )
    assert main(["--yes", "--email"]) == 1
    assert "Missing email address for: Bob" in capsys.readouterr().err
    assert not (workdir / "assignments.toml").exists()


def test_email_failure_is_reported(workdir, monkeypatch, capsys):
    def broken_smtp(*args, **kwargs):
        raise smtplib.SMTPConnectError(421, b"unavailable")

    monkeypatch.setattr(smtplib, "SMTP", broken_smtp)
    monkeypatch.setattr("builtins.input", lambda prompt="": "santa@x.org")
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "secret")
    assert main(["--yes", "--email"]) == 1
    captured = capsys.readouterr()
    assert "Error sending emails" in captured.err
    assert "All emails sent" not in captured.out
    # The draw is saved anyway, so emails can be resent manually.
    assert (workdir / "assignments.toml").exists()
