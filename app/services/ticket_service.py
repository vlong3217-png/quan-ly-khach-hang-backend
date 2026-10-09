import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.schemas.ticket import ChurnRiskAlert, SupportTicketCreate, SupportTicketUpdate, TicketPriority, TicketStatus
from app.services.customer_service import FAKE_CUSTOMERS, get_customer_by_id

INITIAL_TICKETS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "customer_id": 1,
        "title": "Hệ thống gặp lỗi tích hợp API cổng thanh toán",
        "description": "API thỉnh thoảng phản hồi timeout 504 khi thanh toán giờ cao điểm",
        "priority": TicketPriority.HIGH.value,
        "status": TicketStatus.OPEN.value,
        "assigned_to": "admin",
        "resolution_note": None,
        "created_at": datetime(2026, 3, 1, 9, 0, 0, tzinfo=timezone.utc),
        "updated_at": None,
    },
    {
        "id": 2,
        "customer_id": 2,
        "title": "Yêu cầu xuất hoá đơn điều chỉnh tháng 2",
        "description": "Cần hoá đơn VAT cho hợp đồng bảo trì",
        "priority": TicketPriority.LOW.value,
        "status": TicketStatus.RESOLVED.value,
        "assigned_to": "manager",
        "resolution_note": "Đã gửi qua email kế toán ngày 02/03",
        "created_at": datetime(2026, 3, 2, 10, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 3, 2, 11, 0, 0, tzinfo=timezone.utc),
    },
]

FAKE_TICKETS: List[Dict[str, Any]] = copy.deepcopy(INITIAL_TICKETS)


def reset_fake_tickets() -> None:
    global FAKE_TICKETS
    FAKE_TICKETS = copy.deepcopy(INITIAL_TICKETS)


def _enrich_ticket(ticket: dict) -> dict:
    t = copy.deepcopy(ticket)
    c = get_customer_by_id(t["customer_id"])
    t["customer_name"] = c["name"] if c else None
    return t


def list_tickets(customer_id: Optional[int] = None, status: Optional[str] = None) -> List[dict]:
    results = FAKE_TICKETS
    if customer_id is not None:
        results = [t for t in results if t["customer_id"] == customer_id]
    if status is not None:
        results = [t for t in results if t["status"].upper() == status.upper()]
    return [_enrich_ticket(t) for t in results]


def get_ticket_by_id(ticket_id: int) -> Optional[dict]:
    for t in FAKE_TICKETS:
        if t["id"] == ticket_id:
            return _enrich_ticket(t)
    return None


def create_ticket(ticket_data: SupportTicketCreate) -> dict:
    customer = get_customer_by_id(ticket_data.customer_id)
    if not customer:
        raise ValueError(f"Khách hàng #{ticket_data.customer_id} không tồn tại")

    new_id = max([t["id"] for t in FAKE_TICKETS], default=0) + 1
    now = datetime.now(timezone.utc)
    item = {
        "id": new_id,
        "customer_id": ticket_data.customer_id,
        "title": ticket_data.title,
        "description": ticket_data.description,
        "priority": ticket_data.priority.value if hasattr(ticket_data.priority, "value") else str(ticket_data.priority),
        "status": ticket_data.status.value if hasattr(ticket_data.status, "value") else str(ticket_data.status),
        "assigned_to": ticket_data.assigned_to,
        "resolution_note": None,
        "created_at": now,
        "updated_at": None,
    }
    FAKE_TICKETS.append(item)
    return _enrich_ticket(item)


def update_ticket(ticket_id: int, update_data: SupportTicketUpdate) -> Optional[dict]:
    ticket = None
    for t in FAKE_TICKETS:
        if t["id"] == ticket_id:
            ticket = t
            break
    if not ticket:
        return None

    data_dict = update_data.model_dump(exclude_unset=True)
    for k, v in data_dict.items():
        if k in ("priority", "status") and hasattr(v, "value"):
            ticket[k] = v.value
        else:
            ticket[k] = v

    ticket["updated_at"] = datetime.now(timezone.utc)
    return _enrich_ticket(ticket)


def evaluate_churn_risk(customer_id: int) -> dict:
    """
    AC S3-08: Tự động đánh giá và gắn cờ rủi ro rời bỏ (churn risk):
    - Khách hàng có từ 2 ticket chưa giải quyết (OPEN / IN_PROGRESS).
    - Hoặc có ít nhất 1 ticket nghiêm trọng (CRITICAL / HIGH) đang mở.
    """
    customer = get_customer_by_id(customer_id)
    if not customer:
        raise ValueError(f"Khách hàng #{customer_id} không tồn tại")

    cust_tickets = [t for t in FAKE_TICKETS if t["customer_id"] == customer_id]
    unresolved = [t for t in cust_tickets if t["status"] in (TicketStatus.OPEN.value, TicketStatus.IN_PROGRESS.value)]
    critical_or_high = [t for t in unresolved if t["priority"] in (TicketPriority.CRITICAL.value, TicketPriority.HIGH.value)]

    reasons = []
    is_at_risk = False
    risk_level = "LOW"

    if len(critical_or_high) >= 1:
        is_at_risk = True
        risk_level = "HIGH"
        reasons.append(f"Có {len(critical_or_high)} sự cố nghiêm trọng (HIGH/CRITICAL) chưa được xử lý dứt điểm")

    if len(unresolved) >= 2:
        is_at_risk = True
        if risk_level != "HIGH":
            risk_level = "MEDIUM"
        reasons.append(f"Khách hàng có {len(unresolved)} yêu cầu hỗ trợ tồn đọng chưa được giải quyết")

    if not is_at_risk:
        reasons.append("Chỉ số chăm sóc ổn định, không phát hiện rủi ro rời bỏ")

    return {
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "is_at_risk": is_at_risk,
        "risk_level": risk_level,
        "reasons": reasons,
        "unresolved_tickets_count": len(unresolved),
        "critical_tickets_count": len(critical_or_high),
    }


def list_churn_risk_alerts() -> List[dict]:
    """Lấy danh sách tất cả khách hàng đang có nguy cơ rời bỏ cao."""
    alerts = []
    for c in FAKE_CUSTOMERS:
        risk_data = evaluate_churn_risk(c["id"])
        if risk_data["is_at_risk"]:
            alerts.append(risk_data)
    alerts.sort(key=lambda x: (x["risk_level"] == "HIGH", x["unresolved_tickets_count"]), reverse=True)
    return alerts
