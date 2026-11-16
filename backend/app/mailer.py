"""Sending transactional email (verification + password reset).

Configured entirely through environment variables so it works with the
Mailpit container used in development, or a real SMTP provider:

    SMTP_HOST, SMTP_PORT (default 1025), SMTP_USER, SMTP_PASSWORD,
    SMTP_STARTTLS (1/true/yes), SMTP_FROM, APP_BASE_URL

When `SMTP_HOST` is not set the message (and its link) is written to the
application log instead, so the flow still works without a mail server.
"""

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("tasks.mailer")

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_STARTTLS = os.getenv("SMTP_STARTTLS", "").strip().lower() in {"1", "true", "yes"}
SMTP_FROM = os.getenv("SMTP_FROM", "Tasks <no-reply@tasks.local>")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8080").rstrip("/")


def verification_link(token: str) -> str:
    return f"{APP_BASE_URL}/?verify={token}"


def reset_link(token: str) -> str:
    return f"{APP_BASE_URL}/?reset={token}"


def _html(heading: str, body: str, label: str, link: str) -> str:
    return f"""\
<div style="font-family:Inter,Segoe UI,system-ui,sans-serif;max-width:520px;margin:0 auto;
            padding:32px 28px;color:#1e293b">
  <div style="font-size:32px">✅</div>
  <h1 style="font-size:22px;margin:14px 0 8px">{heading}</h1>
  <p style="font-size:15px;line-height:1.6;color:#475569;margin:0 0 22px">{body}</p>
  <a href="{link}"
     style="display:inline-block;padding:12px 22px;border-radius:12px;font-weight:700;
            font-size:15px;color:#fff;text-decoration:none;
            background:linear-gradient(135deg,#6366f1,#a855f7)">{label}</a>
  <p style="font-size:12.5px;line-height:1.6;color:#94a3b8;margin:24px 0 0">
    If the button doesn't work, paste this into your browser:<br />
    <span style="color:#6366f1;word-break:break-all">{link}</span>
  </p>
</div>"""


def send_email(to: str, subject: str, text: str, html: str) -> None:
    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    message.add_alternative(html, subtype="html")

    if not SMTP_HOST:
        logger.warning("SMTP not configured — email to %s:\n%s", to, text)
        return

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=5) as smtp:
            if SMTP_STARTTLS:
                smtp.starttls()
            if SMTP_USER:
                smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(message)
        logger.info("Sent %r to %s", subject, to)
    except Exception:  # noqa: BLE001 — mail must never break the request
        logger.exception("Could not send %r to %s", subject, to)


def send_verification_email(email: str, token: str) -> None:
    link = verification_link(token)
    send_email(
        email,
        "Verify your Tasks email",
        f"Confirm your email address to finish setting up Tasks:\n\n{link}\n",
        _html(
            "Verify your email",
            "Welcome to Tasks! Confirm this address and you're all set. "
            "This link expires in 24 hours.",
            "Verify my email",
            link,
        ),
    )


def send_password_reset_email(email: str, token: str) -> None:
    link = reset_link(token)
    send_email(
        email,
        "Reset your Tasks password",
        f"Use this link to choose a new password:\n\n{link}\n\n"
        "If you didn't ask for this, you can ignore this email. "
        "The link expires in 1 hour.",
        _html(
            "Reset your password",
            "Someone asked to reset the password for this Tasks account. "
            "Choose a new one below — the link expires in 1 hour. "
            "If this wasn't you, you can safely ignore this email.",
            "Choose a new password",
            link,
        ),
    )
