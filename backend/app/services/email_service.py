import smtplib
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app.config import settings


def send_email(
    to_email: str,
    to_name: str | None,
    subject: str,
    body_html: str,
    body_text: str | None = None,
    cc: list[str] | None = None,
) -> str:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((settings.EMAIL_FROM_NAME, settings.EMAIL_FROM))
    msg["To"] = formataddr((to_name or "", to_email))
    if cc:
        msg["Cc"] = ", ".join(cc)
    message_id = make_msgid(domain="nksquared")
    msg["Message-ID"] = message_id

    msg.set_content(body_text or _strip_html(body_html))
    msg.add_alternative(body_html, subtype="html")

    recipients = [to_email] + (cc or [])
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
        if settings.SMTP_USE_TLS:
            smtp.starttls()
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD or "")
        smtp.send_message(msg, from_addr=settings.EMAIL_FROM, to_addrs=recipients)

    return message_id


def _strip_html(html: str) -> str:
    import re

    text = re.sub(r"<\s*br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</\s*p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()
