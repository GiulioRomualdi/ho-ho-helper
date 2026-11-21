"""Delivery of the Secret Santa assignments via email."""

from __future__ import annotations

import smtplib
import ssl
from collections.abc import Callable
from email.message import EmailMessage

from ho_ho_helper.config import GiftSettings

DEFAULT_SMTP_SERVER = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 587
SUBJECT = "Your Secret Santa Assignment 🎅"


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
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = SUBJECT
    message.set_content(build_body(giver, receiver, gift))
    return message


def send_emails(
    assignments: dict[str, str],
    emails: dict[str, str],
    sender_email: str,
    sender_password: str,
    gift: GiftSettings | None = None,
    *,
    smtp_server: str = DEFAULT_SMTP_SERVER,
    smtp_port: int = DEFAULT_SMTP_PORT,
    on_sent: Callable[[str, str], None] | None = None,
) -> None:
    """Send every giver an email with the name of the person they gift.

    Raises:
        ValueError: If a giver has no email address.
        smtplib.SMTPException, OSError: If the connection or delivery fails.
    """
    missing = sorted(giver for giver in assignments if giver not in emails)
    if missing:
        raise ValueError(f"Missing email address for: {', '.join(missing)}")

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls(context=ssl.create_default_context())
        server.login(sender_email, sender_password)
        for giver, receiver in assignments.items():
            recipient = emails[giver]
            server.send_message(
                build_message(sender_email, recipient, giver, receiver, gift)
            )
            if on_sent is not None:
                on_sent(giver, recipient)
