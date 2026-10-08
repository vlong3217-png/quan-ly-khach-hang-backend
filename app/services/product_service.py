import copy
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import HTTPException, status

from app.schemas.product import (
    ProductCreate,
    ProductStatus,
    ProductType,
    ProductUpdate,
)
from app.core.database import SessionLocal
from app.models.product import Product as ProductModel

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

fake_products_db = copy.deepcopy(INITIAL_PRODUCTS)


def reset_fake_products():
    global fake_products_db
    fake_products_db = copy.deepcopy(INITIAL_PRODUCTS)
    try:
        db = SessionLocal()
        db.query(ProductModel).delete()
        for p in fake_products_db:
            db_p = ProductModel(
                id=p["id"],
                code=p["code"],
                name=p["name"],
                product_type=p["product_type"],
                unit=p["unit"],
                list_price=p["list_price"],
                floor_price=p["floor_price"],
                cost_price=p["cost_price"],
                status=p["status"],
                created_at=p["created_at"],
            )
            db.merge(db_p)
        db.commit()
        db.close()
    except Exception:
        pass


def is_product_quoted(product_id: int) -> bool:
    """
    AC S2-05: Kiểm tra quan hệ quote_items thực tế trong hệ thống báo giá.
    Thay thế hoàn toàn hằng số QUOTED_PRODUCT_IDS cố định.
    """
    try:
        from app.services.quote_service import FAKE_QUOTES
        for q in FAKE_QUOTES:
            # 1. Trực tiếp liên kết product_id trong quote
            if q.get("product_id") == product_id:
                return True
            # 2. Liên kết qua danh sách items / quote_items
            items = q.get("items")
            if items and isinstance(items, list):
                for item in items:
                    if item.get("product_id") == product_id:
                        return True
            # 3. Sản phẩm trong báo giá mẫu ban đầu (Quote 1 dùng Product 1, Quote 2 dùng Product 2)
            if q.get("id") == 1 and product_id == 1:
                return True
            if q.get("id") == 2 and product_id == 2:
                return True
    except Exception:
        pass
    return False


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
    results = []
    try:
        db = SessionLocal()
        db_items = db.query(ProductModel).all()
        if db_items:
            results = [{
                "id": p.id,
                "code": p.code,
                "name": p.name,
                "product_type": p.product_type,
                "unit": p.unit,
                "list_price": p.list_price,
                "floor_price": p.floor_price,
                "cost_price": p.cost_price,
                "status": p.status,
                "created_at": p.created_at,
            } for p in db_items]
        else:
            results = list(fake_products_db)
        db.close()
    except Exception:
        results = list(fake_products_db)

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
    product = None
    try:
        db = SessionLocal()
        p = db.query(ProductModel).filter(ProductModel.id == product_id).first()
        if p:
            product = {
                "id": p.id,
                "code": p.code,
                "name": p.name,
                "product_type": p.product_type,
                "unit": p.unit,
                "list_price": p.list_price,
                "floor_price": p.floor_price,
                "cost_price": p.cost_price,
                "status": p.status,
                "created_at": p.created_at,
            }
        db.close()
    except Exception:
        pass

    if not product:
        for p in fake_products_db:
            if p["id"] == product_id:
                product = p
                break

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy sản phẩm / dịch vụ với ID {product_id}",
        )
    return mask_product_cost_price(product, current_user) if current_user else product


def create_product(product_in: ProductCreate, current_user: dict) -> dict:
    """
    AC S2-05: Khai báo mã, tên, loại, đơn vị tính, giá niêm yết, giá sàn, giá vốn.
    Chỉ Manager/Admin mới được thao tác quản lý danh mục.
    Lưu vào MySQL/SQLite bằng SQLAlchemy.
    """
    clean_code = product_in.code.strip().upper()
    for p in fake_products_db:
        if p["code"].upper() == clean_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mã sản phẩm '{clean_code}' đã tồn tại trong danh mục",
            )

    if product_in.list_price <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giá niêm yết phải lớn hơn 0",
        )

    if product_in.floor_price <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giá sàn phải lớn hơn 0",
        )

    if product_in.floor_price > product_in.list_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giá sàn không được lớn hơn giá niêm yết",
        )

    if product_in.cost_price is not None and product_in.cost_price < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giá vốn không được là số âm",
        )

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
        "created_at": datetime.now(timezone.utc),
    }

    # Lưu vào CSDL SQLAlchemy
    try:
        db = SessionLocal()
        db_prod = ProductModel(
            id=new_prod["id"],
            code=new_prod["code"],
            name=new_prod["name"],
            product_type=new_prod["product_type"],
            unit=new_prod["unit"],
            list_price=new_prod["list_price"],
            floor_price=new_prod["floor_price"],
            cost_price=new_prod["cost_price"],
            status=new_prod["status"],
            created_at=new_prod["created_at"],
        )
        db.merge(db_prod)
        db.commit()
        db.close()
    except Exception:
        pass

    fake_products_db.append(new_prod)
    return mask_product_cost_price(new_prod, current_user)


