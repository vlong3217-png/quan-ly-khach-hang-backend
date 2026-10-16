"""
Activity, Task, Calendar, Timeline, and Notification service for Sprint 6.
Supports SQLite / MySQL persistence with RAM fallback for high-performance unit tests.
"""

import copy
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException, status

from app.core.dependencies import DataScope, check_scope_access
from app.core.database import SessionLocal
from app.models.activity import ActivityModel, TaskModel, NotificationModel
from app.models.opportunity import OpportunityModel, OpportunityHistoryModel
from app.models.quote import Quote as QuoteModel
from app.models.customer import Customer as CustomerModel
from app.models.contact import Contact as ContactModel
from app.models.user import User as UserModel

INITIAL_ACTIVITIES = [
    {
        "id": 1,
        "title": "Tư vấn giải pháp Admin",
        "type": "MEETING",
        "description": "Họp trao đổi yêu cầu với Admin",
        "customer_id": 1,
        "contact_id": 1,
        "opportunity_id": None,
        "duration_minutes": 60,
        "occurred_at": datetime(2026, 1, 15, 10, 0, 0),
        "owner_id": 1,
        "team_id": 1,
        "created_at": datetime(2026, 1, 15, 10, 0, 0).isoformat(),
    },
    {
        "id": 2,
        "title": "Gọi điện tư vấn Manager",
        "type": "CALL",
        "description": "Gọi điện giới thiệu tính năng",
        "customer_id": 2,
        "contact_id": 2,
        "opportunity_id": None,
        "duration_minutes": 15,
        "occurred_at": datetime(2026, 1, 16, 14, 30, 0),
        "owner_id": 2,
        "team_id": 1,
        "created_at": datetime(2026, 1, 16, 14, 30, 0).isoformat(),
    },
    {
        "id": 3,
        "title": "Gửi email báo giá User1",
        "type": "EMAIL",
        "description": "Gửi email kèm file báo giá",
        "customer_id": 3,
        "contact_id": None,
        "opportunity_id": None,
        "duration_minutes": 10,
        "occurred_at": datetime(2026, 1, 17, 9, 15, 0),
        "owner_id": 3,
        "team_id": 1,
        "created_at": datetime(2026, 1, 17, 9, 15, 0).isoformat(),
    },
    {
        "id": 4,
        "title": "Ghi chú hợp đồng User2",
        "type": "NOTE",
        "description": "Ghi chú theo dõi hợp đồng",
        "customer_id": 4,
        "contact_id": None,
        "opportunity_id": None,
        "duration_minutes": 5,
        "occurred_at": datetime(2026, 1, 18, 16, 0, 0),
        "owner_id": 4,
        "team_id": 2,
        "created_at": datetime(2026, 1, 18, 16, 0, 0).isoformat(),
    },
]

FAKE_ACTIVITIES = copy.deepcopy(INITIAL_ACTIVITIES)
FAKE_TASKS: List[Dict[str, Any]] = []
FAKE_NOTIFICATIONS: List[Dict[str, Any]] = []


def reset_fake_activities() -> None:
    global FAKE_ACTIVITIES, FAKE_TASKS, FAKE_NOTIFICATIONS
    FAKE_ACTIVITIES = copy.deepcopy(INITIAL_ACTIVITIES)
    FAKE_TASKS.clear()
    FAKE_NOTIFICATIONS.clear()
    db = SessionLocal()
    try:
        db.query(NotificationModel).delete()
        db.query(TaskModel).delete()
        db.query(ActivityModel).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _enrich_activity(act: dict) -> dict:
    c = copy.deepcopy(act)
    # Bổ sung tên khách, contact, opp, owner
    from app.services import customer_service, contact_service, opportunity_service, auth_service
    if c.get("customer_id") and not c.get("customer_name"):
        cust = customer_service.get_raw_customer_by_id(c["customer_id"])
        c["customer_name"] = cust.get("name") if cust else None

    if c.get("contact_id") and not c.get("contact_name"):
        ct = contact_service.get_contact_by_id(c["contact_id"])
        c["contact_name"] = ct.get("name") if ct else None

    if c.get("opportunity_id") and not c.get("opportunity_title"):
        opp = opportunity_service.get_raw_opportunity_by_id(c["opportunity_id"])
        c["opportunity_title"] = opp.get("title") if opp else None

    if c.get("owner_id") and not c.get("owner_name"):
        u = auth_service.get_user_by_id(c["owner_id"])
        c["owner_name"] = (u.get("full_name") or u.get("username")) if u else None

    return c


def get_raw_activity_by_id(activity_id: int) -> Optional[dict]:
    db = SessionLocal()
    try:
        r = db.query(ActivityModel).filter(ActivityModel.id == activity_id).first()
        if r:
            return _enrich_activity({
                "id": r.id,
                "title": r.title,
                "type": r.type,
                "description": r.description or "",
                "result": r.result,
                "duration_minutes": r.duration_minutes or 0,
                "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
                "customer_id": r.customer_id,
                "contact_id": r.contact_id,
                "opportunity_id": r.opportunity_id,
                "lead_id": r.lead_id,
                "owner_id": r.owner_id,
                "team_id": r.team_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })

        for act in FAKE_ACTIVITIES:
            if act["id"] == activity_id:
                return _enrich_activity(act)
        return None
    finally:
        db.close()


