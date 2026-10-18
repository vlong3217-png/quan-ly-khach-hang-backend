"""
Automation Rules API Router (S7-09 EP-09).
- Mẫu quy tắc khi-thì cho Giám đốc kinh doanh (AC 1)
- Điều kiện dựa trên trạng thái hoặc mốc thời gian (AC 2)
- Hành động: tạo công việc, gửi thông báo, đổi người sở hữu (AC 3)
- Bật/tắt từng quy tắc và xem nhật ký quy tắc đã chạy (AC 4)
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.schemas.automation_rule import (
    AutomationRuleCreate,
    AutomationRuleUpdate,
    AutomationRuleResponse,
    AutomationRuleListResponse,
    AutomationRuleToggleResponse,
    AutomationExecutionLogResponse,
    AutomationExecutionLogListResponse,
    AutomationTestRunRequest,
    AutomationTestRunResponse,
)
from app.services import automation_rule_service

router = APIRouter(prefix="/automation-rules", tags=["Automation Rules"])

_READ_ROLES = ["ADMIN", "DIRECTOR", "MANAGER"]
_MANAGE_ROLES = ["ADMIN", "DIRECTOR"]
_ROLE_DENIED_DETAIL = "Chỉ Giám đốc kinh doanh (DIRECTOR) hoặc Quản trị viên (ADMIN) mới có quyền quản lý quy tắc tự động hóa."


# Lưu ý: Các route đường dẫn cố định (/logs) phải được khai báo trước /{rule_id} để tránh va chạm định tuyến

@router.get("/logs", response_model=AutomationExecutionLogListResponse)
def list_execution_logs(
    rule_id: Optional[int] = Query(None, description="Lọc theo mã quy tắc"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái (SUCCESS, FAILED, SKIPPED)"),
    trigger_event: Optional[str] = Query(None, description="Lọc theo sự kiện kích hoạt"),
    page: int = Query(1, ge=1, description="Số trang (bắt đầu từ 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Số lượng bản ghi mỗi trang"),
    current_user: dict = Depends(require_roles(_READ_ROLES, detail="Không có quyền xem nhật ký tự động hóa")),
    db: Session = Depends(get_db),
):
    """
    Xem danh sách nhật ký các lần quy tắc tự động hóa đã chạy (AC 4).
    """
    return automation_rule_service.list_execution_logs(
        rule_id=rule_id,
        status=status,
        trigger_event=trigger_event,
        page=page,
        page_size=page_size,
        db=db,
    )


@router.get("", response_model=AutomationRuleListResponse)
def list_automation_rules(
    is_active: Optional[bool] = Query(None, description="Lọc theo trạng thái bật (true) hoặc tắt (false)"),
    trigger_event: Optional[str] = Query(None, description="Lọc theo loại sự kiện kích hoạt"),
    page: int = Query(1, ge=1, description="Số trang (bắt đầu từ 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Số lượng quy tắc mỗi trang"),
    current_user: dict = Depends(require_roles(_READ_ROLES, detail="Không có quyền xem quy tắc tự động hóa")),
    db: Session = Depends(get_db),
):
    """
    Lấy danh sách các quy tắc tự động hóa bán hàng (AC 1 & AC 4).
    """
    return automation_rule_service.list_automation_rules(
        is_active=is_active,
        trigger_event=trigger_event,
        page=page,
        page_size=page_size,
        db=db,
    )


@router.post("", response_model=AutomationRuleResponse, status_code=status.HTTP_201_CREATED)
def create_automation_rule(
    payload: AutomationRuleCreate,
    current_user: dict = Depends(require_roles(_MANAGE_ROLES, detail=_ROLE_DENIED_DETAIL)),
    db: Session = Depends(get_db),
):
    """
    Khai báo một quy tắc tự động hóa bán hàng mới theo mẫu Khi–Thì (AC 1, AC 2, AC 3).
    Dành cho Giám đốc kinh doanh (DIRECTOR) và Admin.
    """
    return automation_rule_service.create_automation_rule(
        data=payload.model_dump(),
        current_user=current_user,
        db=db,
    )


@router.get("/{rule_id}", response_model=AutomationRuleResponse)
def get_automation_rule(
    rule_id: int,
    current_user: dict = Depends(require_roles(_READ_ROLES, detail="Không có quyền xem quy tắc tự động hóa")),
    db: Session = Depends(get_db),
):
    """
    Lấy thông tin chi tiết một quy tắc tự động hóa.
    """
    rule = automation_rule_service.get_automation_rule_by_id(rule_id=rule_id, db=db)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy quy tắc tự động hóa với mã ID {rule_id}",
        )
    return rule


@router.put("/{rule_id}", response_model=AutomationRuleResponse)
def update_automation_rule(
    rule_id: int,
    payload: AutomationRuleUpdate,
    current_user: dict = Depends(require_roles(_MANAGE_ROLES, detail=_ROLE_DENIED_DETAIL)),
    db: Session = Depends(get_db),
):
    """
    Chỉnh sửa quy tắc tự động hóa bán hàng.
    """
    updated = automation_rule_service.update_automation_rule(
        rule_id=rule_id,
        data=payload.model_dump(exclude_unset=True),
        current_user=current_user,
        db=db,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy quy tắc tự động hóa với mã ID {rule_id}",
        )
    return updated


@router.patch("/{rule_id}/toggle", response_model=AutomationRuleToggleResponse)
def toggle_automation_rule(
    rule_id: int,
    is_active: Optional[bool] = Query(None, description="Bật (true) hoặc tắt (false). Nếu bỏ trống sẽ đảo trạng thái hiện tại."),
    current_user: dict = Depends(require_roles(_MANAGE_ROLES, detail=_ROLE_DENIED_DETAIL)),
    db: Session = Depends(get_db),
):
    """
    Bật / tắt nhanh một quy tắc tự động hóa (AC 4).
    """
    toggled = automation_rule_service.toggle_automation_rule(
        rule_id=rule_id,
        is_active=is_active,
        current_user=current_user,
        db=db,
    )
    if not toggled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy quy tắc tự động hóa với mã ID {rule_id}",
        )
    return toggled


@router.delete("/{rule_id}")
def delete_automation_rule(
    rule_id: int,
    current_user: dict = Depends(require_roles(_MANAGE_ROLES, detail=_ROLE_DENIED_DETAIL)),
    db: Session = Depends(get_db),
):
    """
    Xóa một quy tắc tự động hóa bán hàng.
    """
    deleted = automation_rule_service.delete_automation_rule(rule_id=rule_id, db=db)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy quy tắc tự động hóa với mã ID {rule_id}",
        )
    return {"success": True, "message": f"Đã xóa quy tắc #{rule_id} thành công"}


@router.get("/{rule_id}/logs", response_model=AutomationExecutionLogListResponse)
def list_rule_specific_logs(
    rule_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_roles(_READ_ROLES, detail="Không có quyền xem nhật ký tự động hóa")),
    db: Session = Depends(get_db),
):
    """
    Xem danh sách nhật ký thực thi của riêng quy tắc này (AC 4).
    """
    return automation_rule_service.list_execution_logs(
        rule_id=rule_id,
        page=page,
        page_size=page_size,
        db=db,
    )


@router.post("/{rule_id}/test-run", response_model=AutomationTestRunResponse)
def test_run_rule(
    rule_id: int,
    payload: AutomationTestRunRequest,
    current_user: dict = Depends(require_roles(_MANAGE_ROLES, detail=_ROLE_DENIED_DETAIL)),
    db: Session = Depends(get_db),
):
    """
    Kích hoạt chạy thử nghiệm thủ công quy tắc trên thực thể mẫu (AC 4).
    """
    simulate_data = {
        "to_stage": payload.to_stage,
        "to_status": payload.to_status,
    }
    return automation_rule_service.test_run_rule(
        rule_id=rule_id,
        entity_id=payload.entity_id,
        simulate_payload=simulate_data,
        current_user=current_user,
        db=db,
    )
