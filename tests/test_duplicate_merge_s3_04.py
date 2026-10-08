import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.contact_service import reset_fake_contacts, list_contacts
from app.services.customer_service import reset_fake_customers, FAKE_CUSTOMERS
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


def test_detect_duplicate_customers_by_similar_name_or_domain():
    token = get_auth_token("admin@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    # Tạo một khách hàng mới có tên rất giống Customer 1 ("Công ty Cổ phần Công nghệ ABC")
    # và website gần giống
    resp_create = client.post(
        "/customers",
        json={
            "name": "Công nghệ ABC",
            "website": "https://abc-tech.vn/about",
            "phone": "0988888888",
            "email": "abc_dup@gmail.com",
        },
        headers=headers,
    )
    assert resp_create.status_code == 201
    new_cust = resp_create.json()
    new_id = new_cust["id"]

    # Kiểm tra phát hiện trùng
    resp = client.get(f"/customers/{new_id}/duplicates", headers=headers)
    assert resp.status_code == 200
    dups = resp.json()
    assert len(dups) >= 1
    # Customer 1 phải xuất hiện trong danh sách trùng lặp
    target_dup = next((d for d in dups if d["customer"]["id"] == 1), None)
    assert target_dup is not None
    assert target_dup["confidence_score"] > 0.5
    assert len(target_dup["match_reasons"]) >= 1


def test_merge_customers_as_manager_success():
    # Manager has role MANAGER
    token = get_auth_token("manager@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    # Merge customer 2 (secondary) into customer 1 (primary)
    merge_payload = {
        "primary_customer_id": 1,
        "secondary_customer_id": 2,
        "chosen_fields": {
            "address": "Địa chỉ sau khi gộp hai công ty",
        },
    }
    resp = client.post("/customers/merge", json=merge_payload, headers=headers)
    assert resp.status_code == 200
    merged = resp.json()
    assert merged["id"] == 1
    assert merged["address"] == "Địa chỉ sau khi gộp hai công ty"

    # Customer 2 should no longer exist
    resp_get2 = client.get("/customers/2", headers=headers)
    assert resp_get2.status_code == 404

    # Contacts from Customer 2 should now belong to Customer 1
    contacts_cust1 = list_contacts(customer_id=1)
    assert any(c["name"] == "Lê Kế Toán Trưởng" for c in contacts_cust1)


def test_merge_customers_as_user_forbidden():
    # User 1 has role USER -> Cannot merge
    token = get_auth_token("user1@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    merge_payload = {
        "primary_customer_id": 1,
        "secondary_customer_id": 2,
    }
    resp = client.post("/customers/merge", json=merge_payload, headers=headers)
    assert resp.status_code == 403


def test_normalization_and_duplicate_detection():
    from app.services.customer_service import normalize_tax_code, normalize_company_name, normalize_website_domain

    assert normalize_tax_code(" 0101-234.567 ") == "0101234567"
    assert normalize_company_name("Công ty Cổ phần Công nghệ ABC") == "công nghệ abc"
    assert normalize_website_domain("https://www.abc-tech.vn/about/us?ref=google") == "abc-tech.vn"

    token = get_auth_token("admin@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    # Tạo khách hàng có MST định dạng khác dấu gạch nối ("0101-234-567")
    resp_create = client.post(
        "/customers",
        json={
            "name": "Công ty TNHH MTV ABC Chi Nhánh",
            "tax_code": "0101-234-567",
            "website": "http://abc-tech.vn",
        },
        headers=headers,
    )
    assert resp_create.status_code == 201
    new_id = resp_create.json()["id"]

    # Tra cứu trùng lặp: phải phát hiện trùng với Customer 1 (0101234567) với confidence 1.0
    res_dup = client.get(f"/customers/{new_id}/duplicates", headers=headers)
    assert res_dup.status_code == 200
    dups = res_dup.json()
    c1_dup = next((d for d in dups if d["customer"]["id"] == 1), None)
    assert c1_dup is not None
    assert c1_dup["confidence_score"] == 1.0


def test_merge_preview_endpoint():
    token = get_auth_token("manager@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "primary_customer_id": 1,
        "secondary_customer_id": 2,
    }
    resp = client.post("/customers/merge-preview", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["primary"]["id"] == 1
    assert data["secondary"]["id"] == 2
    assert len(data["comparison_fields"]) > 0
    assert "contacts_to_transfer" in data
    assert "opportunities_to_transfer" in data
    assert "activities_to_transfer" in data
    assert "attachments_to_transfer" in data


def test_merge_scope_manager_must_access_both_customers():
    # Manager Team 1 (id=2, team_id=1)
    token = get_auth_token("manager@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    # Customer 1 (Team 1) và Customer 4 (Team 2)
    # Manager Team 1 cố tình gộp Customer 1 với Customer 4 ngoài phạm vi -> 403 Forbidden
    payload = {
        "primary_customer_id": 1,
        "secondary_customer_id": 4,
    }
    resp = client.post("/customers/merge", json=payload, headers=headers)
    assert resp.status_code == 403
    assert "phạm vi" in resp.json()["detail"].lower()

    # Tương tự cho preview
    resp_prev = client.post("/customers/merge-preview", json=payload, headers=headers)
    assert resp_prev.status_code == 403


def test_merge_history_and_relations_verification():
    from app.core.database import SessionLocal
    from app.models.customer import CustomerMergeHistory as CustomerMergeHistoryModel
    from app.services import opportunity_service, activity_service

    token = get_auth_token("admin@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    # Gộp Customer 2 vào Customer 1
    merge_payload = {
        "primary_customer_id": 1,
        "secondary_customer_id": 2,
        "chosen_fields": {"website": "https://merged-company.vn"},
    }
    res = client.post("/customers/merge", json=merge_payload, headers=headers)
    assert res.status_code == 200
    assert res.json()["website"] == "https://merged-company.vn"

    # 1. Kiểm tra lịch sử gộp được lưu vào DB
    db = SessionLocal()
    try:
        hist = (
            db.query(CustomerMergeHistoryModel)
            .filter(
                CustomerMergeHistoryModel.primary_customer_id == 1,
                CustomerMergeHistoryModel.secondary_customer_id == 2,
            )
            .first()
        )
        assert hist is not None
        assert hist.secondary_customer_id == 2
        assert "XYZ" in hist.secondary_customer_name
    finally:
        db.close()

    # 2. Kiểm tra contacts, opportunities, activities đều chuyển sang Customer 1
    contacts = list_contacts(customer_id=1)
    assert any(c["name"] == "Lê Kế Toán Trưởng" for c in contacts)

    opps = [o for o in opportunity_service.FAKE_OPPORTUNITIES if o.get("customer_id") == 1]
    assert any(o["title"] == "Hợp đồng dịch vụ Manager" for o in opps)

    acts = [a for a in activity_service.FAKE_ACTIVITIES if a.get("customer_id") == 1]
    assert any(a["title"] == "Gọi điện tư vấn Manager" for a in acts)


def test_merge_transaction_rollback_on_failure(monkeypatch):
    import app.services.customer_service as cs

    token = get_auth_token("admin@gmail.com", "123456")
    headers = {"Authorization": f"Bearer {token}"}

    # Mô phỏng lỗi xảy ra khi thực hiện gộp
    def fake_delete_fail(customer_id):
        raise RuntimeError("Database connection lost during commit")

    monkeypatch.setattr(cs, "delete_customer_record", fake_delete_fail)

    payload = {
        "primary_customer_id": 1,
        "secondary_customer_id": 2,
    }
    with pytest.raises(Exception):
        cs.merge_customers(primary_id=1, secondary_id=2)

    # Sau khi lỗi: Customer 2 vẫn tồn tại bình thường
    c2 = cs.get_customer_by_id(2)
    assert c2 is not None
    assert c2["id"] == 2

