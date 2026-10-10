"""
Activity service with data scope filtering (MY/MY_TEAM/TEAM/ALL).
"""

import copy
from typing import Optional
from app.core.dependencies import DataScope

INITIAL_ACTIVITIES = [
    {
        "id": 1,
        "title": "Tư vấn giải pháp Admin",
        "type": "MEETING",
        "description": "Họp trao đổi yêu cầu với Admin",
        "customer_id": 1,
        "owner_id": 1,
        "team_id": 1,
    },
    {
        "id": 2,
        "title": "Gọi điện tư vấn Manager",
        "type": "CALL",
        "description": "Gọi điện giới thiệu tính năng",
        "customer_id": 2,
        "owner_id": 2,
        "team_id": 1,
    },
    {
        "id": 3,
        "title": "Gửi email báo giá User1",
        "type": "EMAIL",
        "description": "Gửi email kèm file báo giá",
        "customer_id": 3,
        "owner_id": 3,
        "team_id": 1,
    },
    {
        "id": 4,
        "title": "Ghi chú hợp đồng User2",
        "type": "NOTE",
        "description": "Ghi chú theo dõi hợp đồng",
        "customer_id": 4,
        "owner_id": 4,
        "team_id": 2,
    },
]

FAKE_ACTIVITIES = copy.deepcopy(INITIAL_ACTIVITIES)


def reset_fake_activities() -> None:
    global FAKE_ACTIVITIES
    FAKE_ACTIVITIES = copy.deepcopy(INITIAL_ACTIVITIES)


def get_raw_activity_by_id(activity_id: int) -> Optional[dict]:
    for act in FAKE_ACTIVITIES:
        if act["id"] == activity_id:
            return act
    return None


def get_activities_by_scope(
    current_user: dict,
    scope: DataScope,
    search: Optional[str] = None,
) -> list[dict]:
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

    if search:
        s = search.lower().strip()
        results = [
            a for a in results
            if s in a.get("title", "").lower()
            or s in a.get("description", "").lower()
            or s in a.get("type", "").lower()
        ]

    return results


def create_activity_record(data: dict, current_user: dict) -> dict:
    new_id = (max(a["id"] for a in FAKE_ACTIVITIES) + 1) if FAKE_ACTIVITIES else 1
    new_act = {
        "id": new_id,
        "title": data["title"],
        "type": data.get("type", "CALL"),
        "description": data.get("description", ""),
        "customer_id": data.get("customer_id"),
        "lead_id": data.get("lead_id"),
        "opportunity_id": data.get("opportunity_id"),
        "owner_id": current_user["id"],
        "team_id": data.get("team_id") if data.get("team_id") is not None else current_user.get("team_id"),
    }
    FAKE_ACTIVITIES.append(new_act)
    return new_act


def update_activity_record(activity_id: int, data: dict) -> Optional[dict]:
    act = get_raw_activity_by_id(activity_id)
    if act is None:
        return None
    for key, value in data.items():
        if value is not None and key not in ("id", "owner_id"):
            act[key] = value
    return act


def delete_activity_record(activity_id: int) -> bool:
    global FAKE_ACTIVITIES
    initial_len = len(FAKE_ACTIVITIES)
    FAKE_ACTIVITIES = [a for a in FAKE_ACTIVITIES if a["id"] != activity_id]
    return len(FAKE_ACTIVITIES) < initial_len
