import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.contact_service import reset_fake_contacts
from app.services.customer_service import reset_fake_customers
from app.services.auth_service import reset_fake_users

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
    yield
    reset_fake_users()
    reset_fake_customers()
    reset_fake_contacts()


def test_list_contacts_by_customer():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Get contacts for Customer 1
    resp = client.get("/contacts?customer_id=1", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert any(c["decision_role"] == "DECISION_MAKER" for c in data)
    assert any(c["decision_role"] == "INFLUENCER" for c in data)


def test_create_contact_with_decision_role():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "customer_id": 1,
        "name": "Vũ Văn Mua Hàng",
        "phone": "0933445566",
        "email": "procurement@abc-tech.vn",
        "position": "Chuyên viên mua hàng",
        "decision_role": "END_USER",
        "is_primary": False,
        "notes": "Người trực tiếp sử dụng phần mềm hàng ngày",
    }
    resp = client.post("/contacts", json=payload, headers=headers)
    assert resp.status_code == 201
    created = resp.json()
    assert created["id"] > 0
    assert created["decision_role"] == "END_USER"
    assert created["name"] == "Vũ Văn Mua Hàng"
    assert len(created["history"]) == 1
    assert created["history"][0]["action"] == "CREATE"


def test_toggle_primary_contact():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Currently contact 1 is primary for customer 1
    # Create or update contact 2 to become primary
    resp = client.put(
        "/contacts/2",
        json={"is_primary": True},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_primary"] is True

    # Contact 1 should now NOT be primary
    c1 = client.get("/contacts/1", headers=headers).json()
    assert c1["is_primary"] is False


def test_transfer_contact_to_another_company_preserves_history():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Transfer Contact 2 (currently at Customer 1) to Customer 2
    transfer_payload = {
        "to_customer_id": 2,
        "note": "Chuyển công tác sang đối tác XYZ",
    }
    resp = client.post(
        "/contacts/2/transfer",
        json=transfer_payload,
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["customer_id"] == 2
    assert len(data["history"]) >= 2
    transfer_hist = [h for h in data["history"] if h["action"] == "TRANSFER"]
    assert len(transfer_hist) == 1
    assert transfer_hist[0]["from_customer_id"] == 1
    assert transfer_hist[0]["to_customer_id"] == 2
    assert "Chuyển công tác" in transfer_hist[0]["note"]


def test_transfer_contact_invalid_customer_returns_400():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/contacts/2/transfer",
        json={"to_customer_id": 99999, "note": "Không tồn tại"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "không tồn tại" in resp.json()["detail"].lower()
