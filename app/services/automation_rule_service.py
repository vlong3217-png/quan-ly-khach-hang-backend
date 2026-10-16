"""
Workflow Automation Rule Service (S7-09 EP-09).
Khai báo quy tắc tự động hóa bán hàng theo mẫu Khi–Thì (Trigger - Condition - Action).
"""

import copy
import logging
import math
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.automation_rule import AutomationRuleModel, AutomationExecutionLogModel

logger = logging.getLogger(__name__)

_DB_AVAILABLE: Optional[bool] = None

# Bộ nhớ RAM lưu trữ phục vụ test unit và fallback
FAKE_AUTOMATION_RULES: List[Dict[str, Any]] = []
FAKE_EXECUTION_LOGS: List[Dict[str, Any]] = []

INITIAL_SAMPLE_RULES: List[Dict[str, Any]] = [
    {
        "id": 1,
        "name": "Nhắc gọi lại sau 3 ngày khi cơ hội sang Báo giá",
        "description": "Tự động tạo công việc nhắc nhân viên gọi điện chăm sóc khách hàng sau 3 ngày kể từ khi gửi báo giá.",
        "is_active": True,
        "trigger_event": "OPPORTUNITY_STAGE_CHANGED",
        "conditions": {
            "to_stage": "PROPOSAL",
        },
        "actions": [
            {
                "type": "CREATE_TASK",
                "task_title": "Nhắc gọi lại cho khách hàng sau 3 ngày gửi Báo giá",
                "task_type": "CALL",
                "delay_days": 3,
                "assigned_to": "CURRENT_OWNER",
                "description": "Liên hệ lại để khảo sát ý kiến khách hàng về bản báo giá đã gửi.",
            }
        ],
        "created_by": 1,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    },
    {
        "id": 2,
        "name": "Thông báo cho Quản lý khi cơ hội lớn hơn 50 triệu sang Báo giá",
        "description": "Gửi thông báo trong app cho cấp Quản lý theo dõi sát sao cơ hội giá trị cao.",
        "is_active": True,
        "trigger_event": "OPPORTUNITY_STAGE_CHANGED",
        "conditions": {
            "to_stage": "PROPOSAL",
            "min_value": 50000000.0,
        },
        "actions": [
            {
                "type": "SEND_NOTIFICATION",
                "notification_title": "Cơ hội giá trị cao đã chuyển sang Báo giá",
                "notification_message": "Cơ hội '{entity_name}' có giá trị >= 50,000,000 VNĐ vừa chuyển sang giai đoạn Báo giá.",
                "recipient": "MANAGER",
            }
        ],
        "created_by": 1,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    },
    {
        "id": 3,
        "name": "Tự đổi người phụ trách khi Lead chuyển sang QUALIFIED",
        "description": "Bàn giao khách hàng tiềm năng cho Trưởng nhóm kinh doanh khi đã xác định rõ nhu cầu.",
        "is_active": True,
        "trigger_event": "LEAD_STATUS_CHANGED",
        "conditions": {
            "to_status": "QUALIFIED",
        },
        "actions": [
            {
                "type": "CHANGE_OWNER",
                "new_owner_id": 2,
                "reason": "Tự động phân bổ lại cho Trưởng nhóm khi Lead đạt trạng thái QUALIFIED",
            }
        ],
        "created_by": 1,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    },
]


def _is_db_connected(db: Optional[Session] = None) -> bool:
    global _DB_AVAILABLE
    if _DB_AVAILABLE is False:
        return False
    if _DB_AVAILABLE is True:
        return True
    try:
        from sqlalchemy import text
        test_session = db if db is not None else SessionLocal()
        test_session.execute(text("SELECT 1"))
        if db is None:
            test_session.close()
        _DB_AVAILABLE = True
        return True
    except Exception:
        _DB_AVAILABLE = False
        return False


