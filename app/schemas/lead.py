from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


# ============================================================================
# CẤU HÌNH BIỂU MẪU WEB-TO-LEAD (LEAD FORM CONFIG)
# ============================================================================

class LeadFormCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Tên biểu mẫu nhúng (VD: Form Đăng ký tư vấn)")
    source_name: Optional[str] = Field("Website Form", max_length=100, description="Tên nguồn gắn vào lead (VD: Website Landing Page, Google Ads, Blog)")
    description: Optional[str] = Field(None, description="Mô tả mục đích biểu mẫu")
    target_url: Optional[str] = Field(None, max_length=500, description="URL website dự kiến nhúng")
    rate_limit_per_minute: Optional[int] = Field(5, ge=1, le=100, description="Số lượt gửi tối đa cho phép / IP / phút")


class LeadFormUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    source_name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    target_url: Optional[str] = None
    rate_limit_per_minute: Optional[int] = Field(None, ge=1, le=100)
    is_active: Optional[bool] = None


class LeadFormResponse(BaseModel):
    id: int
    form_key: str
    name: str
    source_name: str
    description: Optional[str] = None
    target_url: Optional[str] = None
    is_active: bool
    rate_limit_per_minute: int
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    embed_script_tag: Optional[str] = None
    embed_iframe_code: Optional[str] = None
    embed_html_form: Optional[str] = None

    model_config = {"from_attributes": True}


class LeadFormEmbedCodeResponse(BaseModel):
    form_key: str
    name: str
    source_name: str
    endpoint_url: str
    embed_script_tag: str
    embed_iframe_code: str
    embed_html_form: str


# ============================================================================
# NỘP DỮ LIỆU LEAD TỪ WEBSITE (PUBLIC WEB-TO-LEAD SUBMISSION)
# ============================================================================

class WebToLeadSubmitRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255, description="Họ và tên khách hàng")
    email: EmailStr = Field(..., description="Địa chỉ email hợp lệ")
    phone: Optional[str] = Field(None, max_length=50, description="Số điện thoại liên hệ")
    company: Optional[str] = Field(None, max_length=255, description="Tên công ty hoặc doanh nghiệp")
    interest: Optional[str] = Field(None, max_length=2000, description="Nhu cầu quan tâm, thông tin trao đổi")
    
    # Honeypot field chống spam bot (người dùng thật để trống, bot điền sẽ bị từ chối)
    hp_website: Optional[str] = Field(None, description="Honeypot field (hidden)")


class WebToLeadSubmitResponse(BaseModel):
    success: bool
    message: str
    lead_id: Optional[int] = None
    status: str = "NEW"


# ============================================================================
# QUẢN LÝ DANH SÁCH LEAD (CRM LEADS)
# ============================================================================

class LeadResponse(BaseModel):
    id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    company: Optional[str] = None
    interest: Optional[str] = None
    source: str
    status: str
    form_key: Optional[str] = None
    ip_address: Optional[str] = None
    owner_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LeadListResponse(BaseModel):
    total: int
    items: List[LeadResponse]
