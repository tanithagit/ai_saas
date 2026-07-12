from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError

from core.config import settings


def _create_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def create_otp_token(payload: dict, purpose: str, retry_count: int = 0) -> str:
    """
    Carries OTP + expiry + retry_count + any pending data (e.g. registration fields)
    inside the JWT itself — no otp_verifications table needed.
    """
    data = {**payload, "purpose": purpose, "retry_count": retry_count, "type": "otp"}
    return _create_token(data, timedelta(minutes=settings.otp_expire_minutes))


def create_access_token(user_id: int, email: str) -> str:
    data = {"sub": str(user_id), "email": email, "type": "access"}
    return _create_token(data, timedelta(minutes=settings.jwt_access_token_expire_minutes))


def create_refresh_token(user_id: int) -> str:
    """Refresh token is self-contained JWT; no refresh_tokens table for storage/rotation tracking."""
    data = {"sub": str(user_id), "type": "refresh"}
    return _create_token(data, timedelta(days=settings.refresh_token_expire_days))


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None