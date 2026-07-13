import random
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from core.config import settings

logger = logging.getLogger("ai_saas_backend")


def generate_otp() -> str:
    return str(random.randint(100000, 999999))


def send_otp_email(to_email: str, otp: str, purpose: str = "registration"):
    subject_map = {
        "registration": "Verify Your Account - OTP Code",
        "forgot_password": "Password Reset - OTP Code",
    }
    subject = subject_map.get(purpose, "Your OTP Code")

    body = f"""
    <html>
      <body>
        <p>Hello,</p>
        <p>Your OTP code is: <strong style="font-size: 20px;">{otp}</strong></p>
        <p>This code will expire in 5 minutes.</p>
        <p>If you did not request this, please ignore this email.</p>
      </body>
    </html>
    """

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = to_email
    message.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.smtp_from_email, to_email, message.as_string())
        logger.info(f"OTP email sent successfully to {to_email} ({purpose})")
        if settings.debug:
            logger.info(f"[DEV DEBUG] OTP for {to_email} ({purpose}): {otp}")
    except Exception as e:
        logger.error(f"Failed to send OTP email to {to_email}: {e}")
        logger.info(f"[FALLBACK] OTP for {to_email} ({purpose}): {otp}")