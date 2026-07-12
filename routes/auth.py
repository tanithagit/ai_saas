from fastapi import APIRouter, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from fastapi import Depends

from core.database import get_db
from core.security import hash_password, verify_password
from core.jwt_handler import create_otp_token, decode_token, create_access_token, create_refresh_token
from core.otp_utils import generate_otp, send_otp_email
from models.user import User
from schemas.auth import RegisterRequest, RegisterResponse, VerifyOtpRequest, MessageResponse, ResendOtpRequest, LoginRequest, LoginResponse, ForgotPasswordRequest, VerifyForgotOtpRequest, ResetPasswordRequest



from models.tenant import Tenant
from core.config import settings
from core.deps import get_current_user


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    # 1. Email uniqueness check
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered.",
        )

    # 2. Generate OTP
    otp = generate_otp()

    # 3. Build pending-registration payload (hash password now, never store plain text)
    pending_data = {
        "sub": payload.email,
        "full_name": payload.full_name,
        "password_hash": hash_password(payload.password),
        "account_type": payload.account_type.value,
        "organization_name": payload.organization_name,
        "otp": otp,
    }

    # 4. Create OTP JWT and store in HTTP-only cookie
    otp_token = create_otp_token(pending_data, purpose="registration")
    response.set_cookie(
        key="otp_token",
        value=otp_token,
        httponly=True,
        secure=False,   # set True in production (HTTPS)
        samesite="lax",
        max_age=5 * 60,
    )

    # 5. Send OTP via email (mocked/logged for now)
    send_otp_email(payload.email, otp, purpose="registration")

    return RegisterResponse(message="OTP sent to your email. Please verify to activate your account.", email=payload.email)



@router.post("/verify-otp", response_model=MessageResponse)
def verify_otp(
    payload: VerifyOtpRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    otp_token = request.cookies.get("otp_token")
    if not otp_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP session expired or not found. Please register again.",
        )

    token_data = decode_token(otp_token)
    if not token_data or token_data.get("type") != "otp":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP session. Please register again.",
        )

    if token_data.get("purpose") != "registration":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP purpose.")

    # Retry limit check
    retry_count = token_data.get("retry_count", 0)
    if retry_count >= 3:
        response.delete_cookie("otp_token")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Maximum OTP attempts exceeded. Please register again.",
        )

    # OTP mismatch
    if payload.otp != token_data.get("otp"):
        # Re-issue token with incremented retry_count (same data, same expiry window remains via JWT exp)
        new_pending = {k: v for k, v in token_data.items() if k not in ("exp", "type", "purpose", "retry_count")}
        new_token = create_otp_token(new_pending, purpose="registration", retry_count=retry_count + 1)
        response.set_cookie(
            key="otp_token", value=new_token, httponly=True, secure=False, samesite="lax", max_age=5 * 60
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP.")

    # OTP correct -> double-check email still unique (race condition safety)
    email = token_data["sub"]
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        response.delete_cookie("otp_token")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already registered.")

    # Create User
    new_user = User(
        full_name=token_data["full_name"],
        email=email,
        password_hash=token_data["password_hash"],
        account_type=token_data["account_type"],
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # If organization -> create Tenant + assign as owner/admin
    if token_data["account_type"] == "organization":
        new_tenant = Tenant(
            organization_name=token_data.get("organization_name"),
            owner_user_id=new_user.id,
        )
        db.add(new_tenant)
        db.commit()

    response.delete_cookie("otp_token")
    return MessageResponse(message="Account verified and activated successfully.")
@router.post("/resend-otp", response_model=MessageResponse)
def resend_otp(
    payload: ResendOtpRequest,
    request: Request,
    response: Response,
):
    # Determine which OTP session is active: registration or forgot-password
    cookie_name = "otp_token" if payload.purpose == "registration" else "forgot_otp_token"
    otp_token = request.cookies.get(cookie_name)

    if not otp_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending OTP session found. Please start the process again.",
        )

    token_data = decode_token(otp_token)
    if not token_data or token_data.get("type") != "otp":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP session expired. Please start the process again.",
        )

    if token_data.get("purpose") != payload.purpose:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP purpose mismatch.")

    # Generate a fresh OTP, reset retry_count, keep the same pending data (registration fields or email)
    new_otp = generate_otp()
    pending_data = {k: v for k, v in token_data.items() if k not in ("exp", "type", "purpose", "retry_count", "otp")}
    pending_data["otp"] = new_otp

    new_token = create_otp_token(pending_data, purpose=payload.purpose, retry_count=0)
    response.set_cookie(
        key=cookie_name, value=new_token, httponly=True, secure=False, samesite="lax", max_age=5 * 60
    )

    send_otp_email(token_data["sub"], new_otp, purpose=payload.purpose)

    return MessageResponse(message="A new OTP has been sent to your email.")

