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


def test_contact_stored_in_mysql_database():
    from app.core.database import SessionLocal
    from app.models.contact import Contact as ContactModel, ContactCompanyHistory as ContactCompanyHistoryModel

    token = get_auth_token("admin@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "customer_id": 1,
        "name": "Bùi Văn CSDL",
        "phone": "0911223344",
        "email": "db_contact@abc.vn",
        "position": "Kiến trúc sư hệ thống",
        "decision_role": "INFLUENCER",
        "is_primary": False,
        "notes": "Kiểm tra lưu CSDL SQLAlchemy",
    }
    resp = client.post("/contacts", json=payload, headers=headers)
    assert resp.status_code == 201
    cid = resp.json()["id"]

    db = SessionLocal()
    try:
        db_contact = db.query(ContactModel).filter(ContactModel.id == cid).first()
        assert db_contact is not None
        assert db_contact.name == "Bùi Văn CSDL"
        assert db_contact.customer_id == 1

        db_hist = db.query(ContactCompanyHistoryModel).filter(ContactCompanyHistoryModel.contact_id == cid).all()
        assert len(db_hist) >= 1
        assert db_hist[0].action == "CREATE"
    finally:
        db.close()


def test_contact_data_scope_enforcement():
    # User 1 (id=3, Team 1) sở hữu Customer 3. Customer 4 thuộc Team 2.
    token_user1 = get_auth_token("user1@gmail.com")
    headers_u1 = {"Authorization": f"Bearer {token_user1}"}

    # 1. User 1 cố tình xem contacts của Customer 4 (ngoài scope) -> 403 Forbidden
    res_list = client.get("/contacts?customer_id=4", headers=headers_u1)
    assert res_list.status_code == 403

    # 2. User 1 cố tình tạo contact cho Customer 4 -> 403 Forbidden
    res_create = client.post(
        "/contacts",
        json={"customer_id": 4, "name": "Người Liên Hệ Trái Phép", "phone": "0999999999"},
        headers=headers_u1,
    )
    assert res_create.status_code == 403

    # 3. User 1 xem contacts của Customer 3 (thuộc sở hữu) -> 200 OK
    res_own = client.get("/contacts?customer_id=3", headers=headers_u1)
    assert res_own.status_code == 200


def test_maximum_one_primary_contact_enforced():
    token = get_auth_token("admin@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Tạo contact thứ nhất là primary
    resp1 = client.post(
        "/contacts",
        json={"customer_id": 2, "name": "Liên Hệ Chính Một", "is_primary": True},
        headers=headers,
    )
    assert resp1.status_code == 201
    c1_id = resp1.json()["id"]
    assert resp1.json()["is_primary"] is True

    # Tạo contact thứ hai cũng chọn là primary cho cùng khách hàng 2
    resp2 = client.post(
        "/contacts",
        json={"customer_id": 2, "name": "Liên Hệ Chính Hai", "is_primary": True},
        headers=headers,
    )
    assert resp2.status_code == 201
    c2_id = resp2.json()["id"]
    assert resp2.json()["is_primary"] is True

    # Kiểm tra lại contact 1 tự động bị gỡ is_primary = False
    c1_check = client.get(f"/contacts/{c1_id}", headers=headers).json()
    assert c1_check["is_primary"] is False


def test_transfer_contact_database_history_persistence():
    from app.core.database import SessionLocal
    from app.models.contact import ContactCompanyHistory as ContactCompanyHistoryModel

    token = get_auth_token("admin@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Chuyển contact 1 từ customer 1 sang customer 2
    resp = client.post(
        "/contacts/1/transfer",
        json={"to_customer_id": 2, "note": "Chuyển giao quản lý tài khoản sang công ty 2"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["customer_id"] == 2

    # Query DB xác nhận bản ghi transfer được lưu vào bảng contact_company_history
    db = SessionLocal()
    try:
        hist_records = (
            db.query(ContactCompanyHistoryModel)
            .filter(ContactCompanyHistoryModel.contact_id == 1, ContactCompanyHistoryModel.action == "TRANSFER")
            .all()
        )
        assert len(hist_records) >= 1
        record = hist_records[-1]
        assert record.from_customer_id == 1
        assert record.to_customer_id == 2
        assert "Chuyển giao" in record.note
    finally:
        db.close()


def test_contacts_history_retained_after_backend_restart_and_ram_clear():
    """AC S3-02: Xác nhận lịch sử luân chuyển công tác và dữ liệu liên hệ còn nguyên vẹn sau khi restart backend / xóa RAM."""
    from app.services.contact_service import FAKE_CONTACTS

    token = get_auth_token("admin@gmail.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Chuyển contact 2 sang Customer 2
    trans_res = client.post(
        "/contacts/2/transfer",
        json={"to_customer_id": 2, "note": "Luân chuyển công tác sang XYZ Solutions"},
        headers=headers,
    )
    assert trans_res.status_code == 200

    # 2. Xóa sạch RAM cache FAKE_CONTACTS giả lập backend restart
    FAKE_CONTACTS.clear()

    # 3. Truy vấn lại GET /contacts/2 từ backend
    detail_res = client.get("/contacts/2", headers=headers)
    assert detail_res.status_code == 200
    data = detail_res.json()
    assert data["customer_id"] == 2
    assert len(data["history"]) >= 2
    assert any(h["action"] == "TRANSFER" and h["to_customer_id"] == 2 for h in data["history"])

