import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.custom_field_service import reset_fake_custom_fields

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_fake_users()
    reset_fake_custom_fields()
    yield
    reset_fake_users()
    reset_fake_custom_fields()


def get_auth_headers(email: str = "admin@gmail.com", password: str = "123456") -> dict:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# 1. AC S2-08: Lấy danh sách trường tùy chỉnh theo entity (CUSTOMER hoặc OPPORTUNITY)
def test_list_custom_fields_by_entity():
    admin_headers = get_auth_headers("admin@gmail.com")
    res = client.get("/custom-fields?target_entity=CUSTOMER", headers=admin_headers)
    assert res.status_code == 200
    fields = res.json()
    assert len(fields) == 2
    assert all(f["target_entity"] == "CUSTOMER" for f in fields)
    assert any(f["field_key"] == "tax_code" for f in fields)


# 2. AC S2-08: Tạo mới trường tùy biến (Text, Number, Date, Select)
def test_create_custom_field_select_success():
    admin_headers = get_auth_headers("admin@gmail.com")
    payload = {
        "target_entity": "CUSTOMER",
        "field_key": "company_scale_category",
        "label": "Phân loại quy mô nội bộ",
        "field_type": "SELECT",
        "options": ["Khởi nghiệp", "Vừa", "Tập đoàn lớn"],
        "is_required": False,
        "sort_order": 5,
    }
    res = client.post("/custom-fields", json=payload, headers=admin_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["field_key"] == "company_scale_category"
    assert data["field_type"] == "SELECT"
    assert len(data["options"]) == 3


def test_create_custom_field_select_without_options_fails():
    admin_headers = get_auth_headers("admin@gmail.com")
    payload = {
        "target_entity": "CUSTOMER",
        "field_key": "invalid_select",
        "label": "Không có options",
        "field_type": "SELECT",
        "options": [],
    }
    res = client.post("/custom-fields", json=payload, headers=admin_headers)
    assert res.status_code == 400
    assert "bắt buộc phải có danh sách các lựa chọn" in res.json()["detail"]


def test_create_custom_field_duplicate_key_fails():
    admin_headers = get_auth_headers("admin@gmail.com")
    payload = {
        "target_entity": "CUSTOMER",
        "field_key": "tax_code",  # Trùng tax_code
        "label": "Mã số thuế trùng",
        "field_type": "TEXT",
    }
    res = client.post("/custom-fields", json=payload, headers=admin_headers)
    assert res.status_code == 400
    assert "đã tồn tại" in res.json()["detail"]


# 3. AC S2-08: Validate giá trị nhập vào các trường tùy biến
def test_validate_custom_field_values_success():
    admin_headers = get_auth_headers("admin@gmail.com")
    valid_payload = {
        "target_entity": "CUSTOMER",
        "values": {
            "tax_code": "0102030405",
            "customer_tier": "Vàng",
        },
    }
    res = client.post("/custom-fields/validate", json=valid_payload, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is True
    assert len(data["errors"]) == 0


def test_validate_custom_field_values_missing_required():
    admin_headers = get_auth_headers("admin@gmail.com")
    # Thiếu tax_code (trường bắt buộc của CUSTOMER)
    payload = {
        "target_entity": "CUSTOMER",
        "values": {
            "customer_tier": "Bạc",
        },
    }
    res = client.post("/custom-fields/validate", json=payload, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert "tax_code" in data["errors"]


def test_validate_custom_field_values_invalid_type_or_option():
    admin_headers = get_auth_headers("admin@gmail.com")
    payload = {
        "target_entity": "OPPORTUNITY",
        "values": {
            "expected_budget": "không phải số",  # Phải là kiểu NUMBER
            "tender_deadline": "31-12-2026",      # Sai định dạng ngày YYYY-MM-DD
        },
    }
    res = client.post("/custom-fields/validate", json=payload, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert "expected_budget" in data["errors"]
    assert "tender_deadline" in data["errors"]
