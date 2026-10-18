from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import List, Dict, Any
from datetime import datetime

class EmailTemplateBase(BaseModel):
    name: str
    subject: str
    body: str
    category: Optional[str] = "MARKETING"
    is_active: Optional[bool] = True

class EmailTemplateCreate(EmailTemplateBase):
    pass

class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None

class EmailTemplateResponse(EmailTemplateBase):
    id: int
    created_by: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class EmailSendRequest(BaseModel):
    template_id: Optional[int] = None
    recipient_email: EmailStr
    subject: Optional[str] = None
    body: Optional[str] = None
    customer_id: Optional[int] = None
    contact_id: Optional[int] = None
    lead_id: Optional[int] = None
    variables: Optional[Dict[str, Any]] = None
    fail_silently: Optional[bool] = False

class EmailLogResponse(BaseModel):
    id: int
    template_id: Optional[int] = None
    customer_id: Optional[int] = None
    contact_id: Optional[int] = None
    lead_id: Optional[int] = None
    sender_id: int
    recipient_email: str
    subject: str
    body: str
    status: str
    error_message: Optional[str] = None
    retry_count: int
    sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class EmailTemplateListResponse(BaseModel):
    total: int
    templates: List[EmailTemplateResponse]
    page: Optional[int] = None
    limit: Optional[int] = None
    total_pages: Optional[int] = None

class EmailLogListResponse(BaseModel):
    total: int
    logs: List[EmailLogResponse]
    page: Optional[int] = None
    limit: Optional[int] = None
    total_pages: Optional[int] = None