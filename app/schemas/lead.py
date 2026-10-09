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

class LeadCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=50)
    company: Optional[str] = Field(None, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    company_size: Optional[str] = Field(None, max_length=100)
    budget: Optional[float] = None
    job_title: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    interest: Optional[str] = Field(None, max_length=2000)
    source: Optional[str] = Field("Manual Entry", max_length=100)
    status: Optional[str] = Field("NEW", max_length=50)
    owner_id: Optional[int] = None


class LeadUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    budget: Optional[float] = None
    job_title: Optional[str] = None
    city: Optional[str] = None
    interest: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    owner_id: Optional[int] = None


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
    
    # S4-05 Lead Scoring fields
    score: int = 0
    grade: str = "COLD"
    industry: Optional[str] = None
    company_size: Optional[str] = None
    budget: Optional[float] = None
    job_title: Optional[str] = None
    city: Optional[str] = None
    score_details: Optional[str] = None
    last_scored_at: Optional[datetime] = None

    # S4-06 Lead Allocation fields
    allocation_status: str = "UNASSIGNED"
    allocated_at: Optional[datetime] = None
    allocation_rule_id: Optional[int] = None
    allocation_method: Optional[str] = None
    allocation_note: Optional[str] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}



class LeadListResponse(BaseModel):
    total: int
    items: List[LeadResponse]


# ============================================================================
# CẤU HÌNH TIÊU CHÍ CHẤM ĐIỂM LEAD (LEAD SCORING RULES - S4-05)
# ============================================================================

class LeadScoringRuleCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Tên tiêu chí (VD: Ngành CNTT hoặc Tài chính)")
    description: Optional[str] = None
    field_name: str = Field(..., max_length=50, description="Trường lead: industry, company_size, source, budget, job_title, phone, email, interest, city")
    operator: str = Field("EQUALS", max_length=30, description="Toán tử: EQUALS, NOT_EQUALS, CONTAINS, NOT_EMPTY, IS_EMPTY, GREATER_THAN, LESS_THAN, IN")
    target_value: Optional[str] = Field(None, max_length=255, description="Giá trị so sánh")
    points: int = Field(10, description="Số điểm cộng/trừ khi khớp")
    is_active: Optional[bool] = Field(True, description="Trạng thái kích hoạt")


class LeadScoringRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    field_name: Optional[str] = Field(None, max_length=50)
    operator: Optional[str] = Field(None, max_length=30)
    target_value: Optional[str] = None
    points: Optional[int] = None
    is_active: Optional[bool] = None


class LeadScoringRuleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    field_name: str
    operator: str
    target_value: Optional[str] = None
    points: int
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LeadScoringSettingUpdate(BaseModel):
    hot_threshold: int = Field(..., ge=1, description="Ngưỡng điểm Nóng (HOT)")
    warm_threshold: int = Field(..., ge=0, description="Ngưỡng điểm Ấm (WARM)")


class LeadScoringSettingResponse(BaseModel):
    hot_threshold: int
    warm_threshold: int
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LeadRecalculateResponse(BaseModel):
    lead_id: int
    score: int
    grade: str
    matched_rules_count: int
    score_details: Optional[str] = None
    message: str


# ============================================================================
# CẤU HÌNH QUY TẮC PHÂN BỔ LEAD TỰ ĐỘNG (LEAD ALLOCATION - S4-06)
# ============================================================================

class LeadAllocationRuleCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Tên quy tắc phân bổ")
    description: Optional[str] = None
    priority: int = Field(1, ge=1, description="Thứ tự ưu tiên (1 = cao nhất)")
    criterion_type: str = Field("ANY", description="Tiêu chí khớp: REGION, INDUSTRY, SOURCE, ANY")
    criterion_value: Optional[str] = Field(None, max_length=255, description="Giá trị tiêu chí (VD: Hà Nội, Hải Phòng hoặc Công nghệ thông tin)")
    allocation_method: str = Field("ROUND_ROBIN", description="Phương thức: ROUND_ROBIN, SPECIFIC_USER, REGION, INDUSTRY")
    assignee_user_ids: List[int] = Field(..., min_length=1, description="Danh sách User ID nhân viên nhận lead")
    is_active: Optional[bool] = Field(True, description="Trạng thái kích hoạt")


class LeadAllocationRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1)
    criterion_type: Optional[str] = None
    criterion_value: Optional[str] = None
    allocation_method: Optional[str] = None
    assignee_user_ids: Optional[List[int]] = None
    is_active: Optional[bool] = None


class LeadAllocationRuleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    priority: int
    criterion_type: str
    criterion_value: Optional[str] = None
    allocation_method: str
    assignee_user_ids: List[int]
    last_assigned_index: int
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ManualAssignRequest(BaseModel):
    owner_id: int = Field(..., description="ID nhân viên phụ trách được gán")
    note: Optional[str] = Field(None, max_length=500, description="Ghi chú phân bổ của trưởng nhóm")


class LeadAllocationLogResponse(BaseModel):
    id: int
    lead_id: int
    rule_id: Optional[int] = None
    rule_name: Optional[str] = None
    allocation_method: str
    assigned_to: Optional[int] = None
    status: str
    note: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BatchAllocationRunResponse(BaseModel):
    success: bool
    total_processed: int
    assigned_count: int
    queued_count: int
    message: str


