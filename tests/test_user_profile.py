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


def test_update_my_profile_empty_or_whitespace_fullname():
    """
    AC S2-02: Từ chối họ tên rỗng hoặc chỉ chứa toàn khoảng trắng.
    """
    headers = get_auth_headers("user1@gmail.com")

    # Họ tên rỗng
    res1 = client.put("/users/me", json={"full_name": ""}, headers=headers)
    assert res1.status_code == 400
    assert "Họ và tên không được để trống" in res1.json()["detail"]

    # Họ tên toàn khoảng trắng
    res2 = client.put("/users/me", json={"full_name": "   "}, headers=headers)
    assert res2.status_code == 400
    assert "Họ và tên không được để trống" in res2.json()["detail"]

    # Họ tên tab và newline
    res3 = client.put("/users/me", json={"full_name": "\t  \n "}, headers=headers)
    assert res3.status_code == 400
    assert "Họ và tên không được để trống" in res3.json()["detail"]


def test_update_my_profile_database_persistence():
    """
    AC S2-02: Xác nhận dữ liệu được lưu trực tiếp và chính xác vào cơ sở dữ liệu.
    """
    from app.core.database import SessionLocal
    from app.models.user import User as UserModel

    headers = get_auth_headers("user1@gmail.com")
    new_name = "Nguyễn Văn Lưu Vào Database Thật"
    new_phone = "0977889900"
    new_signature = "Chữ ký lưu Database"

    res = client.put(
        "/users/me",
        json={"full_name": new_name, "phone": new_phone, "email_signature": new_signature},
        headers=headers,
    )
    assert res.status_code == 200

    # Kiểm tra trực tiếp qua SQL Database Session
    db = SessionLocal()
    user_in_db = db.query(UserModel).filter(UserModel.email == "user@gmail.com").first()
    assert user_in_db is not None
    assert user_in_db.full_name == new_name
    assert user_in_db.phone == new_phone
    assert user_in_db.email_signature == new_signature
    db.close()


def test_update_my_profile_rollback_on_database_failure(monkeypatch):
    """
    AC S2-02: Khi ghi cơ sở dữ liệu thất bại, hệ thống phải rollback, trả lỗi 500
    và đồng bộ thông tin cũ (không làm biến đổi dữ liệu người dùng).
    """
    from sqlalchemy.orm import Session

    headers = get_auth_headers("user1@gmail.com")

    # Lấy tên ban đầu
    res_orig = client.get("/users/me", headers=headers)
    assert res_orig.status_code == 200
    orig_name = res_orig.json()["full_name"]

    def mock_commit(self):
        raise RuntimeError("Simulated Database I/O Failure")

    monkeypatch.setattr(Session, "commit", mock_commit)

    res = client.put("/users/me", json={"full_name": "Tên Sẽ Bị Rollback"}, headers=headers)
    assert res.status_code == 500
    assert "Lỗi lưu thông tin hồ sơ vào cơ sở dữ liệu" in res.json()["detail"]

    # Khôi phục commit bình thường và kiểm tra dữ liệu vẫn là tên cũ
    monkeypatch.undo()
    res_after = client.get("/users/me", headers=headers)
    assert res_after.status_code == 200
    assert res_after.json()["full_name"] == orig_name


def test_update_my_profile_persists_after_backend_restart():
    """
    AC S2-02: Xác nhận dữ liệu còn nguyên vẹn sau khi restart backend
    (mô phỏng xóa sạch RAM/cache in-memory và đọc trực tiếp từ DB).
    """
    from app.services import auth_service
    from app.core.database import SessionLocal
    from app.models.user import User as UserModel

    headers = get_auth_headers("user1@gmail.com")
    updated_name = "Người Dùng Sau Khi Restart Server"
    updated_phone = "0912345678"

    # 1. Cập nhật qua API
    res = client.put(
        "/users/me",
        json={"full_name": updated_name, "phone": updated_phone},
        headers=headers,
    )
    assert res.status_code == 200

    # 2. Mô phỏng khởi động lại backend:
    # Xóa sạch bản ghi trong memory cache FAKE_USERS
    auth_service.FAKE_USERS.clear()

    # 3. Đọc trực tiếp từ Database xác nhận dữ liệu đã được lưu bền vững
    db = SessionLocal()
    db_user = db.query(UserModel).filter(UserModel.email == "user@gmail.com").first()
    assert db_user is not None
    assert db_user.full_name == updated_name
    assert db_user.phone == updated_phone
    db.close()

    # 4. Gọi lại GET /users/me (hệ thống tự lấy từ DB khi cache trống)
    res_after_restart = client.get("/users/me", headers=headers)
    assert res_after_restart.status_code == 200
    assert res_after_restart.json()["full_name"] == updated_name
    assert res_after_restart.json()["phone"] == updated_phone


