"""
Customer API router with role-based access control and data scope filtering.

All endpoints require authentication (JWT token via HTTPBearer).
Role restrictions:
- ADMIN only: DELETE /customers/{customer_id}
- ADMIN & MANAGER: POST /customers
- ALL roles (ADMIN, MANAGER, USER): GET /customers, GET /customers/{customer_id}, PUT /customers/{customer_id}
  (data and actions are constrained by MY / TEAM / ALL scope).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Response, status


from app.core.dependencies import (
    DataScope,
    check_scope_access,
    get_current_user,
    require_roles,
    resolve_scope,
)
from app.schemas.customer import (
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
    CustomerUpdate,
    Customer360Response,
    DuplicateCandidate,
    MergeCustomerRequest,
    GroupCompanyTreeResponse,
    CustomerImportPreviewResponse,
    CustomerImportCommitRequest,
    CustomerImportCommitResponse,
    SavedFilterCreate,
    SavedFilterResponse,
    PeriodicCareCustomerItem,
    MarkCareInteractionRequest,
)
from app.services.customer_service import (
    commit_customer_import,
    create_customer_record,
    create_saved_filter,
    delete_customer_record,
    delete_saved_filter,
    find_duplicate_customers,
    generate_customer_template_excel,
    get_company_group_tree,
    get_customer_by_id,
    get_customer_360,
    get_customers_by_scope,
    get_periodic_care_customers,
    get_raw_customer_by_id,
    list_saved_filters,
    mark_customer_care_interaction,
    merge_customers,
    preview_customer_import_excel,
    update_customer_record,
)







router = APIRouter(
    prefix="/customers",
    tags=["Customers"],
)


@router.get("", response_model=CustomerListResponse)
def list_customers(
    scope: Optional[str] = Query(
        None,
        description="Data scope filter: MY, MY_TEAM, TEAM, or ALL. Defaults based on role.",
    ),
    search: Optional[str] = Query(None, description="Search query"),
    q: Optional[str] = Query(None, description="Search query alias"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: PROSPECT, IN_TRANSACTION, CUSTOMER, DISCONTINUED"),
    industry: Optional[str] = Query(None, description="Lọc theo ngành nghề"),
    company_size: Optional[str] = Query(None, description="Lọc theo quy mô doanh nghiệp"),
    address: Optional[str] = Query(None, description="Lọc theo địa chỉ / khu vực"),
    owner_id: Optional[int] = Query(None, description="Lọc theo nhân viên phụ trách"),
    page: Optional[int] = Query(None, ge=1, description="Số trang (bắt đầu từ 1)"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Số lượng khách hàng mỗi trang (mặc định 20)"),
    skip: Optional[int] = Query(None, ge=0, description="Vị trí bắt đầu (offset)"),
    current_user: dict = Depends(get_current_user),
):
    """
    List customers based on the user's role and requested scope, with optional search, status filter, and pagination.

    - ADMIN: defaults to ALL, can request MY/MY_TEAM/TEAM/ALL
    - MANAGER: defaults to TEAM, can request MY/MY_TEAM/TEAM (ALL -> 403)
    - USER: defaults to MY, can only use MY (MY_TEAM/TEAM/ALL -> 403)
    """
    import math

    effective_scope = resolve_scope(current_user, scope)
    search_query = search or q

    # Xác định phân trang: hỗ trợ cả page + limit lẫn skip + limit
    effective_limit = limit if limit is not None else 20

    if page is not None:
        effective_skip = (page - 1) * effective_limit
        effective_page = page
    elif skip is not None:
        effective_skip = skip
        effective_page = (effective_skip // effective_limit) + 1
    else:
        # Nếu client không truyền skip hoặc page, mặc định trả từ đầu (skip = 0)
        effective_skip = 0
        effective_page = 1

    total, customers = get_customers_by_scope(
        current_user,
        effective_scope,
        search=search_query,
        skip=effective_skip,
        limit=effective_limit,
        status_filter=status,
        industry_filter=industry,
        company_size_filter=company_size,
        address_filter=address,
        owner_id_filter=owner_id,
    )


    total_pages = max(1, math.ceil(total / effective_limit)) if total > 0 else 1

    return {
        "scope": effective_scope.value,
        "total": total,
        "customers": customers,
        "skip": effective_skip,
        "limit": effective_limit,
        "page": effective_page,
        "total_pages": total_pages,
    }


@router.get("/saved-filters", response_model=List[SavedFilterResponse])
def get_user_saved_filters(
    current_user: dict = Depends(get_current_user),
):
    """AC S3-07: Lấy danh sách các bộ lọc khách hàng đã lưu của người dùng hiện tại."""
    return list_saved_filters(user_id=current_user["id"])


@router.post("/saved-filters", response_model=SavedFilterResponse, status_code=status.HTTP_201_CREATED)
def save_customer_filter(
    payload: SavedFilterCreate,
    current_user: dict = Depends(get_current_user),
):
    """AC S3-07: Lưu bộ lọc tùy biến để tái sử dụng nhanh chóng."""
    return create_saved_filter(
        user_id=current_user["id"],
        name=payload.name,
        filter_criteria=payload.filter_criteria,
    )


@router.delete("/saved-filters/{filter_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_saved_filter(
    filter_id: int,
    current_user: dict = Depends(get_current_user),
):
    """AC S3-07: Xóa bộ lọc đã lưu."""
    success = delete_saved_filter(filter_id=filter_id, user_id=current_user["id"])
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy bộ lọc đã lưu để xóa",
        )
    return None


@router.get("/periodic-care", response_model=List[PeriodicCareCustomerItem])
def get_customers_for_periodic_care(
    days: int = Query(30, ge=1, description="Số ngày tối thiểu không có tương tác"),
    current_user: dict = Depends(get_current_user),
):
    """
    AC S3-09: Lập danh sách khách hàng định kỳ cần chăm sóc:
    - Lọc các khách chưa có tương tác trong N ngày (mặc định 30 ngày).
    - Tự động sắp xếp theo giá trị hợp đồng giảm dần.
    - Đính kèm cờ cảnh báo rủi ro rời bỏ.
    """
    return get_periodic_care_customers(days_threshold=days, current_user=current_user)


@router.post("/{customer_id}/mark-care")
def mark_care_interaction_for_customer(
    customer_id: int,
    payload: MarkCareInteractionRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    AC S3-09: Đánh dấu đã liên hệ chăm sóc khách hàng, cập nhật mốc thời gian tương tác mới nhất.
    """
    try:
        return mark_customer_care_interaction(
            customer_id=customer_id,
            interaction_type=payload.interaction_type,
            note=payload.note,
            current_user=current_user,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{customer_id}", response_model=CustomerResponse)


def get_customer(
    customer_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    Get a single customer by ID, enforced by the user's data scope:
    - Returns 404 if the customer does not exist in the database.
    - Returns 403 if the customer exists but is outside the user's accessible scope.
    """
    customer = get_raw_customer_by_id(customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy khách hàng",
        )

    if not check_scope_access(current_user, customer["owner_id"], customer.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập dữ liệu khách hàng này",
        )

    return customer


@router.get("/{customer_id}/360", response_model=Customer360Response)
def get_customer_360_view(
    customer_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    AC S3-03: Customer 360 View toàn diện.
    Bao gồm thông tin công ty, danh sách người liên hệ, cơ hội đang mở / đã ký,
    dòng thời gian hoạt động tương tác, tài liệu đính kèm, tổng giá trị hợp đồng.
    """
    customer = get_customer_by_id(customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found",
        )

    if not check_scope_access(current_user, customer["owner_id"], customer.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập dữ liệu khách hàng này",
        )

    view_360 = get_customer_360(customer_id)
    return view_360



@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    AC S3-01: Tạo mới hồ sơ khách hàng doanh nghiệp.
    Tất cả nhân viên kinh doanh đều có thể tạo khách hàng thuộc quyền sở hữu của mình.
    """
    new_customer = create_customer_record(payload.model_dump(), current_user)
    return new_customer


@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    current_user: dict = Depends(get_current_user),
):
    """
    Update a customer record with scope verification:
    - 404 if customer does not exist.
    - 403 if user doesn't have permission to modify this customer (outside scope).
    - ADMIN can update any customer.
    - MANAGER can update customers within their team.
    - USER can only update customers they own.
    """
    customer = get_raw_customer_by_id(customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kh??ng t??m th???y kh??ch h??ng",
        )

    if not check_scope_access(current_user, customer["owner_id"], customer.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kh??ng c?? quy???n ch???nh s???a d??? li???u kh??ch h??ng n??y",
        )

    old_owner = customer.get("owner_id")
    updated = update_customer_record(customer_id, payload.model_dump(exclude_unset=True))

    if payload.owner_id is not None and payload.owner_id != old_owner:
        from app.services.audit_log_service import log_change
        log_change(
            user_id=current_user["id"],
            user_name=current_user.get("full_name", current_user.get("username", "User")),
            entity_type="DATA_OWNERSHIP",
            entity_id=f"CUST-{customer_id}",
            action="TRANSFER_OWNER",
            field_name="owner_id",
            old_value=str(old_owner),
            new_value=str(payload.owner_id),
        )

    return updated


@router.get("/{customer_id}/duplicates", response_model=List[DuplicateCandidate])
def check_duplicate_customers(
    customer_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    AC S3-04: Tự động cảnh báo và phát hiện hồ sơ khách hàng trùng lặp:
    - Trùng Mã số thuế (tax_code)
    - Tên doanh nghiệp tương tự
    - Trùng website, điện thoại
    """
    customer = get_customer_by_id(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found",
        )
    return find_duplicate_customers(customer_id)


@router.post(
    "/merge",
    response_model=CustomerResponse,
    dependencies=[Depends(require_roles(["ADMIN", "MANAGER"]))],
)
def merge_customer_profiles(
    payload: MergeCustomerRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    AC S3-04: Gộp khách hàng (Chỉ Trưởng nhóm - MANAGER hoặc ADMIN mới có quyền gộp).
    - Giữ lại hồ sơ chính, chuyển toàn bộ liên hệ, cơ hội, lịch sử tương tác từ hồ sơ phụ sang chính.
    """
    try:
        user_name = current_user.get("username") or current_user.get("full_name") or current_user.get("email") or "manager"
        merged = merge_customers(
            primary_id=payload.primary_customer_id,
            secondary_id=payload.secondary_customer_id,
            chosen_fields=payload.chosen_fields,
            current_user_username=user_name,
        )
        return merged
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{customer_id}/group-tree", response_model=GroupCompanyTreeResponse)
def get_customer_group_tree(
    customer_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    AC S3-05: Sơ đồ phân cấp công ty mẹ - con và tổng giá trị hợp đồng toàn tập đoàn.
    """
    customer = get_customer_by_id(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found",
        )

    if not check_scope_access(current_user, customer["owner_id"], customer.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập dữ liệu công ty này",
        )

    tree = get_company_group_tree(customer_id)
    if not tree:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy cây tập đoàn cho công ty #{customer_id}",
        )
    return tree


@router.get("/import/template")
def download_customer_import_template(
    current_user: dict = Depends(get_current_user),
):
    """AC S3-06: Tải file Excel mẫu để chuẩn bị dữ liệu nhập khẩu."""
    excel_bytes = generate_customer_template_excel()
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=mau_nhap_khach_hang.xlsx"},
    )


@router.post("/import/preview", response_model=CustomerImportPreviewResponse)
async def preview_customer_import(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    AC S3-06: Tải file Excel lên để xem trước, kiểm tra tính hợp lệ và cảnh báo trùng lặp từng dòng.
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp tin phải có định dạng .xlsx",
        )
    content = await file.read()
    try:
        preview_result = preview_customer_import_excel(content)
        return preview_result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lỗi khi đọc file Excel: {str(e)}",
        )


@router.post("/import/commit", response_model=CustomerImportCommitResponse)
def commit_customer_import_records(
    payload: CustomerImportCommitRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    AC S3-06: Tiến hành lưu các dòng khách hàng vào hệ thống với tuỳ chọn xử lý trùng (SKIP / UPDATE).
    """
    rows_data = [r.model_dump() for r in payload.rows]
    result = commit_customer_import(
        rows=rows_data,
        duplicate_handling=payload.duplicate_handling,
        current_user=current_user,
    )
    return result


@router.delete(
    "/{customer_id}",
    dependencies=[Depends(require_roles(["ADMIN"]))],
)




def delete_customer(customer_id: int):
    """
    Delete a customer (ADMIN only).
    - Returns 403 Forbidden for MANAGER or USER.
    - Returns 404 Not Found if customer does not exist.
    """
    success = delete_customer_record(customer_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kh??ng t??m th???y kh??ch h??ng ????? x??a",
        )
    return {"message": f"???? x??a kh??ch h??ng ID {customer_id}"}
