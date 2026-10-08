import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.win_loss_service import reset_fake_win_loss

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_fake_users()
    reset_fake_win_loss()
    yield
    reset_fake_users()
    reset_fake_win_loss()


def get_auth_headers(email: str = "admin@gmail.com", password: str = "123456") -> dict:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# 1. AC S2-10: Cấu hình lý do thắng/thua
def test_get_win_loss_reasons():
    admin_headers = get_auth_headers("admin@gmail.com")
    
    # Get Win reasons
    res_win = client.get("/win-loss/reasons?reason_type=WIN", headers=admin_headers)
    assert res_win.status_code == 200
    wins = res_win.json()
    assert len(wins) == 3
    assert all(r["reason_type"] == "WIN" for r in wins)

    # Get Loss reasons
    res_loss = client.get("/win-loss/reasons?reason_type=LOSS", headers=admin_headers)
    assert res_loss.status_code == 200
    losses = res_loss.json()
    assert len(losses) == 3
    assert any(r["requires_competitor"] is True for r in losses)


def test_create_win_reason():
    admin_headers = get_auth_headers("admin@gmail.com")
    payload = {
        "reason_type": "WIN",
        "code": "WIN_STRATEGIC_PARTNER",
        "name": "Là đối tác chiến lược hệ sinh thái",
        "requires_competitor": False,
        "is_active": True,
        "sort_order": 4,
    }
    res = client.post("/win-loss/reasons", json=payload, headers=admin_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["code"] == "WIN_STRATEGIC_PARTNER"


# 2. AC S2-10: Danh mục đối thủ cạnh tranh
def test_get_and_create_competitor():
    admin_headers = get_auth_headers("admin@gmail.com")
    
    # List competitors
    res_list = client.get("/win-loss/competitors", headers=admin_headers)
    assert res_list.status_code == 200
    assert len(res_list.json()) == 2

    # Create new competitor
    payload = {
        "code": "COMP_STARTUP_C",
        "name": "Công ty Khởi nghiệp C",
        "strengths": "Giao diện hiện đại, tiếp cận nhanh",
        "weaknesses": "Chưa có quy trình kiểm thử hoàn thiện",
        "pricing_strategy": "Freemium",
    }
    res_create = client.post("/win-loss/competitors", json=payload, headers=admin_headers)
    assert res_create.status_code == 201
    assert res_create.json()["code"] == "COMP_STARTUP_C"


# 3. AC S2-10: Ràng buộc khi Đóng cơ hội (Won/Lost)
def test_validate_close_won_success():
    user_headers = get_auth_headers("user@gmail.com")
    # ID 1 là WIN reason
    payload = {
        "status": "WON",
        "reason_id": 1,
    }
    res = client.post("/win-loss/validate-close", json=payload, headers=user_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is True


def test_validate_close_mismatched_reason_fails():
    user_headers = get_auth_headers("user@gmail.com")
    # Đóng WON nhưng chọn lý do ID 4 (LOSS reason)
    payload = {
        "status": "WON",
        "reason_id": 4,
    }
    res = client.post("/win-loss/validate-close", json=payload, headers=user_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert "không phù hợp với trạng thái đóng WON" in data["message"]


def test_validate_close_loss_requiring_competitor_without_competitor_fails():
    user_headers = get_auth_headers("user@gmail.com")
    # ID 4 là LOSS reason có requires_competitor = True
    payload = {
        "status": "LOST",
        "reason_id": 4,
        "competitor_id": None,  # Thiếu đối thủ
    }
    res = client.post("/win-loss/validate-close", json=payload, headers=user_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert "bắt buộc phải khai báo đối thủ cạnh tranh" in data["message"]


def test_validate_close_loss_with_competitor_succeeds():
    user_headers = get_auth_headers("user@gmail.com")
    # ID 4 là LOSS reason kèm đối thủ ID 1
    payload = {
        "status": "LOST",
        "reason_id": 4,
        "competitor_id": 1,
    }
    res = client.post("/win-loss/validate-close", json=payload, headers=user_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is True
    assert "hợp lệ" in data["message"]
