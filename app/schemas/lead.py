from datetime import datetime
from enum import Enum
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, ConfigDict, Field, field_validator


class LeadStatus(str, Enum):
    NEW = "NEW"                     # Mới tạo
    CONTACTED = "CONTACTED"         # Đã liên hệ
    QUALIFIED = "QUALIFIED"         # Tiềm năng
    UNQUALIFIED = "UNQUALIFIED"     # Không tiềm năng
    CONVERTED = "CONVERTED"         # Đã chuyển đổi thành khách hàng / cơ hội
    MERGED = "MERGED"               # Đã gộp vào lead khác


class LeadBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Họ và tên lead")
    company_name: Optional[str] = Field(None, max_length=255, description="Tên công ty / tổ chức")
    title: Optional[str] = Field(None, max_length=255, description="Chức danh / vị trí")
    email: Optional[str] = Field(None, max_length=255, description="Email liên hệ")
    phone: Optional[str] = Field(None, max_length=50, description="Số điện thoại")
    address: Optional[str] = Field(None, max_length=500, description="Địa chỉ")
    source: str = Field(..., min_length=1, max_length=100, description="Nguồn lead (BẮT BUỘC)")
    campaign_id: Optional[int] = Field(None, description="ID chiến dịch liên kết")
    customer_id: Optional[int] = Field(None, description="ID khách hàng liên kết")
    status: str = Field(default="NEW", description="Trạng thái lead")
    notes: Optional[str] = Field(None, description="Ghi chú chi tiết từ sự kiện / danh thiếp")

    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Họ và tên lead là bắt buộc")
        return v.strip()

    @field_validator("source")
    @classmethod
    def validate_source_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Mọi lead nhập vào đều bắt buộc có nguồn")
        return v.strip()


class LeadCreate(LeadBase):
    owner_id: Optional[int] = Field(None, description="Người phụ trách lead")
    team_id: Optional[int] = Field(None, description="Nhóm phụ trách")


class LeadUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    company_name: Optional[str] = Field(None, max_length=255)
    title: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    source: Optional[str] = Field(None, max_length=100)
    campaign_id: Optional[int] = None
    customer_id: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    owner_id: Optional[int] = None
    team_id: Optional[int] = None

    @field_validator("source")
    @classmethod
    def validate_source_update(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Nguồn lead không được để trống")
        return v.strip() if v is not None else None


class LeadResponse(LeadBase):
    id: int
    owner_id: int
    owner_name: Optional[str] = None
    team_id: Optional[int] = None
    campaign_name: Optional[str] = None
    customer_name: Optional[str] = None
    merged_into_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class LeadListResponse(BaseModel):
    total: int
    leads: List[LeadResponse]


# Excel Import Schemas (S4-02)
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


# Duplicate & Merge Schemas (S4-04)
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
