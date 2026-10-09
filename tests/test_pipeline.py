import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.pipeline_service import reset_fake_stages

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_fake_users()
    reset_fake_stages()
    yield
    reset_fake_users()
    reset_fake_stages()


def get_auth_headers(email: str = "admin@gmail.com", password: str = "123456") -> dict:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# 1. AC S2-09: Xem danh sách các stages pipeline và win probability %
def test_get_pipeline_stages():
    admin_headers = get_auth_headers("admin@gmail.com")
    res = client.get("/pipeline-stages", headers=admin_headers)
    assert res.status_code == 200
    stages = res.json()
    assert len(stages) == 6
    assert stages[0]["code"] == "PROSPECTING"
    assert stages[0]["win_probability"] == 10.0
    assert stages[-2]["code"] == "CLOSED_WON"
    assert stages[-2]["win_probability"] == 100.0


# 2. AC S2-09: Thêm mới stage pipeline
def test_create_pipeline_stage():
    admin_headers = get_auth_headers("admin@gmail.com")
    payload = {
        "code": "POC_TRIAL",
        "name": "Dùng thử & Thử nghiệm kỹ thuật (PoC)",
        "win_probability": 65.0,
        "order_index": 3,
        "required_exit_fields": ["poc_feedback", "poc_acceptance_signoff"],
    }
    res = client.post("/pipeline-stages", json=payload, headers=admin_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["code"] == "POC_TRIAL"
    assert data["win_probability"] == 65.0
    assert len(data["required_exit_fields"]) == 2


# 3. AC S2-09: Ràng buộc chuyển giai đoạn (Exit criteria check)
def test_check_transition_fails_when_exit_criteria_missing():
    user_headers = get_auth_headers("user@gmail.com")
    # Stage 1 PROSPECTING yêu cầu 'contact_person' và 'customer_need'
    check_payload = {
        "from_stage_id": 1,
        "to_stage_id": 2,
        "opportunity_data": {
            "contact_person": "Nguyễn Văn A",
            # Thiếu 'customer_need'
        },
    }
    res = client.post("/pipeline-stages/check-transition", json=check_payload, headers=user_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["can_transition"] is False
    assert "customer_need" in data["missing_fields"]
    assert "Không thể chuyển" in data["message"]


def test_check_transition_succeeds_when_all_criteria_met():
    user_headers = get_auth_headers("user@gmail.com")
    check_payload = {
        "from_stage_id": 1,
        "to_stage_id": 2,
        "opportunity_data": {
            "contact_person": "Nguyễn Văn A",
            "customer_need": "Cần nâng cấp hệ thống phần mềm kế toán và CRM",
        },
    }
    res = client.post("/pipeline-stages/check-transition", json=check_payload, headers=user_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["can_transition"] is True
    assert len(data["missing_fields"]) == 0
    assert "Đủ điều kiện chuyển" in data["message"]
