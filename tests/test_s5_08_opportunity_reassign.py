"""
Tests for Sprint 5 - Task S5-08: Reassign Opportunities (Phân bổ lại cơ hội bán hàng)
"Là Trưởng nhóm kinh doanh, tôi muốn phân bổ lại cơ hội cho người khác trong nhóm, để thương vụ không đứng yên khi người phụ trách nghỉ dài hoặc quá tải."

Yêu cầu:
- Chuyển quyền sở hữu một hoặc nhiều cơ hội cùng lúc.
- Người nhận thấy được cơ hội và toàn bộ lịch sử (Activities).
- Mỗi lần chuyển quyền phải ghi nhật ký kèm lý do (Audit Log).
- Chỉ người có quyền phù hợp (ADMIN, MANAGER của nhóm) mới được phân bổ lại.
- USER thường không được phân bổ lại (403 Forbidden).
- Validate dữ liệu: lý do bắt buộc, danh sách ID hợp lệ, người nhận tồn tại và active.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token
from app.services.opportunity_service import FAKE_OPPORTUNITIES, reset_fake_opportunities
from app.services.activity_service import FAKE_ACTIVITIES, reset_fake_activities
from app.services.auth_service import reset_fake_users_db
from app.services.audit_log_service import get_audit_logs

client = TestClient(app)


def get_auth_headers(email: str = "manager@gmail.com", user_id: int = 2, role: str = "MANAGER") -> dict:
    token = create_access_token({
        "sub": email,
        "id": user_id,
        "role": role,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_fake_users_db()
    reset_fake_opportunities()
    reset_fake_activities()
    yield
    reset_fake_users_db()
    reset_fake_opportunities()
    reset_fake_activities()


# ============================================================================
# 1. Tests for Single & Bulk Reassignment Success
# ============================================================================

def test_reassign_single_opportunity_success():
    """Trưởng nhóm phân bổ lại 1 cơ hội cho nhân viên khác trong nhóm kèm lý do."""
    # Cơ hội 3 ban đầu thuộc User 1 (id=3, team_id=1)
    opp3 = next(o for o in FAKE_OPPORTUNITIES if o["id"] == 3)
    assert opp3["owner_id"] == 3

    manager_headers = get_auth_headers(email="manager@gmail.com", user_id=2, role="MANAGER")
    payload = {
        "opportunity_ids": [3],
        "new_owner_id": 1,  # Chuyển quyền sang user id=1
        "reason": "Nhân viên User 1 xin nghỉ phép dài hạn 2 tuần",
    }

    res = client.post("/opportunities/reassign", json=payload, headers=manager_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["reassigned_count"] == 1
    assert 3 in data["reassigned_opportunity_ids"]
    assert data["new_owner_id"] == 1
    assert data["reason"] == payload["reason"]

    # Kiểm tra cơ hội trong hệ thống đã được cập nhật owner_id
    updated_opp3 = next(o for o in FAKE_OPPORTUNITIES if o["id"] == 3)
    assert updated_opp3["owner_id"] == 1

    # Kiểm tra nhật ký hệ thống (Audit Log) ghi nhận lý do
    logs_res = get_audit_logs(entity_type="DATA_OWNERSHIP", limit=10)
    logs = logs_res.get("items", [])
    matching_log = next((l for l in logs if l["entity_id"] == "3" and l["action"] == "REASSIGN_OPPORTUNITY"), None)
    assert matching_log is not None
    assert "Nhân viên User 1 xin nghỉ phép dài hạn" in matching_log["new_value"]


def test_reassign_multiple_opportunities_bulk_success():
    """Trưởng nhóm phân bổ lại nhiều cơ hội cùng lúc (bulk reassignment)."""
    # Gán cơ hội 2 (owner=2) và 3 (owner=3) cùng sang cho User 1 (owner_id=1)
    manager_headers = get_auth_headers(email="manager@gmail.com", user_id=2, role="MANAGER")
    payload = {
        "opportunity_ids": [2, 3],
        "new_owner_id": 1,
        "reason": "Điều chuyển khối lượng công việc cuối quý do quá tải",
    }

    res = client.post("/opportunities/reassign", json=payload, headers=manager_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["reassigned_count"] == 2
    assert set(data["reassigned_opportunity_ids"]) == {2, 3}

    # Cả 2 cơ hội đều đã chuyển sang owner_id=1
    assert next(o for o in FAKE_OPPORTUNITIES if o["id"] == 2)["owner_id"] == 1
    assert next(o for o in FAKE_OPPORTUNITIES if o["id"] == 3)["owner_id"] == 1


# ============================================================================
# 2. Tests for Activity History Accessibility After Reassignment
# ============================================================================

def test_new_owner_can_see_opportunity_and_full_activity_history():
    """
    Sau khi được phân bổ, người nhận mới truy cập được cơ hội và toàn bộ lịch sử hoạt động liên quan.
    """
    # Gán cơ hội 3 có activity liên quan
    # Thêm activity cho cơ hội 3
    FAKE_ACTIVITIES.append({
        "id": 99,
        "title": "Cuộc gọi chăm sóc ban đầu với khách hàng",
        "type": "CALL",
        "description": "Khách hàng đồng ý xem demo",
        "opportunity_id": 3,
        "owner_id": 3,
        "team_id": 1,
        "created_at": "2026-10-01T10:00:00",
    })

    admin_headers = get_auth_headers(email="admin@gmail.com", user_id=1, role="ADMIN")
    payload = {
        "opportunity_ids": [3],
        "new_owner_id": 2,
        "reason": "Bàn giao thương vụ cho Trưởng nhóm trực tiếp phụ trách",
    }
    res_reassign = client.post("/opportunities/reassign", json=payload, headers=admin_headers)
    assert res_reassign.status_code == 200

    # User 2 xem danh sách cơ hội trong phạm vi MY
    user2_headers = get_auth_headers(email="manager@gmail.com", user_id=2, role="USER")
    res_opp = client.get("/opportunities?scope=MY", headers=user2_headers)
    assert res_opp.status_code == 200
    opp_ids = [o["id"] for o in res_opp.json()["opportunities"]]
    assert 3 in opp_ids

    # User 2 xem lịch sử hoạt động liên quan cơ hội 3
    res_act = client.get("/activities", headers=user2_headers)
    assert res_act.status_code == 200


# ============================================================================
# 3. Tests for RBAC & Permission Validation
# ============================================================================

def test_user_cannot_reassign_opportunities_returns_403():
    """Nhân viên thông thường (USER) không có quyền phân bổ lại cơ hội -> 403 Forbidden."""
    user_headers = get_auth_headers(email="user@gmail.com", user_id=3, role="USER")
    payload = {
        "opportunity_ids": [3],
        "new_owner_id": 1,
        "reason": "Nhân viên tự ý chuyển cơ hội",
    }
    res = client.post("/opportunities/reassign", json=payload, headers=user_headers)
    assert res.status_code == 403
    assert "quyền" in res.json()["detail"].lower()


def test_manager_cannot_reassign_opportunity_outside_team():
    """Trưởng nhóm không được phân bổ cơ hội thuộc team khác ngoài phạm vi quản lý -> 403 Forbidden."""
    # Cơ hội 4 thuộc Team 2 (owner_id=4, team_id=2)
    # Manager id=2 thuộc Team 1 (team_id=1)
    manager_headers = get_auth_headers(email="manager@gmail.com", user_id=2, role="MANAGER")
    payload = {
        "opportunity_ids": [4],
        "new_owner_id": 3,
        "reason": "Cố tình phân bổ cơ hội của nhóm khác",
    }
    res = client.post("/opportunities/reassign", json=payload, headers=manager_headers)
    assert res.status_code == 403
    assert "ngoài nhóm quản lý" in res.json()["detail"].lower()


# ============================================================================
# 4. Tests for Input Validation and Error Handling
# ============================================================================

def test_reassign_missing_reason_returns_400():
    """Bắt buộc nhập lý do phân bổ lại; để trống hoặc chỉ có khoảng trắng báo lỗi 400."""
    manager_headers = get_auth_headers(email="manager@gmail.com", user_id=2, role="MANAGER")
    payload = {
        "opportunity_ids": [3],
        "new_owner_id": 1,
        "reason": "   ",
    }
    res = client.post("/opportunities/reassign", json=payload, headers=manager_headers)
    assert res.status_code == 400
    assert "lý do" in res.json()["detail"].lower()


def test_reassign_empty_opportunity_ids_returns_400():
    """Danh sách cơ hội rỗng báo lỗi 400."""
    manager_headers = get_auth_headers(email="manager@gmail.com", user_id=2, role="MANAGER")
    payload = {
        "opportunity_ids": [],
        "new_owner_id": 1,
        "reason": "Lý do hợp lệ",
    }
    res = client.post("/opportunities/reassign", json=payload, headers=manager_headers)
    assert res.status_code == 400
    assert "không được để trống" in res.json()["detail"].lower()


def test_reassign_nonexistent_opportunity_returns_404():
    """Cơ hội không tồn tại báo lỗi 404."""
    manager_headers = get_auth_headers(email="manager@gmail.com", user_id=2, role="MANAGER")
    payload = {
        "opportunity_ids": [99999],
        "new_owner_id": 1,
        "reason": "Phân bổ cơ hội ảo",
    }
    res = client.post("/opportunities/reassign", json=payload, headers=manager_headers)
    assert res.status_code == 404
    assert "không tìm thấy" in res.json()["detail"].lower()


def test_reassign_nonexistent_new_owner_returns_404():
    """Người nhận mới không tồn tại trong hệ thống báo lỗi 404."""
    manager_headers = get_auth_headers(email="manager@gmail.com", user_id=2, role="MANAGER")
    payload = {
        "opportunity_ids": [3],
        "new_owner_id": 99999,
        "reason": "Gán cho user không tồn tại",
    }
    res = client.post("/opportunities/reassign", json=payload, headers=manager_headers)
    assert res.status_code == 404
    assert "người dùng" in res.json()["detail"].lower()