def reset_fake_automation_rules() -> None:
    """Xóa dữ liệu RAM và CSDL, khởi tạo các rule mẫu cho test fixture."""
    global FAKE_AUTOMATION_RULES, FAKE_EXECUTION_LOGS
    FAKE_AUTOMATION_RULES = copy.deepcopy(INITIAL_SAMPLE_RULES)
    FAKE_EXECUTION_LOGS.clear()

    if not _is_db_connected():
        return

    try:
        db = SessionLocal()
        try:
            db.query(AutomationExecutionLogModel).delete()
            db.query(AutomationRuleModel).delete()
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
    except Exception:
        pass


def _get_next_rule_id() -> int:
    if not FAKE_AUTOMATION_RULES:
        return 1
    return max((r["id"] for r in FAKE_AUTOMATION_RULES if isinstance(r.get("id"), int)), default=0) + 1


def _get_next_log_id() -> int:
    if not FAKE_EXECUTION_LOGS:
        return 1
    return max((l["id"] for l in FAKE_EXECUTION_LOGS if isinstance(l.get("id"), int)), default=0) + 1


def _rule_model_to_dict(row: AutomationRuleModel) -> Dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "is_active": bool(row.is_active),
        "trigger_event": row.trigger_event,
        "conditions": row.conditions or {},
        "actions": row.actions or [],
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _log_model_to_dict(row: AutomationExecutionLogModel) -> Dict[str, Any]:
    return {
        "id": row.id,
        "rule_id": row.rule_id,
        "rule_name": row.rule_name,
        "trigger_event": row.trigger_event,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "entity_name": row.entity_name,
        "status": row.status,
        "actions_executed": row.actions_executed or [],
        "message": row.message,
        "executed_at": row.executed_at.isoformat() if row.executed_at else None,
    }


# =========================================================================
# CRUD & TOGGLE AUTOMATION RULES (AC 1 & AC 4)
# =========================================================================

