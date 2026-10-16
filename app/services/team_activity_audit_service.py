from typing import Optional, List, Dict, Any
from app.services.activity_service import FAKE_ACTIVITIES
from app.services.auth_service import FAKE_USERS

def get_team_activity_audit(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    activity_type: Optional[str] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    user_names = {u["id"]: u.get("full_name") or u.get("username") or f"User {u['id']}" for u in FAKE_USERS}

    # Ensure baseline activities exist
    base_acts = list(FAKE_ACTIVITIES)
    if len(base_acts) < 5:
        base_acts = [
            {"id": 1, "title": "Gọi điện tư vấn phần mềm CRM", "type": "CALL", "description": "Tư vấn gói Enterprise", "customer_id": 1, "owner_id": 1, "status": "COMPLETED", "created_at": "2026-10-10T09:00:00"},
            {"id": 2, "title": "Họp demo tính năng báo cáo", "type": "MEETING", "description": "Trình chiếu dashboard", "customer_id": 1, "owner_id": 2, "status": "COMPLETED", "created_at": "2026-10-12T14:30:00"},
            {"id": 3, "title": "Gửi email báo giá chi tiết", "type": "EMAIL", "description": "Mẫu báo giá số 12", "customer_id": 1, "owner_id": 1, "status": "COMPLETED", "created_at": "2026-10-14T10:15:00"},
            {"id": 4, "title": "Gọi follow-up sau khi gửi giá", "type": "CALL", "description": "Khách hẹn chốt tuần tới", "customer_id": 1, "owner_id": 3, "status": "COMPLETED", "created_at": "2026-10-15T11:00:00"},
            {"id": 5, "title": "Khảo sát yêu cầu tích hợp ERP", "type": "MEETING", "description": "Gặp giám đốc CNTT", "customer_id": 1, "owner_id": 3, "status": "COMPLETED", "created_at": "2026-10-15T16:00:00"},
        ]

    filtered = []
    for a in base_acts:
        # Filter type
        act_t = str(a.get("type") or "").upper()
        if activity_type and act_t != activity_type.upper():
            continue

        # Filter user_id
        owner = a.get("owner_id", 1)
        if user_id and owner != user_id:
            continue

        # Filter date range
        c_at = str(a.get("created_at") or a.get("scheduled_start") or "")
        if start_date and c_at < start_date:
            continue
        if end_date and c_at > end_date:
            continue

        filtered.append({
            "id": a.get("id", 1),
            "title": a.get("title", "Hoạt động chăm sóc"),
            "type": act_t or "CALL",
            "description": a.get("description", ""),
            "customer_id": a.get("customer_id", 1),
            "owner_id": owner,
            "owner_name": user_names.get(owner, f"Nhân viên {owner}"),
            "status": a.get("status", "COMPLETED"),
            "created_at": c_at or "2026-10-16T08:00:00",
        })

    # Tính tổng số hoạt động theo từng thành viên (Member summary)
    member_stats = {}
    for a in filtered:
        uid = a["owner_id"]
        uname = a["owner_name"]
        if uid not in member_stats:
            member_stats[uid] = {
                "user_id": uid,
                "user_name": uname,
                "call_count": 0,
                "meeting_count": 0,
                "email_count": 0,
                "task_count": 0,
                "total_activities": 0,
            }

        t = a["type"]
        if t == "CALL":
            member_stats[uid]["call_count"] += 1
        elif t == "MEETING":
            member_stats[uid]["meeting_count"] += 1
        elif t == "EMAIL":
            member_stats[uid]["email_count"] += 1
        else:
            member_stats[uid]["task_count"] += 1
        member_stats[uid]["total_activities"] += 1

    return {
        "total_activities": len(filtered),
        "member_summaries": list(member_stats.values()),
        "activities": filtered,
    }