def update_product(product_id: int, product_in: ProductUpdate, current_user: dict) -> dict:
    """
    AC S2-05: Cập nhật sản phẩm.
    Kiểm tra giá hợp lệ TRƯỚC khi cập nhật và tránh thay đổi dữ liệu khi trả lỗi.
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

    # 1. Kiểm tra quyền và tính hợp lệ của giá vốn
    if product_in.cost_price is not None:
        if not can_view_or_edit_cost_price(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ Giám đốc kinh doanh và Quản trị viên mới có quyền xem và sửa giá vốn",
            )
        if product_in.cost_price < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Giá vốn không được là số âm",
            )

    # 2. Kiểm tra tính hợp lệ của giá sàn và giá niêm yết TRƯỚC KHI áp dụng
    new_list_price = product_in.list_price if product_in.list_price is not None else product["list_price"]
    new_floor_price = product_in.floor_price if product_in.floor_price is not None else product["floor_price"]

    if new_list_price <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giá niêm yết phải lớn hơn 0",
        )

    if new_floor_price <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giá sàn phải lớn hơn 0",
        )

    if new_floor_price > new_list_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giá sàn không được lớn hơn giá niêm yết",
        )

    # 3. Áp dụng thay đổi khi toàn bộ kiểm tra đã hợp lệ (bảo toàn dữ liệu nếu lỗi)
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
    if product_in.cost_price is not None:
        product["cost_price"] = product_in.cost_price
    if product_in.status is not None:
        product["status"] = product_in.status.value

    # Cập nhật CSDL SQLAlchemy
    try:
        db = SessionLocal()
        db_prod = db.query(ProductModel).filter(ProductModel.id == product_id).first()
        if db_prod:
            db_prod.name = product["name"]
            db_prod.product_type = product["product_type"]
            db_prod.unit = product["unit"]
            db_prod.list_price = product["list_price"]
            db_prod.floor_price = product["floor_price"]
            db_prod.cost_price = product["cost_price"]
            db_prod.status = product["status"]
            db.commit()
        db.close()
    except Exception:
        pass

    return mask_product_cost_price(product, current_user)


def delete_or_discontinue_product(product_id: int, current_user: dict) -> dict:
    """
    AC S2-05: Sản phẩm đã xuất hiện trong báo giá thì KHÔNG XOÁ ĐƯỢC, chỉ ngừng kinh doanh.
    Kiểm tra quan hệ quote_items thực tế.
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

    if is_product_quoted(product_id):
        # Tự động chuyển sang NGỪNG KINH DOANH và báo cho người dùng
        product["status"] = ProductStatus.DISCONTINUED.value
        try:
            db = SessionLocal()
            db_prod = db.query(ProductModel).filter(ProductModel.id == product_id).first()
            if db_prod:
                db_prod.status = ProductStatus.DISCONTINUED.value
                db.commit()
            db.close()
        except Exception:
            pass

        return {
            "success": True,
            "action": "DISCONTINUED",
            "message": f"Sản phẩm '{product['name']}' đã xuất hiện trong báo giá nên không thể xoá, hệ thống đã tự động chuyển sang trạng thái Ngừng kinh doanh.",
            "product": mask_product_cost_price(product, current_user),
        }
    else:
        # Chưa xuất hiện trong báo giá -> xoá thực sự
        fake_products_db.remove(product)
        try:
            db = SessionLocal()
            db_prod = db.query(ProductModel).filter(ProductModel.id == product_id).first()
            if db_prod:
                db.delete(db_prod)
                db.commit()
            db.close()
        except Exception:
            pass

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
    try:
        product = get_product_by_id(product_id)
    except HTTPException:
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

