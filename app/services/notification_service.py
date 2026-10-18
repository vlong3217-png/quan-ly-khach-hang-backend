"""Notification Service for In-App Notifications (S7-08 EP-09)."""
import copy
import logging
import math
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.notification import NotificationModel
from app.schemas.notification import NotificationType

logger = logging.getLogger(__name__)

# Bộ nhớ RAM lưu trữ thông báo (hỗ trợ test unit / mock khi chưa kết nối MySQL)
FAKE_NOTIFICATIONS: List[Dict[str, Any]] = []

_DB_AVAILABLE: Optional[bool] = None


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


def reset_fake_notifications() -> None:
    """Xóa dữ liệu thông báo trong RAM và CSDL cho test fixture."""
    global FAKE_NOTIFICATIONS
    FAKE_NOTIFICATIONS.clear()
    if not _is_db_connected():
        return
    try:
        db = SessionLocal()
        try:
            db.query(NotificationModel).delete()
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
    except Exception:
        pass


def _get_next_id() -> int:
    if not FAKE_NOTIFICATIONS:
        return 1
    return max((n["id"] for n in FAKE_NOTIFICATIONS if isinstance(n.get("id"), int)), default=0) + 1


def _model_to_dict(row: NotificationModel) -> Dict[str, Any]:
    return {
        "id": row.id,
        "recipient_id": row.recipient_id,
        "sender_id": row.sender_id,
        "sender_name": row.sender_name,
        "title": row.title,
        "message": row.message,
        "type": row.type,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "link": row.link,
        "is_read": bool(row.is_read),
        "read_at": row.read_at.isoformat() if row.read_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else datetime.utcnow().isoformat(),
        "updated_at": row.updated_at.isoformat() if row.updated_at else datetime.utcnow().isoformat(),
    }


