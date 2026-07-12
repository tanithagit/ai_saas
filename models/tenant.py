import enum

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum, func

from core.database import Base


class TenantStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    organization_name = Column(String(255), nullable=False)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(TenantStatus), default=TenantStatus.active)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())