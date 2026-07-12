import random
import logging

logger = logging.getLogger("ai_saas_backend")


def generate_otp() -> str:
    return str(random.randint(100000, 999999))


def send_otp_email(to_email: str, otp: str, purpose: str = "registration"):
    # TODO: integrate real SMTP/email provider later.
    # For now, log it so we can test the flow end-to-end locally.
    logger.info(f"[MOCK EMAIL] OTP for {to_email} ({purpose}): {otp}")