"""Command line interface of ho-ho-helper."""

from __future__ import annotations

import argparse
import getpass
import random
import smtplib
import sys
from collections.abc import Sequence
from pathlib import Path

from ho_ho_helper.config import Pair, load_config, read_assignments, write_assignments
from ho_ho_helper.emailer import DEFAULT_SMTP_PORT, DEFAULT_SMTP_SERVER, send_emails
from ho_ho_helper.secret_santa import NoValidAssignmentError, secret_santa

DESCRIPTION = """\
🎅 Ho Ho Ho! Welcome to the Secret Santa Helper! 🎁

Provide a TOML file with your participants and constraints, and let the elves
do the work! 🧝 Every valid arrangement is equally likely, the assignments are
saved to a TOML file and, optionally, delivered via email 📬.
"""


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
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("assignments.toml"),
        help="output file with the assignments (default: %(default)s)",
    )
    parser.add_argument(
        "-p",
        "--previous",
        type=Path,
        action="append",
        default=[],
        metavar="FILE",
        help="assignments file of a previous edition: nobody gets the same person "
        "again. Can be given multiple times.",
    )
    parser.add_argument(
        "--single-cycle",
        action="store_true",
        help="make the gifts form a single loop through all the participants "
        "(A -> B -> C -> ... -> A)",
    )
    parser.add_argument(
        "-e", "--email", action="store_true", help="send emails to the participants"
    )
    parser.add_argument(
        "--smtp-server",
        default=DEFAULT_SMTP_SERVER,
        help="SMTP server used to send emails (default: %(default)s)",
    )
    parser.add_argument(
        "--smtp-port",
        type=int,
        default=DEFAULT_SMTP_PORT,
        help="SMTP port, STARTTLS is used (default: %(default)s)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="seed for a reproducible draw (for testing only: by default the "
        "operating system's entropy source is used)",
    )
    parser.add_argument(
        "--force", action="store_true", help="overwrite the output file if it exists"
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


def run(args: argparse.Namespace) -> None:
    if args.output.exists() and not args.force:
        raise FileExistsError(
            f"{args.output} already exists. Use another --output (for instance "
            f"'assignments-YEAR.toml') or pass --force to overwrite it."
        )

    config = load_config(args.file)
    if args.email:
        missing = [p for p in config.participants if p not in config.emails]
        if missing:
            raise ValueError(f"Missing email address for: {', '.join(missing)}")

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
        sender_email = input("Enter your email address: ")
        sender_password = getpass.getpass("Enter your email (app) password: ")
        send_emails(
            assignments,
            config.emails,
            sender_email,
            sender_password,
            config.gift,
            smtp_server=args.smtp_server,
            smtp_port=args.smtp_port,
            on_sent=lambda giver, email: print(f"📨 Email sent to {giver} ({email})"),
        )
        print("✅ All emails sent!")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    print("Welcome to the ho-ho-helper! A Secret Santa organizer 🎅🎁🎄")
    print(f"Reading participants from {args.file}")
    for file in args.previous:
        print(f"Avoiding the assignments in {file}")
    print(f"Saving assignments to {args.output}")
    print(f"Single gift loop: {'Yes' if args.single_cycle else 'No'}")
    print(f"Sending emails: {'Yes' if args.email else 'No'}")

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
    except smtplib.SMTPException as error:
        print(f"❌ Error sending emails: {error}", file=sys.stderr)
        return 1
    except (ValueError, OSError) as error:
        print(f"❌ Error: {error}", file=sys.stderr)
        return 1

    print("Happy Holidays! 🎉🎄🎁")
    return 0


if __name__ == "__main__":
    sys.exit(main())
