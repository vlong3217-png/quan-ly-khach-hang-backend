from typing import List, Optional, Union
import math
from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import get_current_user, require_roles
from app.schemas.win_loss import (
    CloseOpportunityValidationRequest,
    CloseOpportunityValidationResponse,
    CompetitorCreate,
    CompetitorResponse,
    CompetitorUpdate,
    ReasonCreate,
    ReasonResponse,
    ReasonType,
    ReasonUpdate,
    ReasonListResponse,
    CompetitorListResponse,
)
from app.services import win_loss_service

router = APIRouter(prefix="/win-loss", tags=["Win-Loss & Competitor Analysis"])


# --- Lý do Thắng / Thua ---

@router.get("/reasons", response_model=Union[ReasonListResponse, List[ReasonResponse]])
def get_reasons(
    reason_type: Optional[ReasonType] = Query(None, description="Lọc theo WIN hoặc LOSS"),
    active_only: bool = Query(False, description="Chỉ lấy lý do đang kích hoạt"),
    page: Optional[int] = Query(None, ge=1, description="Số trang (bắt đầu từ 1)"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Số lượng bản ghi mỗi trang"),
    skip: Optional[int] = Query(None, ge=0, description="Vị trí bắt đầu"),
    current_user: dict = Depends(get_current_user),
):
    """Danh sách lý do thắng thầu và lý do thất bại có hỗ trợ phân trang."""
    rt_val = reason_type.value if reason_type else None
    all_reasons = win_loss_service.get_reasons(reason_type=rt_val, active_only=active_only)
    total = len(all_reasons)

    # Nếu không truyền page/limit/skip -> trả về List gốc để tương thích 100% tests cũ
    if page is None and limit is None and skip is None:
        return all_reasons

    effective_limit = limit if limit is not None else 10
    if page is not None:
        effective_skip = (page - 1) * effective_limit
        effective_page = page
    elif skip is not None:
        effective_skip = skip
        effective_page = (effective_skip // effective_limit) + 1
    else:
        effective_skip = 0
        effective_page = 1

    paged_items = all_reasons[effective_skip : effective_skip + effective_limit]
    total_pages = max(1, math.ceil(total / effective_limit)) if total > 0 else 1

    return {
        "total": total,
        "items": paged_items,
        "page": effective_page,
        "limit": effective_limit,
        "total_pages": total_pages,
    }


@router.post("/reasons", response_model=ReasonResponse, status_code=status.HTTP_201_CREATED)
def create_reason(
    reason_in: ReasonCreate,
    current_user: dict = Depends(require_roles(["ADMIN"], detail="Chỉ Quản trị viên mới có quyền thêm lý do thắng/thua")),
):
    """Tạo mới lý do thắng/thua (kèm cấu hình bắt buộc đối thủ)."""
    return win_loss_service.create_reason(reason_in)


@router.put("/reasons/{reason_id}", response_model=ReasonResponse)
def update_reason(
    reason_id: int,
    reason_in: ReasonUpdate,
    current_user: dict = Depends(require_roles(["ADMIN"], detail="Chỉ Quản trị viên mới có quyền cập nhật lý do thắng/thua")),
):
    """Cập nhật thông tin lý do thắng/thua."""
    return win_loss_service.update_reason(reason_id, reason_in)


@router.delete("/reasons/{reason_id}")
def delete_reason(
    reason_id: int,
    current_user: dict = Depends(require_roles(["ADMIN"], detail="Chỉ Quản trị viên mới có quyền xoá lý do thắng/thua")),
):
    """Xóa lý do thắng/thua."""
    return win_loss_service.delete_reason(reason_id)


# --- Đối thủ cạnh tranh ---

@router.get("/competitors", response_model=Union[CompetitorListResponse, List[CompetitorResponse]])
def get_competitors(
    active_only: bool = Query(False, description="Chỉ lấy đối thủ đang kích hoạt"),
    page: Optional[int] = Query(None, ge=1, description="Số trang (bắt đầu từ 1)"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Số lượng bản ghi mỗi trang"),
    skip: Optional[int] = Query(None, ge=0, description="Vị trí bắt đầu"),
    current_user: dict = Depends(get_current_user),
):
    """Danh sách đối thủ cạnh tranh có hỗ trợ phân trang."""
    all_competitors = win_loss_service.get_competitors(active_only=active_only)
    total = len(all_competitors)

    if page is None and limit is None and skip is None:
        return all_competitors

    effective_limit = limit if limit is not None else 10
    if page is not None:
        effective_skip = (page - 1) * effective_limit
        effective_page = page
    elif skip is not None:
        effective_skip = skip
        effective_page = (effective_skip // effective_limit) + 1
    else:
        effective_skip = 0
        effective_page = 1

    paged_items = all_competitors[effective_skip : effective_skip + effective_limit]
    total_pages = max(1, math.ceil(total / effective_limit)) if total > 0 else 1

    return {
        "total": total,
        "items": paged_items,
        "page": effective_page,
        "limit": effective_limit,
        "total_pages": total_pages,
    }


@router.post("/competitors", response_model=CompetitorResponse, status_code=status.HTTP_201_CREATED)
def create_competitor(
    comp_in: CompetitorCreate,
    current_user: dict = Depends(require_roles(["ADMIN"], detail="Chỉ Quản trị viên mới có quyền thêm đối thủ cạnh tranh")),
):
    """Tạo mới thông tin đối thủ cạnh tranh."""
    return win_loss_service.create_competitor(comp_in)


@router.put("/competitors/{comp_id}", response_model=CompetitorResponse)
def update_competitor(
    comp_id: int,
    comp_in: CompetitorUpdate,
    current_user: dict = Depends(require_roles(["ADMIN"], detail="Chỉ Quản trị viên mới có quyền cập nhật đối thủ cạnh tranh")),
):
    """Cập nhật thông tin đối thủ cạnh tranh."""
    return win_loss_service.update_competitor(comp_id, comp_in)


@router.delete("/competitors/{comp_id}")
def delete_competitor(
    comp_id: int,
    current_user: dict = Depends(require_roles(["ADMIN"], detail="Chỉ Quản trị viên mới có quyền xoá đối thủ cạnh tranh")),
):
    """Xóa đối thủ cạnh tranh."""
    return win_loss_service.delete_competitor(comp_id)


# --- Kiểm tra hợp lệ khi Đóng cơ hội (Won/Lost) ---

@router.post("/validate-close", response_model=CloseOpportunityValidationResponse)
def validate_close_opportunity(
    req: CloseOpportunityValidationRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    AC S2-10: Kiểm tra tính hợp lệ khi nhân viên kinh doanh chuyển trạng thái sang Won hoặc Lost.
    Bắt buộc chọn lý do phù hợp và bắt buộc chọn đối thủ nếu lý do đó yêu cầu.
    """
    return win_loss_service.validate_close_opportunity(req)