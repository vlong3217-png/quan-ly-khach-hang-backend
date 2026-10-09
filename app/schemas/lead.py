from datetime import datetime
from enum import Enum
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator, field_validator


# ============================================================================
# CẤU HÌNH BIỂU MẪU WEB-TO-LEAD (S4-01)
# ============================================================================

class LeadFormCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Tên biểu mẫu nhúng (VD: Form Đăng ký tư vấn)")
    source_name: Optional[str] = Field("Website Form", max_length=100, description="Tên nguồn gắn vào lead")
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

    model_config = ConfigDict(from_attributes=True)


class LeadFormEmbedCodeResponse(BaseModel):
    form_key: str
    name: str
    source_name: str
    endpoint_url: str
    embed_script_tag: str
    embed_iframe_code: str
    embed_html_form: str


# ============================================================================
# NỘP DỮ LIỆU LEAD TỪ WEBSITE (PUBLIC WEB-TO-LEAD SUBMISSION - S4-01)
# ============================================================================

class WebToLeadSubmitRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255, description="Họ và tên khách hàng")
    email: EmailStr = Field(..., description="Địa chỉ email hợp lệ")
    phone: Optional[str] = Field(None, max_length=50, description="Số điện thoại liên hệ")
    company: Optional[str] = Field(None, max_length=255, description="Tên công ty hoặc doanh nghiệp")
    interest: Optional[str] = Field(None, max_length=2000, description="Nhu cầu quan tâm, thông tin trao đổi")
    hp_website: Optional[str] = Field(None, description="Honeypot field (hidden)")


class WebToLeadSubmitResponse(BaseModel):
    success: bool
    message: str
    lead_id: Optional[int] = None
    status: str = "NEW"


# ============================================================================
# QUẢN LÝ LEAD (CRM LEADS - S4-01, S4-02, S4-03, S4-04, S4-05, S4-06)
# ============================================================================

class LeadCreate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=50)
    company: Optional[str] = Field(None, max_length=255)
    company_name: Optional[str] = Field(None, max_length=255)
    title: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = Field(None, max_length=500)
    industry: Optional[str] = Field(None, max_length=100)
    company_size: Optional[str] = Field(None, max_length=100)
    budget: Optional[float] = None
    job_title: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    interest: Optional[str] = Field(None, max_length=2000)
    notes: Optional[str] = None
    source: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = Field("NEW", max_length=50)
    campaign_id: Optional[int] = None
    customer_id: Optional[int] = None
    owner_id: Optional[int] = None
    team_id: Optional[int] = None

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Mọi lead nhập vào đều bắt buộc có nguồn")
        return v.strip() if v is not None else None

    @model_validator(mode="after")
    def sync_and_validate(self):
        had_name = "name" in self.__pydantic_fields_set__
        had_full_name = "full_name" in self.__pydantic_fields_set__
        had_source = "source" in self.__pydantic_fields_set__

        # Đồng bộ name <-> full_name
        if not self.full_name and self.name:
            self.full_name = self.name
        elif not self.name and self.full_name:
            self.name = self.full_name

        if not self.full_name or not self.full_name.strip():
            raise ValueError("Họ và tên lead là bắt buộc")

        # Đồng bộ company <-> company_name
        if not self.company and self.company_name:
            self.company = self.company_name
        elif not self.company_name and self.company:
            self.company_name = self.company

        # Xử lý quy tắc bắt buộc có nguồn (AC S4-02):
        if not self.source:
            if had_name and not had_full_name and not had_source:
                raise ValueError("Mọi lead nhập vào đều bắt buộc có nguồn")
            elif had_full_name and not had_source:
                self.source = "Manual Entry"
            else:
                raise ValueError("Mọi lead nhập vào đều bắt buộc có nguồn")

        return self


class LeadUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    company_name: Optional[str] = None
    title: Optional[str] = None
    address: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    budget: Optional[float] = None
    job_title: Optional[str] = None
    city: Optional[str] = None
    interest: Optional[str] = None
    notes: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    campaign_id: Optional[int] = None
    customer_id: Optional[int] = None
    owner_id: Optional[int] = None
    team_id: Optional[int] = None

    @field_validator("source")
    @classmethod
    def validate_source_update(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Nguồn lead không được để trống")
        return v.strip() if v is not None else None


class LeadResponse(BaseModel):
    id: int
    full_name: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    company_name: Optional[str] = None
    title: Optional[str] = None
    job_title: Optional[str] = None
    address: Optional[str] = None
    interest: Optional[str] = None
    notes: Optional[str] = None
    source: str
    status: str
    form_key: Optional[str] = None
    ip_address: Optional[str] = None
    campaign_id: Optional[int] = None
    customer_id: Optional[int] = None
    merged_into_id: Optional[int] = None
    owner_id: Optional[int] = None
    team_id: Optional[int] = None
    owner_name: Optional[str] = None
    campaign_name: Optional[str] = None
    customer_name: Optional[str] = None

    # Lead Scoring (S4-05)
    score: int = 0
    grade: str = "COLD"
    industry: Optional[str] = None
    company_size: Optional[str] = None
    budget: Optional[float] = None
    city: Optional[str] = None
    score_details: Optional[str] = None
    last_scored_at: Optional[datetime] = None

    # Lead Allocation (S4-06)
    allocation_status: str = "UNASSIGNED"
    allocated_at: Optional[datetime] = None
    allocation_rule_id: Optional[int] = None
    allocation_method: Optional[str] = None
    allocation_note: Optional[str] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def sync_display_fields(self):
        if not self.name and self.full_name:
            self.name = self.full_name
        elif not self.full_name and self.name:
            self.full_name = self.name
        if not self.company_name and self.company:
            self.company_name = self.company
        elif not self.company and self.company_name:
            self.company = self.company_name
        return self


class LeadListResponse(BaseModel):
    total: int
    leads: List[LeadResponse] = []
    items: List[LeadResponse] = []


# ============================================================================
# EXCEL IMPORT SCHEMAS (S4-02)
# ============================================================================

class LeadImportRowData(BaseModel):
    row_number: int
    name: Optional[str] = None
    source: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    company_name: Optional[str] = None
    title: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    campaign_code: Optional[str] = None
    campaign_id: Optional[int] = None
    is_valid: bool = True
    errors: List[str] = []
    is_duplicate: bool = False
    duplicate_reasons: List[str] = []
    existing_lead_id: Optional[int] = None
    existing_customer_id: Optional[int] = None


class LeadImportPreviewResponse(BaseModel):
    total_rows: int
    valid_rows_count: int
    invalid_rows_count: int
    duplicate_rows_count: int
    rows: List[LeadImportRowData]


class LeadImportCommitRequest(BaseModel):
    duplicate_handling: str = Field(default="SKIP", description="SKIP, UPDATE, IMPORT_ANYWAY")
    rows: List[LeadImportRowData]


class LeadImportCommitResponse(BaseModel):
    total_rows: int
    inserted_count: int
    updated_count: int
    skipped_count: int
    failed_count: int
    leads: List[LeadResponse]


# ============================================================================
# LEAD SCORING SCHEMAS (S4-05)
# ============================================================================

class LeadScoringRuleCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    field_name: str = Field(..., max_length=50)
    operator: str = Field("EQUALS", max_length=30)
    target_value: Optional[str] = Field(None, max_length=255)
    points: int = Field(..., ge=-100, le=100)
    is_active: bool = True


class LeadScoringRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    field_name: Optional[str] = None
    operator: Optional[str] = None
    target_value: Optional[str] = None
    points: Optional[int] = Field(None, ge=-100, le=100)
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

    model_config = ConfigDict(from_attributes=True)


class LeadScoringSettingResponse(BaseModel):
    hot_threshold: int
    warm_threshold: int
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class LeadScoringSettingUpdate(BaseModel):
    hot_threshold: int = Field(..., ge=1, le=1000)
    warm_threshold: int = Field(..., ge=0, le=1000)


class LeadRecalculateResponse(BaseModel):
    success: bool
    message: str
    total_recalculated: int


# ============================================================================
# LEAD ALLOCATION SCHEMAS (S4-06)
# ============================================================================

class LeadAllocationRuleCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    priority: int = Field(1, ge=1, le=1000)
    criterion_type: str = Field(..., max_length=50)
    criterion_value: Optional[str] = Field(None, max_length=255)
    allocation_method: str = Field("ROUND_ROBIN", max_length=50)
    assignee_user_ids: List[int] = Field(..., min_length=1)
    is_active: bool = True


class LeadAllocationRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=1000)
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

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


class ManualAssignRequest(BaseModel):
    owner_id: int = Field(..., description="ID nhân viên nhận lead")
    note: Optional[str] = Field(None, max_length=500, description="Ghi chú phân bổ")


class BatchAllocationRunResponse(BaseModel):
    success: bool
    total_processed: int
    assigned_count: int
    queued_count: int
    message: str


# ============================================================================
# DUPLICATE & MERGE SCHEMAS (S4-04)
# ============================================================================

class DuplicateLeadMatch(BaseModel):
    confidence_score: float
    match_reasons: List[str]
    lead: LeadResponse


class DuplicateCustomerMatch(BaseModel):
    confidence_score: float
    match_reasons: List[str]
    customer: Dict[str, Any]


class LeadDuplicateCheckResponse(BaseModel):
    has_duplicates: bool
    matching_leads: List[DuplicateLeadMatch] = []
    matching_customers: List[DuplicateCustomerMatch] = []


class LeadAttachToCustomerRequest(BaseModel):
    customer_id: int
    create_contact: bool = True


class LeadMergeRequest(BaseModel):
    primary_lead_id: int
    secondary_lead_id: int
    chosen_fields: Optional[Dict[str, Any]] = None


class LeadMergePreviewResponse(BaseModel):
    primary: LeadResponse
    secondary: LeadResponse
    comparison_fields: List[Dict[str, Any]]
    activities_to_transfer: int
