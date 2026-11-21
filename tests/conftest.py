import smtplib
from pathlib import Path
from typing import ClassVar

import pytest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


class FakeSMTP:
    """In-memory SMTP server; ``failures`` maps a recipient to errors to raise."""

    instances: ClassVar[list["FakeSMTP"]] = []
    failures: ClassVar[dict[str, list[Exception]]] = {}
    connect_errors: ClassVar[list[Exception]] = []
    login_error: ClassVar[Exception | None] = None

    def __init__(self, server, port, timeout=None):
        if FakeSMTP.connect_errors:
            raise FakeSMTP.connect_errors.pop(0)
        self.server, self.port = server, port
        self.sent = []
        self.tls = False
        self.credentials = None
        self.closed = False
        FakeSMTP.instances.append(self)

    def starttls(self, context=None):
        self.tls = True

    def login(self, user, password):
        if FakeSMTP.login_error is not None:
            raise FakeSMTP.login_error
        self.credentials = (user, password)

    def send_message(self, message):
        errors = FakeSMTP.failures.get(message["To"])
        if errors:
            raise errors.pop(0)
        self.sent.append(message)

    def quit(self):
        self.closed = True

    def close(self):
        self.closed = True

    @classmethod
    def delivered(cls):
        """Addresses of all the emails delivered through the fake server."""
        return [m["To"] for server in cls.instances for m in server.sent]


@pytest.fixture
def fake_smtp(monkeypatch):
    FakeSMTP.instances = []
    FakeSMTP.failures = {}
    FakeSMTP.connect_errors = []
    FakeSMTP.login_error = None
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    return FakeSMTP
