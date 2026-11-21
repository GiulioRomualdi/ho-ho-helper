"""Delivery of the Secret Santa assignments via email."""

from __future__ import annotations

import smtplib
import ssl
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from email.message import EmailMessage

from ho_ho_helper.config import GiftSettings

DEFAULT_SMTP_SERVER = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 587
SUBJECT = "Your Secret Santa Assignment 🎅"
HIDDEN_RECEIVER = "🤫 (hidden)"


@dataclass(frozen=True)
class SmtpSettings:
    sender: str
    password: str
    server: str = DEFAULT_SMTP_SERVER
    port: int = DEFAULT_SMTP_PORT
    timeout: float = 30.0


@dataclass
class DeliveryReport:
    sent: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)


def budget_line(gift: GiftSettings) -> str:
    if gift.max_budget is None:
        return ""
    amount = gift.max_budget
    if isinstance(amount, float):
        amount = f"{amount:g}"
    currency = f" {gift.currency}" if gift.currency else ""
    return f"💸 Remember: the maximum budget is {amount}{currency}."


def build_body(giver: str, receiver: str, gift: GiftSettings | None = None) -> str:
    budget = budget_line(gift or GiftSettings())
    return (
        f"🎅 Ho Ho Ho, {giver}! 🎁\n\n"
        f"You have been chosen as the Secret Santa for... 🥁 *{receiver}*! 🎉\n\n"
        "✨ Make sure to prepare a thoughtful gift 🎁 "
        "and spread the holiday cheer! 🎄\n"
        + (f"{budget}\n" if budget else "")
        + "\nWishing you a season full of joy, laughter, and surprises! ❄️\n\n"
        "Happy Holidays! 🕊️\n\n"
        "    Your Secret Santa Organizer 🎅\n"
    )


def build_message(
    sender: str,
    recipient: str,
    giver: str,
    receiver: str,
    gift: GiftSettings | None = None,
    subject: str = SUBJECT,
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(build_body(giver, receiver, gift))
    return message


def connect(smtp: SmtpSettings) -> smtplib.SMTP:
    """Open an authenticated SMTP connection (STARTTLS)."""
    server = smtplib.SMTP(smtp.server, smtp.port, timeout=smtp.timeout)
    try:
        server.starttls(context=ssl.create_default_context())
        server.login(smtp.sender, smtp.password)
    except BaseException:
        _close(server)
        raise
    return server


def send_test_email(
    recipient: str, smtp: SmtpSettings, gift: GiftSettings | None = None
) -> None:
    """Send a sample email that does not reveal any assignment."""
    message = build_message(
        smtp.sender,
        recipient,
        "Test",
        HIDDEN_RECEIVER,
        gift,
        subject=f"[TEST] {SUBJECT}",
    )
    server = connect(smtp)
    try:
        server.send_message(message)
    finally:
        _close(server)


def send_emails(
    assignments: dict[str, str],
    emails: dict[str, str],
    smtp: SmtpSettings,
    gift: GiftSettings | None = None,
    *,
    skip: Iterable[str] = (),
    retries: int = 3,
    retry_delay: float = 2.0,
    on_sent: Callable[[str, str], None] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> DeliveryReport:
    """Send every giver an email with the name of the person they gift.

    A failure for one recipient does not stop the others: temporary errors
    (disconnections, timeouts, 4xx replies) are retried with a new connection,
    permanent ones are recorded in the returned report. ``on_sent`` is called
    right after each successful delivery, so progress can be saved.

    Raises:
        ValueError: If a giver has no email address.
        smtplib.SMTPAuthenticationError: If the credentials are rejected.
        smtplib.SMTPException, OSError: If the server cannot be reached.
    """
    sleep = sleep or time.sleep
    skip = set(skip)
    pending = [giver for giver in assignments if giver not in skip]
    missing = sorted(giver for giver in pending if giver not in emails)
    if missing:
        raise ValueError(f"Missing email address for: {', '.join(missing)}")

    report = DeliveryReport()
    server: smtplib.SMTP | None = None
    try:
        for giver in pending:
            recipient = emails[giver]
            message = build_message(
                smtp.sender, recipient, giver, assignments[giver], gift
            )
            for attempt in range(retries + 1):
                if server is None:
                    try:
                        server = connect(smtp)
                    except smtplib.SMTPAuthenticationError:
                        raise
                    except (smtplib.SMTPException, OSError):
                        # The server is unreachable: retrying for every other
                        # recipient would only waste time.
                        if attempt == retries:
                            raise
                        sleep(retry_delay * (attempt + 1))
                        continue
                try:
                    server.send_message(message)
                except smtplib.SMTPResponseException as error:
                    if not 400 <= error.smtp_code < 500 or attempt == retries:
                        report.failed[giver] = _describe(error)
                        break
                except smtplib.SMTPRecipientsRefused as error:
                    codes = [code for code, _ in error.recipients.values()]
                    temporary = bool(codes) and all(400 <= c < 500 for c in codes)
                    if not temporary or attempt == retries:
                        report.failed[giver] = _describe(error)
                        break
                except (smtplib.SMTPException, OSError) as error:
                    if attempt == retries:
                        report.failed[giver] = _describe(error)
                        break
                else:
                    report.sent.append(giver)
                    if on_sent is not None:
                        on_sent(giver, recipient)
                    break
                server = _close(server)
                sleep(retry_delay * (attempt + 1))
    finally:
        _close(server)
    return report


def _close(server: smtplib.SMTP | None) -> None:
    if server is None:
        return None
    try:
        server.quit()
    except (smtplib.SMTPException, OSError):
        server.close()
    return None


def _describe(error: Exception) -> str:
    if isinstance(error, smtplib.SMTPResponseException):
        detail = error.smtp_error
        if isinstance(detail, bytes):
            detail = detail.decode(errors="replace")
        return f"{error.smtp_code} {detail}"
    if isinstance(error, smtplib.SMTPRecipientsRefused):
        return f"recipient refused: {error.recipients}"
    return str(error) or type(error).__name__
