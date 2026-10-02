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
        "name": "Nguy???n V??n A",
        "email": "nguyenvana@example.com",
        "phone": "0901234567",
        "company": "C??ng ty ABC",
        "owner_id": 1,   # Owned by Admin (User 1)
        "team_id": 1,     # Team A
    },
    {
        "id": 2,
        "name": "Tr???n Th??? B",
        "email": "tranthib@example.com",
        "phone": "0912345678",
        "company": "C??ng ty XYZ",
        "owner_id": 2,   # Owned by Manager (User 2, Team A)
        "team_id": 1,     # Team A
    },
    {
        "id": 3,
        "name": "L?? V??n C",
        "email": "levanc@example.com",
        "phone": "0923456789",
        "company": "C??ng ty DEF",
        "owner_id": 3,   # Owned by User 1 (User 3, Team A)
        "team_id": 1,     # Team A
    },
    {
        "id": 4,
        "name": "Ph???m Th??? D",
        "email": "phamthid@example.com",
        "phone": "0934567890",
        "company": "C??ng ty GHI",
        "owner_id": 4,   # Owned by User 2 (User 4, Team B)
        "team_id": 2,     # Team B
    },
    {
        "id": 5,
        "name": "Ho??ng V??n E",
        "email": "hoangvane@example.com",
        "phone": "0945678901",
        "company": "C??ng ty JKL",
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
) -> list[dict]:
    """
    Return customers filtered by the user's data scope.

    - MY: only customers where owner_id == current user's id
    - TEAM: only customers where team_id == current user's team_id
    - ALL: all customers (no filter)
    """
    if scope == DataScope.ALL:
        return list(FAKE_CUSTOMERS)

    if scope == DataScope.TEAM:
        user_team_id = current_user.get("team_id")
        if user_team_id is None:
            # User has no team (e.g. ADMIN) ??? return all
            return list(FAKE_CUSTOMERS)
        return [c for c in FAKE_CUSTOMERS if c.get("team_id") == user_team_id]

    # scope == DataScope.MY
    user_id = current_user["id"]
    return [c for c in FAKE_CUSTOMERS if c.get("owner_id") == user_id]


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
