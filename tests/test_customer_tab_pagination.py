import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users_db
from app.services.customer_service import reset_fake_customers
from app.services.data_handover_service import reset_handover_data_store
from app.services.ticket_service import reset_fake_tickets

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_data():
    reset_fake_users_db()
    reset_fake_customers()
    reset_handover_data_store()
    reset_fake_tickets()
    yield
    reset_fake_users_db()
    reset_fake_customers()
    reset_handover_data_store()
    reset_fake_tickets()


def auth_headers():
    response = client.post("/auth/login", json={"email": "admin@gmail.com", "password": "123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.parametrize(
    "path",
    [
        "/contacts?page=1&limit=5",
        "/tickets?page=1&limit=5",
        "/customers/periodic-care?days=30&page=1&limit=5",
        "/customers/duplicate-groups?page=1&limit=5",
    ],
)
def test_customer_tabs_return_paginated_metadata(path):
    response = client.get(path, headers=auth_headers())

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["items"], list)
    assert payload["total"] >= len(payload["items"])
    assert payload["page"] == 1
    assert payload["limit"] == 5
    assert payload["total_pages"] >= 1


@pytest.mark.parametrize(
    "path",
    ["/contacts", "/tickets", "/customers/periodic-care?days=30"],
)
def test_customer_tab_lists_keep_legacy_array_response(path):
    response = client.get(path, headers=auth_headers())

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_contacts_page_returns_correct_slice_and_total(monkeypatch):
    from app.routers import contacts as contacts_router
    from app.services import contact_service

    monkeypatch.setattr(
        contact_service,
        "list_contacts",
        lambda customer_id=None, db=None: [
            {
                "id": item_id,
                "customer_id": 1,
                "name": f"Contact {item_id}",
                "phone": None,
                "email": None,
                "position": None,
                "decision_role": "INFLUENCER",
                "is_primary": False,
                "notes": None,
                "history": [],
                "created_at": "2026-01-01T00:00:00",
                "updated_at": None,
            }
            for item_id in range(1, 6)
        ],
    )
    monkeypatch.setattr(
        contacts_router,
        "get_raw_customer_by_id",
        lambda customer_id: {"owner_id": 1, "team_id": 1},
    )

    response = client.get("/contacts?page=2&limit=2", headers=auth_headers())
    payload = response.json()

    assert response.status_code == 200
    assert payload["total"] == 5
    assert [item["id"] for item in payload["items"]] == [3, 4]
    assert payload["total_pages"] == 3


def test_tickets_page_returns_correct_slice_and_total(monkeypatch):
    from app.services import ticket_service

    monkeypatch.setattr(
        ticket_service,
        "list_tickets",
        lambda customer_id=None, status=None: [
            {
                "id": item_id,
                "customer_id": 1,
                "customer_name": "Customer",
                "title": f"Ticket {item_id}",
                "description": None,
                "priority": "HIGH",
                "status": "OPEN",
                "assigned_to": "Support",
                "resolution_note": None,
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": None,
            }
            for item_id in range(1, 6)
        ],
    )

    response = client.get("/tickets?page=2&limit=2", headers=auth_headers())
    payload = response.json()

    assert response.status_code == 200
    assert payload["total"] == 5
    assert [item["id"] for item in payload["items"]] == [3, 4]
    assert payload["total_pages"] == 3


def test_periodic_care_page_returns_correct_slice_and_total(monkeypatch):
    from app.routers import customers as customers_router

    monkeypatch.setattr(
        customers_router,
        "get_periodic_care_customers",
        lambda days_threshold, current_user: [
            {
                "customer_id": item_id,
                "customer_name": f"Customer {item_id}",
                "tax_code": None,
                "status": "CUSTOMER",
                "owner_id": 1,
                "owner_name": "Admin",
                "last_interaction_date": "2026-01-01T00:00:00",
                "days_since_last_interaction": 60,
                "total_contract_value": 1000 - item_id,
                "churn_risk": False,
            }
            for item_id in range(1, 6)
        ],
    )

    response = client.get("/customers/periodic-care?days=30&page=2&limit=2", headers=auth_headers())
    payload = response.json()

    assert response.status_code == 200
    assert payload["total"] == 5
    assert [item["customer_id"] for item in payload["items"]] == [3, 4]
    assert payload["total_pages"] == 3


def test_duplicate_groups_page_returns_correct_slice_and_total(monkeypatch):
    from app.routers import customers as customers_router

    customers = [
        {"id": 1, "name": "A One", "tax_code": "TAX-1", "status": "CUSTOMER", "owner_id": 1, "team_id": 1},
        {"id": 2, "name": "A Two", "tax_code": "TAX-1", "status": "CUSTOMER", "owner_id": 1, "team_id": 1},
        {"id": 3, "name": "B One", "tax_code": "TAX-2", "status": "CUSTOMER", "owner_id": 1, "team_id": 1},
        {"id": 4, "name": "B Two", "tax_code": "TAX-2", "status": "CUSTOMER", "owner_id": 1, "team_id": 1},
        {"id": 5, "name": "C One", "website": "https://c.example", "status": "CUSTOMER", "owner_id": 1, "team_id": 1},
        {"id": 6, "name": "C Two", "website": "https://c.example", "status": "CUSTOMER", "owner_id": 1, "team_id": 1},
    ]
    monkeypatch.setattr(customers_router, "get_customers_by_scope", lambda current_user, scope: (len(customers), customers))

    response = client.get("/customers/duplicate-groups?page=2&limit=1", headers=auth_headers())
    payload = response.json()

    assert response.status_code == 200
    assert payload["total"] == 3
    assert len(payload["items"]) == 1
    assert payload["page"] == 2
    assert payload["total_pages"] == 3