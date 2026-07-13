from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_tenant_admin
from core.security import hash_password
from core.jwt_handler import create_otp_token
from core.otp_utils import generate_otp, send_otp_email

from models.user import User, UserRole, AccountType

from schemas.tenant import CreateTenantUserRequest, TenantUserResponse
from typing import List
from schemas.tenant import UpdateTenantUserRequest
from schemas.tenant import UpdateStatusRequest
from schemas.auth import MessageResponse

router = APIRouter(prefix="/tenant", tags=["Tenant"])


@router.post("/create-user", response_model=TenantUserResponse)
def create_tenant_user(
    payload: CreateTenantUserRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_tenant_admin),
):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already registered.")

    new_user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        account_type=AccountType.organization,
        role=UserRole.member,
        tenant_id=admin.tenant_id,
        is_active=True,  # created directly active by trusted admin, no OTP needed
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user

@router.get("/users", response_model=List[TenantUserResponse])
def list_tenant_users(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_tenant_admin),
):
    users = db.query(User).filter(User.tenant_id == admin.tenant_id).all()
    return users

@router.get("/users/{user_id}", response_model=TenantUserResponse)
def get_tenant_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_tenant_admin),
):
    user = db.query(User).filter(User.id == user_id, User.tenant_id == admin.tenant_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in your organization.")
    return user


@router.put("/users/{user_id}", response_model=TenantUserResponse)
def update_tenant_user(
    user_id: int,
    payload: UpdateTenantUserRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_tenant_admin),
):
    user = db.query(User).filter(User.id == user_id, User.tenant_id == admin.tenant_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in your organization.")

    if payload.email and payload.email != user.email:
        existing = db.query(User).filter(User.email == payload.email).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already in use.")
        user.email = payload.email

    if payload.full_name:
        user.full_name = payload.full_name

    db.commit()
    db.refresh(user)
    return user

@router.patch("/users/{user_id}/status", response_model=TenantUserResponse)
def update_tenant_user_status(
    user_id: int,
    payload: UpdateStatusRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_tenant_admin),
):
    user = db.query(User).filter(User.id == user_id, User.tenant_id == admin.tenant_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in your organization.")

    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot change your own account status.")

    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user

@router.delete("/users/{user_id}", response_model=MessageResponse)
def delete_tenant_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_tenant_admin),
):
    user = db.query(User).filter(
        User.id == user_id, User.tenant_id == admin.tenant_id, User.is_deleted == False
    ).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in your organization.")

    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete your own account.")

    user.is_deleted = True
    user.is_active = False
    db.commit()

    return MessageResponse(message="User deleted successfully.")