from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from core.security import verify_password, hash_password

from models.user import User

from schemas.profile import UserProfileResponse, UpdateProfileRequest, ChangePasswordRequest
from schemas.auth import MessageResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/profile", response_model=UserProfileResponse)
def get_my_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/profile", response_model=UserProfileResponse)
def update_my_profile(
    payload: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.full_name:
        current_user.full_name = payload.full_name

    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")

    current_user.password_hash = hash_password(payload.new_password)
    db.commit()

    return MessageResponse(message="Password changed successfully.")