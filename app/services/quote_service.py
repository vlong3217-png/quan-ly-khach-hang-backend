"""
Quote service with data scope filtering (MY/MY_TEAM/TEAM/ALL).
"""

import copy
from typing import Optional
from app.core.dependencies import DataScope

INITIAL_QUOTES = [
    {
        "id": 1,
        "title": "Báo giá phần mềm Admin",
        "amount": 55000000.0,
        "status": "SENT",
        "customer_id": 1,
        "owner_id": 1,
        "team_id": 1,
    },
    {
        "id": 2,
        "title": "Báo giá dịch vụ Manager",
        "amount": 32000000.0,
        "status": "ACCEPTED",
        "customer_id": 2,
        "owner_id": 2,
        "team_id": 1,
    },
    {
        "id": 3,
        "title": "Báo giá thiết bị User1",
        "amount": 16000000.0,
        "status": "DRAFT",
        "customer_id": 3,
        "owner_id": 3,
        "team_id": 1,
    },
    {
        "id": 4,
        "title": "Báo giá bảo trì User2",
        "amount": 22000000.0,
        "status": "REJECTED",
        "customer_id": 4,
        "owner_id": 4,
        "team_id": 2,
    },
]

FAKE_QUOTES = copy.deepcopy(INITIAL_QUOTES)


def reset_fake_quotes() -> None:
    global FAKE_QUOTES
    FAKE_QUOTES = copy.deepcopy(INITIAL_QUOTES)


def get_raw_quote_by_id(quote_id: int) -> Optional[dict]:
    for q in FAKE_QUOTES:
        if q["id"] == quote_id:
            return q
    return None


def get_quotes_by_scope(
    current_user: dict,
    scope: DataScope,
    search: Optional[str] = None,
) -> list[dict]:
    if scope == DataScope.ALL:
        results = list(FAKE_QUOTES)
    elif scope in (DataScope.TEAM, DataScope.MY_TEAM):
        user_team_id = current_user.get("team_id")
        if user_team_id is None:
            results = list(FAKE_QUOTES)
        else:
            results = [q for q in FAKE_QUOTES if q.get("team_id") == user_team_id]
    else:
        user_id = current_user["id"]
        results = [q for q in FAKE_QUOTES if q.get("owner_id") == user_id]

    if search:
        s = search.lower().strip()
        results = [
            q for q in results
            if s in q.get("title", "").lower() or s in q.get("status", "").lower()
        ]

    return results


def create_quote_record(data: dict, current_user: dict) -> dict:
    new_id = (max(q["id"] for q in FAKE_QUOTES) + 1) if FAKE_QUOTES else 1
    new_quote = {
        "id": new_id,
        "title": data["title"],
        "amount": data["amount"],
        "status": data.get("status", "DRAFT"),
        "customer_id": data.get("customer_id"),
        "owner_id": current_user["id"],
        "team_id": data.get("team_id") if data.get("team_id") is not None else current_user.get("team_id"),
    }
    FAKE_QUOTES.append(new_quote)
    return new_quote


def update_quote_record(quote_id: int, data: dict) -> Optional[dict]:
    q = get_raw_quote_by_id(quote_id)
    if q is None:
        return None
    for key, value in data.items():
        if value is not None and key not in ("id", "owner_id"):
            q[key] = value
    return q


def delete_quote_record(quote_id: int) -> bool:
    global FAKE_QUOTES
    initial_len = len(FAKE_QUOTES)
    FAKE_QUOTES = [q for q in FAKE_QUOTES if q["id"] != quote_id]
    return len(FAKE_QUOTES) < initial_len
