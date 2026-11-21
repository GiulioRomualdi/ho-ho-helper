import smtplib

import pytest

from ho_ho_helper.config import GiftSettings
from ho_ho_helper.emailer import (
    HIDDEN_RECEIVER,
    SmtpSettings,
    build_body,
    build_message,
    send_emails,
    send_test_email,
)

SMTP = SmtpSettings(sender="santa@x.org", password="secret", server="smtp.x.org")
ASSIGNMENTS = {"Alice": "Bob", "Bob": "Carol", "Carol": "Alice"}
EMAILS = {"Alice": "alice@x.org", "Bob": "bob@x.org", "Carol": "carol@x.org"}


def send(**kwargs):
    kwargs.setdefault("sleep", lambda seconds: None)
    return send_emails(ASSIGNMENTS, EMAILS, SMTP, GiftSettings(10, "EUR"), **kwargs)


@pytest.mark.parametrize(
    ("gift", "expected"),
    [
        (GiftSettings(10, "EUR"), "maximum budget is 10 EUR."),
        (GiftSettings(12.5, "USD"), "maximum budget is 12.5 USD."),
        (GiftSettings(20, None), "maximum budget is 20."),
        (GiftSettings(0, "EUR"), "maximum budget is 0 EUR."),
    ],
)
def test_budget_is_mentioned(gift, expected):
    assert expected in build_body("Alice", "Bob", gift)


def test_no_budget_line_without_budget():
    body = build_body("Alice", "Bob", GiftSettings(None, "EUR"))
    assert "budget" not in body
    assert "Ho Ho Ho, Alice!" in body
    assert "*Bob*" in body


def test_message_headers_and_unicode():
    message = build_message("santa@x.org", "zoe@x.org", "Zoë", "Bob")
    assert message["From"] == "santa@x.org"
    assert message["To"] == "zoe@x.org"
    assert "Zoë" in message.get_content()


def test_send_emails(fake_smtp):
    sent = []
    report = send(on_sent=lambda giver, email: sent.append((giver, email)))
    (server,) = fake_smtp.instances
    assert server.server == "smtp.x.org"
    assert server.tls
    assert server.credentials == ("santa@x.org", "secret")
    assert server.closed
    assert fake_smtp.delivered() == ["alice@x.org", "bob@x.org", "carol@x.org"]
    assert "*Bob*" in server.sent[0].get_content()
    assert sent == [(g, EMAILS[g]) for g in ASSIGNMENTS]
    assert report.sent == list(ASSIGNMENTS)
    assert report.failed == {}


def test_skip_already_notified(fake_smtp):
    report = send(skip={"Alice", "Carol"})
    assert fake_smtp.delivered() == ["bob@x.org"]
    assert report.sent == ["Bob"]


def test_missing_email_raises_before_connecting(fake_smtp):
    with pytest.raises(ValueError, match="Bob"):
        send_emails(ASSIGNMENTS, {"Alice": "a@x.org", "Carol": "c@x.org"}, SMTP)
    assert fake_smtp.instances == []


def test_transient_errors_are_retried_with_a_new_connection(fake_smtp):
    fake_smtp.failures["bob@x.org"] = [
        smtplib.SMTPServerDisconnected("connection lost"),
        smtplib.SMTPResponseException(421, b"try again later"),
    ]
    report = send()
    assert report.sent == list(ASSIGNMENTS)
    assert sorted(fake_smtp.delivered()) == sorted(EMAILS.values())
    assert len(fake_smtp.instances) == 3


def test_temporary_recipient_refusal_is_retried(fake_smtp):
    fake_smtp.failures["bob@x.org"] = [
        smtplib.SMTPRecipientsRefused({"bob@x.org": (450, b"try again later")})
    ]
    report = send()
    assert report.sent == list(ASSIGNMENTS)
    assert report.failed == {}


def test_permanent_failure_does_not_stop_the_others(fake_smtp):
    fake_smtp.failures["bob@x.org"] = [
        smtplib.SMTPRecipientsRefused({"bob@x.org": (550, b"no such user")})
    ]
    report = send()
    assert report.sent == ["Alice", "Carol"]
    assert list(report.failed) == ["Bob"]
    assert fake_smtp.delivered() == ["alice@x.org", "carol@x.org"]


def test_gives_up_after_the_retries(fake_smtp):
    fake_smtp.failures["bob@x.org"] = [TimeoutError("timed out")] * 10
    delays = []
    report = send(retries=2, sleep=delays.append)
    assert report.sent == ["Alice", "Carol"]
    assert report.failed == {"Bob": "timed out"}
    assert delays == [2.0, 4.0]


def test_unreachable_server_aborts(fake_smtp):
    fake_smtp.connect_errors = [ConnectionRefusedError("refused")] * 10
    with pytest.raises(ConnectionRefusedError):
        send(retries=2)
    assert fake_smtp.instances == []


def test_authentication_error_aborts(fake_smtp):
    fake_smtp.login_error = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    with pytest.raises(smtplib.SMTPAuthenticationError):
        send()
    assert all(server.closed for server in fake_smtp.instances)


def test_test_email_hides_the_match(fake_smtp):
    send_test_email("me@x.org", SMTP, GiftSettings(10, "EUR"))
    ((message,),) = [server.sent for server in fake_smtp.instances]
    assert message["To"] == "me@x.org"
    assert message["Subject"].startswith("[TEST]")
    assert HIDDEN_RECEIVER in message.get_content()
