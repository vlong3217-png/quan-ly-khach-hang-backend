from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import get_current_user, require_roles
from app.schemas.master_data import (
    MasterDataCreate,
    MasterDataReorderRequest,
    MasterDataResponse,
    MasterDataType,
    MasterDataUpdate,
)
from app.services import master_data_service

router = APIRouter(prefix="/master-data", tags=["Sales Master Data"])


@router.get("", response_model=List[MasterDataResponse])
def get_master_data_list(
    category: Optional[MasterDataType] = Query(None, description="Lọc theo loại: INDUSTRY, COMPANY_SIZE, LEAD_SOURCE, ACTIVITY_TYPE"),
    active_only: bool = Query(False, description="Chỉ lấy danh mục đang kích hoạt"),
    current_user: dict = Depends(get_current_user),
):
    """
    Xem danh sách danh mục dùng chung (Ngành nghề, Quy mô, Nguồn Lead, Loại hoạt động).
    Sắp xếp theo thứ tự hiển thị tùy chỉnh.
    """
    cat_val = category.value if category else None
    return master_data_service.get_master_data(category=cat_val, active_only=active_only)


@router.get("/{item_id}", response_model=MasterDataResponse)
def get_master_data_detail(
    item_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Xem chi tiết một danh mục master data."""
    return master_data_service.get_master_data_by_id(item_id)


@router.post("", response_model=MasterDataResponse, status_code=status.HTTP_201_CREATED)
def create_master_data(
    data_in: MasterDataCreate,
    current_user: dict = Depends(require_roles(["ADMIN"], detail="Chỉ Quản trị viên mới có quyền tạo danh mục dữ liệu")),
):
    """Tạo mới danh mục dùng chung."""
    return master_data_service.create_master_data(data_in)


@router.put("/{item_id}", response_model=MasterDataResponse)
def update_master_data(
    item_id: int,
    data_in: MasterDataUpdate,
    current_user: dict = Depends(require_roles(["ADMIN"], detail="Chỉ Quản trị viên mới có quyền cập nhật danh mục dữ liệu")),
):
    """Cập nhật thông tin danh mục, thứ tự hiển thị hoặc kích hoạt/ẩn."""
    return master_data_service.update_master_data(item_id, data_in)


@router.post("/reorder", response_model=List[MasterDataResponse])
def reorder_master_data(
    category: MasterDataType = Query(..., description="Loại danh mục cần đổi thứ tự"),
    reorder_in: MasterDataReorderRequest = ...,
    current_user: dict = Depends(require_roles(["ADMIN"], detail="Chỉ Quản trị viên mới có quyền sắp xếp thứ tự danh mục")),
):
    """Cập nhật hàng loạt thứ tự hiển thị cho một nhóm danh mục."""
    return master_data_service.reorder_master_data(category=category.value, reorder_in=reorder_in)


@router.delete("/{item_id}")
def delete_master_data(
    item_id: int,
    current_user: dict = Depends(require_roles(["ADMIN"], detail="Chỉ Quản trị viên mới có quyền xoá danh mục dữ liệu")),
):
    """
    Xóa danh mục.
    Kiểm tra ràng buộc: Nếu đang có bản ghi tham chiếu -> Không cho phép xóa, yêu cầu chuyển sang Ẩn (Inactive).
    """
    return master_data_service.delete_master_data(item_id)
