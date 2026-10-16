"""Opportunity task service with DB persistence and scope-based RBAC."""
import copy
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.core.database import SessionLocal
from app.core.dependencies import DataScope, check_scope_access
from app.models.opportunity_task import OpportunityTaskModel

INITIAL_TASKS: List[Dict[str, Any]] = []
FAKE_TASKS: List[Dict[str, Any]] = []


def _row_to_dict(row: OpportunityTaskModel) -> Dict[str, Any]:
    created_at_str = (
        row.created_at.isoformat()
        if isinstance(row.created_at, datetime)
        else (str(row.created_at) if row.created_at else datetime.utcnow().isoformat())
    )
    updated_at_str = (
        row.updated_at.isoformat()
        if isinstance(row.updated_at, datetime)
        else (str(row.updated_at) if row.updated_at else created_at_str)
    )
    return {
        "id": row.id,
        "opportunity_id": row.opportunity_id,
        "opportunity_title": row.opportunity_title,
        "customer_id": row.customer_id,
        "customer_name": row.customer_name,
        "title": row.title,
        "description": row.description or "",
        "assigned_to_id": row.assigned_to_id,
        "assigned_to_name": row.assigned_to_name or "Người dùng",
        "due_date": row.due_date,
        "due_time": row.due_time or "17:00",
        "status": row.status,
        "priority": row.priority,
        "reminder_type": row.reminder_type,
        "reminder_at": row.reminder_at,
        "is_completed": bool(row.is_completed),
        "completed_at": row.completed_at,
        "postponed_reason": row.postponed_reason,
        "postponed_at": row.postponed_at,
        "owner_id": row.owner_id,
        "team_id": row.team_id,
        "created_at": created_at_str,
        "updated_at": updated_at_str,
    }


def reset_fake_tasks() -> None:
    global FAKE_TASKS
    FAKE_TASKS.clear()
    db = SessionLocal()
    try:
        db.query(OpportunityTaskModel).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _sync_fake_from_db() -> None:
    global FAKE_TASKS
    db = SessionLocal()
    try:
        rows = db.query(OpportunityTaskModel).all()
        FAKE_TASKS.clear()
        for r in rows:
            FAKE_TASKS.append(_row_to_dict(r))
    except Exception:
        pass
    finally:
        db.close()


