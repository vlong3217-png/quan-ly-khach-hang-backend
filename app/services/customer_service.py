"""
Customer service with data scope filtering (MY/TEAM/ALL).

Provides demo customer data, scope-aware query functions, and CRUD operations.
"""

import copy
from typing import Optional
from app.core.dependencies import DataScope

# Initial customer data for testing scope filtering
INITIAL_CUSTOMERS = [
    {
        "id": 1,
        "name": "Nguyễn Văn A",
        "email": "nguyenvana@example.com",
        "phone": "0901234567",
        "company": "Công ty ABC",
        "owner_id": 1,   # Owned by Admin (User 1)
        "team_id": 1,     # Team A
    },
    {
        "id": 2,
        "name": "Trần Thị B",
        "email": "tranthib@example.com",
        "phone": "0912345678",
        "company": "Công ty XYZ",
        "owner_id": 2,   # Owned by Manager (User 2, Team A)
        "team_id": 1,     # Team A
    },
    {
        "id": 3,
        "name": "Lê Văn C",
        "email": "levanc@example.com",
        "phone": "0923456789",
        "company": "Công ty DEF",
        "owner_id": 3,   # Owned by User 1 (User 3, Team A)
        "team_id": 1,     # Team A
    },
    {
        "id": 4,
        "name": "Phạm Thị D",
        "email": "phamthid@example.com",
        "phone": "0934567890",
        "company": "Công ty GHI",
        "owner_id": 4,   # Owned by User 2 (User 4, Team B)
        "team_id": 2,     # Team B
    },
    {
        "id": 5,
        "name": "Hoàng Văn E",
        "email": "hoangvane@example.com",
        "phone": "0945678901",
        "company": "Công ty JKL",
        "owner_id": 4,   # Owned by User 2 (User 4, Team B)
        "team_id": 2,     # Team B
    },
]

FAKE_CUSTOMERS = copy.deepcopy(INITIAL_CUSTOMERS)


def reset_fake_customers() -> None:
    """Reset customer data back to initial state (useful for tests)."""
    global FAKE_CUSTOMERS
    FAKE_CUSTOMERS = copy.deepcopy(INITIAL_CUSTOMERS)


def get_raw_customer_by_id(customer_id: int) -> Optional[dict]:
    """Find a customer by ID without scope filter (returns raw dict or None)."""
    for c in FAKE_CUSTOMERS:
        if c["id"] == customer_id:
            return c
    return None


def get_customers_by_scope(
    current_user: dict,
    scope: DataScope,
    search: Optional[str] = None,
    skip: Optional[int] = None,
    limit: Optional[int] = None,
) -> tuple[int, list[dict]]:
    """
    Return total count and customers filtered by the user's data scope, optional search term, and pagination.

    - MY: only customers where owner_id == current user's id
    - TEAM / MY_TEAM: only customers where team_id == current user's team_id
    - ALL: all customers (no filter)
    """
    if scope == DataScope.ALL:
        results = list(FAKE_CUSTOMERS)
    elif scope in (DataScope.TEAM, DataScope.MY_TEAM):
        user_team_id = current_user.get("team_id")
        if user_team_id is None:
            results = list(FAKE_CUSTOMERS)
        else:
            results = [c for c in FAKE_CUSTOMERS if c.get("team_id") == user_team_id]
    else:
        user_id = current_user["id"]
        results = [c for c in FAKE_CUSTOMERS if c.get("owner_id") == user_id]

    if search:
        s = search.lower().strip()
        results = [
            c for c in results
            if s in c.get("name", "").lower()
            or s in c.get("email", "").lower()
            or s in c.get("company", "").lower()
            or s in c.get("phone", "").lower()
        ]

    total = len(results)

    # Áp dụng phân trang nếu có skip / limit
    if skip is not None and limit is not None:
        paged_results = results[skip : skip + limit]
    elif limit is not None:
        paged_results = results[:limit]
    elif skip is not None:
        paged_results = results[skip:]
    else:
        paged_results = results

    return total, paged_results



def get_customer_by_id_and_scope(
    customer_id: int,
    current_user: dict,
    scope: DataScope,
) -> Optional[dict]:
    """
    Get a single customer by ID, filtered by scope.
    Returns None if the customer doesn't exist or is outside the user's scope.
    """
    customers = get_customers_by_scope(current_user, scope)
    for c in customers:
        if c["id"] == customer_id:
            return c
    return None


def create_customer_record(data: dict, current_user: dict) -> dict:
    """Create a new customer record and add it to FAKE_CUSTOMERS."""
    new_id = (max(c["id"] for c in FAKE_CUSTOMERS) + 1) if FAKE_CUSTOMERS else 1
    new_customer = {
        "id": new_id,
        "name": data["name"],
        "email": data.get("email"),
        "phone": data.get("phone"),
        "company": data.get("company"),
        "owner_id": current_user["id"],
        "team_id": data.get("team_id") if data.get("team_id") is not None else current_user.get("team_id"),
    }
    FAKE_CUSTOMERS.append(new_customer)
    return new_customer


def update_customer_record(
    customer_id: int,
    data: dict,
) -> Optional[dict]:
    """Update fields of an existing customer."""
    customer = get_raw_customer_by_id(customer_id)
    if customer is None:
        return None

    for key, value in data.items():
        if value is not None and key not in ("id", "owner_id"):
            customer[key] = value

    return customer


def delete_customer_record(customer_id: int) -> bool:
    """Delete a customer by ID. Returns True if deleted, False if not found."""
    global FAKE_CUSTOMERS
    initial_len = len(FAKE_CUSTOMERS)
    FAKE_CUSTOMERS = [c for c in FAKE_CUSTOMERS if c["id"] != customer_id]
    return len(FAKE_CUSTOMERS) < initial_len
