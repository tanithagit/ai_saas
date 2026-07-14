from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator, model_validator

from schemas.auth import PASSWORD_REGEX


class UserProfileResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    account_type: str
    role: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password_policy(cls, v: str) -> str:
        if not PASSWORD_REGEX.match(v):
            raise ValueError(
                "Password must be at least 8 characters and include uppercase, "
                "lowercase, a number, and a special character."
            )
        return v

    @model_validator(mode="after")
    def validate_match(self):
        if self.new_password != self.confirm_new_password:
            raise ValueError("New Password and Confirm New Password do not match.")
        return self


class OrganizationProfileResponse(BaseModel):
    id: int
    organization_name: str
    status: str

    class Config:
        from_attributes = True


class UpdateOrganizationRequest(BaseModel):
    organization_name: Optional[str] = None