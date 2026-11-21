import smtplib

import pytest

from ho_ho_helper.config import (
    read_assignments,
    read_emails_sent,
    write_assignments,
)
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


@pytest.fixture
def credentials(monkeypatch):
    """Answer the email prompts; fail if a password is asked unexpectedly."""
    prompts = []

    def fake_input(prompt=""):
        prompts.append(prompt)
        return "santa@x.org"

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "secret")
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    return prompts


def test_draw_and_email_records_delivery(workdir, fake_smtp, credentials, capsys):
    assert main(["--yes", "--email"]) == 0
    assert len(fake_smtp.delivered()) == 5
    sent = read_emails_sent(workdir / "assignments.toml")
    assert sent["Alice"] == "alice@example.com"
    assert len(sent) == 5
    assert "All 5 emails sent" in capsys.readouterr().out


def test_interrupted_delivery_can_be_resumed_without_a_new_draw(
    workdir, fake_smtp, credentials, capsys
):
    fake_smtp.failures["diana@example.com"] = [
        smtplib.SMTPRecipientsRefused({"diana@example.com": (550, b"mailbox full")})
    ]
    assert main(["--yes", "--email"]) == 1
    err = capsys.readouterr().err
    assert "4/5 email(s) sent" in err
    assert "Diana" in err
    assert "--send assignments.toml" in err
    draw = read_assignments(workdir / "assignments.toml")
    assert "Diana" not in read_emails_sent(workdir / "assignments.toml")

    fake_smtp.instances.clear()
    assert main(["--yes", "--send", "assignments.toml"]) == 0
    assert fake_smtp.delivered() == ["diana@example.com"]
    assert f"*{draw['Diana']}*" in fake_smtp.instances[0].sent[0].get_content()
    assert read_assignments(workdir / "assignments.toml") == draw
    assert len(read_emails_sent(workdir / "assignments.toml")) == 5

    fake_smtp.instances.clear()
    assert main(["--yes", "--send", "assignments.toml"]) == 0
    assert fake_smtp.delivered() == []
    assert "Everybody already received" in capsys.readouterr().out

    assert main(["--yes", "--send", "assignments.toml", "--force"]) == 0
    assert len(fake_smtp.delivered()) == 5


def test_corrected_address_is_emailed_again(workdir, fake_smtp, credentials, capsys):
    assert main(["--yes", "--email"]) == 0
    config = workdir / "participants.toml"
    config.write_text(config.read_text().replace("bob@example.com", "bob@new.org"))

    fake_smtp.instances.clear()
    assert main(["--yes", "--send", "assignments.toml"]) == 0
    assert fake_smtp.delivered() == ["bob@new.org"]
    assert "Bob's address changed" in capsys.readouterr().out
    assert read_emails_sent(workdir / "assignments.toml")["Bob"] == "bob@new.org"


def test_unreachable_server_keeps_the_draw_and_explains_how_to_resume(
    workdir, fake_smtp, credentials, capsys
):
    fake_smtp.connect_errors = [smtplib.SMTPConnectError(421, b"unavailable")] * 10
    assert main(["--yes", "--email"]) == 1
    captured = capsys.readouterr()
    assert "Error sending emails" in captured.err
    assert "--send assignments.toml" in captured.err
    assert "All 5 emails sent" not in captured.out
    assert (workdir / "assignments.toml").exists()


def test_wrong_password_gives_a_hint(workdir, fake_smtp, credentials, capsys):
    fake_smtp.login_error = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    assert main(["--yes", "--email"]) == 1
    assert "App Password" in capsys.readouterr().err


def test_dry_run_sends_nothing_and_does_not_spoil(
    workdir, fake_smtp, credentials, capsys
):
    assert main(["--yes", "--seed", "1"]) == 0
    draw = read_assignments(workdir / "assignments.toml")
    capsys.readouterr()

    assert main(["--yes", "--send", "assignments.toml", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert fake_smtp.instances == []
    assert credentials == []
    assert "alice@example.com" in out
    assert all(f"*{receiver}*" not in out for receiver in draw.values())
    assert read_emails_sent(workdir / "assignments.toml") == {}


def test_test_email(workdir, fake_smtp, credentials, capsys):
    assert main(["--yes", "--test-to", "me@x.org"]) == 0
    assert fake_smtp.delivered() == ["me@x.org"]
    assert not (workdir / "assignments.toml").exists()


def test_send_rejects_a_file_that_does_not_match(workdir, fake_smtp, capsys):
    write_assignments(workdir / "old.toml", {"Alice": "Zed", "Zed": "Alice"})
    assert main(["--yes", "--send", "old.toml"]) == 1
    assert "Zed" in capsys.readouterr().err
    assert fake_smtp.instances == []


@pytest.mark.parametrize(
    "args",
    [
        ["--send", "a.toml", "--single-cycle"],
        ["--send", "a.toml", "--email"],
        ["--test-to", "me@x.org", "-p", "a.toml"],
        ["--dry-run"],
    ],
)
def test_incompatible_options(args):
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2
