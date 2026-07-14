from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator, model_validator

from schemas.auth import PASSWORD_REGEX
from models.user import UserRole

class CreateTenantUserRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    confirm_password: str

    @field_validator("password")
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
        if self.password != self.confirm_password:
            raise ValueError("Password and Confirm Password do not match.")
        return self


class TenantUserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    is_active: bool
    role: str

    class Config:
        from_attributes = True


class UpdateTenantUserRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None


class UpdateStatusRequest(BaseModel):
    is_active: bool


class VerifyInvitedUserRequest(BaseModel):
    token: str
    otp: str

class UpdateRoleRequest(BaseModel):
    role: UserRole