@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not activated. Please verify OTP first.",
        )

    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,       # True in production (HTTPS)
        samesite="lax",
        max_age=settings.jwt_access_token_expire_minutes * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
    )

    return LoginResponse(message="Login successful.", email=user.email)

@router.post("/logout", response_model=MessageResponse)
def logout(response: Response, current_user: User = Depends(get_current_user)):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return MessageResponse(message="Logged out successfully.")



@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        # Don't reveal whether the email exists — generic response either way
        return MessageResponse(message="If this email is registered, an OTP has been sent.")

    otp = generate_otp()
    pending_data = {"sub": user.email, "otp": otp}
    otp_token = create_otp_token(pending_data, purpose="forgot_password")

    response.set_cookie(
        key="forgot_otp_token",
        value=otp_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=5 * 60,
    )

    send_otp_email(user.email, otp, purpose="forgot_password")

    return MessageResponse(message="If this email is registered, an OTP has been sent.")


@router.post("/verify-forgot-otp", response_model=MessageResponse)
def verify_forgot_otp(payload: VerifyForgotOtpRequest, request: Request, response: Response):
    otp_token = request.cookies.get("forgot_otp_token")
    if not otp_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP session expired. Please try again.")

    token_data = decode_token(otp_token)
    if not token_data or token_data.get("type") != "otp" or token_data.get("purpose") != "forgot_password":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP session.")

    retry_count = token_data.get("retry_count", 0)
    if retry_count >= 3:
        response.delete_cookie("forgot_otp_token")
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Maximum OTP attempts exceeded.")

    if payload.otp != token_data.get("otp"):
        new_token = create_otp_token(
            {"sub": token_data["sub"], "otp": token_data["otp"]},
            purpose="forgot_password",
            retry_count=retry_count + 1,
        )
        response.set_cookie(
            key="forgot_otp_token", value=new_token, httponly=True, secure=False, samesite="lax", max_age=5 * 60
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP.")

    # OTP correct -> issue a short-lived "reset_token" allowing password reset, clear the OTP cookie
    reset_token = create_otp_token({"sub": token_data["sub"]}, purpose="password_reset_allowed")
    response.delete_cookie("forgot_otp_token")
    response.set_cookie(
        key="reset_token", value=reset_token, httponly=True, secure=False, samesite="lax", max_age=5 * 60
    )

    return MessageResponse(message="OTP verified. You may now reset your password.")


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    reset_token = request.cookies.get("reset_token")
    if not reset_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset session expired. Please verify OTP again.")

    token_data = decode_token(reset_token)
    if not token_data or token_data.get("purpose") != "password_reset_allowed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset session.")

    email = token_data["sub"]
    user = db.query(User).filter(User.email == email).first()
    if not user:
        response.delete_cookie("reset_token")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found.")

    user.password_hash = hash_password(payload.new_password)
    db.commit()

    response.delete_cookie("reset_token")
    return MessageResponse(message="Password has been reset successfully. Please log in with your new password.")