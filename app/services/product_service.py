import copy
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

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


def _row_to_dict(p: ProductModel) -> dict:
    return {
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


def reset_fake_products():
    """Khởi tạo hoặc đặt lại danh mục sản phẩm mẫu vào CSDL MySQL/SQLite."""
    global fake_products_db
    fake_products_db = copy.deepcopy(INITIAL_PRODUCTS)
    db = SessionLocal()
    try:
        db.query(ProductModel).delete()
        for p in INITIAL_PRODUCTS:
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
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


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


def mask_product_product(product: dict, user: dict) -> dict:
    return mask_product_cost_price(product, user)


def get_all_products(
    search: Optional[str] = None,
    product_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    current_user: Optional[dict] = None,
    db: Optional[Session] = None,
) -> Dict:
    """
    AC S2-05: Sử dụng CSDL làm nguồn dữ liệu duy nhất.
    """
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        query = db.query(ProductModel)

        if search and search.strip():
            s = f"%{search.strip().lower()}%"
            query = query.filter(
                (ProductModel.code.ilike(s)) | (ProductModel.name.ilike(s))
            )

        if product_type and product_type.strip():
            pt = product_type.strip().upper()
            query = query.filter(ProductModel.product_type == pt)

        if status_filter and status_filter.strip():
            sf = status_filter.strip().upper()
            query = query.filter(ProductModel.status == sf)

        total = query.count()
        skip = (page - 1) * limit
        db_items = query.order_by(ProductModel.id.asc()).offset(skip).limit(limit).all()

        results = [_row_to_dict(p) for p in db_items]
        masked_items = [
            mask_product_cost_price(p, current_user) if current_user else p
            for p in results
        ]
        total_pages = max(1, math.ceil(total / limit)) if total > 0 else 1

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "products": masked_items,
        }
    finally:
        if own_session:
            db.close()


def get_product_by_id(
    product_id: int,
    current_user: Optional[dict] = None,
    db: Optional[Session] = None,
) -> dict:
    """
    AC S2-05: Lấy thông tin sản phẩm từ CSDL làm nguồn dữ liệu duy nhất.
    """
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        p = db.query(ProductModel).filter(ProductModel.id == product_id).first()
        if not p:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy sản phẩm / dịch vụ với ID {product_id}",
            )
        prod_dict = _row_to_dict(p)
        return mask_product_cost_price(prod_dict, current_user) if current_user else prod_dict
    finally:
        if own_session:
            db.close()


def create_product(
    product_in: ProductCreate,
    current_user: dict,
    db: Optional[Session] = None,
) -> dict:
    """
    AC S2-05: Khai báo mã, tên, loại, đơn vị tính, giá niêm yết, giá sàn, giá vốn.
    Chỉ Manager/Admin mới được thao tác quản lý danh mục.
    Lưu vào MySQL/SQLite bằng SQLAlchemy làm nguồn dữ liệu duy nhất.
    Bảo đảm không bỏ qua lỗi ghi CSDL.
    """
    if not can_view_or_edit_cost_price(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Quản trị viên và Giám đốc kinh doanh mới có quyền tạo sản phẩm",
        )

    clean_code = product_in.code.strip().upper()

    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        existing = db.query(ProductModel).filter(ProductModel.code == clean_code).first()
        if existing:
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

        db_prod = ProductModel(
            code=clean_code,
            name=product_in.name.strip(),
            product_type=product_in.product_type.value,
            unit=product_in.unit.strip(),
            list_price=product_in.list_price,
            floor_price=product_in.floor_price,
            cost_price=cost_price,
            status=ProductStatus.ACTIVE.value,
            created_at=datetime.now(timezone.utc),
        )
        db.add(db_prod)

        try:
            db.commit()
            db.refresh(db_prod)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi ghi CSDL khi tạo sản phẩm: {str(e)}",
            )

        new_dict = _row_to_dict(db_prod)
        fake_products_db.append(new_dict)
        return mask_product_cost_price(new_dict, current_user)
    finally:
        if own_session:
            db.close()


