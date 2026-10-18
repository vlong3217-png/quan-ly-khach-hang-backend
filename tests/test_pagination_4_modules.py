import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.win_loss_service import reset_fake_win_loss
from app.services.email_marketing_service import reset_fake_email_data

client = TestClient(app)

def get_auth_token(email: str = "admin@gmail.com", password: str = "123456") -> str:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]

@pytest.fixture(autouse=True)
def setup_teardown():
    reset_fake_users()
    reset_fake_win_loss()
    reset_fake_email_data()
    yield
    reset_fake_users()
    reset_fake_win_loss()
    reset_fake_email_data()

def test_win_loss_pagination():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Test reasons pagination
    res = client.get("/win-loss/reasons?page=1&limit=2", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["limit"] == 2
    assert len(data["items"]) <= 2

    # Test competitors pagination
    res_comp = client.get("/win-loss/competitors?page=1&limit=1", headers=headers)
    assert res_comp.status_code == 200
    comp_data = res_comp.json()
    assert "items" in comp_data
    assert comp_data["page"] == 1
    assert comp_data["limit"] == 1
    assert len(comp_data["items"]) <= 1

def test_email_marketing_pagination():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Test templates pagination
    res = client.get("/email-marketing/templates?page=1&limit=1", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "templates" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["limit"] == 1

    # Test logs pagination
    res_logs = client.get("/email-marketing/logs?page=1&limit=2", headers=headers)
    assert res_logs.status_code == 200
    log_data = res_logs.json()
    assert "logs" in log_data
    assert "total" in log_data
    assert log_data["page"] == 1
    assert log_data["limit"] == 2