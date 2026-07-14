from fastapi import Request, HTTPException, status, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from core.jwt_handler import decode_token
from models.user import User, UserRole


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please log in.",
        )

    token_data = decode_token(token)
    if not token_data or token_data.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
        )

    user = db.query(User).filter(User.id == int(token_data["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive.")

    return user


def get_current_tenant_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.tenant_admin or not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Tenant Admins can perform this action.",
        )
    return current_user

def get_current_org_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action is only available to organization accounts.",
        )
    return current_user