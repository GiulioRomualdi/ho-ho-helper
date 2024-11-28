import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_emails(assignments, emails, sender_email, sender_password):
    """
    Sends Secret Santa assignments via email.

    Parameters:
        assignments (dict): Secret Santa assignments.
        emails (dict): Email addresses of participants (name -> email).
        sender_email (str): Sender's email address.
        sender_password (str): Sender's email password.
    """
    subject = "Your Secret Santa Assignment"
    smtp_server = "smtp.gmail.com"
    smtp_port = 587

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
                    body = f"""🎅 Ho Ho Ho, {giver}! 🎁 \n\n You have been chosen as the Secret Santa for... 🥁 *{receiver}*! 🎉 \n\n✨ Make sure to prepare a thoughtful gift 🎁 and spread the holiday cheer! 🎄 \n\nWishing you a season full of joy, laughter, and surprises! ❄️ \n\nHappy Holidays! 🕊️\n\n    Your Secret Santa Organizer 🎅"""
                    message.attach(MIMEText(body, "plain"))
                    server.sendmail(sender_email, recipient_email, message.as_string())
                    print(f"Email sent to {giver} ({recipient_email})")

    except Exception as e:
        print(f"Error sending emails: {e}")
