"""
Quote API router with role-based access control and data scope filtering (S7-01).
"""

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
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
    QuoteApprovalRequest,
    QuoteApprovalHistoryItem,
    QuoteApprovalHistoryListResponse,
    QuoteVersionCreateRequest,
    QuoteVersionListResponse,
    QuoteComparisonResponse,
)
from app.schemas.contract import ContractConvertRequest, ContractResponse
from app.services.contract_service import convert_quote_to_contract
from app.services.pdf_template_service import get_template_by_id, get_default_template
from app.services.pdf_generator_service import generate_quote_pdf
from app.services.quote_service import (
    create_quote_record,
    delete_quote_record,
    get_quotes_by_scope,
    get_raw_quote_by_id,
    update_quote_record,
    submit_quote_record,
    approve_quote_record,
    reject_quote_record,
    return_quote_record,
    send_quote_to_customer_record,
    get_quote_approval_history,
    get_pending_approvals_by_scope,
    create_new_quote_version,
    set_active_quote_version,
    get_all_quote_versions,
    compare_quote_versions,
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
    opportunity_id: Optional[int] = Query(None, description="Lọc theo mã cơ hội"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái báo giá (DRAFT, PENDING_APPROVAL, APPROVED, REJECTED, RETURNED, SENT...)"),
    search: Optional[str] = Query(None, description="Search query"),
    q: Optional[str] = Query(None, description="Search query alias"),
    page: Optional[int] = Query(None, ge=1, description="Trang hiện tại (bắt đầu từ 1)"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Số lượng báo giá mỗi trang (mặc định 20)"),
    skip: Optional[int] = Query(None, ge=0, description="Vị trí bắt đầu (offset)"),
    current_user: dict = Depends(get_current_user),
):
    import math

    effective_scope = resolve_scope(current_user, scope)
    search_query = search or q
    all_quotes = get_quotes_by_scope(
        current_user,
        effective_scope,
        search=search_query,
        opportunity_id=opportunity_id,
        status=status,
    )
    total = len(all_quotes)

    effective_limit = limit if limit is not None else 20
    if page is not None:
        effective_skip = (page - 1) * effective_limit
        effective_page = page
    elif skip is not None:
        effective_skip = skip
        effective_page = (effective_skip // effective_limit) + 1
    else:
        effective_skip = 0
        effective_page = 1

    paged_items = all_quotes[effective_skip : effective_skip + effective_limit]
    total_pages = max(1, math.ceil(total / effective_limit)) if total > 0 else 1

    return {
        "scope": effective_scope.value,
        "total": total,
        "quotes": paged_items,
        "page": effective_page,
        "limit": effective_limit,
        "skip": effective_skip,
        "total_pages": total_pages,
    }


@router.get("/pending-approvals", response_model=QuoteListResponse)
def list_pending_approvals(
    page: Optional[int] = Query(None, ge=1, description="Trang hiện tại (bắt đầu từ 1)"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Số lượng mỗi trang"),
    skip: Optional[int] = Query(None, ge=0, description="Vị trí bắt đầu"),
    current_user: dict = Depends(require_roles(["ADMIN", "DIRECTOR", "MANAGER"])),
):
    """Lấy danh sách các báo giá đang chờ phê duyệt (S7-02)."""
    import math
    effective_scope = resolve_scope(current_user, None)
    pending_quotes = get_pending_approvals_by_scope(current_user, effective_scope)
    total = len(pending_quotes)

    effective_limit = limit if limit is not None else 20
    if page is not None:
        effective_skip = (page - 1) * effective_limit
        effective_page = page
    elif skip is not None:
        effective_skip = skip
        effective_page = (effective_skip // effective_limit) + 1
    else:
        effective_skip = 0
        effective_page = 1

    paged_items = pending_quotes[effective_skip : effective_skip + effective_limit]
    total_pages = max(1, math.ceil(total / effective_limit)) if total > 0 else 1

    return {
        "scope": effective_scope.value,
        "total": total,
        "quotes": paged_items,
        "page": effective_page,
        "limit": effective_limit,
        "skip": effective_skip,
        "total_pages": total_pages,
    }


@router.get("/by-opportunity/{opportunity_id}", response_model=QuoteListResponse)
def list_quotes_by_opportunity(
    opportunity_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Lấy danh sách các báo giá thuộc một cơ hội (S7-01)."""
    effective_scope = resolve_scope(current_user, None)
    quotes = get_quotes_by_scope(current_user, effective_scope, opportunity_id=opportunity_id)
    return {
        "scope": effective_scope.value,
        "total": len(quotes),
        "quotes": quotes,
        "page": 1,
        "limit": len(quotes) if quotes else 20,
        "skip": 0,
        "total_pages": 1,
    }


@router.get("/compare", response_model=QuoteComparisonResponse)
def compare_quotes_query(
    version_a_id: int = Query(..., description="ID của phiên bản thứ nhất (hoặc phiên bản gốc)"),
    version_b_id: int = Query(..., description="ID của phiên bản thứ hai (hoặc phiên bản mới)"),
    current_user: dict = Depends(get_current_user),
):
    """
    So sánh song song (side-by-side) 2 phiên bản báo giá bất kỳ (S7-03 AC 2):
    - Tài chính: delta subtotal, discount, vat, grand total.
    - Hàng hóa: row-by-row matching theo product_id/item_id (ADDED, REMOVED, MODIFIED, UNCHANGED).
    - Điều khoản: valid_until, payment_terms, delivery_terms, notes.
    """
    qa = get_raw_quote_by_id(version_a_id)
    qb = get_raw_quote_by_id(version_b_id)
    if qa is None or qb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy một trong hai phiên bản báo giá để so sánh",
        )
    if not check_scope_access(current_user, qa["owner_id"], qa.get("team_id")) or not check_scope_access(current_user, qb["owner_id"], qb.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập dữ liệu một trong hai báo giá này",
        )

    return compare_quote_versions(version_a_id, version_b_id)


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
    current_user: dict = Depends(get_current_user),  # S7-01: Cho phép Sales Rep (USER) tạo báo giá
    db: Session = Depends(get_db),
):
    # AC 4: Validate hạn hiệu lực báo giá không được ở trong quá khứ
    if payload.valid_until and payload.valid_until < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ngày hết hạn hiệu lực báo giá không thể ở trong quá khứ",
        )

    quote_data = payload.model_dump()

    # AC S2-05: Tích hợp kiểm tra giá sàn vào quy trình tạo báo giá đơn lẻ (tương thích backward)
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

    new_q = create_quote_record(quote_data, current_user, db=db)

    try:
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
    except Exception:
        pass

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

    # AC 4: Validate hạn hiệu lực không được ở trong quá khứ nếu cập nhật
    if payload.valid_until and payload.valid_until < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ngày hết hạn hiệu lực báo giá không thể ở trong quá khứ",
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

    updated = update_quote_record(quote_id, quote_update_data, current_user=current_user, db=db)

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
        try:
            db.commit()
        except Exception:
            pass

    return updated


@router.post("/{quote_id}/submit", response_model=QuoteResponse)
def submit_quote(
    quote_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Chuyển bản nháp sang chính thức / gửi duyệt (S7-01 & S7-02):
    - AC 1: Chiết khấu dưới ngưỡng 1 (<10% và không dưới giá sàn) thì tự động thông qua (AUTO_APPROVED).
    - AC 2: Vượt ngưỡng thì chuyển PENDING_APPROVAL.
    """
    q_item = get_raw_quote_by_id(quote_id)
    if q_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy báo giá",
        )

    if not check_scope_access(current_user, q_item["owner_id"], q_item.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền gửi duyệt báo giá này",
        )

    submitted = submit_quote_record(quote_id, current_user=current_user, db=db)
    return submitted


@router.post("/{quote_id}/approve", response_model=QuoteResponse)
def approve_quote(
    quote_id: int,
    payload: Optional[QuoteApprovalRequest] = None,
    current_user: dict = Depends(require_roles(["ADMIN", "DIRECTOR", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """
    Phê duyệt báo giá (S7-02 AC 2 & AC 3):
    - Trưởng nhóm (MANAGER), Giám đốc (DIRECTOR) hoặc Admin duyệt.
    - Nếu báo giá yêu cầu cấp DIRECTOR mà người duyệt là MANAGER -> Bị từ chối HTTP 403 Forbidden.
    """
    comments = payload.comments if payload else None
    return approve_quote_record(quote_id, current_user=current_user, comments=comments, db=db)


@router.post("/{quote_id}/reject", response_model=QuoteResponse)
def reject_quote(
    quote_id: int,
    payload: QuoteApprovalRequest,
    current_user: dict = Depends(require_roles(["ADMIN", "DIRECTOR", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """
    Từ chối duyệt báo giá (S7-02 AC 3):
    - Bắt buộc phải có lý do/ý kiến từ chối (nếu không trả về HTTP 400 Bad Request).
    """
    if not payload or not payload.comments or not payload.comments.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bắt buộc nhập ý kiến khi từ chối duyệt báo giá (S7-02 AC)",
        )
    return reject_quote_record(quote_id, current_user=current_user, comments=payload.comments, db=db)


@router.post("/{quote_id}/return", response_model=QuoteResponse)
def return_quote(
    quote_id: int,
    payload: QuoteApprovalRequest,
    current_user: dict = Depends(require_roles(["ADMIN", "DIRECTOR", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """
    Trả lại báo giá để nhân viên sửa lại (S7-02 AC 3):
    - Bắt buộc phải có ý kiến yêu cầu chỉnh sửa (nếu không trả về HTTP 400 Bad Request).
    - Chuyển trạng thái sang RETURNED và mở lại is_draft = True để sửa tiếp.
    """
    if not payload or not payload.comments or not payload.comments.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bắt buộc nhập ý kiến khi trả lại báo giá yêu cầu sửa (S7-02 AC)",
        )
    return return_quote_record(quote_id, current_user=current_user, comments=payload.comments, db=db)


@router.post("/{quote_id}/send", response_model=QuoteResponse)
def send_quote(
    quote_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Gửi báo giá cho khách hàng (S7-02 AC 4):
    - Chỉ báo giá đã được phê duyệt (status == APPROVED) mới được phép gửi cho khách.
    - Nếu chưa duyệt (DRAFT, PENDING_APPROVAL, REJECTED, RETURNED) -> Báo lỗi HTTP 400 Bad Request.
    """
    q_item = get_raw_quote_by_id(quote_id)
    if q_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy báo giá",
        )

    if not check_scope_access(current_user, q_item["owner_id"], q_item.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền gửi báo giá này",
        )

    return send_quote_to_customer_record(quote_id, current_user=current_user, db=db)


@router.get("/{quote_id}/approval-history", response_model=QuoteApprovalHistoryListResponse)
def get_quote_history(
    quote_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    Lấy lịch sử xét duyệt báo giá (S7-02 AC 5):
    - Lịch sử duyệt là bất biến (immutable), không thể sửa và không thể xoá.
    """
    q_item = get_raw_quote_by_id(quote_id)
    if q_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy báo giá",
        )

    if not check_scope_access(current_user, q_item["owner_id"], q_item.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền xem lịch sử báo giá này",
        )

    history = get_quote_approval_history(quote_id)
    return {
        "quote_id": quote_id,
        "quote_number": q_item.get("quote_number"),
        "total": len(history),
        "history": history,
    }


@router.delete("/{quote_id}/approval-history")
def block_delete_approval_history(quote_id: int):
    """S7-02 AC 5: Lịch sử duyệt không xoá được."""
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Lịch sử phê duyệt là bất biến, không thể xoá (S7-02 AC 5)",
    )


@router.put("/{quote_id}/approval-history")
def block_update_approval_history(quote_id: int):
    """S7-02 AC 5: Lịch sử duyệt không sửa được."""
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Lịch sử phê duyệt là bất biến, không thể sửa (S7-02 AC 5)",
    )


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


# ============================================================================
# S7-03: Quote Versioning and Side-by-Side Comparison Endpoints
# ============================================================================

@router.get("/{quote_id}/compare/{target_quote_id}", response_model=QuoteComparisonResponse)
def compare_quotes_path(
    quote_id: int,
    target_quote_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    So sánh song song 2 phiên bản báo giá qua path param (S7-03 AC 2):
    - Tài chính: delta subtotal, discount, vat, grand total.
    - Hàng hóa: row-by-row matching theo product_id/item_id (ADDED, REMOVED, MODIFIED, UNCHANGED).
    - Điều khoản: valid_until, payment_terms, delivery_terms, notes.
    """
    qa = get_raw_quote_by_id(quote_id)
    qb = get_raw_quote_by_id(target_quote_id)
    if qa is None or qb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy một trong hai phiên bản báo giá để so sánh",
        )
    if not check_scope_access(current_user, qa["owner_id"], qa.get("team_id")) or not check_scope_access(current_user, qb["owner_id"], qb.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập dữ liệu một trong hai báo giá này",
        )

    return compare_quote_versions(quote_id, target_quote_id)


@router.get("/{quote_id}/versions", response_model=QuoteVersionListResponse)
def get_quote_versions_endpoint(
    quote_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    Lấy danh sách tất cả các phiên bản của một báo giá (S7-03 AC 3):
    - Trả về danh sách các phiên bản sắp xếp giảm dần theo số phiên bản.
    - Hiển thị rõ phiên bản nào đang là active.
    """
    q_item = get_raw_quote_by_id(quote_id)
    if q_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy báo giá",
        )

    if not check_scope_access(current_user, q_item["owner_id"], q_item.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền xem danh sách phiên bản của báo giá này",
        )

    return get_all_quote_versions(quote_id)


@router.post("/{quote_id}/versions", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED)
def create_quote_version_endpoint(
    quote_id: int,
    payload: Optional[QuoteVersionCreateRequest] = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Tạo phiên bản mới (v[N+1]) từ báo giá hiện tại (S7-03 AC 1):
    - Sao chép toàn bộ dữ liệu, độc lập dòng hàng.
    - Phiên bản cũ giữ nguyên trạng thái và dữ liệu lịch sử.
    - Phiên bản mới tự động thành active version (is_active_version=True) và ở trạng thái DRAFT.
    """
    q_item = get_raw_quote_by_id(quote_id)
    if q_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy báo giá gốc để tạo phiên bản mới",
        )

    if not check_scope_access(current_user, q_item["owner_id"], q_item.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền tạo phiên bản mới cho báo giá này",
        )

    reason = payload.reason if payload else None
    return create_new_quote_version(quote_id, current_user=current_user, reason=reason, db=db)


@router.post("/{quote_id}/set-active", response_model=QuoteResponse)
def set_active_version_endpoint(
    quote_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Thiết lập một phiên bản làm Active Version duy nhất (S7-03 AC 3):
    - Đặt is_active_version = True cho phiên bản chỉ định.
    - Đặt is_active_version = False cho tất cả các phiên bản khác cùng quote_number.
    - Ghi nhận lịch sử thay đổi phiên bản active.
    """
    q_item = get_raw_quote_by_id(quote_id)
    if q_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phiên bản báo giá",
        )

    if not check_scope_access(current_user, q_item["owner_id"], q_item.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền thao tác trên báo giá này",
        )

    return set_active_quote_version(quote_id, current_user=current_user, db=db)


@router.post("/{quote_id}/convert-to-contract", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
def convert_quote_to_contract_quote_endpoint(
    quote_id: int,
    payload: ContractConvertRequest,
    current_user: dict = Depends(require_roles(["ADMIN", "ACCOUNTANT", "DIRECTOR", "MANAGER"], detail="Chỉ Kế toán, Giám đốc hoặc Quản trị viên mới có quyền chuyển báo giá thành hợp đồng (S7-04)")),
    db: Session = Depends(get_db),
):
    """
    Chuyển một báo giá được chấp nhận thành hợp đồng (S7-04):
    - AC 1: Kế thừa 100% dòng sản phẩm và các giá trị tài chính đã chốt.
    - AC 2: Khai báo số hợp đồng, ngày ký, ngày hiệu lực, ngày hết hạn, điều khoản thanh toán.
    - AC 3: Tự động chuyển cơ hội tương ứng sang Đóng thắng (CLOSED_WON) với giá trị bằng đúng giá trị hợp đồng.
    - AC 4: Kiểm tra tính duy nhất của số hợp đồng.
    """
    return convert_quote_to_contract(
        quote_id=quote_id,
        data=payload.model_dump(),
        current_user=current_user,
        db=db,
    )


@router.get("/{quote_id}/export-pdf")
def export_quote_pdf(
    quote_id: int,
    template_id: Optional[int] = Query(None, description="ID của mẫu PDF cần áp dụng (nếu bỏ trống sẽ lấy mẫu mặc định)"),
    preview: bool = Query(False, description="True để xem trực tiếp (inline), False để tải về (attachment)"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Xuất báo giá ra file PDF theo mẫu công ty (S7-05 AC 1 & AC 2):
    - Logo và nhận diện thương hiệu công ty từ cấu hình template.
    - Bảng dòng sản phẩm đầy đủ số lượng, đơn giá, chiết khấu, VAT, thành tiền.
    - Tổng tiền bằng số và tự động chuyển đổi sang chữ tiếng Việt.
    - Tùy biến mẫu theo template_id hoặc mẫu mặc định.
    """
    quote = get_raw_quote_by_id(quote_id)
    if quote is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy báo giá để xuất PDF",
        )

    if not check_scope_access(current_user, quote["owner_id"], quote.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập dữ liệu báo giá này",
        )

    # Lấy mẫu PDF cấu hình
    if template_id is not None:
        template = get_template_by_id(template_id, db=db)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy mẫu PDF với ID {template_id}",
            )
    else:
        template = get_default_template("QUOTE", db=db)

    pdf_bytes = generate_quote_pdf(quote, template)
    quote_num = quote.get("quote_number") or f"BG_{quote_id}"
    filename = f"Bao_Gia_{quote_num}.pdf"
    disposition = "inline" if preview else f'attachment; filename="{filename}"'

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": disposition,
            "X-Report-Template-Id": str(template.get("id", 1)),
        },
    )