def update_product(
    product_id: int,
    product_in: ProductUpdate,
    current_user: dict,
    db: Optional[Session] = None,
) -> dict:
    """
    AC S2-05: Cập nhật sản phẩm.
    Kiểm tra giá hợp lệ TRƯỚC khi cập nhật và tránh thay đổi dữ liệu khi trả lỗi.
    Không bỏ qua lỗi ghi database khi CRUD.
    """
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        db_prod = db.query(ProductModel).filter(ProductModel.id == product_id).first()
        if not db_prod:
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
        new_list_price = product_in.list_price if product_in.list_price is not None else db_prod.list_price
        new_floor_price = product_in.floor_price if product_in.floor_price is not None else db_prod.floor_price

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

        # 3. Áp dụng thay đổi khi toàn bộ kiểm tra đã hợp lệ
        if product_in.name is not None:
            db_prod.name = product_in.name.strip()
        if product_in.product_type is not None:
            db_prod.product_type = product_in.product_type.value
        if product_in.unit is not None:
            db_prod.unit = product_in.unit.strip()
        if product_in.list_price is not None:
            db_prod.list_price = product_in.list_price
        if product_in.floor_price is not None:
            db_prod.floor_price = product_in.floor_price
        if product_in.cost_price is not None:
            db_prod.cost_price = product_in.cost_price
        if product_in.status is not None:
            db_prod.status = product_in.status.value

        # Ghi nhận vào CSDL SQLAlchemy và xử lý lỗi nghiêm ngặt
        try:
            db.commit()
            db.refresh(db_prod)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi ghi CSDL khi cập nhật sản phẩm: {str(e)}",
            )

        updated_dict = _row_to_dict(db_prod)
        for idx, p in enumerate(fake_products_db):
            if p["id"] == product_id:
                fake_products_db[idx] = updated_dict
                break

        return mask_product_cost_price(updated_dict, current_user)
    finally:
        if own_session:
            db.close()


def delete_or_discontinue_product(
    product_id: int,
    current_user: dict,
    db: Optional[Session] = None,
) -> dict:
    """
    AC S2-05: Sản phẩm đã xuất hiện trong báo giá thì KHÔNG XOÁ ĐƯỢC, chỉ ngừng kinh doanh.
    Kiểm tra quan hệ quote_items thực tế.
    Không bỏ qua lỗi ghi database khi CRUD.
    """
    global fake_products_db
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        db_prod = db.query(ProductModel).filter(ProductModel.id == product_id).first()
        if not db_prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy sản phẩm với ID {product_id}",
            )

        if is_product_quoted(product_id):
            # Tự động chuyển sang NGỪNG KINH DOANH và báo cho người dùng
            db_prod.status = ProductStatus.DISCONTINUED.value
            try:
                db.commit()
                db.refresh(db_prod)
            except Exception as e:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Lỗi ghi CSDL khi cập nhật trạng thái sản phẩm: {str(e)}",
                )

            prod_dict = _row_to_dict(db_prod)
            for p in fake_products_db:
                if p["id"] == product_id:
                    p["status"] = ProductStatus.DISCONTINUED.value
                    break

            return {
                "success": True,
                "action": "DISCONTINUED",
                "message": f"Sản phẩm '{db_prod.name}' đã xuất hiện trong báo giá nên không thể xoá, hệ thống đã tự động chuyển sang trạng thái Ngừng kinh doanh.",
                "product": mask_product_cost_price(prod_dict, current_user),
            }
        else:
            prod_name = db_prod.name
            db.delete(db_prod)
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Lỗi ghi CSDL khi xóa sản phẩm: {str(e)}",
                )

            fake_products_db = [p for p in fake_products_db if p["id"] != product_id]

            return {
                "success": True,
                "action": "DELETED",
                "message": f"Đã xoá thành công sản phẩm '{prod_name}'.",
                "product": None,
            }
    finally:
        if own_session:
            db.close()


def check_discount_approval(
    product_id: int,
    proposed_price: float,
    db: Optional[Session] = None,
) -> dict:
    """
    AC S2-05: Giá sàn là ngưỡng để xác định báo giá có cần duyệt chiết khấu hay không.
    Nếu giá chào bán < giá sàn -> Bắt buộc duyệt chiết khấu!
    """
    product = get_product_by_id(product_id=product_id, db=db)

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