def create_notification(data: dict, db: Optional[Session] = None) -> dict:
    """
    Tạo mới một thông báo (AC 1, AC 3).
    Hỗ trợ lưu vào DB nếu có kết nối, và luôn cập nhật vào RAM FAKE_NOTIFICATIONS.
    """
    now = datetime.utcnow()
    now_iso = now.isoformat()

    notif_type = data.get("type") or NotificationType.SYSTEM.value
    if hasattr(notif_type, "value"):
        notif_type = notif_type.value

    # Thử lưu vào CSDL
    session_created = False
    if _is_db_connected(db):
        if db is None:
            try:
                db = SessionLocal()
                session_created = True
            except Exception:
                db = None

        if db is not None:
            try:
                row = NotificationModel(
                    recipient_id=int(data["recipient_id"]),
                    sender_id=data.get("sender_id"),
                    sender_name=data.get("sender_name"),
                    title=str(data["title"]),
                    message=str(data["message"]),
                    type=str(notif_type),
                    entity_type=data.get("entity_type"),
                    entity_id=data.get("entity_id"),
                    link=data.get("link"),
                    is_read=False,
                    read_at=None,
                    created_at=now,
                    updated_at=now,
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                res = _model_to_dict(row)
                FAKE_NOTIFICATIONS.append(copy.deepcopy(res))
                return res
            except Exception as e:
                if db:
                    db.rollback()
                logger.warning(f"Error persisting notification to DB, falling back to RAM: {e}")
            finally:
                if session_created and db:
                    db.close()

    # Fallback RAM
    new_id = _get_next_id()
    item = {
        "id": new_id,
        "recipient_id": int(data["recipient_id"]),
        "sender_id": data.get("sender_id"),
        "sender_name": data.get("sender_name"),
        "title": str(data["title"]),
        "message": str(data["message"]),
        "type": str(notif_type),
        "entity_type": data.get("entity_type"),
        "entity_id": data.get("entity_id"),
        "link": data.get("link"),
        "is_read": False,
        "read_at": None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    FAKE_NOTIFICATIONS.append(item)
    return item


def dispatch_notification_async(
    data: dict,
    background_tasks: Optional[BackgroundTasks] = None,
    db: Optional[Session] = None,
) -> None:
    """
    Gửi thông báo bất đồng bộ (AC 4):
    - Nếu có FastAPI BackgroundTasks, đăng ký task chạy nền.
    - Nếu không, thực thi trực tiếp trong khối try/except an toàn, không bao giờ làm gián đoạn luồng chính.
    """
    try:
        if background_tasks is not None:
            background_tasks.add_task(create_notification, data, None)
        else:
            # Safe fire-and-forget
            create_notification(data, db=db)
    except Exception as exc:
        logger.error(f"Safe dispatch notification error (ignored): {exc}")


def get_user_notifications(
    user_id: int,
    is_read: Optional[bool] = None,
    notif_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Optional[Session] = None,
) -> dict:
    """
    Lấy danh sách thông báo của người dùng kèm phân trang và số chưa đọc (AC 2).
    """
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20

    # Ưu tiên truy vấn DB nếu có kết nối
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
                q = db.query(NotificationModel).filter(NotificationModel.recipient_id == user_id)
                if is_read is not None:
                    q = q.filter(NotificationModel.is_read == is_read)
                if notif_type:
                    q = q.filter(NotificationModel.type == notif_type)

                total = q.count()
                unread_count = db.query(NotificationModel).filter(
                    NotificationModel.recipient_id == user_id,
                    NotificationModel.is_read == False,
                ).count()

                rows = (
                    q.order_by(NotificationModel.created_at.desc(), NotificationModel.id.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                    .all()
                )
                items = [_model_to_dict(r) for r in rows]
                total_pages = math.ceil(total / page_size) if total > 0 else 1
                return {
                    "total": total,
                    "unread_count": unread_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                    "notifications": items,
                }
            except Exception:
                pass
            finally:
                if session_created and db:
                    db.close()

    # Fallback RAM
    user_items = [n for n in FAKE_NOTIFICATIONS if n.get("recipient_id") == user_id]
    if is_read is not None:
        user_items = [n for n in user_items if n.get("is_read") == is_read]
    if notif_type:
        user_items = [n for n in user_items if n.get("type") == notif_type]

    unread_count = sum(1 for n in FAKE_NOTIFICATIONS if n.get("recipient_id") == user_id and not n.get("is_read"))
    total = len(user_items)

    # Sắp xếp mới nhất lên đầu
    user_items.sort(key=lambda x: (x.get("created_at") or "", x.get("id") or 0), reverse=True)

    start = (page - 1) * page_size
    paged = user_items[start : start + page_size]
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return {
        "total": total,
        "unread_count": unread_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "notifications": copy.deepcopy(paged),
    }


def get_user_unread_count(user_id: int, db: Optional[Session] = None) -> int:
    """
    Đếm số lượng thông báo chưa đọc của người dùng để hiển thị trên biểu tượng chuông (AC 2).
    """
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
                return db.query(NotificationModel).filter(
                    NotificationModel.recipient_id == user_id,
                    NotificationModel.is_read == False,
                ).count()
            except Exception:
                pass
            finally:
                if session_created and db:
                    db.close()

    return sum(1 for n in FAKE_NOTIFICATIONS if n.get("recipient_id") == user_id and not n.get("is_read"))


def mark_notification_as_read(
    notification_id: int,
    user_id: int,
    db: Optional[Session] = None,
) -> Optional[dict]:
    """
    Đánh dấu 1 thông báo là đã đọc (AC 2).
    """
    now = datetime.utcnow()
    now_iso = now.isoformat()

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
                row = db.query(NotificationModel).filter(
                    NotificationModel.id == notification_id,
                    NotificationModel.recipient_id == user_id,
                ).first()
                if row:
                    row.is_read = True
                    row.read_at = now
                    row.updated_at = now
                    db.commit()
                    db.refresh(row)
                    res = _model_to_dict(row)
                    for n in FAKE_NOTIFICATIONS:
                        if n["id"] == notification_id:
                            n["is_read"] = True
                            n["read_at"] = now_iso
                    return res
            except Exception:
                if db:
                    db.rollback()
            finally:
                if session_created and db:
                    db.close()

    # Fallback RAM
    for n in FAKE_NOTIFICATIONS:
        if n.get("id") == notification_id and n.get("recipient_id") == user_id:
            n["is_read"] = True
            n["read_at"] = now_iso
            n["updated_at"] = now_iso
            return copy.deepcopy(n)

    return None


def mark_all_notifications_as_read(user_id: int, db: Optional[Session] = None) -> int:
    """
    Đánh dấu tất cả thông báo của người dùng là đã đọc (AC 2).
    """
    now = datetime.utcnow()
    now_iso = now.isoformat()
    updated_count = 0

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
                updated_count = db.query(NotificationModel).filter(
                    NotificationModel.recipient_id == user_id,
                    NotificationModel.is_read == False,
                ).update({"is_read": True, "read_at": now, "updated_at": now})
                db.commit()
                for n in FAKE_NOTIFICATIONS:
                    if n.get("recipient_id") == user_id and not n.get("is_read"):
                        n["is_read"] = True
                        n["read_at"] = now_iso
                return updated_count
            except Exception:
                if db:
                    db.rollback()
            finally:
                if session_created and db:
                    db.close()

    # Fallback RAM
    for n in FAKE_NOTIFICATIONS:
        if n.get("recipient_id") == user_id and not n.get("is_read"):
            n["is_read"] = True
            n["read_at"] = now_iso
            n["updated_at"] = now_iso
            updated_count += 1

    return updated_count


def delete_notification(
    notification_id: int,
    user_id: int,
    db: Optional[Session] = None,
) -> bool:
    """Xóa thông báo của người dùng."""
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
                deleted = db.query(NotificationModel).filter(
                    NotificationModel.id == notification_id,
                    NotificationModel.recipient_id == user_id,
                ).delete()
                db.commit()
                if deleted:
                    global FAKE_NOTIFICATIONS
                    FAKE_NOTIFICATIONS = [n for n in FAKE_NOTIFICATIONS if n.get("id") != notification_id]
                    return True
            except Exception:
                if db:
                    db.rollback()
            finally:
                if session_created and db:
                    db.close()

    for idx, n in enumerate(FAKE_NOTIFICATIONS):
        if n.get("id") == notification_id and n.get("recipient_id") == user_id:
            FAKE_NOTIFICATIONS.pop(idx)
            return True

    return False

    for idx, n in enumerate(FAKE_NOTIFICATIONS):
        if n.get("id") == notification_id and n.get("recipient_id") == user_id:
            FAKE_NOTIFICATIONS.pop(idx)
            return True

    return False


# =========================================================================
# TRIGGER HELPER METHODS (AC 1 & AC 3)
# =========================================================================

def notify_lead_assigned(
    lead_id: int,
    lead_name: str,
    assigned_to_id: int,
    assigner_user: Optional[dict] = None,
    background_tasks: Optional[BackgroundTasks] = None,
    db: Optional[Session] = None,
) -> None:
    """Sự kiện: Được phân lead (AC 1 - LEAD_ASSIGNED). Link: /leads/{id}"""
    assigner_name = assigner_user.get("full_name") if assigner_user else "Hệ thống"
    sender_id = assigner_user.get("id") if assigner_user else None

    payload = {
        "recipient_id": assigned_to_id,
        "sender_id": sender_id,
        "sender_name": assigner_name,
        "title": "Bạn được phân công một Lead mới",
        "message": f"Bạn vừa được phân công phụ trách lead '{lead_name}' (#{lead_id}).",
        "type": NotificationType.LEAD_ASSIGNED.value,
        "entity_type": "LEAD",
        "entity_id": lead_id,
        "link": f"/leads/{lead_id}",
    }
    dispatch_notification_async(payload, background_tasks=background_tasks, db=db)


def notify_quote_waiting_approval(
    quote_id: int,
    quote_number: str,
    quote_title: str,
    submitter_user: Optional[dict] = None,
    approver_user_ids: Optional[List[int]] = None,
    background_tasks: Optional[BackgroundTasks] = None,
    db: Optional[Session] = None,
) -> None:
    """Sự kiện: Có báo giá chờ mình duyệt (AC 1 - QUOTE_WAITING_APPROVAL). Link: /quotes/{id}"""
    submitter_name = submitter_user.get("full_name") if submitter_user else "Nhân viên kinh doanh"
    sender_id = submitter_user.get("id") if submitter_user else None

    # Mặc định gửi cho Quản lý / Admin (ID 1, 2) nếu chưa truyền danh sách cụ thể
    recipients = approver_user_ids if approver_user_ids else [1, 2]

    for approver_id in recipients:
        if sender_id and approver_id == sender_id:
            continue  # Không tự gửi cho chính mình
        payload = {
            "recipient_id": approver_id,
            "sender_id": sender_id,
            "sender_name": submitter_name,
            "title": "Báo giá mới cần bạn phê duyệt",
            "message": f"Báo giá '{quote_number} - {quote_title}' vừa được {submitter_name} gửi duyệt và đang chờ bạn phê duyệt.",
            "type": NotificationType.QUOTE_WAITING_APPROVAL.value,
            "entity_type": "QUOTE",
            "entity_id": quote_id,
            "link": f"/quotes/{quote_id}",
        }
        dispatch_notification_async(payload, background_tasks=background_tasks, db=db)


def notify_quote_customer_response(
    quote_id: int,
    quote_number: str,
    response_action: str,  # ACCEPTED hoặc REJECTED
    feedback: Optional[str] = None,
    recipient_id: int = 1,
    customer_name: Optional[str] = None,
    background_tasks: Optional[BackgroundTasks] = None,
    db: Optional[Session] = None,
) -> None:
    """Sự kiện: Khách phản hồi báo giá (AC 1 - QUOTE_CUSTOMER_RESPONSE). Link: /quotes/{id}"""
    is_accepted = response_action.upper() == "ACCEPTED"
    action_text = "Chấp nhận" if is_accepted else "Từ chối"
    client_name = customer_name or "Khách hàng"
    fb_text = f"Ý kiến phản hồi: '{feedback}'" if feedback else "Không có ý kiến kèm theo."

    payload = {
        "recipient_id": recipient_id,
        "sender_id": None,
        "sender_name": client_name,
        "title": f"Khách hàng đã {action_text.upper()} báo giá",
        "message": f"{client_name} vừa {action_text.lower()} báo giá {quote_number}.\n{fb_text}",
        "type": NotificationType.QUOTE_CUSTOMER_RESPONSE.value,
        "entity_type": "QUOTE",
        "entity_id": quote_id,
        "link": f"/quotes/{quote_id}",
    }
    dispatch_notification_async(payload, background_tasks=background_tasks, db=db)


def notify_task_assigned(
    activity_id: int,
    activity_title: str,
    assigned_to_id: int,
    creator_user: Optional[dict] = None,
    background_tasks: Optional[BackgroundTasks] = None,
    db: Optional[Session] = None,
) -> None:
    """Sự kiện: Được giao việc (AC 1 - TASK_ASSIGNED). Link: /tasks/{id}"""
    creator_name = creator_user.get("full_name") if creator_user else "Hệ thống"
    sender_id = creator_user.get("id") if creator_user else None

    payload = {
        "recipient_id": assigned_to_id,
        "sender_id": sender_id,
        "sender_name": creator_name,
        "title": "Bạn được giao một công việc mới",
        "message": f"Bạn vừa được giao công việc '{activity_title}' (#{activity_id}) bởi {creator_name}.",
        "type": NotificationType.TASK_ASSIGNED.value,
        "entity_type": "TASK",
        "entity_id": activity_id,
        "link": f"/tasks/{activity_id}",
    }
    dispatch_notification_async(payload, background_tasks=background_tasks, db=db)


def notify_opportunity_stagnant(
    opportunity_id: int,
    opp_title: str,
    recipient_id: int,
    days_inactive: Optional[int] = None,
    background_tasks: Optional[BackgroundTasks] = None,
    db: Optional[Session] = None,
) -> None:
    """Sự kiện: Cơ hội bị gắn cờ đình trệ (AC 1 - OPPORTUNITY_STAGNANT). Link: /opportunities/{id}"""
    inactive_text = f"{days_inactive} ngày" if days_inactive else "thời gian dài"

    payload = {
        "recipient_id": recipient_id,
        "sender_id": None,
        "sender_name": "Hệ thống cảnh báo",
        "title": "Cảnh báo cơ hội bán hàng đình trệ",
        "message": f"Cơ hội '{opp_title}' (#{opportunity_id}) đã không có hoạt động trong {inactive_text} và bị gắn cờ đình trệ.",
        "type": NotificationType.OPPORTUNITY_STAGNANT.value,
        "entity_type": "OPPORTUNITY",
        "entity_id": opportunity_id,
        "link": f"/opportunities/{opportunity_id}",
    }
    dispatch_notification_async(payload, background_tasks=background_tasks, db=db)
