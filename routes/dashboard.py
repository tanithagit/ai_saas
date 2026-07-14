from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from models.user import User, AccountType
from models.tenant import Tenant

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/individual")
def individual_dashboard(current_user: User = Depends(get_current_user)):
    if current_user.account_type != AccountType.individual:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This dashboard is only available to individual accounts.",
        )

    return {
        "message": f"Welcome, {current_user.full_name}!",
        "profile": {
            "id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
            "account_type": current_user.account_type,
            "is_active": current_user.is_active,
        },
    }


@router.get("/organization")
def organization_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.account_type != AccountType.organization or not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This dashboard is only available to organization accounts.",
        )

    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    total_users = db.query(User).filter(
        User.tenant_id == current_user.tenant_id, User.is_deleted == False
    ).count()
    active_users = db.query(User).filter(
        User.tenant_id == current_user.tenant_id, User.is_deleted == False, User.is_active == True
    ).count()

    return {
        "message": f"Welcome, {current_user.full_name}!",
        "role": current_user.role,
        "organization": {
            "id": tenant.id if tenant else None,
            "organization_name": tenant.organization_name if tenant else None,
            "status": tenant.status if tenant else None,
        },
        "stats": {
            "total_users": total_users,
            "active_users": active_users,
        },
    }