def get_activities_by_scope(
    current_user: dict,
    scope: DataScope,
    search: Optional[str] = None,
    customer_id: Optional[int] = None,
    opportunity_id: Optional[int] = None,
    contact_id: Optional[int] = None,
    activity_type: Optional[str] = None,
) -> list[dict]:
    db = SessionLocal()
    try:
        q = db.query(ActivityModel)
        if scope == DataScope.ALL:
            pass
        elif scope in (DataScope.TEAM, DataScope.MY_TEAM):
            user_team_id = current_user.get("team_id")
            if user_team_id is not None:
                q = q.filter(ActivityModel.team_id == user_team_id)
        else:
            q = q.filter(ActivityModel.owner_id == current_user["id"])

        if customer_id is not None:
            q = q.filter(ActivityModel.customer_id == customer_id)
        if opportunity_id is not None:
            q = q.filter(ActivityModel.opportunity_id == opportunity_id)
        if contact_id is not None:
            q = q.filter(ActivityModel.contact_id == contact_id)
        if activity_type:
            q = q.filter(ActivityModel.type == activity_type.upper())

        if search:
            s = f"%{search.strip().lower()}%"
            q = q.filter((ActivityModel.title.ilike(s)) | (ActivityModel.description.ilike(s)))

        rows = q.order_by(ActivityModel.occurred_at.desc(), ActivityModel.id.desc()).all()
        if rows:
            return [_enrich_activity({
                "id": r.id,
                "title": r.title,
                "type": r.type,
                "description": r.description or "",
                "result": r.result,
                "duration_minutes": r.duration_minutes or 0,
                "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
                "customer_id": r.customer_id,
                "contact_id": r.contact_id,
                "opportunity_id": r.opportunity_id,
                "lead_id": r.lead_id,
                "owner_id": r.owner_id,
                "team_id": r.team_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }) for r in rows]

        # Fallback RAM
        if scope == DataScope.ALL:
            results = list(FAKE_ACTIVITIES)
        elif scope in (DataScope.TEAM, DataScope.MY_TEAM):
            user_team_id = current_user.get("team_id")
            if user_team_id is None:
                results = list(FAKE_ACTIVITIES)
            else:
                results = [a for a in FAKE_ACTIVITIES if a.get("team_id") == user_team_id]
        else:
            user_id = current_user["id"]
            results = [a for a in FAKE_ACTIVITIES if a.get("owner_id") == user_id]

        if customer_id is not None:
            results = [a for a in results if a.get("customer_id") == customer_id]
        if opportunity_id is not None:
            results = [a for a in results if a.get("opportunity_id") == opportunity_id]
        if contact_id is not None:
            results = [a for a in results if a.get("contact_id") == contact_id]
        if activity_type:
            results = [a for a in results if (a.get("type") or "").upper() == activity_type.upper()]

        if search:
            s = search.lower().strip()
            results = [
                a for a in results
                if s in a.get("title", "").lower()
                or s in a.get("description", "").lower()
                or s in a.get("type", "").lower()
            ]

        results.sort(key=lambda x: str(x.get("occurred_at") or x.get("created_at") or ""), reverse=True)
        return [_enrich_activity(a) for a in results]
    finally:
        db.close()


