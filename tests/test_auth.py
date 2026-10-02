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

client = TestClient(app)


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
    assert data["detail"] == "T??i kho???n ho???c m???t kh???u kh??ng ch??nh x??c"


def test_login_wrong_email_or_username():
    """Test login with non-existent email or username."""
    response = client.post(
        "/auth/login",
        json={"email": "nonexistent@gmail.com", "password": "123456"}
    )
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "T??i kho???n ho???c m???t kh???u kh??ng ch??nh x??c"


def test_login_invalid_email_format():
    """Test login when identifier is not a standard email (treated as invalid account -> 401)."""
    response = client.post(
        "/auth/login",
        json={"email": "not-an-email", "password": "123456"}
    )
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "T??i kho???n ho???c m???t kh???u kh??ng ch??nh x??c"


def test_login_missing_fields():
    """Test validation when required fields are missing."""
    response = client.post(
        "/auth/login",
        json={"email": "admin@gmail.com"}
    )
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "T??i kho???n ho???c m???t kh???u kh??ng ch??nh x??c"


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
