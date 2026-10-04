from typing import Optional
from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import get_current_user, require_roles
from app.schemas.product import (
    DiscountCheckRequest,
    DiscountCheckResponse,
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from app.services import product_service

router = APIRouter(prefix="/products", tags=["Product Catalog"])


@router.get("", response_model=ProductListResponse)
def list_products(
    search: Optional[str] = Query(None, description="Tìm theo mã hoặc tên sản phẩm"),
    product_type: Optional[str] = Query(None, description="Loại sản phẩm: ONE_TIME / SUBSCRIPTION"),
    status: Optional[str] = Query(None, description="Trạng thái: ACTIVE / DISCONTINUED"),
    page: int = Query(1, ge=1, description="Trang hiện tại"),
    limit: int = Query(20, ge=1, le=100, description="Số sản phẩm trên một trang"),
    current_user: dict = Depends(get_current_user),
):
    """
    Danh sách sản phẩm / dịch vụ.
    User thông thường sẽ không thấy thông tin cost_price (None).
    """
    return product_service.get_all_products(
        search=search,
        product_type=product_type,
        status_filter=status,
        page=page,
        limit=limit,
        current_user=current_user,
    )


@router.get("/{product_id}", response_model=ProductResponse)
def get_product_detail(
    product_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    Xem chi tiết sản phẩm / dịch vụ.
    """
    return product_service.get_product_by_id(product_id=product_id, current_user=current_user)


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    product_in: ProductCreate,
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"], detail="Chỉ Quản trị viên và Giám đốc kinh doanh mới có quyền tạo sản phẩm")),
):
    """
    Tạo mới sản phẩm / dịch vụ.
    Quyền: ADMIN, MANAGER.
    """
    return product_service.create_product(product_in=product_in, current_user=current_user)


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    product_in: ProductUpdate,
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"], detail="Chỉ Quản trị viên và Giám đốc kinh doanh mới có quyền cập nhật sản phẩm")),
):
    """
    Cập nhật sản phẩm / dịch vụ.
    Quyền: ADMIN, MANAGER.
    """
    return product_service.update_product(product_id=product_id, product_in=product_in, current_user=current_user)


@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"], detail="Chỉ Quản trị viên và Giám đốc kinh doanh mới có quyền xoá hoặc ngừng kinh doanh sản phẩm")),
):
    """
    Xóa sản phẩm.
    Nếu sản phẩm đã từng xuất hiện trong báo giá, hệ thống tự động chuyển sang DISCONTINUED.
    """
    return product_service.delete_or_discontinue_product(product_id=product_id, current_user=current_user)


@router.post("/check-discount", response_model=DiscountCheckResponse)
def check_discount(
    req: DiscountCheckRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Kiểm tra giá chào bán so với giá sàn để xác định xem có cần phê duyệt chiết khấu hay không.
    """
    return product_service.check_discount_approval(
        product_id=req.product_id,
        proposed_price=req.proposed_price,
    )
