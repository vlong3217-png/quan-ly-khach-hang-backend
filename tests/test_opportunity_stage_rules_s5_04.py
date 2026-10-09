"""
Tests for Sprint 5 - S5-04: Điều kiện bắt buộc khi cơ hội rời một giai đoạn (Stage Exit Rules).

Backlog AC:
- Không cho chuyển giai đoạn nếu chưa đủ điều kiện.
- Thông báo rõ điều kiện còn thiếu.
- Trưởng nhóm trở lên (MANAGER, ADMIN) có thể ghi đè và phải nhập lý do.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.services.pipeline_service import reset_fake_stages
from app.services.opportunity_service import reset_fake_opportunities, FAKE_OPPORTUNITIES

client = TestClient(app)


def get_auth_header(email: str = "user@gmail.com", role: str = "USER", user_id: int = 3):
    token = create_access_token(data={"sub": email, "id": user_id, "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def setup_data():
    reset_fake_stages()
    reset_fake_opportunities()
    # Cơ hội 3 do user 3 (USER) sở hữu ở stage PROSPECTING (Stage ID 1)
    # Stage 1 yêu cầu contact_person và customer_need
    opp3 = next(o for o in FAKE_OPPORTUNITIES if o["id"] == 3)
    opp3["stage"] = "PROSPECTING"
    opp3["contact_person"] = "Nguyễn Văn A"
    opp3.pop("customer_need", None)
    opp3["stage_overridden"] = False
    opp3["override_reason"] = None


def test_stage_rules_configuration_permissions():
    """
    AC S5-04: Cấu hình điều kiện rời giai đoạn:
    - Quản lý / Giám đốc (ADMIN, MANAGER) có quyền thêm, xem, xóa điều kiện.
    - Nhân viên thường (USER) bị cấm (403).
    """
    admin_auth = get_auth_header("admin@gmail.com", role="ADMIN", user_id=1)
    manager_auth = get_auth_header("manager@gmail.com", role="MANAGER", user_id=2)
    user_auth = get_auth_header("user@gmail.com", role="USER", user_id=3)

    # 1. USER cố thêm rule -> 403
    resp_user = client.post(
        "/pipeline-stages/1/rules",
        json={"rule_name": "Kiểm tra khảo sát", "field_name": "survey_completed"},
        headers=user_auth,
    )
    assert resp_user.status_code == 403

    # 2. MANAGER thêm rule mới thành công
    resp_mgr = client.post(
        "/pipeline-stages/1/rules",
        json={"rule_name": "Khảo sát nhu cầu thực tế", "field_name": "survey_completed"},
        headers=manager_auth,
    )
    assert resp_mgr.status_code == 201
    created_rule = resp_mgr.json()
    assert created_rule["field_name"] == "survey_completed"
    rule_id = created_rule["id"]

    # 3. Xem danh sách rules
    resp_list = client.get("/pipeline-stages/1/rules", headers=user_auth)
    assert resp_list.status_code == 200
    rule_names = [r["field_name"] for r in resp_list.json()]
    assert "survey_completed" in rule_names

    # 4. ADMIN xóa rule thành công
    resp_del = client.delete(f"/pipeline-stages/1/rules/{rule_id}", headers=admin_auth)
    assert resp_del.status_code == 200


def test_block_transition_when_exit_criteria_missing():
    """
    AC S5-04: Không cho chuyển giai đoạn nếu chưa đủ điều kiện và thông báo rõ điều kiện còn thiếu.
    """
    user_auth = get_auth_header("user@gmail.com", role="USER", user_id=3)

    # Cơ hội 3 đang ở PROSPECTING, đã có contact_person nhưng THIẾU customer_need
    # Chuyển sang QUALIFICATION
    resp = client.post(
        "/opportunities/3/transition-stage",
        json={"target_stage": "QUALIFICATION"},
        headers=user_auth,
    )
    assert resp.status_code == 400
    err = resp.json()["detail"]
    assert "customer_need" in err["missing_requirements"]
    assert "Chưa thỏa mãn các điều kiện bắt buộc" in err["message"]


def test_user_cannot_override_stage_transition():
    """
    AC S5-04: Nhân viên thường (USER) KHÔNG được phép ghi đè điều kiện chuyển giai đoạn (403).
    """
    user_auth = get_auth_header("user@gmail.com", role="USER", user_id=3)

    resp = client.post(
        "/opportunities/3/transition-stage",
        json={
            "target_stage": "QUALIFICATION",
            "override": True,
            "override_reason": "Tôi muốn đẩy nhanh tiến độ",
        },
        headers=user_auth,
    )
    assert resp.status_code == 403
    assert "Chỉ Trưởng nhóm (MANAGER) hoặc Quản trị viên (ADMIN) mới có quyền ghi đè" in resp.json()["detail"]


def test_manager_must_provide_reason_to_override():
    """
    AC S5-04: Trưởng nhóm/Quản lý cố ghi đè nhưng không nhập lý do thì bị từ chối (400).
    """
    # Manager Team A (team_id=1, có scope quản lý cơ hội 3 thuộc team 1)
    manager_auth = get_auth_header("manager@gmail.com", role="MANAGER", user_id=2)

    resp = client.post(
        "/opportunities/3/transition-stage",
        json={
            "target_stage": "QUALIFICATION",
            "override": True,
            "override_reason": "   ",  # Trống / chỉ có khoảng trắng
        },
        headers=manager_auth,
    )
    assert resp.status_code == 400
    assert "Vui lòng nhập lý do ghi đè" in resp.json()["detail"]


def test_manager_override_success_with_reason():
    """
    AC S5-04: Trưởng nhóm trở lên ghi đè kèm lý do thành công:
    - Cơ hội được chuyển sang giai đoạn mới.
    - Lưu lại thông tin ghi đè: stage_overridden, override_reason, override_by.
    """
    manager_auth = get_auth_header("manager@gmail.com", role="MANAGER", user_id=2)

    resp = client.post(
        "/opportunities/3/transition-stage",
        json={
            "target_stage": "QUALIFICATION",
            "override": True,
            "override_reason": "Khách hàng quen của Giám đốc, duyệt đặc cách khảo sát sau",
        },
        headers=manager_auth,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["current_stage"] == "QUALIFICATION"
    assert data["overridden"] is True
    assert data["override_reason"] == "Khách hàng quen của Giám đốc, duyệt đặc cách khảo sát sau"

    # Kiểm tra cơ hội trong hệ thống
    opp_resp = client.get("/opportunities/3", headers=manager_auth)
    opp = opp_resp.json()
    assert opp["stage"] == "QUALIFICATION"
    assert opp["stage_overridden"] is True
    assert opp["override_reason"] == "Khách hàng quen của Giám đốc, duyệt đặc cách khảo sát sau"


def test_transition_success_when_criteria_met():
    """
    AC S5-04: Khi đã hoàn thành đầy đủ điều kiện bắt buộc, chuyển giai đoạn thành công mà không cần ghi đè.
    """
    user_auth = get_auth_header("user@gmail.com", role="USER", user_id=3)

    # Cập nhật đủ điều kiện customer_need cho cơ hội
    resp = client.put(
        "/opportunities/3",
        json={
            "customer_need": "Khách hàng cần triển khai phần mềm CRM cho 50 nhân viên",
            "stage": "QUALIFICATION",
        },
        headers=user_auth,
    )
    assert resp.status_code == 200
    opp = resp.json()
    assert opp["stage"] == "QUALIFICATION"
    assert opp["stage_overridden"] is False
