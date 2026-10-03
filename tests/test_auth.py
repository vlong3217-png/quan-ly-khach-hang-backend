import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    SECRET_KEY,
    ALGORITHM,
)
from app.services.auth_service import fake_user, reset_fake_users_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_user_password():
    reset_fake_users_db()
    yield
    reset_fake_users_db()


def test_root():
    """Test health/root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Customer Management API is running"}


def test_login_success_with_email():
    """Test login with valid admin email credentials."""
    response = client.post(
        "/auth/login",
        json={"email": "admin@gmail.com", "password": "123456"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["token_type"] == "bearer"
    assert "access_token" in data
    assert data["user"]["email"] == "admin@gmail.com"
    assert data["user"]["role"] == "ADMIN"
    assert data["user"]["full_name"] == "Admin"
    assert data["user"]["id"] == 1


def test_login_success_with_username():
    """Test login with valid admin username credentials."""
    response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "123456"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["user"]["email"] == "admin@gmail.com"


def test_login_wrong_password():
    """Test login with invalid password."""
    response = client.post(
        "/auth/login",
        json={"email": "admin@gmail.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Tài khoản hoặc mật khẩu không chính xác"


def test_login_wrong_email_or_username():
    """Test login with non-existent email or username."""
    response = client.post(
        "/auth/login",
        json={"email": "nonexistent@gmail.com", "password": "123456"}
    )
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Tài khoản hoặc mật khẩu không chính xác"


def test_login_invalid_email_format():
    """Test login when identifier is not a standard email (treated as invalid account -> 401)."""
    response = client.post(
        "/auth/login",
        json={"email": "not-an-email", "password": "123456"}
    )
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Tài khoản hoặc mật khẩu không chính xác"


def test_login_missing_fields():
    """Test validation when required fields are missing."""
    response = client.post(
        "/auth/login",
        json={"email": "admin@gmail.com"}
    )
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Tài khoản hoặc mật khẩu không chính xác"


def test_security_hash_and_verify():
    """Test password hashing and verification logic."""
    raw_pass = "TestPassword@123"
    hashed = hash_password(raw_pass)
    assert hashed != raw_pass
    assert verify_password(raw_pass, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_token_payload():
    """Test JWT token encoding and decoded claims."""
    token = create_access_token({
        "sub": "admin@gmail.com",
        "id": 1,
        "role": "ADMIN"
    })
    decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert decoded["sub"] == "admin@gmail.com"
    assert decoded["id"] == 1
    assert decoded["role"] == "ADMIN"
    assert "exp" in decoded


def test_change_password_no_token():
    """Test change password without authorization token returns 401."""
    response = client.post(
        "/auth/change-password",
        json={"current_password": "123456", "new_password": "newpassword123"}
    )
    assert response.status_code == 401


def test_change_password_invalid_token():
    """Test change password with invalid token returns 401."""
    response = client.post(
        "/auth/change-password",
        headers={"Authorization": "Bearer invalid_token_12345"},
        json={"current_password": "123456", "new_password": "newpassword123"}
    )
    assert response.status_code == 401


def test_change_password_wrong_current_password():
    """Test change password with incorrect current password returns error."""
    login_res = client.post(
        "/auth/login",
        json={"email": "admin@gmail.com", "password": "123456"}
    )
    token = login_res.json()["access_token"]

    response = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "wrong_password", "new_password": "newpassword123"}
    )
    assert response.status_code in [400, 401]
    data = response.json()
    assert "Mật khẩu hiện tại không chính xác" in data["detail"]


def test_change_password_empty_new_password():
    """Test change password with empty new password returns error."""
    login_res = client.post(
        "/auth/login",
        json={"email": "admin@gmail.com", "password": "123456"}
    )
    token = login_res.json()["access_token"]

    response = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "123456", "new_password": ""}
    )
    assert response.status_code in [400, 422]


def test_change_password_short_new_password():
    """Test change password with new password shorter than 6 characters returns error."""
    login_res = client.post(
        "/auth/login",
        json={"email": "admin@gmail.com", "password": "123456"}
    )
    token = login_res.json()["access_token"]

    response = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "123456", "new_password": "123"}
    )
    assert response.status_code in [400, 422]


def test_change_password_success_flow():
    """
    Test successful change password flow:
    1. Login with initial password
    2. Change password with valid token and correct current password
    3. Verify response contains success message and no sensitive password fields
    4. Verify login with NEW password succeeds
    5. Verify login with OLD password fails (401)
    """
    # 1. Login with initial password
    initial_login = client.post(
        "/auth/login",
        json={"email": "admin@gmail.com", "password": "123456"}
    )
    assert initial_login.status_code == 200
    token = initial_login.json()["access_token"]

    # 2. Change password
    change_res = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "123456", "new_password": "newsecretpass123"}
    )
    assert change_res.status_code == 200
    data = change_res.json()
    assert data["success"] is True
    assert data["message"] == "Đổi mật khẩu thành công"
    assert "password" not in data
    assert "hashed_password" not in data

    # 3. Verify new password can log in
    new_login = client.post(
        "/auth/login",
        json={"email": "admin@gmail.com", "password": "newsecretpass123"}
    )
    assert new_login.status_code == 200
    assert new_login.json()["success"] is True

    # 4. Verify old password can no longer log in
    old_login = client.post(
        "/auth/login",
        json={"email": "admin@gmail.com", "password": "123456"}
    )
    assert old_login.status_code == 401
    assert old_login.json()["detail"] == "Tài khoản hoặc mật khẩu không chính xác"


def test_login_lockout_after_five_failed_attempts():
    """AC S1-01: Tạm thời khóa 15 phút sau 5 lần sai liên tiếp."""
    # First 4 failed attempts
    for _ in range(4):
        res = client.post(
            "/auth/login",
            json={"email": "admin@gmail.com", "password": "wrongpassword"}
        )
        assert res.status_code == 401
        assert res.json()["detail"] == "Tài khoản hoặc mật khẩu không chính xác"

    # 5th failed attempt triggers lock
    res5 = client.post(
        "/auth/login",
        json={"email": "admin@gmail.com", "password": "wrongpassword"}
    )
    assert res5.status_code == 401
    assert "khóa 15 phút" in res5.json()["detail"]

    # Even with correct password, cannot log in during lockout
    res_correct = client.post(
        "/auth/login",
        json={"email": "admin@gmail.com", "password": "123456"}
    )
    assert res_correct.status_code == 401
    assert "khóa 15 phút" in res_correct.json()["detail"]

