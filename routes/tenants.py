from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_tenant_admin, get_current_org_user
from core.security import hash_password

from models.user import User, UserRole, AccountType
from models.tenant import Tenant

from schemas.tenant import (
    CreateTenantUserRequest,
    TenantUserResponse,
    UpdateTenantUserRequest,
    UpdateStatusRequest,
    
)
from schemas.auth import MessageResponse
from schemas.profile import OrganizationProfileResponse, UpdateOrganizationRequest

tenant_user_router = APIRouter(prefix="/organizations", tags=["Tenant User"])

org_router = APIRouter(prefix="/organizations", tags=["Organizations"])


# --- Organization Profile ---

@org_router.get("/profile", response_model=OrganizationProfileResponse)
def get_organization_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_org_user),
):
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    return tenant


@org_router.put("/profile", response_model=OrganizationProfileResponse)
def update_organization_profile(
    payload: UpdateOrganizationRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_tenant_admin),
):
    tenant = db.query(Tenant).filter(Tenant.id == admin.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")

    if payload.organization_name:
        tenant.organization_name = payload.organization_name

    db.commit()
    db.refresh(tenant)
    return tenant


# --- Tenant User Management (/organizations/users/*) ---

@tenant_user_router.post("/users/invite", response_model=TenantUserResponse)
def invite_organization_user(
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
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@tenant_user_router.get("/users", response_model=List[TenantUserResponse])
def list_organization_users(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_tenant_admin),
):
    users = db.query(User).filter(User.tenant_id == admin.tenant_id, User.is_deleted == False).all()
    return users


@tenant_user_router.get("/users/{user_id}", response_model=TenantUserResponse)
def get_organization_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_tenant_admin),
):
    user = db.query(User).filter(
        User.id == user_id, User.tenant_id == admin.tenant_id, User.is_deleted == False
    ).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in your organization.")
    return user


@tenant_user_router.put("/users/{user_id}", response_model=TenantUserResponse)
def update_organization_user(
    user_id: int,
    payload: UpdateTenantUserRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_tenant_admin),
):
    user = db.query(User).filter(
        User.id == user_id, User.tenant_id == admin.tenant_id, User.is_deleted == False
    ).first()
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


@tenant_user_router.patch("/users/{user_id}/status", response_model=TenantUserResponse)
def update_organization_user_status(
    user_id: int,
    payload: UpdateStatusRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_tenant_admin),
):
    user = db.query(User).filter(
        User.id == user_id, User.tenant_id == admin.tenant_id, User.is_deleted == False
    ).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in your organization.")

    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot change your own account status.")

    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user

@tenant_user_router.delete("/users/{user_id}", response_model=MessageResponse)
def delete_organization_user(
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