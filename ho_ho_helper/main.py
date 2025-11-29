from ho_ho_helper.secret_santa import secret_santa
from ho_ho_helper.utils import read_toml_file, write_toml_file
from ho_ho_helper.emailer import send_emails
import argparse
import getpass


def main():
    parser = argparse.ArgumentParser(
        description="🎅 Ho Ho Ho! Welcome to the Secret Santa Helper! 🎁\n"
        "This magical tool takes the hassle out of organizing your Secret Santa 🎄. "
        "Just provide a TOML file with your participants and constraints, and let the elves do the work! 🧝‍♂️\n\n"
        "✨ Features:\n"
        "- Assigns each participant a Secret Santa with love ❤️ and logic 🧠.\n"
        "- Saves the assignments neatly to a TOML file 📄.\n"
        "- Optional: Delivers assignments via email! 📬 (No reindeer required 🦌).\n\n"
        "Ready to spread the holiday cheer? Let's go! 🎉"
    )

    parser.add_argument(
        "--file",
        "-f",
        type=str,
        help="Path to the participants file. If not provided the default one is used ('./participants.toml')",
        default="participants.toml",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Path to the output file. If not provided the default one is used ('./assignments.toml')",
        default="assignments.toml",
    )
    parser.add_argument(
        "--email",
        "-e",
        action="store_true",
        help="Send emails to participants",
        default=False,
    )
    args = parser.parse_args()

    input_file = args.file
    output_file = args.output

    print(f"Welcome to the ho-ho-helper! A Secret Santa organizer 🎅🎁🎄")
    print(f"Reading participants from {input_file}...")
    print(f"Saving assignments to {output_file}...")
    print(f"Sending emails: {'Yes' if args.email else 'No'}")
    input("Press Enter to continue...")

    try:
        participants, constraints, emails, gift_settings = read_toml_file(input_file)
        result = secret_santa(participants, constraints)

        # Save the result to a TOML file
        write_toml_file(output_file, result)
        print(f"Assignments saved to {output_file}")

        # Send emails if email addresses are provided
        if emails and args.email:
            sender_email = input("Enter your email address: ")
            sender_password = getpass.getpass("Enter your email password: ")
            send_emails(
                result,
                emails,
                sender_email,
                sender_password,
                gift_settings,
            )
            print("Emails sent successfully!")

    except ValueError as e:
        print(f"Error: {e}")
    except FileNotFoundError:
        print(f"File not found: {input_file}")

    print("Happy Holidays! 🎉🎄🎁")


if __name__ == "__main__":
    main()
