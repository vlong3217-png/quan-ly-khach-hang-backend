"""Schemas package."""
from app.schemas.auth import LoginRequest, LoginResponse, UserResponse
from app.schemas.customer import (
    CustomerBase,
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerListResponse,
)

from app.schemas.lead import (
    LeadRejectSchema,
    LeadCreate,
    LeadUpdate,
    LeadResponse,
    LeadStatus,
)

__all__ = [
    "LoginRequest",
    "LoginResponse",
    "UserResponse",
    "CustomerBase",
    "CustomerCreate",
    "CustomerUpdate",
    "CustomerResponse",
    "CustomerListResponse",
    "LeadRejectSchema",
    "LeadCreate",
    "LeadUpdate",
    "LeadResponse",
    "LeadStatus",
]
