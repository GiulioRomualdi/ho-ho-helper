import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_emails(assignments, emails, sender_email, sender_password, gift_settings=None):
    """
    Sends Secret Santa assignments via email.

    Parameters:
        assignments (dict): Secret Santa assignments.
        emails (dict): Email addresses of participants (name -> email).
        sender_email (str): Sender's email address.
        sender_password (str): Sender's email password.
        gift_settings (dict, optional): Gift configuration containing max budget and currency.
    """
    subject = "Your Secret Santa Assignment"
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    gift_settings = gift_settings or {}
    max_budget = gift_settings.get("max_budget")
    currency = gift_settings.get("currency")

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)

            for giver, receiver in assignments.items():
                if giver in emails:
                    recipient_email = emails[giver]
                    message = MIMEMultipart()
                    message["From"] = sender_email
                    message["To"] = recipient_email
                    message["Subject"] = subject
                    budget_line = ""
                    if max_budget and currency:
                        budget_line = f"\n💸 Remember: the maximum budget is {max_budget} {currency}."
                    elif max_budget:
                        budget_line = (
                            f"\n💸 Remember: the maximum budget is {max_budget}."
                        )

                    body = (
                        f"🎅 Ho Ho Ho, {giver}! 🎁 \n\n"
                        f"You have been chosen as the Secret Santa for... 🥁 *{receiver}*! 🎉 \n\n"
                        f"✨ Make sure to prepare a thoughtful gift 🎁 and spread the holiday cheer! 🎄{budget_line} \n\n"
                        "Wishing you a season full of joy, laughter, and surprises! ❄️ \n\n"
                        "Happy Holidays! 🕊️\n\n"
                        "    Your Secret Santa Organizer 🎅"
                    )
                    message.attach(MIMEText(body, "plain"))
                    server.sendmail(sender_email, recipient_email, message.as_string())
                    print(f"Email sent to {giver} ({recipient_email})")

    except Exception as e:
        print(f"Error sending emails: {e}")
