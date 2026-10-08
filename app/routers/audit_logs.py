from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.audit_log import AuditLogListResponse
from app.services.audit_log_service import VALID_ENTITY_TYPES, get_audit_logs, log_change
from app.services.auth_service import require_admin

router = APIRouter(
    prefix="/audit-logs",
    tags=["Audit Logs"],
)


@router.get(
    "",
    response_model=AuditLogListResponse,
    summary="Xem nhật ký thay đổi trên dữ liệu nhạy cảm (ADMIN only)",
)
def list_audit_logs_endpoint(
    user_id: Optional[int] = Query(None, description="Lọc theo ID người thực hiện"),
    entity_type: Optional[str] = Query(None, description="Lọc theo loại đối tượng: ROLE, DISCOUNT, TARGET, DATA_OWNERSHIP"),
    from_date: Optional[datetime] = Query(None, description="Thời điểm bắt đầu (ISO format)"),
    to_date: Optional[datetime] = Query(None, description="Thời điểm kết thúc (ISO format)"),
    skip: int = Query(0, ge=0, description="Vị trí bắt đầu"),
    limit: int = Query(50, ge=1, le=200, description="Số lượng bản ghi tối đa"),
    admin_user: dict = Depends(require_admin),
):
    """
    AC S2-04:
    - Ghi lại mọi thay đổi trên chiết khấu, chỉ tiêu, quyền sở hữu dữ liệu và vai trò người dùng.
    - Mỗi bản ghi có người thực hiện, thời điểm, giá trị trước và sau.
    - Lọc theo người dùng, loại đối tượng, khoảng thời gian.
    """
    if entity_type and entity_type.strip().upper() not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Loại đối tượng không hợp lệ. Các loại hợp lệ: {', '.join(sorted(VALID_ENTITY_TYPES))}",
        )

    return get_audit_logs(
        user_id=user_id,
        entity_type=entity_type,
        from_date=from_date,
        to_date=to_date,
        skip=skip,
        limit=limit,
    )


@router.delete(
    "",
    summary="Xóa toàn bộ nhật ký hệ thống (ADMIN only)",
)
def clear_audit_logs_endpoint(admin_user: dict = Depends(require_admin)):
    """Xóa toàn bộ nhật ký trong CSDL và RAM."""
    from app.services.audit_log_service import clear_all_audit_logs
    count = clear_all_audit_logs()
    return {"message": f"Đã xóa thành công {count} bản ghi nhật ký hệ thống", "deleted_count": count}