def validate_related_entities_and_permissions(
    customer_id: Optional[int],
    contact_id: Optional[int],
    opportunity_id: Optional[int],
    current_user: dict,
) -> None:
    """S6-05: Kiểm tra tính tồn tại và quyền truy cập với khách hàng, contact, cơ hội liên kết."""
    from app.services import customer_service, contact_service, opportunity_service

    if customer_id is not None:
        cust = customer_service.get_raw_customer_by_id(customer_id)
        if not cust:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Khách hàng với ID {customer_id} không tồn tại")
        if not check_scope_access(current_user, cust.get("owner_id", 0), cust.get("team_id")):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền truy cập dữ liệu khách hàng này")

    if contact_id is not None:
        ct = contact_service.get_contact_by_id(contact_id)
        if not ct:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Người liên hệ với ID {contact_id} không tồn tại")
        if customer_id is not None and ct.get("customer_id") != customer_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Người liên hệ không thuộc khách hàng đã chọn")

    if opportunity_id is not None:
        opp = opportunity_service.get_raw_opportunity_by_id(opportunity_id)
        if not opp:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Cơ hội với ID {opportunity_id} không tồn tại")
        if not opportunity_service.check_opportunity_access_permission(opp, current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền truy cập dữ liệu cơ hội này")
        if customer_id is not None and opp.get("customer_id") and opp.get("customer_id") != customer_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cơ hội không thuộc khách hàng đã chọn")


def create_activity_record(data: dict, current_user: dict) -> dict:
    """
    S6-05: Ghi nhận hoạt động với 4 loại: CALL, MEETING, EMAIL, NOTE.
    Validate loại, khách hàng, người liên hệ, cơ hội và quyền truy cập.
    Cho phép ghi nhận thời điểm diễn ra trong quá khứ.
    """
    act_type = (data.get("type") or "CALL").strip().upper()
    valid_types = {"CALL", "MEETING", "EMAIL", "NOTE"}
    if act_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Loại hoạt động không hợp lệ: '{act_type}'. Các loại cho phép: {', '.join(sorted(valid_types))}",
        )

    validate_related_entities_and_permissions(
        customer_id=data.get("customer_id"),
        contact_id=data.get("contact_id"),
        opportunity_id=data.get("opportunity_id"),
        current_user=current_user,
    )

    occurred_at_val = data.get("occurred_at")
    if occurred_at_val is None:
        occurred_dt = datetime.now()
    elif isinstance(occurred_at_val, datetime):
        occurred_dt = occurred_at_val
    elif isinstance(occurred_at_val, str):
        try:
            occurred_dt = datetime.fromisoformat(occurred_at_val.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            occurred_dt = datetime.now()
    else:
        occurred_dt = datetime.now()

    now = datetime.now()
    new_act = {
        "title": data["title"].strip(),
        "type": act_type,
        "description": data.get("description", "") or "",
        "result": data.get("result"),
        "duration_minutes": int(data.get("duration_minutes") or 0),
        "occurred_at": occurred_dt,
        "customer_id": data.get("customer_id"),
        "contact_id": data.get("contact_id"),
        "opportunity_id": data.get("opportunity_id"),
        "lead_id": data.get("lead_id"),
        "owner_id": current_user["id"],
        "team_id": data.get("team_id") if data.get("team_id") is not None else current_user.get("team_id"),
        "created_at": now.isoformat(),
    }

    db = SessionLocal()
    try:
        m = ActivityModel(
            title=new_act["title"],
            type=new_act["type"],
            description=new_act["description"],
            result=new_act["result"],
            duration_minutes=new_act["duration_minutes"],
            occurred_at=occurred_dt,
            customer_id=new_act["customer_id"],
            contact_id=new_act["contact_id"],
            opportunity_id=new_act["opportunity_id"],
            lead_id=new_act["lead_id"],
            owner_id=new_act["owner_id"],
            team_id=new_act["team_id"],
            created_at=now,
        )
        db.add(m)
        db.commit()
        db.refresh(m)
        new_act["id"] = m.id
    except Exception:
        db.rollback()
        new_id = (max(a["id"] for a in FAKE_ACTIVITIES) + 1) if FAKE_ACTIVITIES else 1
        new_act["id"] = new_id
    finally:
        db.close()

    FAKE_ACTIVITIES.append(new_act)
    return _enrich_activity(new_act)


def update_activity_record(activity_id: int, data: dict, current_user: Optional[dict] = None) -> Optional[dict]:
    act = get_raw_activity_by_id(activity_id)
    if act is None:
        return None

    validate_related_entities_and_permissions(
        customer_id=data.get("customer_id", act.get("customer_id")),
        contact_id=data.get("contact_id", act.get("contact_id")),
        opportunity_id=data.get("opportunity_id", act.get("opportunity_id")),
        current_user=current_user or {"id": act["owner_id"], "role": "ADMIN"},
    )

    db = SessionLocal()
    try:
        m = db.query(ActivityModel).filter(ActivityModel.id == activity_id).first()
        if m:
            for k, v in data.items():
                if v is not None and k not in ("id", "owner_id"):
                    setattr(m, k, v)
            db.commit()
            db.refresh(m)
    except Exception:
        db.rollback()
    finally:
        db.close()

    for a in FAKE_ACTIVITIES:
        if a["id"] == activity_id:
            for key, value in data.items():
                if value is not None and key not in ("id", "owner_id"):
                    a[key] = value
            return _enrich_activity(a)

    return get_raw_activity_by_id(activity_id)


def delete_activity_record(activity_id: int) -> bool:
    global FAKE_ACTIVITIES
    db = SessionLocal()
    found = False
    try:
        m = db.query(ActivityModel).filter(ActivityModel.id == activity_id).first()
        if m:
            db.delete(m)
            db.commit()
            found = True
    except Exception:
        db.rollback()
    finally:
        db.close()

    initial_len = len(FAKE_ACTIVITIES)
    FAKE_ACTIVITIES = [a for a in FAKE_ACTIVITIES if a["id"] != activity_id]
    if len(FAKE_ACTIVITIES) < initial_len:
        found = True
    return found


# ============================================================================
# S6-06: TẠO VÀ THEO DÕI CÔNG VIỆC (TASKS)
# ============================================================================

def _enrich_task(task: dict) -> dict:
    c = copy.deepcopy(task)
    from app.services import customer_service, opportunity_service, contact_service, auth_service
    if c.get("customer_id") and not c.get("customer_name"):
        cust = customer_service.get_raw_customer_by_id(c["customer_id"])
        c["customer_name"] = cust.get("name") if cust else None

    if c.get("opportunity_id") and not c.get("opportunity_title"):
        opp = opportunity_service.get_raw_opportunity_by_id(c["opportunity_id"])
        c["opportunity_title"] = opp.get("title") if opp else None

    if c.get("contact_id") and not c.get("contact_name"):
        ct = contact_service.get_contact_by_id(c["contact_id"])
        c["contact_name"] = ct.get("name") if ct else None

    if c.get("assignee_id") and not c.get("assignee_name"):
        u = auth_service.get_user_by_id(c["assignee_id"])
        c["assignee_name"] = (u.get("full_name") or u.get("username")) if u else None

    if c.get("creator_id") and not c.get("creator_name"):
        cu = auth_service.get_user_by_id(c["creator_id"])
        c["creator_name"] = (cu.get("full_name") or cu.get("username")) if cu else None

    # Check is_overdue
    due = c.get("due_date")
    if due and c.get("status") not in ("COMPLETED", "CANCELLED"):
        try:
            if isinstance(due, str):
                due_dt = datetime.fromisoformat(due.replace("Z", "+00:00")).replace(tzinfo=None)
            else:
                due_dt = due
            c["is_overdue"] = due_dt < datetime.now()
        except Exception:
            c["is_overdue"] = False
    else:
        c["is_overdue"] = False

    return c


def get_task_by_id(task_id: int) -> Optional[dict]:
    db = SessionLocal()
    try:
        r = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        if r:
            return _enrich_task({
                "id": r.id,
                "title": r.title,
                "description": r.description,
                "due_date": r.due_date.isoformat() if r.due_date else None,
                "priority": r.priority,
                "status": r.status,
                "assignee_id": r.assignee_id,
                "creator_id": r.creator_id,
                "updater_id": r.updater_id,
                "customer_id": r.customer_id,
                "opportunity_id": r.opportunity_id,
                "contact_id": r.contact_id,
                "postpone_reason": r.postpone_reason,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            })

        for t in FAKE_TASKS:
            if t["id"] == task_id:
                return _enrich_task(t)
        return None
    finally:
        db.close()


def check_task_permission(task: dict, current_user: dict, require_edit: bool = False) -> bool:
    """
    Quyền với công việc:
    - ADMIN: Toàn quyền.
    - MANAGER: Có thể xem/sửa công việc do mình tạo, giao cho thành viên trong team hoặc việc trong team.
    - USER: Xem/cập nhật công việc được giao cho mình hoặc do mình tạo.
    """
    role = current_user.get("role", "USER")
    uid = current_user.get("id")
    if role == "ADMIN":
        return True
    if task.get("assignee_id") == uid or task.get("creator_id") == uid:
        return True

    from app.services import auth_service
    if role == "MANAGER":
        mgr_team = current_user.get("team_id")
        assignee = auth_service.get_user_by_id(task.get("assignee_id"))
        if assignee and assignee.get("team_id") == mgr_team:
            return True

    return False


def create_task_record(data: dict, current_user: dict) -> dict:
    """
    S6-06: Tạo công việc và giao việc:
    - Trưởng nhóm được giao việc cho thành viên thuộc phạm vi quản lý.
    - Nhân viên thường chỉ được tự giao việc cho mình hoặc người trong quyền quy định.
    """
    validate_related_entities_and_permissions(
        customer_id=data.get("customer_id"),
        contact_id=data.get("contact_id"),
        opportunity_id=data.get("opportunity_id"),
        current_user=current_user,
    )

    creator_id = current_user.get("id")
    role = current_user.get("role", "USER")
    assignee_id = data.get("assignee_id") or creator_id

    from app.services import auth_service
    assignee = auth_service.get_user_by_id(assignee_id)
    if not assignee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy người thực hiện với ID {assignee_id}")

    # Kiểm tra quyền giao việc
    if assignee_id != creator_id:
        if role == "USER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Nhân viên chỉ có thể tạo công việc cho chính mình",
            )
        elif role == "MANAGER":
            mgr_team = current_user.get("team_id")
            if assignee.get("team_id") != mgr_team:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Trưởng nhóm chỉ được giao việc cho thành viên thuộc nhóm quản lý",
                )

    due_val = data.get("due_date")
    if isinstance(due_val, str):
        try:
            due_dt = datetime.fromisoformat(due_val.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Định dạng hạn hoàn thành due_date không hợp lệ")
    elif isinstance(due_val, datetime):
        due_dt = due_val
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Hạn hoàn thành due_date là bắt buộc")

    priority = (data.get("priority") or "MEDIUM").upper()
    now = datetime.now()
    new_task = {
        "title": data["title"].strip(),
        "description": data.get("description"),
        "due_date": due_dt,
        "priority": priority,
        "status": "PENDING",
        "assignee_id": assignee_id,
        "creator_id": creator_id,
        "updater_id": creator_id,
        "customer_id": data.get("customer_id"),
        "opportunity_id": data.get("opportunity_id"),
        "contact_id": data.get("contact_id"),
        "postpone_reason": None,
        "completed_at": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }

    db = SessionLocal()
    try:
        m = TaskModel(
            title=new_task["title"],
            description=new_task["description"],
            due_date=due_dt,
            priority=priority,
            status="PENDING",
            assignee_id=assignee_id,
            creator_id=creator_id,
            updater_id=creator_id,
            customer_id=new_task["customer_id"],
            opportunity_id=new_task["opportunity_id"],
            contact_id=new_task["contact_id"],
            created_at=now,
            updated_at=now,
        )
        db.add(m)
        db.commit()
        db.refresh(m)
        new_task["id"] = m.id
    except Exception:
        db.rollback()
        new_id = (max([t["id"] for t in FAKE_TASKS], default=0) + 1)
        new_task["id"] = new_id
    finally:
        db.close()

    FAKE_TASKS.append(new_task)
    return _enrich_task(new_task)


def update_task_record(task_id: int, data: dict, current_user: dict) -> dict:
    task = get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy công việc")
    if not check_task_permission(task, current_user, require_edit=True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền chỉnh sửa công việc này")

    validate_related_entities_and_permissions(
        customer_id=data.get("customer_id", task.get("customer_id")),
        contact_id=data.get("contact_id", task.get("contact_id")),
        opportunity_id=data.get("opportunity_id", task.get("opportunity_id")),
        current_user=current_user,
    )

    now = datetime.now()
    updater_id = current_user.get("id")

    db = SessionLocal()
    try:
        m = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        if m:
            for k, v in data.items():
                if v is not None and hasattr(m, k) and k not in ("id", "creator_id"):
                    setattr(m, k, v)
            m.updater_id = updater_id
            m.updated_at = now
            db.commit()
            db.refresh(m)
    except Exception:
        db.rollback()
    finally:
        db.close()

    for t in FAKE_TASKS:
        if t["id"] == task_id:
            for k, v in data.items():
                if v is not None and k not in ("id", "creator_id"):
                    t[k] = v
            t["updater_id"] = updater_id
            t["updated_at"] = now.isoformat()
            return _enrich_task(t)

    return get_task_by_id(task_id)


def complete_task_record(task_id: int, current_user: dict, note: Optional[str] = None) -> dict:
    """S6-06: Đánh dấu hoàn thành công việc."""
    task = get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy công việc")
    if not check_task_permission(task, current_user, require_edit=True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền hoàn thành công việc này")

    now = datetime.now()
    updater_id = current_user.get("id")

    db = SessionLocal()
    try:
        m = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        if m:
            m.status = "COMPLETED"
            m.completed_at = now
            m.updater_id = updater_id
            m.updated_at = now
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    for t in FAKE_TASKS:
        if t["id"] == task_id:
            t["status"] = "COMPLETED"
            t["completed_at"] = now.isoformat()
            t["updater_id"] = updater_id
            t["updated_at"] = now.isoformat()
            return _enrich_task(t)

    return get_task_by_id(task_id)


def postpone_task_record(task_id: int, new_due_date: datetime, reason: str, current_user: dict) -> dict:
    """S6-06: Hoãn công việc - bắt buộc phải có lý do."""
    clean_reason = (reason or "").strip()
    if not clean_reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hoãn công việc bắt buộc phải có lý do hoãn",
        )

    task = get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy công việc")
    if not check_task_permission(task, current_user, require_edit=True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền hoãn công việc này")

    now = datetime.now()
    updater_id = current_user.get("id")

    db = SessionLocal()
    try:
        m = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        if m:
            m.status = "POSTPONED"
            m.due_date = new_due_date
            m.postpone_reason = clean_reason
            m.updater_id = updater_id
            m.updated_at = now
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    for t in FAKE_TASKS:
        if t["id"] == task_id:
            t["status"] = "POSTPONED"
            t["due_date"] = new_due_date
            t["postpone_reason"] = clean_reason
            t["updater_id"] = updater_id
            t["updated_at"] = now.isoformat()
            return _enrich_task(t)

    return get_task_by_id(task_id)


def list_tasks_by_scope(
    current_user: dict,
    scope: DataScope,
    assignee_id: Optional[int] = None,
    task_status: Optional[str] = None,
    priority: Optional[str] = None,
    due_from: Optional[str] = None,
    due_to: Optional[str] = None,
    customer_id: Optional[int] = None,
    opportunity_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 20,
) -> Tuple[List[Dict[str, Any]], int]:
    """S6-06: Truy vấn danh sách công việc theo bộ lọc và phân quyền."""
    db = SessionLocal()
    try:
        q = db.query(TaskModel)
        role = current_user.get("role", "USER")
        uid = current_user.get("id")
        user_team = current_user.get("team_id")

        if scope == DataScope.ALL:
            pass
        elif scope in (DataScope.TEAM, DataScope.MY_TEAM):
            if user_team is not None:
                # Assignee hoặc creator trong team
                team_user_ids = [u.id for u in db.query(UserModel.id).filter(UserModel.team_id == user_team).all()]
                q = q.filter((TaskModel.assignee_id.in_(team_user_ids)) | (TaskModel.creator_id.in_(team_user_ids)))
        else:
            q = q.filter((TaskModel.assignee_id == uid) | (TaskModel.creator_id == uid))

        if assignee_id is not None:
            q = q.filter(TaskModel.assignee_id == assignee_id)
        if task_status:
            q = q.filter(TaskModel.status == task_status.upper())
        if priority:
            q = q.filter(TaskModel.priority == priority.upper())
        if customer_id is not None:
            q = q.filter(TaskModel.customer_id == customer_id)
        if opportunity_id is not None:
            q = q.filter(TaskModel.opportunity_id == opportunity_id)

        if due_from:
            try:
                df = datetime.strptime(due_from[:10], "%Y-%m-%d")
                q = q.filter(TaskModel.due_date >= df)
            except Exception:
                pass
        if due_to:
            try:
                dt = datetime.strptime(due_to[:10], "%Y-%m-%d") + timedelta(days=1)
                q = q.filter(TaskModel.due_date < dt)
            except Exception:
                pass

        total = q.count()
        rows = q.order_by(TaskModel.due_date.asc(), TaskModel.id.desc()).offset(skip).limit(limit).all()
        if total > 0 or rows:
            items = [_enrich_task({
                "id": r.id,
                "title": r.title,
                "description": r.description,
                "due_date": r.due_date.isoformat() if r.due_date else None,
                "priority": r.priority,
                "status": r.status,
                "assignee_id": r.assignee_id,
                "creator_id": r.creator_id,
                "updater_id": r.updater_id,
                "customer_id": r.customer_id,
                "opportunity_id": r.opportunity_id,
                "contact_id": r.contact_id,
                "postpone_reason": r.postpone_reason,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }) for r in rows]
            return items, total

        # Fallback RAM
        results = list(FAKE_TASKS)
        if scope == DataScope.ALL:
            pass
        elif scope in (DataScope.TEAM, DataScope.MY_TEAM):
            from app.services import auth_service
            results = [
                t for t in results
                if (auth_service.get_user_by_id(t.get("assignee_id")) or {}).get("team_id") == user_team
                or (auth_service.get_user_by_id(t.get("creator_id")) or {}).get("team_id") == user_team
            ]
        else:
            results = [t for t in results if t.get("assignee_id") == uid or t.get("creator_id") == uid]

        if assignee_id is not None:
            results = [t for t in results if t.get("assignee_id") == assignee_id]
        if task_status:
            results = [t for t in results if (t.get("status") or "").upper() == task_status.upper()]
        if priority:
            results = [t for t in results if (t.get("priority") or "").upper() == priority.upper()]
        if customer_id is not None:
            results = [t for t in results if t.get("customer_id") == customer_id]
        if opportunity_id is not None:
            results = [t for t in results if t.get("opportunity_id") == opportunity_id]

        total_ram = len(results)
        results.sort(key=lambda x: str(x.get("due_date", "")))
        paged = [_enrich_task(t) for t in results[skip : skip + limit]]
        return paged, total_ram
    finally:
        db.close()


# ============================================================================
# S6-07: LỊCH LÀM VIỆC CÁ NHÂN VÀ NHÓM (CALENDAR)
# ============================================================================

def get_calendar_events(
    view_type: str,
    target_date: Optional[str],
    user_id: Optional[int],
    team_id: Optional[int],
    current_user: dict,
) -> dict:
    """
    S6-07: Trả về cuộc gặp đã đặt và công việc có hạn trong khoảng thời gian (ngày, tuần, tháng).
    Kiểm tra lịch chồng lấn và kiểm soát phân quyền xem lịch nhóm.
    """
    vt = (view_type or "DAY").upper()
    try:
        base_date = datetime.strptime(target_date[:10], "%Y-%m-%d").date() if target_date else date.today()
    except Exception:
        base_date = date.today()

    if vt == "DAY":
        start_dt = datetime(base_date.year, base_date.month, base_date.day, 0, 0, 0)
        end_dt = start_dt + timedelta(days=1)
    elif vt == "WEEK":
        # Bắt đầu từ thứ 2 của tuần
        weekday = base_date.weekday()
        start_date = base_date - timedelta(days=weekday)
        start_dt = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0)
        end_dt = start_dt + timedelta(days=7)
    elif vt == "MONTH":
        start_dt = datetime(base_date.year, base_date.month, 1, 0, 0, 0)
        if base_date.month == 12:
            end_dt = datetime(base_date.year + 1, 1, 1, 0, 0, 0)
        else:
            end_dt = datetime(base_date.year, base_date.month + 1, 1, 0, 0, 0)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="view_type hợp lệ: DAY, WEEK, MONTH")

    # Kiểm tra phân quyền truy cập lịch
    role = current_user.get("role", "USER")
    cur_uid = current_user.get("id")
    cur_team = current_user.get("team_id")

    from app.services import auth_service
    target_uid = user_id
    if target_uid is not None:
        if role == "USER" and target_uid != cur_uid:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nhân viên chỉ được xem lịch làm việc của cá nhân")
        if role == "MANAGER":
            t_user = auth_service.get_user_by_id(target_uid)
            if target_uid != cur_uid and (not t_user or t_user.get("team_id") != cur_team):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Trưởng nhóm chỉ được xem lịch thành viên thuộc nhóm quản lý")
    elif team_id is not None:
        if role == "USER":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nhân viên không có quyền xem lịch của nhóm")
        if role == "MANAGER" and team_id != cur_team:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Trưởng nhóm chỉ được xem lịch của nhóm do mình quản lý")
    else:
        # Mặc định theo vai trò: USER -> chính mình, MANAGER/ADMIN -> chính mình nếu không yêu cầu
        if role == "USER":
            target_uid = cur_uid

    # 1. Thu thập Cuộc gặp (Activities loại MEETING)
    events: List[Dict[str, Any]] = []

    # Lấy activities
    all_acts = get_activities_by_scope(current_user, DataScope.ALL if role in ("ADMIN", "MANAGER") else DataScope.MY)
    for a in all_acts:
        if (a.get("type") or "").upper() != "MEETING":
            continue
        # Filter user/team
        act_owner = a.get("owner_id")
        act_team = a.get("team_id")
        if target_uid is not None and act_owner != target_uid:
            continue
        if team_id is not None and act_team != team_id:
            continue

        occ = a.get("occurred_at")
        if not occ:
            continue
        try:
            occ_dt = datetime.fromisoformat(str(occ).replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            continue

        if start_dt <= occ_dt < end_dt:
            dur = a.get("duration_minutes") or 60
            end_occ = occ_dt + timedelta(minutes=dur)
            events.append({
                "id": f"meeting_{a['id']}",
                "event_type": "MEETING",
                "title": a.get("title") or "Cuộc gặp",
                "start_time": occ_dt.isoformat(),
                "end_time": end_occ.isoformat(),
                "status": "SCHEDULED",
                "priority": "HIGH",
                "user_id": act_owner,
                "user_name": a.get("owner_name"),
                "customer_id": a.get("customer_id"),
                "customer_name": a.get("customer_name"),
                "opportunity_id": a.get("opportunity_id"),
                "opportunity_title": a.get("opportunity_title"),
                "has_conflict": False,
            })

    # 2. Thu thập Công việc (Tasks)
    task_scope = DataScope.ALL if role in ("ADMIN", "MANAGER") else DataScope.MY
    all_tasks, _ = list_tasks_by_scope(
        current_user=current_user,
        scope=task_scope,
        assignee_id=target_uid,
        skip=0,
        limit=1000,
    )
    for t in all_tasks:
        due = t.get("due_date")
        if not due:
            continue
        try:
            due_dt = datetime.fromisoformat(str(due).replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            continue

        if team_id is not None:
            assignee = auth_service.get_user_by_id(t.get("assignee_id"))
            if not assignee or assignee.get("team_id") != team_id:
                continue

        if start_dt <= due_dt < end_dt:
            events.append({
                "id": f"task_{t['id']}",
                "event_type": "TASK",
                "title": t.get("title") or "Công việc",
                "start_time": due_dt.isoformat(),
                "end_time": (due_dt + timedelta(minutes=30)).isoformat(),
                "status": t.get("status"),
                "priority": t.get("priority"),
                "user_id": t.get("assignee_id"),
                "user_name": t.get("assignee_name"),
                "customer_id": t.get("customer_id"),
                "customer_name": t.get("customer_name"),
                "opportunity_id": t.get("opportunity_id"),
                "opportunity_title": t.get("opportunity_title"),
                "has_conflict": False,
            })

    # 3. Kiểm tra xung đột / chồng lấn thời gian (Conflict Detection)
    # Hai sự kiện của cùng 1 user chồng lấn nếu startA < endB và startB < endA
    conflicts_count = 0
    parsed_intervals = []
    for ev in events:
        s = datetime.fromisoformat(ev["start_time"])
        e = datetime.fromisoformat(ev["end_time"]) if ev.get("end_time") else s + timedelta(minutes=30)
        parsed_intervals.append((ev, s, e, ev["user_id"]))

    for i in range(len(parsed_intervals)):
        for j in range(i + 1, len(parsed_intervals)):
            ev1, s1, e1, u1 = parsed_intervals[i]
            ev2, s2, e2, u2 = parsed_intervals[j]
            if u1 == u2 and s1 < e2 and s2 < e1:
                ev1["has_conflict"] = True
                ev2["has_conflict"] = True
                conflicts_count += 1

    events.sort(key=lambda x: str(x["start_time"]))

    return {
        "view_type": vt,
        "from_date": start_dt.date().isoformat(),
        "to_date": end_dt.date().isoformat(),
        "user_id": target_uid,
        "team_id": team_id,
        "total_events": len(events),
        "conflicts_count": conflicts_count,
        "events": events,
    }


# ============================================================================
# S6-08: DÒNG THỜI GIAN TƯƠNG TÁC KHÁCH HÀNG (CUSTOMER TIMELINE)
# ============================================================================

def get_customer_timeline(
    customer_id: int,
    current_user: dict,
    event_type_filter: Optional[str] = None,
    performer_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 20,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    S6-08: Tổng hợp dòng thời gian tương tác đầy đủ của một khách hàng:
    - Hoạt động (Activities: CALL, MEETING, EMAIL, NOTE)
    - Thay đổi cơ hội (Opportunity Histories)
    - Báo giá đã gửi (Quotes)
    - Sắp xếp mới nhất trước, phân trang, lọc theo loại sự kiện và người thực hiện.
    """
    from app.services import customer_service, quote_service, opportunity_service

    cust = customer_service.get_raw_customer_by_id(customer_id)
    if not cust:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy khách hàng với ID {customer_id}")
    if not check_scope_access(current_user, cust.get("owner_id", 0), cust.get("team_id")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền xem dòng thời gian của khách hàng này")

    timeline: List[Dict[str, Any]] = []

    # 1. Activities của khách hàng
    activities = get_activities_by_scope(current_user, DataScope.ALL, customer_id=customer_id)
    for a in activities:
        ev_type = f"ACTIVITY_{a.get('type', 'NOTE')}"
        ts = a.get("occurred_at") or a.get("created_at")
        timeline.append({
            "id": f"act_{a['id']}",
            "event_type": ev_type,
            "title": f"Hoạt động: {a.get('title')}",
            "timestamp": ts,
            "actor_id": a.get("owner_id"),
            "actor_name": a.get("owner_name") or f"User {a.get('owner_id')}",
            "summary": a.get("description") or a.get("result") or "",
            "details": a,
        })

    # 2. Cơ hội và Lịch sử thay đổi cơ hội của khách hàng
    opps = opportunity_service.get_opportunities_by_scope(current_user, DataScope.ALL, customer_id=customer_id)
    for opp in opps:
        # Lấy histories của opp
        histories, _ = opportunity_service.list_opportunity_histories(opp["id"], skip=0, limit=100)
        for h in histories:
            timeline.append({
                "id": f"opp_hist_{h['id']}",
                "event_type": f"OPPORTUNITY_{h['field_name'].upper()}_CHANGE",
                "title": f"Cơ hội '{opp['title']}': Thay đổi {h['field_name']}",
                "timestamp": h.get("created_at"),
                "actor_id": h.get("performed_by"),
                "actor_name": h.get("performer_name") or f"User {h.get('performed_by')}",
                "summary": f"Từ '{h.get('old_value')}' thành '{h.get('new_value')}'",
                "details": h,
            })

    # 3. Báo giá gửi cho khách hàng
    quotes = quote_service.get_quotes_by_scope(current_user, DataScope.ALL)
    for q in quotes:
        if q.get("customer_id") == customer_id:
            timeline.append({
                "id": f"quote_{q['id']}",
                "event_type": f"QUOTE_{q.get('status', 'SENT')}",
                "title": f"Báo giá: {q.get('title')}",
                "timestamp": q.get("created_at") or datetime(2026, 1, 15, 0, 0, 0).isoformat(),
                "actor_id": q.get("owner_id"),
                "actor_name": f"User {q.get('owner_id')}",
                "summary": f"Số tiền: {float(q.get('amount') or 0):,.0f} VNĐ - Trạng thái: {q.get('status')}",
                "details": q,
            })

    # Lọc theo event_type
    if event_type_filter:
        et = event_type_filter.upper().strip()
        timeline = [item for item in timeline if et in item["event_type"]]

    # Lọc theo người thực hiện
    if performer_id is not None:
        timeline = [item for item in timeline if item["actor_id"] == performer_id]

    # Sắp xếp theo timestamp giảm dần (mới nhất trước)
    timeline.sort(key=lambda x: str(x.get("timestamp") or ""), reverse=True)

    total = len(timeline)
    paged = timeline[skip : skip + limit]
    return paged, total


# ============================================================================
# S6-09: NHẮC VIỆC SẮP ĐẾN HẠN VÀ QUÁ HẠN (REMINDERS & NOTIFICATIONS)
# ============================================================================

def scan_task_reminders(threshold_hours: int = 24, db: Optional[Any] = None) -> Dict[str, Any]:
    """
    S6-09: Cơ chế chạy nền quét công việc sắp đến hạn và quá hạn:
    - Tạo thông báo in-app cho người được giao việc.
    - Chống gửi thông báo trùng lặp bằng dedup_key.
    - Không tính công việc đã hoàn thành hoặc hủy.
    """
    now = datetime.now()
    threshold_dt = now + timedelta(hours=threshold_hours)

    local_db = None
    if db is None:
        local_db = SessionLocal()
        session = local_db
    else:
        session = db

    created_notifications = []
    try:
        tasks = session.query(TaskModel).filter(~TaskModel.status.in_(["COMPLETED", "CANCELLED"])).all()
        for t in tasks:
            due = t.due_date
            if not due:
                continue

            # 1. Quá hạn
            if due < now:
                dedup_key = f"OVERDUE_TASK_{t.id}_{due.date()}"
                existing = session.query(NotificationModel).filter(NotificationModel.dedup_key == dedup_key).first()
                if not existing:
                    notif = NotificationModel(
                        user_id=t.assignee_id,
                        title=f"Cảnh báo quá hạn: {t.title}",
                        message=f"Công việc '{t.title}' đã quá hạn vào {due.strftime('%d/%m/%Y %H:%M')}.",
                        type="OVERDUE_TASK",
                        reference_id=t.id,
                        dedup_key=dedup_key,
                        is_read=False,
                        created_at=now,
                    )
                    session.add(notif)
                    created_notifications.append(dedup_key)

            # 2. Sắp đến hạn
            elif now <= due <= threshold_dt:
                dedup_key = f"UPCOMING_TASK_{t.id}_{due.date()}"
                existing = session.query(NotificationModel).filter(NotificationModel.dedup_key == dedup_key).first()
                if not existing:
                    notif = NotificationModel(
                        user_id=t.assignee_id,
                        title=f"Nhắc việc sắp đến hạn: {t.title}",
                        message=f"Công việc '{t.title}' sẽ đến hạn vào {due.strftime('%d/%m/%Y %H:%M')}.",
                        type="TASK_REMINDER",
                        reference_id=t.id,
                        dedup_key=dedup_key,
                        is_read=False,
                        created_at=now,
                    )
                    session.add(notif)
                    created_notifications.append(dedup_key)

        session.commit()
    except Exception:
        if local_db is not None:
            session.rollback()
        # Fallback RAM
        for t in FAKE_TASKS:
            if t.get("status") in ("COMPLETED", "CANCELLED"):
                continue
            due = t.get("due_date")
            if not due:
                continue
            due_dt = due if isinstance(due, datetime) else datetime.fromisoformat(str(due))
            if due_dt < now:
                dkey = f"OVERDUE_TASK_{t['id']}_{due_dt.date()}"
                if not any(n["dedup_key"] == dkey for n in FAKE_NOTIFICATIONS):
                    new_id = (max([n["id"] for n in FAKE_NOTIFICATIONS], default=0) + 1)
                    FAKE_NOTIFICATIONS.append({
                        "id": new_id,
                        "user_id": t["assignee_id"],
                        "title": f"Cảnh báo quá hạn: {t['title']}",
                        "message": f"Công việc '{t['title']}' đã quá hạn.",
                        "type": "OVERDUE_TASK",
                        "reference_id": t["id"],
                        "dedup_key": dkey,
                        "is_read": False,
                        "created_at": now.isoformat(),
                    })
                    created_notifications.append(dkey)
            elif now <= due_dt <= threshold_dt:
                dkey = f"UPCOMING_TASK_{t['id']}_{due_dt.date()}"
                if not any(n["dedup_key"] == dkey for n in FAKE_NOTIFICATIONS):
                    new_id = (max([n["id"] for n in FAKE_NOTIFICATIONS], default=0) + 1)
                    FAKE_NOTIFICATIONS.append({
                        "id": new_id,
                        "user_id": t["assignee_id"],
                        "title": f"Nhắc việc sắp đến hạn: {t['title']}",
                        "message": f"Công việc '{t['title']}' sắp đến hạn.",
                        "type": "TASK_REMINDER",
                        "reference_id": t["id"],
                        "dedup_key": dkey,
                        "is_read": False,
                        "created_at": now.isoformat(),
                    })
                    created_notifications.append(dkey)
    finally:
        if local_db is not None:
            local_db.close()

    return {
        "status": "SUCCESS",
        "new_notifications_count": len(created_notifications),
        "notifications": created_notifications,
    }


def list_user_notifications(user_id: int) -> Tuple[List[Dict[str, Any]], int]:
    """Lấy danh sách thông báo của user và số lượng chưa đọc."""
    db = SessionLocal()
    try:
        rows = db.query(NotificationModel).filter(NotificationModel.user_id == user_id).order_by(NotificationModel.id.desc()).all()
        if rows:
            items = [{
                "id": r.id,
                "user_id": r.user_id,
                "title": r.title,
                "message": r.message,
                "type": r.type,
                "reference_id": r.reference_id,
                "is_read": bool(r.is_read),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            } for r in rows]
            unread = sum(1 for i in items if not i["is_read"])
            return items, unread

        ram_items = [n for n in FAKE_NOTIFICATIONS if n["user_id"] == user_id]
        ram_items.sort(key=lambda x: str(x.get("id")), reverse=True)
        unread = sum(1 for i in ram_items if not i["is_read"])
        return ram_items, unread
    finally:
        db.close()


def mark_notification_as_read(notification_id: int, user_id: int) -> bool:
    db = SessionLocal()
    found = False
    try:
        r = db.query(NotificationModel).filter(
            NotificationModel.id == notification_id,
            NotificationModel.user_id == user_id,
        ).first()
        if r:
            r.is_read = True
            db.commit()
            found = True
    except Exception:
        db.rollback()
    finally:
        db.close()

    for n in FAKE_NOTIFICATIONS:
        if n["id"] == notification_id and n["user_id"] == user_id:
            n["is_read"] = True
            found = True

    return found


def get_overdue_tasks_summary_for_manager(current_user: dict) -> dict:
    """
    S6-09: Dữ liệu tổng hợp số lượng công việc quá hạn của từng thành viên để trưởng nhóm xem.
    Chỉ tính công việc chưa hoàn thành và đã quá hạn.
    """
    role = current_user.get("role", "USER")
    if role not in ("ADMIN", "MANAGER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Trưởng nhóm kinh doanh hoặc Quản trị viên mới được xem báo cáo tổng hợp công việc quá hạn",
        )

    from app.services import auth_service
    now = datetime.now()

    all_users = auth_service.fake_users_db
    mgr_team = current_user.get("team_id")
    if role == "MANAGER":
        members = [u for u in all_users if u.get("team_id") == mgr_team]
    else:
        members = all_users

    db = SessionLocal()
    summary_members = []
    total_overdue = 0

    try:
        for m in members:
            uid = m["id"]
            # Query tasks of member
            cnt = db.query(TaskModel).filter(
                TaskModel.assignee_id == uid,
                ~TaskModel.status.in_(["COMPLETED", "CANCELLED"]),
                TaskModel.due_date < now,
            ).count()

            # Include RAM
            ram_cnt = len([
                t for t in FAKE_TASKS
                if t.get("assignee_id") == uid
                and t.get("status") not in ("COMPLETED", "CANCELLED")
                and (t.get("due_date") if isinstance(t.get("due_date"), datetime) else datetime.fromisoformat(str(t.get("due_date")))) < now
            ])
            member_overdue = max(cnt, ram_cnt)
            total_overdue += member_overdue
            summary_members.append({
                "user_id": uid,
                "user_name": m.get("full_name") or m.get("username") or f"User {uid}",
                "team_id": m.get("team_id"),
                "overdue_count": member_overdue,
            })
    finally:
        db.close()

    return {
        "total_overdue": total_overdue,
        "members": summary_members,
    }


# ============================================================================
# S6-10: GHI NHANH KẾT QUẢ CUỘC GỌI (QUICK CALL LOG)
# ============================================================================

def log_quick_call(
    customer_id: int,
    result: str,
    note: Optional[str],
    occurred_at: Optional[datetime],
    opportunity_id: Optional[int],
    schedule_callback: Optional[datetime],
    callback_note: Optional[str],
    current_user: dict,
) -> dict:
    """
    S6-10: Ghi nhanh kết quả cuộc gọi trên điện thoại:
    - Tái sử dụng module Activity (S6-05).
    - Tự động gắn cơ hội OPEN gần nhất của khách hàng mà user có quyền truy cập nếu opp_id bỏ trống.
    - Nếu đặt lịch gọi lại, tự động tạo Task (S6-06).
    """
    from app.services import customer_service, opportunity_service

    cust = customer_service.get_raw_customer_by_id(customer_id)
    if not cust:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy khách hàng với ID {customer_id}")
    if not check_scope_access(current_user, cust.get("owner_id", 0), cust.get("team_id")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền ghi nhận cuộc gọi cho khách hàng này")

    # Xác định cơ hội tự động nếu chưa có
    target_opp_id = opportunity_id
    auto_linked = False
    target_opp_title = None

    if target_opp_id is None:
        # Tìm các cơ hội OPEN của khách hàng
        cust_opps = opportunity_service.get_opportunities_by_scope(current_user, DataScope.ALL, customer_id=customer_id)
        open_opps = [o for o in cust_opps if (o.get("status") or "OPEN").upper() == "OPEN" and o.get("stage") not in ("CLOSED_WON", "CLOSED_LOST")]
        # Lọc cơ hội mà user có quyền truy cập
        accessible_open_opps = [
            o for o in open_opps
            if opportunity_service.check_opportunity_access_permission(o, current_user)
        ]
        if accessible_open_opps:
            # Chọn cơ hội gần nhất (theo created_at hoặc id lớn nhất)
            accessible_open_opps.sort(key=lambda x: (str(x.get("created_at", "")), x["id"]), reverse=True)
            chosen_opp = accessible_open_opps[0]
            target_opp_id = chosen_opp["id"]
            target_opp_title = chosen_opp["title"]
            auto_linked = True
    else:
        opp = opportunity_service.get_raw_opportunity_by_id(target_opp_id)
        if not opp:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy cơ hội với ID {target_opp_id}")
        if not opportunity_service.check_opportunity_access_permission(opp, current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền truy cập cơ hội đã chọn")
        target_opp_title = opp.get("title")

    # 1. Tạo Activity
    act_data = {
        "title": f"Cuộc gọi: {cust.get('name')}",
        "type": "CALL",
        "description": note or "",
        "result": result,
        "duration_minutes": 5,
        "occurred_at": occurred_at or datetime.now(),
        "customer_id": customer_id,
        "opportunity_id": target_opp_id,
    }
    created_act = create_activity_record(act_data, current_user)

    # 2. Tạo lịch gọi lại nếu yêu cầu
    callback_task_res = None
    if schedule_callback:
        task_data = {
            "title": f"Gọi lại cho {cust.get('name')}: {callback_note or 'Theo dõi sau cuộc gọi'}",
            "description": f"Lịch gọi lại tạo tự động từ cuộc gọi nhanh lúc {datetime.now().strftime('%d/%m/%Y %H:%M')}. Kết quả trước: {result}",
            "due_date": schedule_callback,
            "priority": "HIGH",
            "assignee_id": current_user.get("id"),
            "customer_id": customer_id,
            "opportunity_id": target_opp_id,
        }
        callback_task_res = create_task_record(task_data, current_user)

    return {
        "activity": created_act,
        "opportunity_auto_linked": auto_linked,
        "opportunity_id": target_opp_id,
        "opportunity_title": target_opp_title,
        "callback_task": callback_task_res,
        "message": "Ghi nhận kết quả cuộc gọi thành công",
    }

