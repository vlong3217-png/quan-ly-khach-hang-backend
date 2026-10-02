"""
Opportunity service with data scope filtering (MY/MY_TEAM/TEAM/ALL).
"""

import copy
from typing import Optional
from app.core.dependencies import DataScope

INITIAL_OPPORTUNITIES = [
    {
        "id": 1,
        "title": "Hợp đồng phần mềm Admin",
        "value": 50000000.0,
        "stage": "PROPOSAL",
        "customer_id": 1,
        "owner_id": 1,
        "team_id": 1,
    },
    {
        "id": 2,
        "title": "Hợp đồng dịch vụ Manager",
        "value": 30000000.0,
        "stage": "QUALIFICATION",
        "customer_id": 2,
        "owner_id": 2,
        "team_id": 1,
    },
    {
        "id": 3,
        "title": "Cung cấp thiết bị User1",
        "value": 15000000.0,
        "stage": "PROSPECTING",
        "customer_id": 3,
        "owner_id": 3,
        "team_id": 1,
    },
    {
        "id": 4,
        "title": "Bảo trì hệ thống User2",
        "value": 20000000.0,
        "stage": "CLOSED_WON",
        "customer_id": 4,
        "owner_id": 4,
        "team_id": 2,
    },
]

FAKE_OPPORTUNITIES = copy.deepcopy(INITIAL_OPPORTUNITIES)


def reset_fake_opportunities() -> None:
    global FAKE_OPPORTUNITIES
    FAKE_OPPORTUNITIES = copy.deepcopy(INITIAL_OPPORTUNITIES)


def get_raw_opportunity_by_id(opportunity_id: int) -> Optional[dict]:
    for opp in FAKE_OPPORTUNITIES:
        if opp["id"] == opportunity_id:
            return opp
    return None


def get_opportunities_by_scope(
    current_user: dict,
    scope: DataScope,
    search: Optional[str] = None,
) -> list[dict]:
    if scope == DataScope.ALL:
        results = list(FAKE_OPPORTUNITIES)
    elif scope in (DataScope.TEAM, DataScope.MY_TEAM):
        user_team_id = current_user.get("team_id")
        if user_team_id is None:
            results = list(FAKE_OPPORTUNITIES)
        else:
            results = [o for o in FAKE_OPPORTUNITIES if o.get("team_id") == user_team_id]
    else:
        user_id = current_user["id"]
        results = [o for o in FAKE_OPPORTUNITIES if o.get("owner_id") == user_id]

    if search:
        s = search.lower().strip()
        results = [
            o for o in results
            if s in o.get("title", "").lower() or s in o.get("stage", "").lower()
        ]

    return results


def create_opportunity_record(data: dict, current_user: dict) -> dict:
    new_id = (max(o["id"] for o in FAKE_OPPORTUNITIES) + 1) if FAKE_OPPORTUNITIES else 1
    new_opp = {
        "id": new_id,
        "title": data["title"],
        "value": data["value"],
        "stage": data.get("stage", "PROSPECTING"),
        "customer_id": data.get("customer_id"),
        "owner_id": current_user["id"],
        "team_id": data.get("team_id") if data.get("team_id") is not None else current_user.get("team_id"),
    }
    FAKE_OPPORTUNITIES.append(new_opp)
    return new_opp


def update_opportunity_record(opportunity_id: int, data: dict) -> Optional[dict]:
    opp = get_raw_opportunity_by_id(opportunity_id)
    if opp is None:
        return None
    for key, value in data.items():
        if value is not None and key not in ("id", "owner_id"):
            opp[key] = value
    return opp


def delete_opportunity_record(opportunity_id: int) -> bool:
    global FAKE_OPPORTUNITIES
    initial_len = len(FAKE_OPPORTUNITIES)
    FAKE_OPPORTUNITIES = [o for o in FAKE_OPPORTUNITIES if o["id"] != opportunity_id]
    return len(FAKE_OPPORTUNITIES) < initial_len
