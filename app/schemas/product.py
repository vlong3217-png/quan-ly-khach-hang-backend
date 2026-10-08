from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ProductType(str, Enum):
    ONE_TIME = "ONE_TIME"          # Sản phẩm một lần
    SUBSCRIPTION = "SUBSCRIPTION"  # Dịch vụ thuê bao


class ProductStatus(str, Enum):
    ACTIVE = "ACTIVE"              # Đang kinh doanh
    DISCONTINUED = "DISCONTINUED"  # Ngừng kinh doanh


class ProductBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="Mã sản phẩm / dịch vụ")
    name: str = Field(..., min_length=1, max_length=255, description="Tên sản phẩm / dịch vụ")
    product_type: ProductType = Field(default=ProductType.ONE_TIME, description="Loại sản phẩm")
    unit: str = Field(..., min_length=1, max_length=50, description="Đơn vị tính (Gói, Bộ, Tháng, Năm...)")
    list_price: float = Field(..., ge=0, description="Giá niêm yết chuẩn")
    floor_price: float = Field(..., ge=0, description="Giá sàn (ngưỡng xác định duyệt chiết khấu)")


class ProductCreate(ProductBase):
    cost_price: Optional[float] = Field(None, ge=0, description="Giá vốn (chỉ GĐ kinh doanh / Admin xem/sửa)")


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    product_type: Optional[ProductType] = None
    unit: Optional[str] = Field(None, min_length=1, max_length=50)
    list_price: Optional[float] = Field(None, ge=0)
    floor_price: Optional[float] = Field(None, ge=0)
    cost_price: Optional[float] = Field(None, ge=0)
    status: Optional[ProductStatus] = None


class ProductResponse(BaseModel):
    id: int
    code: str
    name: str
    product_type: ProductType
    unit: str
    list_price: float
    floor_price: float
    cost_price: Optional[float] = None  # None nếu user không có quyền xem
    status: ProductStatus
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ProductListResponse(BaseModel):
    total: int
    page: int
    limit: int
    total_pages: int
    products: List[ProductResponse]


class DiscountCheckRequest(BaseModel):
    product_id: int
    proposed_price: float


class DiscountCheckResponse(BaseModel):
    product_id: int
    product_name: str
    list_price: float
    floor_price: float
    proposed_price: float
    needs_approval: bool
    reason: str
