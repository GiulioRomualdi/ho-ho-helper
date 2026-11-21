"""Command line interface of ho-ho-helper."""

from __future__ import annotations

import argparse
import getpass
import random
import smtplib
import sys
from collections.abc import Sequence
from pathlib import Path

from ho_ho_helper.config import (
    Config,
    Pair,
    load_config,
    read_assignments,
    read_emails_sent,
    write_assignments,
)
from ho_ho_helper.emailer import (
    DEFAULT_SMTP_PORT,
    DEFAULT_SMTP_SERVER,
    HIDDEN_RECEIVER,
    SmtpSettings,
    build_body,
    send_emails,
    send_test_email,
)
from ho_ho_helper.secret_santa import NoValidAssignmentError, secret_santa

DESCRIPTION = """\
🎅 Ho Ho Ho! Welcome to the Secret Santa Helper! 🎁

Provide a TOML file with your participants and constraints, and let the elves
do the work! 🧝 Every valid arrangement is equally likely, the assignments are
saved to a TOML file and, optionally, delivered via email 📬.
"""


class DeliveryError(Exception):
    """Raised when some emails could not be delivered."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ho-ho-helper",
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        default=Path("participants.toml"),
        help="participants file (default: %(default)s)",
    )

    draw = parser.add_argument_group("draw")
    draw.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("assignments.toml"),
        help="output file with the assignments (default: %(default)s)",
    )
    draw.add_argument(
        "-p",
        "--previous",
        type=Path,
        action="append",
        default=[],
        metavar="FILE",
        help="assignments file of a previous edition: nobody gets the same person "
        "again. Can be given multiple times.",
    )
    draw.add_argument(
        "--single-cycle",
        action="store_true",
        help="make the gifts form a single loop through all the participants "
        "(A -> B -> C -> ... -> A)",
    )
    draw.add_argument(
        "--seed",
        type=int,
        help="seed for a reproducible draw (for testing only: by default the "
        "operating system's entropy source is used)",
    )

    email = parser.add_argument_group("email")
    mode = email.add_mutually_exclusive_group()
    mode.add_argument(
        "-e",
        "--email",
        action="store_true",
        help="after the draw, send emails to the participants",
    )
    mode.add_argument(
        "--send",
        type=Path,
        metavar="FILE",
        help="do not draw: send the emails for an existing assignments file, "
        "skipping who already received theirs",
    )
    mode.add_argument(
        "--test-to",
        metavar="ADDRESS",
        help="only send one sample email (with the match hidden) to ADDRESS, "
        "to check that sending works",
    )
    email.add_argument(
        "--dry-run",
        action="store_true",
        help="show which emails would be sent, without sending them",
    )
    email.add_argument(
        "--smtp-server",
        default=DEFAULT_SMTP_SERVER,
        help="SMTP server used to send emails (default: %(default)s)",
    )
    email.add_argument(
        "--smtp-port",
        type=int,
        default=DEFAULT_SMTP_PORT,
        help="SMTP port, STARTTLS is used (default: %(default)s)",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite the output file if it exists; with --send, email again "
        "also who already received the assignment",
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="do not ask for confirmation"
    )
    return parser


def previous_constraints(
    files: Sequence[Path], participants: Sequence[str]
) -> set[Pair]:
    """Forbid every (giver, receiver) pair that already happened in the files."""
    known = set(participants)
    return {
        (giver, receiver)
        for file in files
        for giver, receiver in read_assignments(file).items()
        if giver in known and receiver in known
    }


def draw(args: argparse.Namespace, config: Config) -> None:
    if args.output.exists() and not args.force:
        raise FileExistsError(
            f"{args.output} already exists. Use another --output (for instance "
            f"'assignments-YEAR.toml'), pass --force to overwrite it, or use "
            f"--send {args.output} to (re)send its emails."
        )
    if args.email:
        _check_emails(config, config.participants)

    constraints = config.constraints | previous_constraints(
        args.previous, config.participants
    )
    rng = random.Random(args.seed) if args.seed is not None else None
    try:
        assignments = secret_santa(
            config.participants,
            constraints,
            single_cycle=args.single_cycle,
            rng=rng,
        )
    except NoValidAssignmentError as error:
        if args.previous:
            raise NoValidAssignmentError(
                f"{error} Avoiding the previous assignments may be too restrictive: "
                "try with fewer --previous files."
            ) from error
        raise

    write_assignments(args.output, assignments)
    print(f"✅ Assignments saved to {args.output}")
    if args.email:
        deliver(args, config, args.output)


def deliver(args: argparse.Namespace, config: Config, path: Path) -> None:
    """Email the assignments stored in ``path``, recording who received them."""
    assignments = read_assignments(path)
    participants = set(config.participants)
    unknown = sorted(
        (set(assignments) ^ participants) | (set(assignments.values()) - participants)
    )
    if unknown:
        raise ValueError(
            f"{path} does not match {args.file}: check the names {', '.join(unknown)}"
        )
    emails_sent = read_emails_sent(path)
    # Someone counts as notified only if the address did not change since.
    already_sent = set()
    if not args.force:
        already_sent = {
            giver
            for giver, address in emails_sent.items()
            if address == config.emails.get(giver)
        }
    pending = [giver for giver in assignments if giver not in already_sent]
    _check_emails(config, pending)

    if not pending:
        print("📭 Everybody already received their email (use --force to resend).")
        return
    if already_sent:
        print(f"⏭️  Skipping {len(already_sent)} participant(s) already notified.")
    for giver in pending:
        if not args.force and giver in emails_sent:
            print(
                f"📮 {giver}'s address changed ({emails_sent[giver]} -> "
                f"{config.emails[giver]}): sending again."
            )

    if args.dry_run:
        print(f"🧪 Dry run: {len(pending)} email(s) would be sent to:")
        for giver in pending:
            print(f"   - {giver} <{config.emails[giver]}>")
        print("\nExample (the match is hidden):\n")
        print(build_body(pending[0], HIDDEN_RECEIVER, config.gift))
        return

    smtp = _ask_credentials(args)

    def on_sent(giver: str, address: str) -> None:
        emails_sent[giver] = address
        write_assignments(path, assignments, emails_sent)
        print(f"📨 Email sent to {giver} ({address})")

    resume_hint = (
        "Fix the problem and send the missing emails (without a new draw) with:\n"
        f"   ho-ho-helper -f {args.file} --send {path}"
    )
    try:
        report = send_emails(
            {giver: assignments[giver] for giver in pending},
            config.emails,
            smtp,
            config.gift,
            on_sent=on_sent,
        )
    except smtplib.SMTPAuthenticationError:
        raise
    except (smtplib.SMTPException, OSError) as error:
        raise DeliveryError(
            f"❌ Error sending emails: {error}\n"
            f"{len(emails_sent)}/{len(assignments)} participants have their email. "
            f"{resume_hint}"
        ) from error
    if report.failed:
        print(
            f"\n⚠️  {len(report.sent)}/{len(pending)} email(s) sent. Failed:",
            file=sys.stderr,
        )
        for giver, reason in report.failed.items():
            print(f"   - {giver} <{config.emails[giver]}>: {reason}", file=sys.stderr)
        raise DeliveryError(resume_hint)
    print(f"✅ All {len(report.sent)} emails sent!")


def test_email(args: argparse.Namespace, config: Config) -> None:
    if args.dry_run:
        print(f"🧪 Dry run: a sample email would be sent to {args.test_to}:\n")
        print(build_body("Test", HIDDEN_RECEIVER, config.gift))
        return
    send_test_email(args.test_to, _ask_credentials(args), config.gift)
    print(f"✅ Test email sent to {args.test_to}: check your inbox (and spam).")


def run(args: argparse.Namespace) -> None:
    config = load_config(args.file)
    if args.test_to:
        test_email(args, config)
    elif args.send:
        deliver(args, config, args.send)
    else:
        draw(args, config)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if (args.send or args.test_to) and (
        args.previous or args.single_cycle or args.seed is not None
    ):
        parser.error("--previous, --single-cycle and --seed are only used to draw")
    if args.dry_run and not (args.email or args.send or args.test_to):
        parser.error("--dry-run needs --email, --send or --test-to")

    print("Welcome to the ho-ho-helper! A Secret Santa organizer 🎅🎁🎄")
    print(f"Reading participants from {args.file}")
    if args.test_to:
        print(f"Sending a test email to {args.test_to}")
    elif args.send:
        print(f"Sending the emails for the assignments in {args.send}")
    else:
        for file in args.previous:
            print(f"Avoiding the assignments in {file}")
        print(f"Saving assignments to {args.output}")
        print(f"Single gift loop: {'Yes' if args.single_cycle else 'No'}")
        print(f"Sending emails: {'Yes' if args.email else 'No'}")
    if args.dry_run:
        print("Dry run: no email will be sent")

    try:
        if not args.yes:
            input("Press Enter to continue (Ctrl+C to abort)...")
        run(args)
    except (KeyboardInterrupt, EOFError):
        print("\nAborted.", file=sys.stderr)
        return 130
    except FileNotFoundError as error:
        print(f"❌ File not found: {error.filename}", file=sys.stderr)
        return 1
    except smtplib.SMTPAuthenticationError as error:
        print(
            f"❌ Login refused by the SMTP server ({error.smtp_code}). With Gmail "
            "you need an App Password, not your normal password (see the README).",
            file=sys.stderr,
        )
        return 1
    except DeliveryError as error:
        print(error, file=sys.stderr)
        return 1
    except smtplib.SMTPException as error:
        print(f"❌ Error sending emails: {error}", file=sys.stderr)
        return 1
    except (ValueError, OSError) as error:
        print(f"❌ Error: {error}", file=sys.stderr)
        return 1

    print("Happy Holidays! 🎉🎄🎁")
    return 0


def _check_emails(config: Config, givers: Sequence[str]) -> None:
    missing = [giver for giver in givers if giver not in config.emails]
    if missing:
        raise ValueError(f"Missing email address for: {', '.join(missing)}")


def _ask_credentials(args: argparse.Namespace) -> SmtpSettings:
    sender = input("Enter your email address: ").strip()
    password = getpass.getpass("Enter your email (app) password: ")
    return SmtpSettings(
        sender=sender,
        password=password,
        server=args.smtp_server,
        port=args.smtp_port,
    )
