import copy
import math
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import HTTPException, status

from app.schemas.product import (
    ProductCreate,
    ProductStatus,
    ProductType,
    ProductUpdate,
)

# Initial sample products for catalog
INITIAL_PRODUCTS = [
    {
        "id": 1,
        "code": "PROD-CRM-BASE",
        "name": "Phần mềm Quản lý Khách hàng - Gói Tiêu chuẩn",
        "product_type": "ONE_TIME",
        "unit": "Gói",
        "list_price": 20000000.0,
        "floor_price": 15000000.0,
        "cost_price": 8000000.0,
        "status": "ACTIVE",
        "created_at": datetime(2026, 1, 15, 8, 0, 0),
    },
    {
        "id": 2,
        "code": "SERV-CLOUD-SUB",
        "name": "Dịch vụ Điện toán đám mây Doanh nghiệp",
        "product_type": "SUBSCRIPTION",
        "unit": "Tháng",
        "list_price": 5000000.0,
        "floor_price": 4000000.0,
        "cost_price": 2500000.0,
        "status": "ACTIVE",
        "created_at": datetime(2026, 2, 10, 9, 30, 0),
    },
    {
        "id": 3,
        "code": "SERV-MAINT-ANNUAL",
        "name": "Gói Bảo trì & Nâng cấp Hệ thống Định kỳ",
        "product_type": "SUBSCRIPTION",
        "unit": "Năm",
        "list_price": 12000000.0,
        "floor_price": 10000000.0,
        "cost_price": 4000000.0,
        "status": "ACTIVE",
        "created_at": datetime(2026, 3, 1, 10, 0, 0),
    },
]

# Danh sách ID sản phẩm đã từng xuất hiện trong báo giá
QUOTED_PRODUCT_IDS = {1, 2}

fake_products_db = copy.deepcopy(INITIAL_PRODUCTS)


def reset_fake_products():
    global fake_products_db
    fake_products_db = copy.deepcopy(INITIAL_PRODUCTS)


def can_view_or_edit_cost_price(user: dict) -> bool:
    """
    AC S2-05: Giá vốn chỉ Giám đốc kinh doanh (hoặc Admin) xem và sửa được.
    """
    role = user.get("role", "").upper()
    return role in {"ADMIN", "MANAGER"}


def mask_product_cost_price(product: dict, user: dict) -> dict:
    """Ẩn giá vốn nếu user không có quyền."""
    res = dict(product)
    if not can_view_or_edit_cost_price(user):
        res["cost_price"] = None
    return res


def get_all_products(
    search: Optional[str] = None,
    product_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    current_user: Optional[dict] = None,
) -> Dict:
    results = fake_products_db

    if search and search.strip():
        s = search.strip().lower()
        results = [
            p for p in results
            if s in p["code"].lower() or s in p["name"].lower()
        ]

    if product_type and product_type.strip():
        pt = product_type.strip().upper()
        results = [p for p in results if p["product_type"] == pt]

    if status_filter and status_filter.strip():
        sf = status_filter.strip().upper()
        results = [p for p in results if p["status"] == sf]

    total = len(results)
    skip = (page - 1) * limit
    paged_items = results[skip : skip + limit]

    masked_items = [mask_product_product(p, current_user) if current_user else p for p in paged_items]
    total_pages = max(1, math.ceil(total / limit)) if total > 0 else 1

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "products": masked_items,
    }


def mask_product_product(product: dict, user: dict) -> dict:
    return mask_product_cost_price(product, user)


def get_product_by_id(product_id: int, current_user: Optional[dict] = None) -> dict:
    for p in fake_products_db:
        if p["id"] == product_id:
            return mask_product_cost_price(p, current_user) if current_user else p
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Không tìm thấy sản phẩm / dịch vụ với ID {product_id}",
    )


