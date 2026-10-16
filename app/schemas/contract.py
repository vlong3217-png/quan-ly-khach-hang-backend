"""Contract Pydantic Schemas (S7-04: Convert Quote to Contract)."""
from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field


class ContractConvertRequest(BaseModel):
    """Payload từ Kế toán khi chuyển báo giá thành hợp đồng (S7-04 AC 2)."""
    contract_number: Optional[str] = Field(None, description="Số hợp đồng (duy nhất). Nếu không truyền sẽ tự động sinh.")
    title: Optional[str] = Field(None, description="Tiêu đề hợp đồng (mặc định lấy từ báo giá)")
    signed_date: date = Field(..., description="Ngày ký hợp đồng")
    effective_date: date = Field(..., description="Ngày hợp đồng bắt đầu có hiệu lực")
    expiration_date: date = Field(..., description="Ngày hết hạn hợp đồng")
    payment_terms: Optional[str] = Field(None, description="Điều khoản thanh toán (kế thừa từ báo giá nếu bỏ trống)")
    delivery_terms: Optional[str] = Field(None, description="Điều khoản giao hàng / bàn giao (kế thừa từ báo giá nếu bỏ trống)")
    notes: Optional[str] = Field(None, description="Ghi chú thêm của hợp đồng")


class ContractItemResponse(BaseModel):
    """Dòng sản phẩm kế thừa từ báo giá trong hợp đồng (S7-04 AC 1)."""
    id: Optional[str | int] = None
    product_id: Optional[int] = None
    product_code: Optional[str] = None
    product_name: str
    unit: Optional[str] = "Gói"
    quantity: int = 1
    unit_price: float = 0.0
    floor_price: Optional[float] = None
    discount_type: Optional[str] = "PERCENT"
    discount_value: Optional[float] = 0.0
    line_discount_amount: Optional[float] = 0.0
    vat_rate: Optional[int] = 10
    line_vat_amount: Optional[float] = 0.0
    line_total: float = 0.0
    notes: Optional[str] = None


class ContractResponse(BaseModel):
    """Thông tin chi tiết một hợp đồng kinh tế."""
    id: int
    contract_number: str
    title: str
    quote_id: int
    quote_number: Optional[str] = None
    customer_id: int
    customer_name: Optional[str] = None
    opportunity_id: Optional[int] = None
    opportunity_title: Optional[str] = None
    owner_id: int
    team_id: Optional[int] = None
    status: str = "ACTIVE"
    
    # Dates & Terms (AC 2)
    signed_date: str
    effective_date: str
    expiration_date: str
    payment_terms: Optional[str] = None
    delivery_terms: Optional[str] = None
    notes: Optional[str] = None

    # Line Items & Financials (AC 1)
    items: List[ContractItemResponse] = []
    subtotal: float = 0.0
    total_line_discount: float = 0.0
    overall_discount_type: Optional[str] = "PERCENT"
    overall_discount_value: Optional[float] = 0.0
    overall_discount_amount: Optional[float] = 0.0
    total_discount_amount: float = 0.0
    discount_percentage: float = 0.0
    vat_amount: float = 0.0
    grand_total: float = 0.0

    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ContractListResponse(BaseModel):
    """Danh sách hợp đồng kèm phân trang và data scope."""
    scope: str
    total: int
    contracts: List[ContractResponse]
    page: Optional[int] = 1
    limit: Optional[int] = 20
    skip: Optional[int] = 0
    total_pages: Optional[int] = 1


class ContractGenerateNumberResponse(BaseModel):
    """Mã số hợp đồng gợi ý tự sinh (AC 4)."""
    suggested_contract_number: str