def get_tasks_by_scope(
    current_user: dict,
    scope: DataScope,
    opportunity_id: Optional[str] = None,
    assigned_to_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    # Đảm bảo RAM đồng bộ từ DB nếu có
    _sync_fake_from_db()

    results = list(FAKE_TASKS)

    # 1. Scope filter
    role = current_user.get("role", "USER")
    if role != "ADMIN" and scope != DataScope.ALL:
        if scope in (DataScope.TEAM, DataScope.MY_TEAM):
            user_team_id = current_user.get("team_id")
            if user_team_id is not None:
                results = [
                    t for t in results
                    if t.get("team_id") == user_team_id
                    or t.get("owner_id") == current_user.get("id")
                    or t.get("assigned_to_id") == current_user.get("id")
                ]
        else:
            user_id = current_user.get("id")
            results = [
                t for t in results
                if t.get("owner_id") == user_id or t.get("assigned_to_id") == user_id
            ]

    # 2. Opportunity filter
    if opportunity_id:
        results = [t for t in results if str(t.get("opportunity_id")) == str(opportunity_id)]

    # 3. Assigned to filter
    if assigned_to_id is not None:
        results = [t for t in results if t.get("assigned_to_id") == assigned_to_id]

    # 4. Status filter
    if status:
        results = [t for t in results if t.get("status") == status]

    # 5. Search query
    if search:
        s = search.lower().strip()
        results = [
            t for t in results
            if s in (t.get("title") or "").lower()
            or s in (t.get("description") or "").lower()
            or s in (t.get("opportunity_title") or "").lower()
            or s in (t.get("customer_name") or "").lower()
        ]

    # Sắp xếp theo due_date tăng dần
    results.sort(key=lambda x: (x.get("is_completed", False), x.get("due_date", "")))
    return results


def get_raw_task_by_id(task_id: str) -> Optional[Dict[str, Any]]:
    for t in FAKE_TASKS:
        if str(t.get("id")) == str(task_id):
            return t

    db = SessionLocal()
    try:
        row = db.query(OpportunityTaskModel).filter(OpportunityTaskModel.id == str(task_id)).first()
        if row:
            d = _row_to_dict(row)
            FAKE_TASKS.append(d)
            return d
    except Exception:
        pass
    finally:
        db.close()
    return None


def create_task_record(data: dict, current_user: dict) -> Dict[str, Any]:
    task_id = data.get("id") or f"task-{int(datetime.utcnow().timestamp() * 1000)}-{uuid.uuid4().hex[:6]}"
    now_iso = datetime.utcnow().isoformat()

    user_id = current_user.get("id", 1)
    team_id = current_user.get("team_id")
    assigned_name = data.get("assigned_to_name") or current_user.get("full_name") or "Người dùng"

    task_dict = {
        "id": str(task_id),
        "opportunity_id": str(data["opportunity_id"]) if data.get("opportunity_id") is not None else None,
        "opportunity_title": data.get("opportunity_title"),
        "customer_id": str(data["customer_id"]) if data.get("customer_id") is not None else None,
        "customer_name": data.get("customer_name"),
        "title": data["title"].strip(),
        "description": data.get("description", "") or "",
        "assigned_to_id": data.get("assigned_to_id"),
        "assigned_to_name": assigned_name,
        "due_date": data.get("due_date", now_iso[:10]),
        "due_time": data.get("due_time", "17:00"),
        "status": data.get("status", "TODO"),
        "priority": data.get("priority", "MEDIUM"),
        "reminder_type": data.get("reminder_type", "NONE"),
        "reminder_at": data.get("reminder_at"),
        "is_completed": bool(data.get("is_completed", False)),
        "completed_at": data.get("completed_at"),
        "postponed_reason": data.get("postponed_reason"),
        "postponed_at": data.get("postponed_at"),
        "owner_id": user_id,
        "team_id": team_id,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    db = SessionLocal()
    try:
        new_row = OpportunityTaskModel(
            id=task_dict["id"],
            opportunity_id=task_dict["opportunity_id"],
            opportunity_title=task_dict["opportunity_title"],
            customer_id=task_dict["customer_id"],
            customer_name=task_dict["customer_name"],
            title=task_dict["title"],
            description=task_dict["description"],
            assigned_to_id=task_dict["assigned_to_id"],
            assigned_to_name=task_dict["assigned_to_name"],
            due_date=task_dict["due_date"],
            due_time=task_dict["due_time"],
            status=task_dict["status"],
            priority=task_dict["priority"],
            reminder_type=task_dict["reminder_type"],
            reminder_at=task_dict["reminder_at"],
            is_completed=task_dict["is_completed"],
            completed_at=task_dict["completed_at"],
            postponed_reason=task_dict["postponed_reason"],
            postponed_at=task_dict["postponed_at"],
            owner_id=user_id,
            team_id=team_id,
        )
        db.add(new_row)
        db.commit()
        db.refresh(new_row)
        task_dict = _row_to_dict(new_row)
    except Exception:
        db.rollback()
    finally:
        db.close()

    # Lưu vào RAM
    FAKE_TASKS.append(task_dict)
    return task_dict


def update_task_record(task_id: str, data: dict, current_user: dict) -> Optional[Dict[str, Any]]:
    existing = get_raw_task_by_id(task_id)
    if not existing:
        return None

    # Update fields
    now_iso = datetime.utcnow().isoformat()
    for field in [
        "title", "description", "customer_id", "customer_name",
        "assigned_to_id", "assigned_to_name", "due_date", "due_time",
        "status", "priority", "reminder_type", "reminder_at",
        "postponed_reason", "postponed_at"
    ]:
        if field in data and data[field] is not None:
            existing[field] = data[field]

    if "is_completed" in data and data["is_completed"] is not None:
        existing["is_completed"] = bool(data["is_completed"])
        if existing["is_completed"]:
            existing["completed_at"] = existing.get("completed_at") or now_iso
            existing["status"] = "COMPLETED"
        else:
            if existing.get("status") == "COMPLETED":
                existing["status"] = "TODO"

    if data.get("status") == "COMPLETED" and not existing.get("is_completed"):
        existing["is_completed"] = True
        existing["completed_at"] = existing.get("completed_at") or now_iso

    existing["updated_at"] = now_iso

    db = SessionLocal()
    try:
        row = db.query(OpportunityTaskModel).filter(OpportunityTaskModel.id == str(task_id)).first()
        if row:
            for k, v in existing.items():
                if hasattr(row, k) and k not in ("created_at", "updated_at"):
                    setattr(row, k, v)
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    return existing


def delete_task_record(task_id: str) -> bool:
    global FAKE_TASKS
    found = False
    for i, t in enumerate(FAKE_TASKS):
        if str(t.get("id")) == str(task_id):
            FAKE_TASKS.pop(i)
            found = True
            break

    db = SessionLocal()
    try:
        row = db.query(OpportunityTaskModel).filter(OpportunityTaskModel.id == str(task_id)).first()
        if row:
            db.delete(row)
            db.commit()
            found = True
    except Exception:
        db.rollback()
    finally:
        db.close()

    return found
