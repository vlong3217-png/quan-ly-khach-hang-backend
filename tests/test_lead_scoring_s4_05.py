import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal, engine
from app.models.lead import Lead, LeadScoringRule, LeadScoringSetting
from app.models.user import Base
from app.core.security import create_access_token

client = TestClient(app)


def get_auth_headers(email: str = "admin@gmail.com", role: str = "ADMIN", user_id: int = 1) -> dict:
    token = create_access_token(data={"sub": email, "id": user_id, "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def clean_scoring_tables():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.query(Lead).delete()
    db.query(LeadScoringRule).delete()
    db.query(LeadScoringSetting).delete()
    db.commit()
    db.close()
    yield


def test_scoring_rules_configuration_and_rbac():
    """
    AC S4-05: Khai báo tiêu chí và số điểm.
    - Giám đốc kinh doanh (ADMIN / MANAGER) có quyền thêm, sửa, xóa tiêu chí.
    - Nhân viên thông thường (USER) bị từ chối 403.
    """
    admin_headers = get_auth_headers("admin@gmail.com", role="ADMIN", user_id=1)
    manager_headers = get_auth_headers("manager@gmail.com", role="MANAGER", user_id=2)
    user_headers = get_auth_headers("user1@gmail.com", role="USER", user_id=3)

    # 1. USER không có quyền tạo tiêu chí
    res_forbidden = client.post(
        "/leads/scoring-rules",
        json={"name": "Tiêu chí test", "field_name": "industry", "operator": "EQUALS", "target_value": "IT", "points": 20},
        headers=user_headers,
    )
    assert res_forbidden.status_code == 403

    # 2. MANAGER tạo tiêu chí ngành nghề
    rule_payload = {
        "name": "Ngành CNTT & Phần mềm",
        "description": "Ưu tiên doanh nghiệp công nghệ",
        "field_name": "industry",
        "operator": "EQUALS",
        "target_value": "Công nghệ thông tin",
        "points": 30,
        "is_active": True,
    }
    res_mgr = client.post("/leads/scoring-rules", json=rule_payload, headers=manager_headers)
    assert res_mgr.status_code == 201
    rule_data = res_mgr.json()
    assert rule_data["id"] is not None
    assert rule_data["points"] == 30
    rule_id = rule_data["id"]

    # 3. ADMIN cập nhật tiêu chí
    res_update = client.put(
        f"/leads/scoring-rules/{rule_id}",
        json={"points": 35, "name": "Ngành CNTT & Chuyển đổi số"},
        headers=admin_headers,
    )
    assert res_update.status_code == 200
    assert res_update.json()["points"] == 35
    assert res_update.json()["name"] == "Ngành CNTT & Chuyển đổi số"

    # 4. Xem danh sách tiêu chí
    res_list = client.get("/leads/scoring-rules", headers=user_headers)
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 1

    # 5. ADMIN xóa tiêu chí
    res_del = client.delete(f"/leads/scoring-rules/{rule_id}", headers=admin_headers)
    assert res_del.status_code == 204


def test_scoring_thresholds_configuration():
    """
    AC S4-05: Cấu hình ngưỡng phân loại Nóng, Ấm, Lạnh.
    """
    manager_headers = get_auth_headers("manager@gmail.com", role="MANAGER", user_id=2)
    user_headers = get_auth_headers("user1@gmail.com", role="USER", user_id=3)

    # 1. Xem cấu hình mặc định (HOT >= 50, WARM >= 20, còn lại COLD)
    res_get = client.get("/leads/scoring-settings", headers=user_headers)
    assert res_get.status_code == 200
    assert res_get.json()["hot_threshold"] == 50
    assert res_get.json()["warm_threshold"] == 20

    # 2. MANAGER cập nhật ngưỡng (HOT >= 70, WARM >= 30)
    res_put = client.put(
        "/leads/scoring-settings",
        json={"hot_threshold": 70, "warm_threshold": 30},
        headers=manager_headers,
    )
    assert res_put.status_code == 200
    assert res_put.json()["hot_threshold"] == 70
    assert res_put.json()["warm_threshold"] == 30

    # 3. Validate lỗi nếu warm >= hot
    res_invalid = client.put(
        "/leads/scoring-settings",
        json={"hot_threshold": 40, "warm_threshold": 50},
        headers=manager_headers,
    )
    assert res_invalid.status_code == 400


def test_automatic_lead_scoring_and_classification():
    """
    AC S4-05:
    - Tự động tính lại điểm khi thông tin lead thay đổi.
    - Phân loại Nóng (HOT), Ấm (WARM), Lạnh (COLD) theo ngưỡng cấu hình.
    - Điểm chỉ dùng để ưu tiên, không tự động loại lead.
    """
    admin_headers = get_auth_headers("admin@gmail.com", role="ADMIN", user_id=1)
    user_headers = get_auth_headers("user@gmail.com", role="USER", user_id=3)

    # 1. Cấu hình ngưỡng: HOT >= 60, WARM >= 25, COLD < 25
    client.put(
        "/leads/scoring-settings",
        json={"hot_threshold": 60, "warm_threshold": 25},
        headers=admin_headers,
    )

    # 2. Khai báo các tiêu chí chấm điểm
    rules = [
        {"name": "Ngành CNTT", "field_name": "industry", "operator": "EQUALS", "target_value": "Công nghệ thông tin", "points": 30},
        {"name": "Có số điện thoại", "field_name": "phone", "operator": "NOT_EMPTY", "target_value": None, "points": 20},
        {"name": "Doanh nghiệp lớn", "field_name": "company_size", "operator": "IN", "target_value": "50 - 100 nhân sự, Trên 100 nhân sự", "points": 25},
        {"name": "Nguồn Google Ads", "field_name": "source", "operator": "EQUALS", "target_value": "Google Ads", "points": 15},
    ]
    for r in rules:
        resp = client.post("/leads/scoring-rules", json=r, headers=admin_headers)
        assert resp.status_code == 201

    # 3. Tạo lead thỏa mãn tất cả tiêu chí -> Tổng điểm: 30 + 20 + 25 + 15 = 90 (HOT)
    lead_payload = {
        "full_name": "Nguyễn Văn Hùng",
        "email": "hung.nguyen@techcorp.vn",
        "phone": "0912345678",
        "company": "Công ty Cổ phần TechCorp",
        "industry": "Công nghệ thông tin",
        "company_size": "Trên 100 nhân sự",
        "source": "Google Ads",
    }
    res_lead = client.post("/leads", json=lead_payload, headers=user_headers)
    assert res_lead.status_code == 201
    lead_data = res_lead.json()
    assert lead_data["score"] == 90
    assert lead_data["grade"] == "HOT"
    lead_id = lead_data["id"]

    # 4. Cập nhật thông tin lead -> Tự động tính lại điểm
    # Chuyển industry thành "Bán lẻ" (mất 30 điểm) -> Điểm còn 60 -> Vẫn đạt HOT
    res_up1 = client.put(f"/leads/{lead_id}", json={"industry": "Bán lẻ"}, headers=user_headers)
    assert res_up1.status_code == 200
    assert res_up1.json()["score"] == 60
    assert res_up1.json()["grade"] == "HOT"

    # Chuyển source thành "Vãng lai" (mất thêm 15 điểm) -> Điểm còn 45 -> Xuống hạng WARM (25 <= 45 < 60)
    res_up2 = client.put(f"/leads/{lead_id}", json={"source": "Vãng lai"}, headers=user_headers)
    assert res_up2.status_code == 200
    assert res_up2.json()["score"] == 45
    assert res_up2.json()["grade"] == "WARM"

    # Chuyển quy mô công ty thành "Dưới 10 nhân sự" (mất thêm 25 điểm) -> Điểm còn 20 -> Xuống hạng COLD (20 < 25)
    res_up3 = client.put(f"/leads/{lead_id}", json={"company_size": "Dưới 10 nhân sự"}, headers=user_headers)
    assert res_up3.status_code == 200
    assert res_up3.json()["score"] == 20
    assert res_up3.json()["grade"] == "COLD"

    # 5. AC S4-05: "Điểm chỉ dùng để ưu tiên, không tự động loại lead."
    # Trạng thái status của lead vẫn là "NEW", không bị loại bỏ hay chuyển sang DISQUALIFIED
    assert res_up3.json()["status"] == "NEW"


def test_prioritize_leads_by_score_and_filter_by_grade():
    """
    AC S4-05: Nhân viên kinh doanh có thể lọc theo phân loại Nóng/Ấm/Lạnh
    và sắp xếp theo điểm giảm dần để gọi lead tiềm năng nhất trước.
    """
    admin_headers = get_auth_headers("admin@gmail.com", role="ADMIN", user_id=1)
    user_headers = get_auth_headers("user@gmail.com", role="USER", user_id=3)

    # Tiêu chí: có SĐT +20, Ngành CNTT +30
    client.post("/leads/scoring-rules", json={"name": "Ngành", "field_name": "industry", "operator": "EQUALS", "target_value": "CNTT", "points": 30}, headers=admin_headers)
    client.post("/leads/scoring-rules", json={"name": "SĐT", "field_name": "phone", "operator": "NOT_EMPTY", "points": 20}, headers=admin_headers)

    # Lead A: 50 điểm (HOT)
    client.post("/leads", json={"full_name": "Lead A", "email": "a@gmail.com", "phone": "0981111111", "industry": "CNTT"}, headers=user_headers)
    # Lead B: 20 điểm (WARM)
    client.post("/leads", json={"full_name": "Lead B", "email": "b@gmail.com", "phone": "0982222222", "industry": "Xây dựng"}, headers=user_headers)
    # Lead C: 0 điểm (COLD)
    client.post("/leads", json={"full_name": "Lead C", "email": "c@gmail.com"}, headers=user_headers)

    # Lọc lead Nóng (HOT)
    res_hot = client.get("/leads?grade=HOT", headers=user_headers)
    assert res_hot.status_code == 200
    assert res_hot.json()["total"] == 1
    assert res_hot.json()["items"][0]["full_name"] == "Lead A"

    # Sắp xếp theo điểm giảm dần (score_desc)
    res_sorted = client.get("/leads?sort_by=score_desc", headers=user_headers)
    assert res_sorted.status_code == 200
    items = res_sorted.json()["items"]
    assert len(items) == 3
    assert items[0]["score"] == 50
    assert items[1]["score"] == 20
    assert items[2]["score"] == 0
    assert items[0]["full_name"] == "Lead A"


def test_recalculate_all_scores_when_rules_change():
    """
    AC S4-05: Khi ban giám đốc thêm tiêu chí mới, có thể kích hoạt tính lại toàn bộ điểm lead.
    """
    admin_headers = get_auth_headers("admin@gmail.com", role="ADMIN", user_id=1)
    user_headers = get_auth_headers("user@gmail.com", role="USER", user_id=3)

    # Tạo 2 lead ban đầu
    res1 = client.post("/leads", json={"full_name": "Doanh Nghiệp A", "email": "a@corp.vn", "industry": "Y tế"}, headers=user_headers)
    res2 = client.post("/leads", json={"full_name": "Doanh Nghiệp B", "email": "b@corp.vn", "industry": "Giáo dục"}, headers=user_headers)
    lead1_id = res1.json()["id"]
    lead2_id = res2.json()["id"]

    assert res1.json()["score"] == 0
    assert res2.json()["score"] == 0

    # Thêm tiêu chí mới: Ngành Y tế +40 điểm
    client.post("/leads/scoring-rules", json={"name": "Ưu tiên Y tế", "field_name": "industry", "operator": "EQUALS", "target_value": "Y tế", "points": 40}, headers=admin_headers)

    # Kích hoạt tính lại toàn bộ điểm
    res_batch = client.post("/leads/recalculate-all-scores", headers=admin_headers)
    assert res_batch.status_code == 200
    assert res_batch.json()["total_recalculated"] == 2

    # Kiểm tra lead1 đã được cập nhật 40 điểm (WARM)
    res_l1 = client.get(f"/leads/{lead1_id}", headers=user_headers)
    assert res_l1.json()["score"] == 40
    assert res_l1.json()["grade"] == "WARM"

    # Lead 2 vẫn 0 điểm (COLD)
    res_l2 = client.get(f"/leads/{lead2_id}", headers=user_headers)
    assert res_l2.json()["score"] == 0
    assert res_l2.json()["grade"] == "COLD"

