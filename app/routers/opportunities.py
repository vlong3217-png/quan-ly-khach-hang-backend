"""
Opportunity API router with role-based access control and data scope filtering.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File

from app.core.dependencies import (
    DataScope,
    check_scope_access,
    get_current_user,
    require_roles,
    resolve_scope,
)
from app.schemas.opportunity import (
    KanbanBoardResponse,
    KanbanColumnResponse,
    OpportunityCreate,
    OpportunityListResponse,
    OpportunityProductCreate,
    OpportunityProductResponse,
    OpportunityProductUpdate,
    OpportunityReassignRequest,
    OpportunityReassignResponse,
    OpportunityResponse,
    OpportunityStageMoveRequest,
    OpportunityUpdate,
    OpportunityHistoryItem,
    OpportunityHistoryListResponse,
    OpportunitySavedFilterCreate,
    OpportunitySavedFilterUpdate,
    OpportunitySavedFilterResponse,
    OpportunityShareCreate,
    OpportunityShareResponse,
    OpportunityTransferOwnershipRequest,
    OpportunityAttachmentResponse,
)
from app.schemas.pipeline import (
    OpportunityStageTransitionRequest,
    OpportunityStageTransitionResponse,
)
from app.services import pipeline_service
from app.services.opportunity_service import (
    add_product_to_opportunity,
    create_opportunity_record,
    delete_opportunity_product,
    delete_opportunity_record,
    get_kanban_board_data,
    get_opportunities_by_scope,
    get_raw_opportunity_by_id,
    list_opportunity_products,
    move_opportunity_kanban_stage,
    reassign_opportunities,
    update_opportunity_product,
    update_opportunity_record,
    list_opportunity_histories,
    filter_opportunities_advanced,
    list_opportunity_saved_filters,
    create_opportunity_saved_filter,
    update_opportunity_saved_filter,
    delete_opportunity_saved_filter,
    list_opportunity_shares,
    add_opportunity_share,
    remove_opportunity_share,
    transfer_opportunity_ownership,
    list_opportunity_attachments,
    add_opportunity_attachment,
    get_opportunity_attachment_by_id,
    delete_opportunity_attachment_record,
    check_opportunity_access_permission,
)


router = APIRouter(
    prefix="/opportunities",
    tags=["Opportunities"],
)


@router.get("/kanban", response_model=KanbanBoardResponse)
def get_pipeline_kanban(
    scope: Optional[str] = Query(None, description="Data scope: MY, MY_TEAM, TEAM, ALL"),
    owner_id: Optional[int] = Query(None, description="Lọc theo người sở hữu"),
    team_id: Optional[int] = Query(None, description="Lọc theo nhóm"),
    from_date: Optional[str] = Query(None, description="Từ ngày dự kiến chốt (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Đến ngày dự kiến chốt (YYYY-MM-DD)"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo tiêu đề hoặc giai đoạn"),
    current_user: dict = Depends(get_current_user),
):
    """
    AC S5-02: Bảng pipeline dạng Kanban:
    - Mỗi cột là một giai đoạn, hiển thị số cơ hội và tổng giá trị của cột.
    - Thẻ cơ hội hiển thị tên khách, giá trị, ngày dự kiến chốt và cảnh báo nếu đình trệ.
    - Lọc theo người sở hữu, nhóm, khoảng ngày chốt; nhân viên mặc định chỉ thấy cơ hội của mình.
    """
    effective_scope = resolve_scope(current_user, scope)
    return get_kanban_board_data(
        current_user=current_user,
        scope=effective_scope,
        owner_id=owner_id,
        team_id=team_id,
        expected_close_date_from=from_date,
        expected_close_date_to=to_date,
        search=search,
    )


@router.get("", response_model=OpportunityListResponse)
def list_opportunities(
    scope: Optional[str] = Query(
        None,
        description="Data scope filter: MY, MY_TEAM, TEAM, or ALL. Defaults based on role.",
    ),
    customer_id: Optional[int] = Query(None, description="Lọc theo khách hàng"),
    search: Optional[str] = Query(None, description="Search query"),
    q: Optional[str] = Query(None, description="Search query alias"),
    page: Optional[int] = Query(None, ge=1, description="Trang hiện tại (bắt đầu từ 1)"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Số lượng cơ hội mỗi trang (mặc định 20)"),
    skip: Optional[int] = Query(None, ge=0, description="Vị trí bắt đầu (offset)"),
    current_user: dict = Depends(get_current_user),
):
    import math

    effective_scope = resolve_scope(current_user, scope)
    search_query = search or q
    all_opportunities = get_opportunities_by_scope(current_user, effective_scope, search=search_query, customer_id=customer_id)
    total = len(all_opportunities)

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

    paged_items = all_opportunities[effective_skip : effective_skip + effective_limit]
    total_pages = max(1, math.ceil(total / effective_limit)) if total > 0 else 1
    return {
        "scope": effective_scope.value,
        "total": total,
        "opportunities": paged_items,
        "page": effective_page,
        "limit": effective_limit,
        "skip": effective_skip,
        "total_pages": total_pages,
    }


# S6-02: Tìm kiếm và lọc cơ hội nâng cao kết hợp nhiều điều kiện
@router.get("/search/advanced", response_model=OpportunityListResponse)
def search_opportunities_advanced(
    stage: Optional[str] = Query(None, description="Lọc theo giai đoạn"),
    min_value: Optional[float] = Query(None, ge=0, description="Khoảng giá trị tối thiểu"),
    max_value: Optional[float] = Query(None, ge=0, description="Khoảng giá trị tối đa"),
    from_date: Optional[str] = Query(None, description="Từ ngày dự kiến chốt (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Đến ngày dự kiến chốt (YYYY-MM-DD)"),
    product_id: Optional[int] = Query(None, description="Lọc theo sản phẩm"),
    owner_id: Optional[int] = Query(None, description="Lọc theo người sở hữu"),
    search: Optional[str] = Query(None, description="Tìm kiếm tiêu đề hoặc nội dung"),
    scope: Optional[str] = Query(None, description="Scope dữ liệu: MY, MY_TEAM, TEAM, ALL"),
    page: Optional[int] = Query(1, ge=1, description="Trang hiện tại (bắt đầu từ 1)"),
    limit: Optional[int] = Query(20, ge=1, le=100, description="Số lượng cơ hội mỗi trang"),
    current_user: dict = Depends(get_current_user),
):
    """
    S6-02: API tìm kiếm cơ hội kết hợp:
    - Giai đoạn, khoảng giá trị min/max, khoảng ngày chốt, sản phẩm, người sở hữu.
    - Hỗ trợ phân trang, validate điều kiện lọc.
    """
    import math
    effective_scope = resolve_scope(current_user, scope)
    eff_page = page or 1
    eff_limit = limit or 20
    skip = (eff_page - 1) * eff_limit

    items, total = filter_opportunities_advanced(
        current_user=current_user,
        scope=effective_scope,
        stage=stage,
        min_value=min_value,
        max_value=max_value,
        expected_close_date_from=from_date,
        expected_close_date_to=to_date,
        product_id=product_id,
        owner_id=owner_id,
        search=search,
        skip=skip,
        limit=eff_limit,
    )
    total_pages = max(1, math.ceil(total / eff_limit)) if total > 0 else 1

    return {
        "scope": effective_scope.value,
        "total": total,
        "opportunities": items,
        "page": eff_page,
        "limit": eff_limit,
        "skip": skip,
        "total_pages": total_pages,
    }


# S6-02: Bộ lọc cơ hội đã lưu (Saved Filters)
@router.get("/saved-filters", response_model=List[OpportunitySavedFilterResponse])
def get_opportunity_saved_filters_endpoint(
    current_user: dict = Depends(get_current_user),
):
    """S6-02: Lấy danh sách bộ lọc cơ hội của người dùng hiện tại (bộ lọc riêng tư)."""
    return list_opportunity_saved_filters(user_id=current_user["id"])


@router.post("/saved-filters", response_model=OpportunitySavedFilterResponse, status_code=status.HTTP_201_CREATED)
def create_opportunity_saved_filter_endpoint(
    payload: OpportunitySavedFilterCreate,
    current_user: dict = Depends(get_current_user),
):
    """S6-02: Lưu bộ lọc cơ hội thường dùng."""
    if not payload.name or not payload.name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên bộ lọc không được để trống",
        )
    return create_opportunity_saved_filter(
        user_id=current_user["id"],
        name=payload.name.strip(),
        filter_criteria=payload.filter_criteria,
    )


@router.put("/saved-filters/{filter_id}", response_model=OpportunitySavedFilterResponse)
def update_opportunity_saved_filter_endpoint(
    filter_id: int,
    payload: OpportunitySavedFilterUpdate,
    current_user: dict = Depends(get_current_user),
):
    """S6-02: Cập nhật bộ lọc đã lưu (chỉ người tạo mới sửa được)."""
    updated = update_opportunity_saved_filter(
        filter_id=filter_id,
        user_id=current_user["id"],
        name=payload.name.strip() if payload.name else None,
        filter_criteria=payload.filter_criteria,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không tìm thấy bộ lọc đã lưu hoặc bạn không có quyền chỉnh sửa",
        )
    return updated


@router.delete("/saved-filters/{filter_id}", status_code=status.HTTP_200_OK)
def delete_opportunity_saved_filter_endpoint(
    filter_id: int,
    current_user: dict = Depends(get_current_user),
):
    """S6-02: Xóa bộ lọc đã lưu (chỉ người tạo mới xóa được)."""
    success = delete_opportunity_saved_filter(filter_id=filter_id, user_id=current_user["id"])
    if not success:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không tìm thấy bộ lọc đã lưu để xóa",
        )
    return {"message": "Đã xóa bộ lọc thành công"}


@router.get("/{opportunity_id}", response_model=OpportunityResponse)
def get_opportunity(
    opportunity_id: int,
    current_user: dict = Depends(get_current_user),
):
    opp = get_raw_opportunity_by_id(opportunity_id)
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cơ hội bán hàng",
        )

    if not check_opportunity_access_permission(opp, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập dữ liệu cơ hội này",
        )

    return opp


@router.post("", response_model=OpportunityResponse, status_code=status.HTTP_201_CREATED)
def create_opportunity(
    payload: OpportunityCreate,
    current_user: dict = Depends(get_current_user),
):
    new_opp = create_opportunity_record(payload.model_dump(), current_user)
    return new_opp


@router.post("/reassign", response_model=OpportunityReassignResponse)
def reassign_opportunity_endpoint(
    payload: OpportunityReassignRequest,
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"], detail="Chỉ Trưởng nhóm kinh doanh hoặc Quản trị viên mới có quyền phân bổ lại cơ hội")),
):
    """
    S5-08: Phân bổ lại một hoặc nhiều cơ hội cho người khác trong nhóm:
    - Chuyển quyền sở hữu một hoặc nhiều cơ hội cùng lúc.
    - Người nhận thấy được cơ hội và toàn bộ lịch sử (Activities).
    - Mỗi lần chuyển quyền phải ghi nhật ký kèm lý do.
    - Chỉ người có quyền phù hợp (ADMIN hoặc MANAGER của nhóm) mới được phân bổ lại.
    """
    return reassign_opportunities(
        opportunity_ids=payload.opportunity_ids,
        new_owner_id=payload.new_owner_id,
        reason=payload.reason,
        current_user=current_user,
    )


@router.put("/{opportunity_id}", response_model=OpportunityResponse)
def update_opportunity(
    opportunity_id: int,
    payload: OpportunityUpdate,
    current_user: dict = Depends(get_current_user),
):
    opp = get_raw_opportunity_by_id(opportunity_id)
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cơ hội bán hàng",
        )

    if not check_opportunity_access_permission(opp, current_user, require_write=True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền chỉnh sửa dữ liệu cơ hội này",
        )

    payload_dict = payload.model_dump(exclude_unset=True)

    # AC S5-04: Kiểm tra điều kiện bắt buộc khi cơ hội rời một giai đoạn
    if payload.stage is not None and payload.stage != opp.get("stage"):
        transition_result = pipeline_service.validate_and_execute_stage_transition(
            opportunity=opp,
            target_stage_identifier=payload.stage,
            current_user=current_user,
            override=bool(payload.override),
            override_reason=payload.override_reason,
            extra_opportunity_data=payload_dict,
        )
        payload_dict["stage"] = transition_result["current_stage"]
        payload_dict["stage_overridden"] = transition_result["overridden"]
        payload_dict["override_reason"] = transition_result["override_reason"]
        payload_dict["override_by"] = transition_result["override_by"]

    updated = update_opportunity_record(opportunity_id, payload_dict, current_user=current_user)
    return updated


@router.patch("/{opportunity_id}/stage", response_model=OpportunityResponse)
def move_opportunity_stage(
    opportunity_id: int,
    payload: OpportunityStageMoveRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    AC S5-02: Kéo thả để chuyển giai đoạn trên bảng Kanban.
    """
    opp = get_raw_opportunity_by_id(opportunity_id)
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cơ hội bán hàng",
        )

    if not check_scope_access(current_user, opp["owner_id"], opp.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền cập nhật giai đoạn cơ hội này",
        )

    updated = move_opportunity_kanban_stage(
        opportunity_id=opportunity_id,
        new_stage_identifier=payload.new_stage,
        current_user=current_user,
        probability=payload.probability,
        probability_notes=payload.probability_notes,
    )
    return updated


