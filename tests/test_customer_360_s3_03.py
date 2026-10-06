import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.contact_service import reset_fake_contacts
from app.services.customer_service import reset_fake_customers
from app.services.opportunity_service import reset_fake_opportunities
from app.services.activity_service import reset_fake_activities

client = TestClient(app)


def get_auth_token(email: str = "admin@gmail.com", password: str = "123456") -> str:
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(autouse=True)
def setup_data():
    reset_fake_users()
    reset_fake_customers()
    reset_fake_contacts()
    reset_fake_opportunities()
    reset_fake_activities()
    yield
    reset_fake_users()
    reset_fake_customers()
    reset_fake_contacts()
    reset_fake_opportunities()
    reset_fake_activities()


def test_customer_360_view_full_data():
    token = get_auth_token("admin@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch Customer 1 360 view
    resp = client.get("/customers/1/360", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # Check basic profile
    customer = data["customer"]
    assert customer["id"] == 1
    assert customer["name"] == "Công ty Cổ phần Công nghệ ABC"
    assert customer["tax_code"] == "0101234567"

    # Check contacts
    assert len(data["contacts"]) >= 2
    assert any(c["name"] == "Nguyễn Văn Giám Đốc" for c in data["contacts"])

    # Check opportunities
    assert len(data["open_opportunities"]) >= 1
    assert data["open_opportunities"][0]["stage"] == "PROPOSAL"
    assert data["total_open_value"] > 0

    # Check activities timeline
    assert len(data["activities_timeline"]) >= 1
    assert any(a["type"] == "MEETING" for a in data["activities_timeline"])

    # Check attachments
    assert len(data["attachments"]) >= 2
    assert any("hop_dong" in a["filename"] for a in data["attachments"])


def test_customer_360_view_scope_forbidden():
    # User 2 belongs to Team B, customer 1 belongs to Team A
    token = get_auth_token("user2@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/customers/1/360", headers=headers)
    assert resp.status_code == 403


def test_customer_360_view_not_found():
    token = get_auth_token("admin@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/customers/99999/360", headers=headers)
    assert resp.status_code == 404
