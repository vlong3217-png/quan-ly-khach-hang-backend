"""Customer schemas for request and response validation (S3-01)."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CustomerStatus(str, Enum):
    PROSPECT = "PROSPECT"               # Tiềm năng
    IN_TRANSACTION = "IN_TRANSACTION"   # Đang giao dịch
    CUSTOMER = "CUSTOMER"               # Khách hàng
    DISCONTINUED = "DISCONTINUED"       # Ngừng hợp tác


class CustomerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Tên công ty / khách hàng doanh nghiệp")
    tax_code: Optional[str] = Field(None, max_length=50, description="Mã số thuế (nếu có phải là duy nhất)")
    industry: Optional[str] = Field(None, max_length=100, description="Ngành nghề kinh doanh")
    company_size: Optional[str] = Field(None, max_length=100, description="Quy mô doanh nghiệp")
    website: Optional[str] = Field(None, max_length=255, description="Website doanh nghiệp")
    address: Optional[str] = Field(None, max_length=500, description="Địa chỉ công ty")
    status: CustomerStatus = Field(default=CustomerStatus.PROSPECT, description="Trạng thái khách hàng")

    # Giữ tương thích ngược với các trường cũ nếu có client dùng
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None


class CustomerCreate(CustomerBase):
    owner_id: Optional[int] = Field(None, description="ID người sở hữu (mặc định là người tạo)")
    team_id: Optional[int] = Field(None, description="ID nhóm kinh doanh phụ trách")


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    tax_code: Optional[str] = Field(None, max_length=50)
    industry: Optional[str] = Field(None, max_length=100)
    company_size: Optional[str] = Field(None, max_length=100)
    website: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = Field(None, max_length=500)
    status: Optional[CustomerStatus] = None
    owner_id: Optional[int] = None
    team_id: Optional[int] = None

    # Tương thích ngược
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None


class CustomerResponse(CustomerBase):
    id: int
    owner_id: int
    owner_name: Optional[str] = None
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CustomerListResponse(BaseModel):
    scope: str
    total: int
    customers: List[CustomerResponse]
    skip: Optional[int] = 0
    limit: Optional[int] = 20
    page: Optional[int] = 1
    total_pages: Optional[int] = 1


class CustomerAttachment(BaseModel):
    id: int
    filename: str
    file_url: str
    file_size_bytes: int
    uploaded_by: str
    created_at: datetime


class Customer360Response(BaseModel):
    customer: CustomerResponse
    contacts: List[dict] = []
    open_opportunities: List[dict] = []
    closed_opportunities: List[dict] = []
    activities_timeline: List[dict] = []
    attachments: List[CustomerAttachment] = []
    total_won_value: float = 0.0
    total_open_value: float = 0.0
    churn_risk: bool = False
