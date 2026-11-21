import smtplib
from typing import ClassVar

import pytest

from ho_ho_helper.config import GiftSettings
from ho_ho_helper.emailer import build_body, build_message, send_emails


class FakeSMTP:
    instances: ClassVar[list["FakeSMTP"]] = []

    def __init__(self, server, port):
        self.server, self.port = server, port
        self.sent = []
        self.tls = False
        self.credentials = None
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        self.tls = True

    def login(self, user, password):
        self.credentials = (user, password)

    def send_message(self, message):
        self.sent.append(message)


@pytest.fixture
def fake_smtp(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    return FakeSMTP


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
    send_emails(
        {"Alice": "Bob", "Bob": "Alice"},
        {"Alice": "alice@x.org", "Bob": "bob@x.org"},
        "santa@x.org",
        "secret",
        GiftSettings(10, "EUR"),
        smtp_server="smtp.example.org",
        smtp_port=2525,
        on_sent=lambda giver, email: sent.append((giver, email)),
    )
    (server,) = fake_smtp.instances
    assert (server.server, server.port) == ("smtp.example.org", 2525)
    assert server.tls
    assert server.credentials == ("santa@x.org", "secret")
    assert [m["To"] for m in server.sent] == ["alice@x.org", "bob@x.org"]
    assert "*Bob*" in server.sent[0].get_content()
    assert sent == [("Alice", "alice@x.org"), ("Bob", "bob@x.org")]


def test_missing_email_raises_before_connecting(fake_smtp):
    with pytest.raises(ValueError, match="Bob"):
        send_emails(
            {"Alice": "Bob", "Bob": "Alice"}, {"Alice": "alice@x.org"}, "s", "p"
        )
    assert fake_smtp.instances == []


def test_smtp_errors_are_propagated(fake_smtp, monkeypatch):
    def fail(self, user, password):
        raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

    monkeypatch.setattr(FakeSMTP, "login", fail)
    with pytest.raises(smtplib.SMTPAuthenticationError):
        send_emails({"Alice": "Bob"}, {"Alice": "a@x.org"}, "s", "p")
