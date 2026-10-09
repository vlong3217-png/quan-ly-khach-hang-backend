"""
Quote API router with role-based access control and data scope filtering.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.database import get_db
from sqlalchemy.orm import Session
from app.core.dependencies import (
    DataScope,
    check_scope_access,
    get_current_user,
    require_roles,
    resolve_scope,
)
from app.schemas.quote import (
    QuoteCreate,
    QuoteListResponse,
    QuoteResponse,
    QuoteUpdate,
)
from app.services.quote_service import (
    create_quote_record,
    delete_quote_record,
    get_quotes_by_scope,
    get_raw_quote_by_id,
    update_quote_record,
)

router = APIRouter(
    prefix="/quotes",
    tags=["Quotes"],
)


@router.get("", response_model=QuoteListResponse)
def list_quotes(
    scope: Optional[str] = Query(
        None,
        description="Data scope filter: MY, MY_TEAM, TEAM, or ALL. Defaults based on role.",
    ),
    search: Optional[str] = Query(None, description="Search query"),
    q: Optional[str] = Query(None, description="Search query alias"),
    current_user: dict = Depends(get_current_user),
):
    effective_scope = resolve_scope(current_user, scope)
    search_query = search or q
    quotes = get_quotes_by_scope(current_user, effective_scope, search=search_query)
    return {
        "scope": effective_scope.value,
        "total": len(quotes),
        "quotes": quotes,
    }


@router.get("/{quote_id}", response_model=QuoteResponse)
def get_quote(
    quote_id: int,
    current_user: dict = Depends(get_current_user),
):
    q_item = get_raw_quote_by_id(quote_id)
    if q_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy báo giá",
        )

    if not check_scope_access(current_user, q_item["owner_id"], q_item.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập dữ liệu báo giá này",
        )

    return q_item


@router.post("", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED)
def create_quote(
    payload: QuoteCreate,
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    quote_data = payload.model_dump()

    # AC S2-05: Tích hợp kiểm tra giá sàn vào quy trình tạo báo giá
    prod_id = quote_data.get("product_id")
    check_price = quote_data.get("unit_price") or quote_data.get("amount")
    if prod_id and check_price:
        try:
            from app.services.product_service import check_discount_approval
            discount_info = check_discount_approval(prod_id, float(check_price), db=db)
            if discount_info["needs_approval"]:
                quote_data["requires_discount_approval"] = True
                quote_data["discount_approval_status"] = "PENDING_APPROVAL"
            else:
                quote_data["requires_discount_approval"] = False
                quote_data["discount_approval_status"] = "APPROVED"
        except HTTPException:
            pass

    new_q = create_quote_record(quote_data, current_user)

    # Ghi nhận Audit Log cho nghiệp vụ định giá / chiết khấu (AC S2-04) cùng transaction
    from app.services.audit_log_service import log_change
    user_name = current_user.get("full_name", current_user.get("username", "User"))
    log_change(
        user_id=current_user["id"],
        user_name=user_name,
        entity_type="DISCOUNT",
        entity_id=f"QUOTE-{new_q['id']}",
        action="CREATE_QUOTE",
        field_name="amount",
        old_value=None,
        new_value=str(new_q["amount"]),
        db=db,
    )
    if new_q.get("unit_price") is not None:
        log_change(
            user_id=current_user["id"],
            user_name=user_name,
            entity_type="DISCOUNT",
            entity_id=f"QUOTE-{new_q['id']}",
            action="CREATE_QUOTE",
            field_name="unit_price",
            old_value=None,
            new_value=str(new_q["unit_price"]),
            db=db,
        )
    db.commit()

    return new_q


@router.put("/{quote_id}", response_model=QuoteResponse)
def update_quote(
    quote_id: int,
    payload: QuoteUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q_item = get_raw_quote_by_id(quote_id)
    if q_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy báo giá",
        )

    if not check_scope_access(current_user, q_item["owner_id"], q_item.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền chỉnh sửa dữ liệu báo giá này",
        )

    quote_update_data = payload.model_dump(exclude_unset=True)

    # AC S2-05: Kiểm tra giá sàn khi cập nhật báo giá
    prod_id = quote_update_data.get("product_id") or q_item.get("product_id")
    check_price = quote_update_data.get("unit_price") or quote_update_data.get("amount")
    if prod_id and check_price:
        try:
            from app.services.product_service import check_discount_approval
            discount_info = check_discount_approval(prod_id, float(check_price), db=db)
            if discount_info["needs_approval"]:
                quote_update_data["requires_discount_approval"] = True
                quote_update_data["discount_approval_status"] = "PENDING_APPROVAL"
            else:
                quote_update_data["requires_discount_approval"] = False
                quote_update_data["discount_approval_status"] = "APPROVED"
        except HTTPException:
            pass

    old_amount = q_item["amount"]
    old_unit_price = q_item.get("unit_price")
    old_status = q_item.get("discount_approval_status")

    updated = update_quote_record(quote_id, quote_update_data)

    # Ghi nhận Audit Log nếu thay đổi giá trị/chiết khấu (AC S2-04) cùng transaction
    from app.services.audit_log_service import log_change
    user_name = current_user.get("full_name", current_user.get("username", "User"))

    has_logged = False
    if payload.amount is not None and payload.amount != old_amount:
        log_change(
            user_id=current_user["id"],
            user_name=user_name,
            entity_type="DISCOUNT",
            entity_id=f"QUOTE-{quote_id}",
            action="UPDATE_DISCOUNT",
            field_name="amount",
            old_value=str(old_amount),
            new_value=str(updated["amount"]),
            db=db,
        )
        has_logged = True

    if payload.unit_price is not None and payload.unit_price != old_unit_price:
        log_change(
            user_id=current_user["id"],
            user_name=user_name,
            entity_type="DISCOUNT",
            entity_id=f"QUOTE-{quote_id}",
            action="UPDATE_DISCOUNT",
            field_name="unit_price",
            old_value=str(old_unit_price),
            new_value=str(updated.get("unit_price")),
            db=db,
        )
        has_logged = True

    if updated.get("discount_approval_status") != old_status and updated.get("discount_approval_status") is not None:
        log_change(
            user_id=current_user["id"],
            user_name=user_name,
            entity_type="DISCOUNT",
            entity_id=f"QUOTE-{quote_id}",
            action="UPDATE_DISCOUNT",
            field_name="discount_approval_status",
            old_value=str(old_status),
            new_value=str(updated.get("discount_approval_status")),
            db=db,
        )
        has_logged = True

    if has_logged:
        db.commit()

    return updated


@router.delete(
    "/{quote_id}",
    dependencies=[Depends(require_roles(["ADMIN"]))],
)
def delete_quote(quote_id: int):
    success = delete_quote_record(quote_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy báo giá để xóa",
        )
    return {"message": f"Đã xóa báo giá ID {quote_id}"}
