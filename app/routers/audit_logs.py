from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.database import get_db
from sqlalchemy.orm import Session
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
    entity_type: Optional[str] = Query(None, description="Lọc theo loại đối tượng: USER, ROLE, DISCOUNT, TARGET, DATA_OWNERSHIP"),
    from_date: Optional[datetime] = Query(None, description="Thời điểm bắt đầu (ISO format)"),
    to_date: Optional[datetime] = Query(None, description="Thời điểm kết thúc (ISO format)"),
    page: Optional[int] = Query(None, ge=1, description="Trang hiện tại (bắt đầu từ 1)"),
    skip: Optional[int] = Query(None, ge=0, description="Vị trí bắt đầu"),
    limit: Optional[int] = Query(None, ge=1, le=200, description="Số lượng bản ghi tối đa (mặc định 50)"),
    admin_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    AC S2-04:
    - Ghi lại mọi thay đổi trên chiết khấu, chỉ tiêu, quyền sở hữu dữ liệu và vai trò người dùng.
    - Mỗi bản ghi có người thực hiện, thời điểm, giá trị trước và sau.
    - Lọc theo người dùng, loại đối tượng, khoảng thời gian.
    """
    import math

    if entity_type and entity_type.strip().upper() not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Loại đối tượng không hợp lệ. Các loại hợp lệ: {', '.join(sorted(VALID_ENTITY_TYPES))}",
        )

    effective_limit = limit if limit is not None else 50
    if page is not None:
        effective_skip = (page - 1) * effective_limit
        effective_page = page
    elif skip is not None:
        effective_skip = skip
        effective_page = (effective_skip // effective_limit) + 1
    else:
        effective_skip = 0
        effective_page = 1

    res = get_audit_logs(
        user_id=user_id,
        entity_type=entity_type,
        from_date=from_date,
        to_date=to_date,
        skip=effective_skip,
        limit=effective_limit,
        db=db,
    )
    total = res.get("total", 0)
    total_pages = max(1, math.ceil(total / effective_limit)) if total > 0 else 1

    return {
        "total": total,
        "items": res.get("items", []),
        "page": effective_page,
        "limit": effective_limit,
        "skip": effective_skip,
        "total_pages": total_pages,
    }

