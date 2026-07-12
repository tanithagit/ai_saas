import enum

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, func

from core.database import Base


class AccountType(str, enum.Enum):
    individual = "individual"
    organization = "organization"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    account_type = Column(Enum(AccountType), nullable=False)
    is_active = Column(Boolean, default=False)  # True only after OTP verification
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())