def create_product(product_in: ProductCreate, current_user: dict) -> dict:
    """
    AC S2-05: Khai báo mã, tên, loại, đơn vị tính, giá niêm yết, giá sàn, giá vốn.
    Chỉ Manager/Admin mới được thao tác quản lý danh mục.
    """
    clean_code = product_in.code.strip().upper()
    for p in fake_products_db:
        if p["code"].upper() == clean_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mã sản phẩm '{clean_code}' đã tồn tại trong danh mục",
            )

    if product_in.floor_price > product_in.list_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giá sàn không được lớn hơn giá niêm yết",
        )

    # Nếu user không có quyền xem/sửa giá vốn mà truyền cost_price -> bỏ qua hoặc cảnh báo
    cost_price = product_in.cost_price if can_view_or_edit_cost_price(current_user) else None

    next_id = max([p["id"] for p in fake_products_db], default=0) + 1
    new_prod = {
        "id": next_id,
        "code": clean_code,
        "name": product_in.name.strip(),
        "product_type": product_in.product_type.value,
        "unit": product_in.unit.strip(),
        "list_price": product_in.list_price,
        "floor_price": product_in.floor_price,
        "cost_price": cost_price,
        "status": ProductStatus.ACTIVE.value,
        "created_at": datetime.utcnow(),
    }
    fake_products_db.append(new_prod)
    return mask_product_cost_price(new_prod, current_user)


def update_product(product_id: int, product_in: ProductUpdate, current_user: dict) -> dict:
    product = None
    for p in fake_products_db:
        if p["id"] == product_id:
            product = p
            break
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy sản phẩm với ID {product_id}",
        )

    if product_in.name is not None:
        product["name"] = product_in.name.strip()
    if product_in.product_type is not None:
        product["product_type"] = product_in.product_type.value
    if product_in.unit is not None:
        product["unit"] = product_in.unit.strip()
    if product_in.list_price is not None:
        product["list_price"] = product_in.list_price
    if product_in.floor_price is not None:
        product["floor_price"] = product_in.floor_price

    if product["floor_price"] > product["list_price"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giá sàn không được lớn hơn giá niêm yết",
        )

    # AC S2-05: Giá vốn chỉ GĐ kinh doanh / Admin xem và sửa được
    if product_in.cost_price is not None:
        if not can_view_or_edit_cost_price(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ Giám đốc kinh doanh và Quản trị viên mới có quyền xem và sửa giá vốn",
            )
        product["cost_price"] = product_in.cost_price

    if product_in.status is not None:
        product["status"] = product_in.status.value

    return mask_product_cost_price(product, current_user)


def delete_or_discontinue_product(product_id: int, current_user: dict) -> dict:
    """
    AC S2-05: Sản phẩm đã xuất hiện trong báo giá thì KHÔNG XOÁ ĐƯỢC, chỉ ngừng kinh doanh.
    """
    product = None
    for p in fake_products_db:
        if p["id"] == product_id:
            product = p
            break
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy sản phẩm với ID {product_id}",
        )

    if product_id in QUOTED_PRODUCT_IDS:
        # Tự động chuyển sang NGỪNG KINH DOANH và báo cho người dùng
        product["status"] = ProductStatus.DISCONTINUED.value
        return {
            "success": True,
            "action": "DISCONTINUED",
            "message": f"Sản phẩm '{product['name']}' đã xuất hiện trong báo giá nên không thể xoá, hệ thống đã tự động chuyển sang trạng thái Ngừng kinh doanh.",
            "product": mask_product_cost_price(product, current_user),
        }
    else:
        # Chưa xuất hiện trong báo giá -> xoá thực sự
        fake_products_db.remove(product)
        return {
            "success": True,
            "action": "DELETED",
            "message": f"Đã xoá thành công sản phẩm '{product['name']}'.",
            "product": None,
        }


def check_discount_approval(product_id: int, proposed_price: float) -> dict:
    """
    AC S2-05: Giá sàn là ngưỡng để xác định báo giá có cần duyệt chiết khấu hay không.
    Nếu giá chào bán < giá sàn -> Bắt buộc duyệt chiết khấu!
    """
    product = None
    for p in fake_products_db:
        if p["id"] == product_id:
            product = p
            break
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy sản phẩm với ID {product_id}",
        )

    needs_approval = proposed_price < product["floor_price"]
    if needs_approval:
        reason = f"Đơn giá chào bán ({proposed_price:,.0f} đ) thấp hơn giá sàn ({product['floor_price']:,.0f} đ). Bắt buộc phải có phê duyệt chiết khấu từ Giám đốc kinh doanh."
    else:
        reason = f"Đơn giá chào bán ({proposed_price:,.0f} đ) đạt mức giá sàn quy định ({product['floor_price']:,.0f} đ). Không cần duyệt chiết khấu đặc biệt."

    return {
        "product_id": product["id"],
        "product_name": product["name"],
        "list_price": product["list_price"],
        "floor_price": product["floor_price"],
        "proposed_price": proposed_price,
        "needs_approval": needs_approval,
        "reason": reason,
    }
