"""
Tests for Sprint 5 - Task S5-05: Close Opportunity Won / Lost & Reopen
"Là Nhân viên kinh doanh, tôi muốn đóng một cơ hội với kết quả thắng hoặc thua, để công ty học được từ cả thương vụ thắng lẫn thua."

Yêu cầu (AC):
- Đóng Thắng bắt buộc nhập giá trị chốt thực tế và ngày ký.
- Đóng Thua bắt buộc chọn lý do thua và đối thủ thắng thầu nếu có.
- Cơ hội đã đóng không sửa được, chỉ Trưởng nhóm trở lên mở lại được kèm lý do.
- Cơ hội thắng được tính vào chỉ tiêu của người sở hữu.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token
from app.services.opportunity_service import FAKE_OPPORTUNITIES, reset_fake_opportunities
from app.services.auth_service import reset_fake_users_db
from app.services.audit_log_service import get_audit_logs

client = TestClient(app)


def get_auth_headers(email: str = "user1@gmail.com", user_id: int = 3, role: str = "USER", team_id: int = 1) -> dict:
    token = create_access_token({
        "sub": email,
        "id": user_id,
        "role": role,
        "team_id": team_id,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_fake_users_db()
    reset_fake_opportunities()
    yield


def test_close_won_success():
    """Nhân viên đóng thắng cơ hội với đầy đủ giá trị thực tế và ngày ký."""
    # Cơ hội 3 thuộc User 1 (id=3, team_id=1, stage=PROSPECTING)
    headers = get_auth_headers(email="user1@gmail.com", user_id=3, role="USER", team_id=1)

    payload = {
        "actual_revenue": 18500000.0,
        "contract_signed_date": "2026-10-10",
        "note": "Khách hàng chốt gói cao cấp có thêm bảo trì 1 năm",
    }

    res = client.post("/opportunities/3/close-won", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["stage"] == "CLOSED_WON"
    assert data["status"] == "CLOSED_WON"
    assert data["actual_revenue"] == 18500000.0
    assert data["contract_signed_date"] == "2026-10-10"

    # Kiểm tra Audit Log
    logs_data = get_audit_logs(entity_type="DATA_OWNERSHIP", limit=10)
    logs = logs_data.get("items", [])
    matching_log = next((l for l in logs if l["entity_id"] == "3" and l["action"] == "CLOSE_OPPORTUNITY_WON"), None)
    assert matching_log is not None
    assert "18,500,000" in matching_log["new_value"]


def test_close_won_validation_missing_actual_revenue():
    """Đóng Thắng bắt buộc nhập giá trị chốt thực tế > 0."""
    headers = get_auth_headers(email="user1@gmail.com", user_id=3, role="USER", team_id=1)

    # Missing actual_revenue
    res = client.post(
        "/opportunities/3/close-won",
        json={"contract_signed_date": "2026-10-10"},
        headers=headers,
    )
    assert res.status_code in (400, 422)

    # actual_revenue <= 0
    res = client.post(
        "/opportunities/3/close-won",
        json={"actual_revenue": 0, "contract_signed_date": "2026-10-10"},
        headers=headers,
    )
    assert res.status_code == 400
    assert "actual_revenue > 0" in res.json()["detail"]


def test_close_won_validation_missing_contract_signed_date():
    """Đóng Thắng bắt buộc nhập ngày ký hợp đồng."""
    headers = get_auth_headers(email="user1@gmail.com", user_id=3, role="USER", team_id=1)

    # Empty contract_signed_date
    res = client.post(
        "/opportunities/3/close-won",
        json={"actual_revenue": 10000000.0, "contract_signed_date": ""},
        headers=headers,
    )
    assert res.status_code == 400
    assert "contract_signed_date" in res.json()["detail"]


def test_close_lost_success():
    """Nhân viên đóng thua cơ hội kèm lý do và đối thủ cạnh tranh."""
    headers = get_auth_headers(email="user1@gmail.com", user_id=3, role="USER", team_id=1)

    payload = {
        "loss_reason": "Khách hàng ưu tiên giải pháp giá thấp hơn của bên đối thủ",
        "competitor": "Công ty phần mềm ABC",
        "note": "Khách hẹn xem xét lại vào quý 2 năm sau",
    }

    res = client.post("/opportunities/3/close-lost", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["stage"] == "CLOSED_LOST"
    assert data["status"] == "CLOSED_LOST"
    assert data["loss_reason"] == payload["loss_reason"]
    assert data["competitor"] == "Công ty phần mềm ABC"

    # Kiểm tra Audit Log
    logs_data = get_audit_logs(entity_type="DATA_OWNERSHIP", limit=10)
    logs = logs_data.get("items", [])
    matching_log = next((l for l in logs if l["entity_id"] == "3" and l["action"] == "CLOSE_OPPORTUNITY_LOST"), None)
    assert matching_log is not None
    assert "Công ty phần mềm ABC" in matching_log["new_value"]


def test_close_lost_validation_missing_reason():
    """Đóng Thua bắt buộc phải có lý do thua."""
    headers = get_auth_headers(email="user1@gmail.com", user_id=3, role="USER", team_id=1)

    res = client.post(
        "/opportunities/3/close-lost",
        json={"loss_reason": "", "competitor": "ABC"},
        headers=headers,
    )
    assert res.status_code == 400
    assert "loss_reason" in res.json()["detail"]


def test_closed_opportunity_cannot_be_edited():
    """Cơ hội đã đóng không sửa được."""
    headers = get_auth_headers(email="user1@gmail.com", user_id=3, role="USER", team_id=1)

    # Đóng thắng cơ hội 3 trước
    client.post(
        "/opportunities/3/close-won",
        json={"actual_revenue": 15000000.0, "contract_signed_date": "2026-10-10"},
        headers=headers,
    )

    # Thử sửa cơ hội 3 -> Phải bị từ chối với HTTP 400
    res_update = client.put(
        "/opportunities/3",
        json={"title": "Tên mới cố tình sửa", "value": 99999999.0},
        headers=headers,
    )
    assert res_update.status_code == 400
    assert "không thể chỉnh sửa" in res_update.json()["detail"]


def test_cannot_reclose_already_closed_opportunity():
    """Không thể đóng lại một cơ hội đã đóng nếu chưa mở lại."""
    headers = get_auth_headers(email="user1@gmail.com", user_id=3, role="USER", team_id=1)

    client.post(
        "/opportunities/3/close-won",
        json={"actual_revenue": 15000000.0, "contract_signed_date": "2026-10-10"},
        headers=headers,
    )

    # Đóng lại lần nữa
    res_reclose = client.post(
        "/opportunities/3/close-lost",
        json={"loss_reason": "Lại đóng thua nữa"},
        headers=headers,
    )
    assert res_reclose.status_code == 400
    assert "đã được đóng trước đó" in res_reclose.json()["detail"]


def test_reopen_by_user_forbidden():
    """Nhân viên thường (USER) không được tự mở lại cơ hội (403 Forbidden)."""
    user_headers = get_auth_headers(email="user1@gmail.com", user_id=3, role="USER", team_id=1)

    # Đóng thắng
    client.post(
        "/opportunities/3/close-won",
        json={"actual_revenue": 15000000.0, "contract_signed_date": "2026-10-10"},
        headers=user_headers,
    )

    # User gọi reopen
    res = client.post(
        "/opportunities/3/reopen",
        json={"reason": "Khách hàng đổi ý muốn đàm phán lại"},
        headers=user_headers,
    )
    assert res.status_code == 403
    assert "Trưởng nhóm" in res.json()["detail"]


def test_reopen_by_manager_success():
    """Trưởng nhóm mở lại cơ hội đã đóng thành công kèm lý do."""
    user_headers = get_auth_headers(email="user1@gmail.com", user_id=3, role="USER", team_id=1)
    manager_headers = get_auth_headers(email="manager@gmail.com", user_id=2, role="MANAGER", team_id=1)

    # User đóng thua cơ hội 3
    client.post(
        "/opportunities/3/close-lost",
        json={"loss_reason": "Khách hàng bảo hết ngân sách"},
        headers=user_headers,
    )

    # Manager mở lại cơ hội
    reopen_payload = {
        "reason": "Khách hàng được cấp thêm ngân sách bổ sung quý 4, tiếp tục thương thảo",
        "target_stage": "NEGOTIATION",
    }
    res = client.post("/opportunities/3/reopen", json=reopen_payload, headers=manager_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["stage"] == "NEGOTIATION"
    assert data["status"] == "OPEN"
    assert data["reopen_reason"] == reopen_payload["reason"]

    # Sau khi mở lại, user có thể cập nhật bình thường
    res_edit = client.put(
        "/opportunities/3",
        json={"title": "Cung cấp thiết bị User1 - Mở lại đàm phán"},
        headers=user_headers,
    )
    assert res_edit.status_code == 200


def test_won_opportunity_counted_in_user_quota_achievement():
    """Cơ hội thắng được tính vào chỉ tiêu của người sở hữu."""
    user_headers = get_auth_headers(email="user1@gmail.com", user_id=3, role="USER", team_id=1)

    # Đóng thắng cơ hội 3 với actual_revenue = 30,000,000 đ
    client.post(
        "/opportunities/3/close-won",
        json={"actual_revenue": 30000000.0, "contract_signed_date": "2026-10-10"},
        headers=user_headers,
    )

    # Gọi API kiểm tra tiến độ chỉ tiêu của user 3
    res = client.get("/opportunities/users/3/quota-achievement", headers=user_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == 3
    assert data["total_won_opportunities"] >= 1
    assert data["total_won_value"] >= 30000000.0
    assert any(o["id"] == 3 for o in data["won_opportunities"])