@router.post("/{opportunity_id}/transition-stage", response_model=OpportunityStageTransitionResponse)
def transition_opportunity_stage(
    opportunity_id: int,
    payload: OpportunityStageTransitionRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    AC S5-04: Chuyển giai đoạn cơ hội bán hàng với kiểm tra điều kiện rời giai đoạn (Exit criteria).
    - Không cho chuyển giai đoạn nếu chưa đủ điều kiện.
    - Thông báo rõ điều kiện còn thiếu.
    - Trưởng nhóm trở lên (MANAGER, ADMIN) có thể ghi đè kèm lý do bắt buộc.
    """
    opp = get_raw_opportunity_by_id(opportunity_id)
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cơ hội bán hàng",
        )

    if not check_scope_access(current_user, opp["owner_id"], opp.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền thay đổi giai đoạn cơ hội này",
        )

    result = pipeline_service.validate_and_execute_stage_transition(
        opportunity=opp,
        target_stage_identifier=payload.target_stage,
        current_user=current_user,
        override=bool(payload.override),
        override_reason=payload.override_reason,
        extra_opportunity_data=payload.opportunity_data,
    )

    # Đồng bộ vào dữ liệu lưu trữ
    sync_data = {
        "stage": result["current_stage"],
        "stage_overridden": result["overridden"],
        "override_reason": result["override_reason"],
        "override_by": result["override_by"],
    }
    if payload.opportunity_data:
        sync_data.update(payload.opportunity_data)
    update_opportunity_record(opportunity_id, sync_data)
    result["opportunity_id"] = opportunity_id
    return result


@router.delete(
    "/{opportunity_id}",
    dependencies=[Depends(require_roles(["ADMIN"]))],
)
def delete_opportunity(opportunity_id: int):
    success = delete_opportunity_record(opportunity_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cơ hội bán hàng để xóa",
        )
    return {"message": f"Đã xóa cơ hội bán hàng ID {opportunity_id}"}


# ============================================================================
# SẢN PHẨM / DỊCH VỤ TRONG CƠ HỘI (S5-03)
# ============================================================================

@router.get("/{opportunity_id}/products", response_model=list[OpportunityProductResponse])
def get_opportunity_products(
    opportunity_id: int,
    current_user: dict = Depends(get_current_user),
):
    opp = get_raw_opportunity_by_id(opportunity_id)
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cơ hội bán hàng",
        )
    if not check_scope_access(current_user, opp["owner_id"], opp.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập cơ hội này",
        )
    return list_opportunity_products(opportunity_id)


@router.post("/{opportunity_id}/products", response_model=OpportunityProductResponse, status_code=status.HTTP_201_CREATED)
def add_product(
    opportunity_id: int,
    payload: OpportunityProductCreate,
    current_user: dict = Depends(get_current_user),
):
    opp = get_raw_opportunity_by_id(opportunity_id)
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cơ hội bán hàng",
        )
    if not check_scope_access(current_user, opp["owner_id"], opp.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền thêm sản phẩm vào cơ hội này",
        )
    return add_product_to_opportunity(opportunity_id, payload.model_dump(), current_user)


@router.put("/{opportunity_id}/products/{item_id}", response_model=OpportunityProductResponse)
def update_product(
    opportunity_id: int,
    item_id: int,
    payload: OpportunityProductUpdate,
    current_user: dict = Depends(get_current_user),
):
    opp = get_raw_opportunity_by_id(opportunity_id)
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cơ hội bán hàng",
        )
    if not check_scope_access(current_user, opp["owner_id"], opp.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền cập nhật sản phẩm trong cơ hội này",
        )
    return update_opportunity_product(opportunity_id, item_id, payload.model_dump(exclude_unset=True))


@router.delete("/{opportunity_id}/products/{item_id}")
def delete_product(
    opportunity_id: int,
    item_id: int,
    current_user: dict = Depends(get_current_user),
):
    opp = get_raw_opportunity_by_id(opportunity_id)
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cơ hội bán hàng",
        )
    if not check_scope_access(current_user, opp["owner_id"], opp.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền xóa sản phẩm khỏi cơ hội này",
        )
    success = delete_opportunity_product(opportunity_id, item_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy dòng sản phẩm ID {item_id}",
        )
    return {"message": f"Đã xóa sản phẩm ID {item_id} khỏi cơ hội"}


# ============================================================================
# SPRINT 6: S6-01, S6-02, S6-03, S6-04 ENDPOINTS
# ============================================================================

# S6-01: Lịch sử thay đổi cơ hội
@router.get("/{opportunity_id}/history", response_model=OpportunityHistoryListResponse)
def get_opportunity_history(
    opportunity_id: int,
    page: Optional[int] = Query(1, ge=1, description="Trang hiện tại (bắt đầu từ 1)"),
    limit: Optional[int] = Query(20, ge=1, le=100, description="Số lượng bản ghi mỗi trang"),
    current_user: dict = Depends(get_current_user),
):
    """
    S6-01: Lấy lịch sử thay đổi của cơ hội:
    - Kiểm tra quyền xem cơ hội trước khi trả lịch sử.
    - Sắp xếp mới nhất trước, có phân trang.
    """
    import math
    opp = get_raw_opportunity_by_id(opportunity_id)
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cơ hội bán hàng",
        )
    if not check_opportunity_access_permission(opp, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền xem lịch sử cơ hội này",
        )

    eff_page = page or 1
    eff_limit = limit or 20
    skip = (eff_page - 1) * eff_limit

    items, total = list_opportunity_histories(opportunity_id, skip=skip, limit=eff_limit)
    total_pages = max(1, math.ceil(total / eff_limit)) if total > 0 else 1

    return {
        "total": total,
        "page": eff_page,
        "limit": eff_limit,
        "total_pages": total_pages,
        "items": items,
    }








# S6-03: Chia sẻ cơ hội cho nhiều thành viên
@router.get("/{opportunity_id}/shares", response_model=List[OpportunityShareResponse])
def get_opportunity_shares_endpoint(
    opportunity_id: int,
    current_user: dict = Depends(get_current_user),
):
    """S6-03: Lấy danh sách thành viên được chia sẻ của một cơ hội."""
    opp = get_raw_opportunity_by_id(opportunity_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cơ hội bán hàng")
    if not check_opportunity_access_permission(opp, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền xem danh sách chia sẻ của cơ hội này")

    return list_opportunity_shares(opportunity_id)


@router.post("/{opportunity_id}/shares", response_model=OpportunityShareResponse, status_code=status.HTTP_201_CREATED)
def add_opportunity_share_endpoint(
    opportunity_id: int,
    payload: OpportunityShareCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    S6-03: Chia sẻ cơ hội cho thành viên khác:
    - Chỉ người sở hữu hoặc Quản lý/Admin có quyền chia sẻ.
    - Chặn thành viên trùng lặp.
    - Giữ nguyên người sở hữu chính của cơ hội.
    """
    return add_opportunity_share(
        opportunity_id=opportunity_id,
        user_id=payload.user_id,
        permission=payload.permission or "READ_WRITE",
        current_user=current_user,
    )


@router.delete("/{opportunity_id}/shares/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_opportunity_share_endpoint(
    opportunity_id: int,
    user_id: int,
    current_user: dict = Depends(get_current_user),
):
    """S6-03: Gỡ thành viên được chia sẻ khỏi cơ hội."""
    success = remove_opportunity_share(
        opportunity_id=opportunity_id,
        user_id=user_id,
        current_user=current_user,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy thông tin chia sẻ cho thành viên này để gỡ",
        )
    return None


@router.post("/{opportunity_id}/transfer-ownership")
def transfer_opportunity_ownership_endpoint(
    opportunity_id: int,
    payload: OpportunityTransferOwnershipRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    S6-03: Chuyển quyền sở hữu cơ hội cho người dùng khác:
    - Thành viên được chia sẻ không được tự ý đổi người sở hữu.
    - Ghi lịch sử đầy đủ: người sở hữu cũ, người sở hữu mới, người thực hiện, thời điểm và lý do.
    """
    return transfer_opportunity_ownership(
        opportunity_id=opportunity_id,
        new_owner_id=payload.new_owner_id,
        reason=payload.reason,
        current_user=current_user,
    )


# S6-04: Đính kèm tài liệu vào cơ hội
@router.post("/{opportunity_id}/attachments", response_model=OpportunityAttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_opportunity_attachment_endpoint(
    opportunity_id: int,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    S6-04: Tải lên tài liệu cho cơ hội:
    - Kích thước tối đa mỗi tệp 20 MB.
    - Kiểm tra loại nội dung và phần mở rộng an toàn.
    - Chỉ người sở hữu, thành viên được chia sẻ hoặc quản lý có quyền.
    """
    opp = get_raw_opportunity_by_id(opportunity_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cơ hội bán hàng")

    if not check_opportunity_access_permission(opp, current_user, require_write=True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền tải lên tài liệu cho cơ hội này")

    # Kiểm tra kích thước <= 20 MB (20 * 1024 * 1024 bytes)
    MAX_FILE_SIZE = 20 * 1024 * 1024
    contents = await file.read()
    file_size = len(contents)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Kích thước tệp vượt quá giới hạn tối đa 20 MB (kích thước hiện tại: {file_size / (1024*1024):.2f} MB)",
        )

    # Validate phần mở rộng tệp an toàn
    import os
    import uuid
    safe_extensions = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".png", ".jpg", ".jpeg", ".zip", ".txt"}
    _, ext = os.path.splitext(file.filename or "")
    if ext.lower() not in safe_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Phần mở rộng tệp '{ext}' không được hỗ trợ. Các định dạng cho phép: {', '.join(sorted(safe_extensions))}",
        )

    # Lưu tệp an toàn với tên không phụ thuộc vào input người dùng
    unique_filename = f"{uuid.uuid4().hex}_{os.path.basename(file.filename)}"
    storage_dir = os.path.join(os.getcwd(), "uploads", "opportunity_documents", str(opportunity_id))
    os.makedirs(storage_dir, exist_ok=True)
    stored_path = os.path.join(storage_dir, unique_filename)

    try:
        with open(stored_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Lỗi lưu trữ tệp tin trên máy chủ")

    # Lưu metadata
    meta = add_opportunity_attachment(
        opportunity_id=opportunity_id,
        filename=unique_filename,
        original_name=file.filename or "document",
        file_path=stored_path,
        file_size_bytes=file_size,
        content_type=file.content_type,
        current_user=current_user,
    )
    return meta


@router.get("/{opportunity_id}/attachments", response_model=List[OpportunityAttachmentResponse])
def list_opportunity_attachments_endpoint(
    opportunity_id: int,
    current_user: dict = Depends(get_current_user),
):
    """S6-04: Liệt kê danh sách tài liệu đính kèm của cơ hội."""
    opp = get_raw_opportunity_by_id(opportunity_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cơ hội bán hàng")

    if not check_opportunity_access_permission(opp, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền xem tài liệu của cơ hội này")

    return list_opportunity_attachments(opportunity_id)


@router.get("/{opportunity_id}/attachments/{attachment_id}/download")
def download_opportunity_attachment_endpoint(
    opportunity_id: int,
    attachment_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    S6-04: Tải xuống tài liệu đính kèm theo quyền:
    - Chỉ người sở hữu, thành viên được chia sẻ hoặc quản lý có quyền tải xuống.
    - Người ngoài không thể tải dù biết ID/URL.
    """
    opp = get_raw_opportunity_by_id(opportunity_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cơ hội bán hàng")

    if not check_opportunity_access_permission(opp, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền tải xuống tài liệu của cơ hội này")

    meta = get_opportunity_attachment_by_id(opportunity_id, attachment_id)
    if not meta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài liệu đính kèm")

    import os
    from fastapi.responses import FileResponse
    file_path = meta.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tệp tin không tồn tại trên hệ thống lưu trữ")

    return FileResponse(
        path=file_path,
        filename=meta.get("original_name") or "document",
        media_type=meta.get("content_type") or "application/octet-stream",
    )


@router.delete("/{opportunity_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_opportunity_attachment_endpoint(
    opportunity_id: int,
    attachment_id: int,
    current_user: dict = Depends(get_current_user),
):
    """S6-04: Xóa tệp đính kèm theo quyền và dọn dẹp bộ nhớ."""
    opp = get_raw_opportunity_by_id(opportunity_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cơ hội bán hàng")

    if not check_opportunity_access_permission(opp, current_user, require_write=True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền xóa tài liệu của cơ hội này")

    meta = get_opportunity_attachment_by_id(opportunity_id, attachment_id)
    if not meta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài liệu đính kèm để xóa")

    deleted = delete_opportunity_attachment_record(opportunity_id, attachment_id)
    if deleted and deleted.get("file_path"):
        import os
        try:
            if os.path.exists(deleted["file_path"]):
                os.remove(deleted["file_path"])
        except Exception:
            pass

    return None


