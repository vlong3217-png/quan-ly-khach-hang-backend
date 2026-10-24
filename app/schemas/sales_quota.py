from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class SalesQuotaBase(BaseModel):
    quota_type: str  # month | quarter
    period_name: str # e.g. "2026-10", "2026-Q4"
    year: int
    period_number: int
    target_type: str # user | team
    user_id: Optional[int] = None
    team_id: Optional[str] = None
    target_amount: float

class SalesQuotaCreate(SalesQuotaBase):
    pass

class SalesQuotaUpdate(BaseModel):
    target_amount: float
    reason: Optional[str] = None  # Mandatory if period is passed / locked

class SalesQuotaResponse(SalesQuotaBase):
    id: int
    achieved_amount: float = 0.0
    attainment_rate: float = 0.0
    is_locked: bool = False
    lock_reason: Optional[str] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class SalesQuotaAuditLogResponse(BaseModel):
    id: int
    quota_id: int
    action: str
    old_target_amount: Optional[float] = None
    new_target_amount: Optional[float] = None
    reason: str
    changed_by: int
    changed_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class TeamQuotaValidationResponse(BaseModel):
    is_valid: bool
    team_id: str
    period_name: str
    team_target: float
    members_total_target: float
    difference: float
    warning: Optional[str] = None

class SalesQuotaListResponse(BaseModel):
    total: int
    quotas: List[SalesQuotaResponse]
    page: Optional[int] = 1
    limit: Optional[int] = 20
    total_pages: Optional[int] = 1