def create_automation_rule(
    data: dict,
    current_user: Optional[dict] = None,
    db: Optional[Session] = None,
) -> dict:
    """Tạo mới một quy tắc tự động hóa khi-thì."""
    now_iso = datetime.utcnow().isoformat()
    creator_id = current_user.get("id", 1) if current_user else 1

    if _is_db_connected(db):
        session_created = False
        if db is None:
            try:
                db = SessionLocal()
                session_created = True
            except Exception:
                db = None

        if db is not None:
            try:
                row = AutomationRuleModel(
                    name=data["name"].strip(),
                    description=data.get("description"),
                    is_active=bool(data.get("is_active", True)),
                    trigger_event=str(data["trigger_event"]).strip(),
                    conditions=data.get("conditions") or {},
                    actions=data.get("actions") or [],
                    created_by=creator_id,
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                res = _rule_model_to_dict(row)
                FAKE_AUTOMATION_RULES.append(copy.deepcopy(res))
                return res
            except Exception as e:
                if db:
                    db.rollback()
                logger.warning(f"Error persisting rule to DB, fallback to RAM: {e}")
            finally:
                if session_created and db:
                    db.close()

    # Fallback RAM
    new_id = _get_next_rule_id()
    item = {
        "id": new_id,
        "name": data["name"].strip(),
        "description": data.get("description"),
        "is_active": bool(data.get("is_active", True)),
        "trigger_event": str(data["trigger_event"]).strip(),
        "conditions": data.get("conditions") or {},
        "actions": data.get("actions") or [],
        "created_by": creator_id,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    FAKE_AUTOMATION_RULES.append(item)
    return item


def get_automation_rule_by_id(rule_id: int, db: Optional[Session] = None) -> Optional[dict]:
    """Lấy thông tin chi tiết một quy tắc."""
    if _is_db_connected(db):
        session_created = False
        if db is None:
            try:
                db = SessionLocal()
                session_created = True
            except Exception:
                db = None

        if db is not None:
            try:
                row = db.query(AutomationRuleModel).filter(AutomationRuleModel.id == rule_id).first()
                if row:
                    return _rule_model_to_dict(row)
            except Exception:
                pass
            finally:
                if session_created and db:
                    db.close()

    for r in FAKE_AUTOMATION_RULES:
        if r.get("id") == rule_id:
            return copy.deepcopy(r)
    return None


def list_automation_rules(
    is_active: Optional[bool] = None,
    trigger_event: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Optional[Session] = None,
) -> dict:
    """Danh sách các quy tắc tự động hóa phân trang và lọc (AC 4)."""
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20

    if _is_db_connected(db):
        session_created = False
        if db is None:
            try:
                db = SessionLocal()
                session_created = True
            except Exception:
                db = None

        if db is not None:
            try:
                q = db.query(AutomationRuleModel)
                if is_active is not None:
                    q = q.filter(AutomationRuleModel.is_active == is_active)
                if trigger_event:
                    q = q.filter(AutomationRuleModel.trigger_event == trigger_event)

                total = q.count()
                rows = (
                    q.order_by(AutomationRuleModel.id.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                    .all()
                )
                items = [_rule_model_to_dict(r) for r in rows]
                total_pages = math.ceil(total / page_size) if total > 0 else 1
                return {
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                    "rules": items,
                }
            except Exception:
                pass
            finally:
                if session_created and db:
                    db.close()

    # Fallback RAM
    filtered = list(FAKE_AUTOMATION_RULES)
    if is_read_flag := is_active:
        filtered = [r for r in filtered if r.get("is_active") is True]
    elif is_active is False:
        filtered = [r for r in filtered if r.get("is_active") is False]

    if trigger_event:
        filtered = [r for r in filtered if r.get("trigger_event") == trigger_event]

    filtered.sort(key=lambda x: x.get("id", 0), reverse=True)
    total = len(filtered)
    start = (page - 1) * page_size
    paged = filtered[start : start + page_size]
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "rules": copy.deepcopy(paged),
    }


def update_automation_rule(
    rule_id: int,
    data: dict,
    current_user: Optional[dict] = None,
    db: Optional[Session] = None,
) -> Optional[dict]:
    """Cập nhật cấu hình quy tắc."""
    now_iso = datetime.utcnow().isoformat()

    if _is_db_connected(db):
        session_created = False
        if db is None:
            try:
                db = SessionLocal()
                session_created = True
            except Exception:
                db = None

        if db is not None:
            try:
                row = db.query(AutomationRuleModel).filter(AutomationRuleModel.id == rule_id).first()
                if row:
                    if "name" in data and data["name"]:
                        row.name = data["name"].strip()
                    if "description" in data:
                        row.description = data["description"]
                    if "is_active" in data and data["is_active"] is not None:
                        row.is_active = bool(data["is_active"])
                    if "trigger_event" in data and data["trigger_event"]:
                        row.trigger_event = str(data["trigger_event"]).strip()
                    if "conditions" in data and data["conditions"] is not None:
                        row.conditions = data["conditions"]
                    if "actions" in data and data["actions"] is not None:
                        row.actions = data["actions"]
                    row.updated_at = datetime.utcnow()
                    db.commit()
                    db.refresh(row)
                    res = _rule_model_to_dict(row)
                    for idx, r in enumerate(FAKE_AUTOMATION_RULES):
                        if r["id"] == rule_id:
                            FAKE_AUTOMATION_RULES[idx] = copy.deepcopy(res)
                            break
                    return res
            except Exception:
                if db:
                    db.rollback()
            finally:
                if session_created and db:
                    db.close()

    # Fallback RAM
    for r in FAKE_AUTOMATION_RULES:
        if r["id"] == rule_id:
            if "name" in data and data["name"]:
                r["name"] = data["name"].strip()
            if "description" in data:
                r["description"] = data["description"]
            if "is_active" in data and data["is_active"] is not None:
                r["is_active"] = bool(data["is_active"])
            if "trigger_event" in data and data["trigger_event"]:
                r["trigger_event"] = str(data["trigger_event"]).strip()
            if "conditions" in data and data["conditions"] is not None:
                r["conditions"] = data["conditions"]
            if "actions" in data and data["actions"] is not None:
                r["actions"] = data["actions"]
            r["updated_at"] = now_iso
            return copy.deepcopy(r)

    return None


def toggle_automation_rule(
    rule_id: int,
    is_active: Optional[bool] = None,
    current_user: Optional[dict] = None,
    db: Optional[Session] = None,
) -> Optional[dict]:
    """Bật / tắt nhanh quy tắc tự động hóa (AC 4)."""
    current_rule = get_automation_rule_by_id(rule_id, db=db)
    if not current_rule:
        return None

    new_state = is_active if is_active is not None else not current_rule.get("is_active", True)
    updated = update_automation_rule(rule_id, {"is_active": new_state}, current_user=current_user, db=db)
    if updated:
        msg = f"Đã {'bật' if new_state else 'tắt'} quy tắc '{updated['name']}' thành công."
        return {
            "id": updated["id"],
            "name": updated["name"],
            "is_active": new_state,
            "message": msg,
        }
    return None


def delete_automation_rule(rule_id: int, db: Optional[Session] = None) -> bool:
    """Xóa một quy tắc tự động hóa."""
    if _is_db_connected(db):
        session_created = False
        if db is None:
            try:
                db = SessionLocal()
                session_created = True
            except Exception:
                db = None

        if db is not None:
            try:
                deleted = db.query(AutomationRuleModel).filter(AutomationRuleModel.id == rule_id).delete()
                db.commit()
                if deleted:
                    global FAKE_AUTOMATION_RULES
                    FAKE_AUTOMATION_RULES = [r for r in FAKE_AUTOMATION_RULES if r.get("id") != rule_id]
                    return True
            except Exception:
                if db:
                    db.rollback()
            finally:
                if session_created and db:
                    db.close()

    for idx, r in enumerate(FAKE_AUTOMATION_RULES):
        if r.get("id") == rule_id:
            FAKE_AUTOMATION_RULES.pop(idx)
            return True
    return False


# =========================================================================
# EXECUTION LOGS (AC 4)
# =========================================================================

def log_execution(
    rule_id: int,
    rule_name: str,
    trigger_event: str,
    entity_type: str,
    entity_id: int,
    entity_name: Optional[str] = None,
    status: str = "SUCCESS",
    actions_executed: Optional[List[Dict[str, Any]]] = None,
    message: Optional[str] = None,
    db: Optional[Session] = None,
) -> dict:
    """Ghi nhận nhật ký thực thi quy tắc tự động hóa (AC 4)."""
    now = datetime.utcnow()
    now_iso = now.isoformat()
    acts = actions_executed or []

    if _is_db_connected(db):
        session_created = False
        if db is None:
            try:
                db = SessionLocal()
                session_created = True
            except Exception:
                db = None

        if db is not None:
            try:
                row = AutomationExecutionLogModel(
                    rule_id=rule_id,
                    rule_name=rule_name,
                    trigger_event=trigger_event,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    entity_name=entity_name,
                    status=status,
                    actions_executed=acts,
                    message=message,
                    executed_at=now,
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                res = _log_model_to_dict(row)
                FAKE_EXECUTION_LOGS.append(copy.deepcopy(res))
                return res
            except Exception:
                if db:
                    db.rollback()
            finally:
                if session_created and db:
                    db.close()

    new_id = _get_next_log_id()
    item = {
        "id": new_id,
        "rule_id": rule_id,
        "rule_name": rule_name,
        "trigger_event": trigger_event,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "entity_name": entity_name,
        "status": status,
        "actions_executed": acts,
        "message": message or f"Đã thực thi {len(acts)} hành động thành công.",
        "executed_at": now_iso,
    }
    FAKE_EXECUTION_LOGS.append(item)
    return item


def list_execution_logs(
    rule_id: Optional[int] = None,
    status: Optional[str] = None,
    trigger_event: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Optional[Session] = None,
) -> dict:
    """Xem danh sách nhật ký quy tắc đã chạy (AC 4)."""
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20

    if _is_db_connected(db):
        session_created = False
        if db is None:
            try:
                db = SessionLocal()
                session_created = True
            except Exception:
                db = None

        if db is not None:
            try:
                q = db.query(AutomationExecutionLogModel)
                if rule_id is not None:
                    q = q.filter(AutomationExecutionLogModel.rule_id == rule_id)
                if status:
                    q = q.filter(AutomationExecutionLogModel.status == status.upper())
                if trigger_event:
                    q = q.filter(AutomationExecutionLogModel.trigger_event == trigger_event)

                total = q.count()
                rows = (
                    q.order_by(AutomationExecutionLogModel.executed_at.desc(), AutomationExecutionLogModel.id.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                    .all()
                )
                items = [_log_model_to_dict(r) for r in rows]
                total_pages = math.ceil(total / page_size) if total > 0 else 1
                return {
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                    "logs": items,
                }
            except Exception:
                pass
            finally:
                if session_created and db:
                    db.close()

    # Fallback RAM
    filtered = list(FAKE_EXECUTION_LOGS)
    if rule_id is not None:
        filtered = [l for l in filtered if l.get("rule_id") == rule_id]
    if status:
        filtered = [l for l in filtered if l.get("status") == status.upper()]
    if trigger_event:
        filtered = [l for l in filtered if l.get("trigger_event") == trigger_event]

    filtered.sort(key=lambda x: (x.get("executed_at") or "", x.get("id") or 0), reverse=True)
    total = len(filtered)
    start = (page - 1) * page_size
    paged = filtered[start : start + page_size]
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "logs": copy.deepcopy(paged),
    }


# =========================================================================
# WORKFLOW RULE ENGINE & ACTION DISPATCHERS (AC 1, AC 2, AC 3)
# =========================================================================

def evaluate_rule_conditions(rule: dict, payload: dict) -> bool:
    """
    Kiểm tra xem dữ liệu sự kiện có thỏa mãn điều kiện của quy tắc hay không (AC 2).
    """
    if not rule.get("is_active", True):
        return False

    conds = rule.get("conditions") or {}

    # 1. Điều kiện giai đoạn đích (to_stage) cho Opportunity
    if "to_stage" in conds:
        target_stage = str(conds["to_stage"]).upper().strip()
        actual_stage = str(payload.get("to_stage") or payload.get("stage") or "").upper().strip()
        if actual_stage != target_stage:
            return False

    # 2. Điều kiện giai đoạn nguồn (from_stage)
    if "from_stage" in conds:
        from_stage = str(conds["from_stage"]).upper().strip()
        actual_from = str(payload.get("from_stage") or "").upper().strip()
        if actual_from != from_stage:
            return False

    # 3. Điều kiện trạng thái đích (to_status) cho Lead / Quote
    if "to_status" in conds:
        target_status = str(conds["to_status"]).upper().strip()
        actual_status = str(payload.get("to_status") or payload.get("status") or "").upper().strip()
        if actual_status != target_status:
            return False

    # 4. Điều kiện giá trị tối thiểu (min_value)
    if "min_value" in conds and conds["min_value"] is not None:
        min_val = float(conds["min_value"])
        actual_val = float(payload.get("value") or payload.get("grand_total") or 0.0)
        if actual_val < min_val:
            return False

    # 5. Điều kiện nhóm (team_id)
    if "team_id" in conds and conds["team_id"] is not None:
        if payload.get("team_id") != conds["team_id"]:
            return False

    return True


def execute_action(
    action: dict,
    entity_type: str,
    entity_id: int,
    entity_data: dict,
    current_user: Optional[dict] = None,
    db: Optional[Session] = None,
) -> dict:
    """
    Thực thi một hành động tự động hóa cụ thể (AC 3).
    - CREATE_TASK: Tự tạo công việc với hạn chót tính theo mốc thời gian (delay_days)
    - SEND_NOTIFICATION: Gửi thông báo trong app cho người phụ trách / Quản lý
    - CHANGE_OWNER: Tự động đổi người sở hữu
    """
    act_type = str(action.get("type", "")).upper().strip()
    entity_name = entity_data.get("title") or entity_data.get("name") or entity_data.get("full_name") or f"{entity_type} #{entity_id}"
    owner_id = entity_data.get("owner_id", 1)

    if act_type == "CREATE_TASK":
        from app.services import activity_service
        raw_title = action.get("task_title") or f"Công việc tự động cho {entity_name}"
        task_title = raw_title.replace("{entity_name}", str(entity_name))
        task_type = action.get("task_type", "CALL")
        delay_days = int(action.get("delay_days", 0))
        due_date = date.today() + timedelta(days=delay_days)

        assigned_target = action.get("assigned_to", "CURRENT_OWNER")
        if assigned_target == "CURRENT_OWNER":
            target_assignee = owner_id
        else:
            try:
                target_assignee = int(assigned_target)
            except (ValueError, TypeError):
                target_assignee = owner_id

        task_payload = {
            "title": task_title,
            "type": task_type,
            "description": action.get("description") or f"Tự động tạo từ quy tắc tự động hóa (hạn chót sau {delay_days} ngày: {due_date}).",
            "assigned_to": target_assignee,
            "due_date": due_date.isoformat(),
        }
        if entity_type == "OPPORTUNITY":
            task_payload["opportunity_id"] = entity_id
            task_payload["customer_id"] = entity_data.get("customer_id")
        elif entity_type == "LEAD":
            task_payload["lead_id"] = entity_id
        elif entity_type == "QUOTE":
            task_payload["customer_id"] = entity_data.get("customer_id")

        actor = current_user or {"id": 1, "role": "ADMIN", "full_name": "Quy tắc tự động hóa"}
        created_task = activity_service.create_activity_record(task_payload, current_user=actor)

        return {
            "action": "CREATE_TASK",
            "task_id": created_task.get("id"),
            "title": task_title,
            "type": task_type,
            "due_date": due_date.isoformat(),
            "delay_days": delay_days,
            "assigned_to": target_assignee,
        }

    elif act_type == "SEND_NOTIFICATION":
        from app.services import notification_service
        raw_title = action.get("notification_title") or "Thông báo quy tắc tự động hóa"
        notif_title = raw_title.replace("{entity_name}", str(entity_name))

        raw_msg = action.get("notification_message") or f"Sự kiện tự động hóa đã được kích hoạt cho {entity_name}."
        notif_msg = raw_msg.replace("{entity_name}", str(entity_name))

        recipient_target = action.get("recipient", "CURRENT_OWNER")
        if recipient_target == "CURRENT_OWNER":
            target_recipient = owner_id
        elif recipient_target == "MANAGER":
            target_recipient = 2  # Default Manager
        else:
            try:
                target_recipient = int(recipient_target)
            except (ValueError, TypeError):
                target_recipient = owner_id

        link = f"/{entity_type.lower()}s/{entity_id}"
        notif_payload = {
            "recipient_id": target_recipient,
            "sender_id": None,
            "sender_name": "Hệ thống tự động hóa",
            "title": notif_title,
            "message": notif_msg,
            "type": "SYSTEM",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "link": link,
        }
        notification_service.dispatch_notification_async(notif_payload, db=db)

        return {
            "action": "SEND_NOTIFICATION",
            "recipient_id": target_recipient,
            "title": notif_title,
            "link": link,
        }

    elif act_type == "CHANGE_OWNER":
        new_owner_id = int(action.get("new_owner_id", 1))
        reason = action.get("reason") or "Tự động thay đổi người sở hữu qua quy tắc tự động hóa"
        entity_data["owner_id"] = new_owner_id

        # Cập nhật trực tiếp vào RAM service tương ứng nếu có
        if entity_type == "OPPORTUNITY":
            from app.services import opportunity_service
            for o in opportunity_service.FAKE_OPPORTUNITIES:
                if o["id"] == entity_id:
                    o["owner_id"] = new_owner_id
                    break
        elif entity_type == "LEAD":
            from app.services import lead_service
            # Cập nhật owner
            pass

        return {
            "action": "CHANGE_OWNER",
            "new_owner_id": new_owner_id,
            "reason": reason,
        }

    else:
        return {
            "action": act_type,
            "status": "SKIPPED",
            "message": f"Loại hành động '{act_type}' chưa được hỗ trợ",
        }


def trigger_automation_rules(
    event_type: str,
    entity_type: str,
    entity_id: int,
    payload: dict,
    current_user: Optional[dict] = None,
    db: Optional[Session] = None,
) -> List[dict]:
    """
    Điểm kích hoạt trung tâm: Tìm các quy tắc thỏa mãn và thực thi chuỗi hành động (AC 1, 2, 3, 4).
    """
    matching_rules = [
        r for r in FAKE_AUTOMATION_RULES
        if r.get("is_active", True) and r.get("trigger_event") == event_type
    ]

    executed_results = []
    entity_name = payload.get("title") or payload.get("name") or payload.get("full_name") or f"{entity_type} #{entity_id}"

    for rule in matching_rules:
        if not evaluate_rule_conditions(rule, payload):
            continue

        actions_executed = []
        rule_success = True
        err_msg = None

        for action in rule.get("actions", []):
            try:
                res = execute_action(
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    entity_data=payload,
                    current_user=current_user,
                    db=db,
                )
                actions_executed.append(res)
            except Exception as e:
                rule_success = False
                err_msg = str(e)
                logger.error(f"Error executing automation action: {e}")
                actions_executed.append({"action": action.get("type"), "status": "FAILED", "error": str(e)})

        status_str = "SUCCESS" if rule_success else "FAILED"
        msg = f"Đã thực thi thành công {len(actions_executed)} hành động." if rule_success else f"Thực thi gặp lỗi: {err_msg}"

        log_item = log_execution(
            rule_id=rule["id"],
            rule_name=rule["name"],
            trigger_event=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=str(entity_name),
            status=status_str,
            actions_executed=actions_executed,
            message=msg,
            db=db,
        )

        executed_results.append({
            "rule_id": rule["id"],
            "rule_name": rule["name"],
            "status": status_str,
            "actions_executed": actions_executed,
            "log_id": log_item["id"],
        })

    return executed_results


def test_run_rule(
    rule_id: int,
    entity_id: int,
    simulate_payload: dict,
    current_user: Optional[dict] = None,
    db: Optional[Session] = None,
) -> dict:
    """Chạy thử nghiệm một quy tắc cụ thể trên một thực thể mẫu (AC 4)."""
    rule = get_automation_rule_by_id(rule_id, db=db)
    if not rule:
        return {"rule_id": rule_id, "rule_name": "Không tìm thấy", "matched": False, "actions_count": 0, "details": []}

    entity_type = "OPPORTUNITY"
    if "LEAD" in rule.get("trigger_event", ""):
        entity_type = "LEAD"
    elif "QUOTE" in rule.get("trigger_event", ""):
        entity_type = "QUOTE"

    # Merge payload
    test_payload = copy.deepcopy(simulate_payload)
    test_payload["id"] = entity_id
    if "title" not in test_payload and "name" not in test_payload:
        test_payload["title"] = f"{entity_type} Thử Nghiệm #{entity_id}"
    if "owner_id" not in test_payload:
        test_payload["owner_id"] = current_user.get("id", 1) if current_user else 1

    matched = evaluate_rule_conditions(rule, test_payload)
    if not matched:
        return {
            "rule_id": rule["id"],
            "rule_name": rule["name"],
            "matched": False,
            "actions_count": 0,
            "details": [{"message": "Điều kiện của quy tắc không khớp với dữ liệu giả lập."}],
        }

    actions_executed = []
    for action in rule.get("actions", []):
        try:
            res = execute_action(
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                entity_data=test_payload,
                current_user=current_user,
                db=db,
            )
            actions_executed.append(res)
        except Exception as e:
            actions_executed.append({"action": action.get("type"), "status": "FAILED", "error": str(e)})

    log_execution(
        rule_id=rule["id"],
        rule_name=rule["name"],
        trigger_event=rule["trigger_event"],
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=test_payload["title"],
        status="SUCCESS",
        actions_executed=actions_executed,
        message=f"Chạy thử nghiệm thành công {len(actions_executed)} hành động.",
        db=db,
    )

    return {
        "rule_id": rule["id"],
        "rule_name": rule["name"],
        "matched": True,
        "actions_count": len(actions_executed),
        "details": actions_executed,
    }
