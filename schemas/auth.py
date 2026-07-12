import re
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator, model_validator

from models.user import AccountType


PASSWORD_REGEX = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&#])[A-Za-z\d@$!%*?&#]{8,}$"
)


class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    confirm_password: str
    account_type: AccountType
    organization_name: Optional[str] = None

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
    def validate_all(self):
        if self.password != self.confirm_password:
            raise ValueError("Password and Confirm Password do not match.")

        if self.account_type == AccountType.organization:
            if not self.organization_name or not self.organization_name.strip():
                raise ValueError("Organization Name is required for Organization accounts.")
            # Basic official/business email check: reject common free email domains
            free_domains = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com"}
            domain = self.email.split("@")[-1].lower()
            if domain in free_domains:
                raise ValueError("Please use an official business email for Organization accounts.")
        return self


class RegisterResponse(BaseModel):
    message: str
    email: EmailStr


class VerifyOtpRequest(BaseModel):
    otp: str


class ResendOtpRequest(BaseModel):
    purpose: str = "registration"


class MessageResponse(BaseModel):
    message: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    message: str
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyForgotOtpRequest(BaseModel):
    otp: str


class ResetPasswordRequest(BaseModel):
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