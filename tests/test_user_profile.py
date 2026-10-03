import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.auth_service import reset_fake_users

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_fake_users()
    yield
    reset_fake_users()


def get_auth_headers(email: str = "user1@gmail.com", password: str = "123456") -> dict:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_get_my_profile_success():
    """AC S2-02: Xem hồ sơ cá nhân của chính mình."""
    headers = get_auth_headers("user1@gmail.com")
    res = client.get("/users/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["email"] in ["user@gmail.com", "user1@gmail.com"]
    assert "phone" in data
    assert "email_signature" in data
    assert "full_name" in data


def test_update_my_profile_valid_fields_success():
    """
    AC S2-02: Sửa được họ tên, số điện thoại, chữ ký email.
    """
    headers = get_auth_headers("user1@gmail.com")
    payload = {
        "full_name": "Nguyễn Văn Người Dùng Cập Nhật",
        "phone": "0988123456",
        "email_signature": "Trân trọng,\nChữ ký mới gửi báo giá",
    }
    res = client.put("/users/me", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["full_name"] == "Nguyễn Văn Người Dùng Cập Nhật"
    assert data["phone"] == "0988123456"
    assert data["email_signature"] == "Trân trọng,\nChữ ký mới gửi báo giá"

    # Kiểm tra lại qua GET /users/me
    get_res = client.get("/users/me", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["phone"] == "0988123456"


def test_update_my_profile_invalid_vietnamese_phone():
    """
    AC S2-02: Kiểm tra định dạng số điện thoại Việt Nam.
    """
    headers = get_auth_headers("user1@gmail.com")

    # Quá ngắn hoặc đầu số không đúng
    invalid_phones = ["12345", "0123456789", "09888", "abcd123456", "0241234567"]
    for p in invalid_phones:
        res = client.put("/users/me", json={"phone": p}, headers=headers)
        assert res.status_code == 400
        assert "Số điện thoại không đúng định dạng" in res.json()["detail"]


def test_update_my_profile_prevent_self_change_email():
    """
    AC S2-02: Không tự đổi được email.
    """
    headers = get_auth_headers("user1@gmail.com")
    res = client.put("/users/me", json={"email": "hacked_email@gmail.com"}, headers=headers)
    assert res.status_code == 400
    assert "không được phép tự thay đổi địa chỉ email" in res.json()["detail"]


def test_update_my_profile_prevent_self_change_role():
    """
    AC S2-02: Không tự đổi được vai trò (role).
    """
    headers = get_auth_headers("user1@gmail.com")
    res = client.put("/users/me", json={"role": "ADMIN"}, headers=headers)
    assert res.status_code == 400
    assert "không được phép tự thay đổi vai trò" in res.json()["detail"]


def test_update_my_profile_prevent_self_change_team():
    """
    AC S2-02: Không tự đổi được nhóm (team).
    """
    headers = get_auth_headers("user1@gmail.com")
    res = client.put("/users/me", json={"team_id": 99}, headers=headers)
    assert res.status_code == 400
    assert "không được phép tự thay đổi nhóm" in res.json()["detail"]
