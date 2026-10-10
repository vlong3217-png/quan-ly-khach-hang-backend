import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import reset_fake_users
from app.services.customer_service import reset_fake_customers
from app.services.opportunity_service import reset_fake_opportunities
from app.services.campaign_service import reset_fake_campaigns
from app.services import lead_service

client = TestClient(app)


def get_auth_token(email: str = "admin@gmail.com", password: str = "123456") -> str:
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(autouse=True)
def setup_data():
    reset_fake_users()
    reset_fake_customers()
    reset_fake_opportunities()
    reset_fake_campaigns()
    lead_service.reset_fake_leads()
    yield
    reset_fake_users()
    reset_fake_customers()
    reset_fake_opportunities()
    reset_fake_campaigns()
    lead_service.reset_fake_leads()


# ==============================================================================
# 1. AC S4-03: Khai báo chiến dịch với ngân sách, thời gian chạy, kênh
# ==============================================================================

def test_create_campaign_success():
    """Nhân viên marketing khai báo chiến dịch với ngân sách, thời gian chạy, kênh tiếp thị."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "name": "Chiến dịch Triển lãm Quốc tế 2026",
        "code": "CAMP-EXPO-2026",
        "budget": 80000000.0,
        "actual_cost": 75000000.0,
        "start_date": "2026-04-01T08:00:00",
        "end_date": "2026-04-30T18:00:00",
        "channel": "EVENT",
        "target_leads": 120,
        "expected_revenue": 300000000.0,
        "status": "ACTIVE",
        "description": "Gian hàng công nghệ tại Triển lãm VietBuild 2026",
    }
    resp = client.post("/campaigns", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Chiến dịch Triển lãm Quốc tế 2026"
    assert data["code"] == "CAMP-EXPO-2026"
    assert data["budget"] == 80000000.0
    assert data["actual_cost"] == 75000000.0
    assert data["channel"] == "EVENT"
    assert data["target_leads"] == 120
    assert data["id"] is not None


def test_create_campaign_duplicate_code_rejected():
    """Mã chiến dịch là duy nhất, không cho phép trùng lặp."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "name": "Chiến dịch Trùng Mã",
        "code": "CAMP-2026-EXPO",  # Mã đã tồn tại trong INITIAL_CAMPAIGNS
        "budget": 50000000.0,
        "start_date": "2026-05-01T00:00:00",
        "channel": "WORKSHOP",
    }
    resp = client.post("/campaigns", json=payload, headers=headers)
    assert resp.status_code == 400
    assert "đã tồn tại" in resp.json()["detail"]


def test_list_and_filter_campaigns():
    """Xem danh sách chiến dịch, tìm kiếm và lọc theo kênh hoặc trạng thái."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/campaigns", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    assert len(data["campaigns"]) >= 2

    # Lọc theo kênh
    resp_event = client.get("/campaigns?channel=EVENT", headers=headers)
    assert resp_event.status_code == 200
    for camp in resp_event.json()["campaigns"]:
        assert camp["channel"] == "EVENT"

    # Tìm kiếm theo từ khóa
    resp_search = client.get("/campaigns?search=Facebook", headers=headers)
    assert resp_search.status_code == 200
    assert any("Facebook" in c["name"] for c in resp_search.json()["campaigns"])


def test_update_and_delete_campaign():
    """Cập nhật thông tin chiến dịch và xóa chiến dịch."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Cập nhật
    update_payload = {
        "name": "Hội thảo Chuyển đổi số 2026 (Cập nhật)",
        "budget": 60000000.0,
        "actual_cost": 55000000.0,
        "status": "COMPLETED",
    }
    resp_up = client.put("/campaigns/1", json=update_payload, headers=headers)
    assert resp_up.status_code == 200
    assert resp_up.json()["name"] == "Hội thảo Chuyển đổi số 2026 (Cập nhật)"
    assert resp_up.json()["budget"] == 60000000.0
    assert resp_up.json()["status"] == "COMPLETED"

    # Xóa
    resp_del = client.delete("/campaigns/1", headers=headers)
    assert resp_del.status_code == 200
    assert "Đã xóa thành công" in resp_del.json()["message"]

    # Kiểm tra lại 404
    resp_get = client.get("/campaigns/1", headers=headers)
    assert resp_get.status_code == 404


# ==============================================================================
# 2. AC S4-03: Lead và Cơ hội giữ liên kết tới chiến dịch đã sinh ra chúng
# ==============================================================================

def test_lead_and_opportunity_linked_to_campaign():
    """Lead và cơ hội giữ liên kết tới campaign_id đã sinh ra chúng."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Tạo Lead gắn với chiến dịch ID 1
    lead_payload = {
        "name": "Vũ Mạnh Cường",
        "email": "cuong.vu@vietsoftware.vn",
        "phone": "0911223344",
        "company_name": "Công ty Phần mềm Việt Cường",
        "source": "Hội thảo",
        "campaign_id": 1,
    }
    resp_lead = client.post("/leads", json=lead_payload, headers=headers)
    assert resp_lead.status_code == 201
    lead_data = resp_lead.json()
    lead_id = lead_data["id"]
    assert lead_data["campaign_id"] == 1

    # Xem danh sách lead của chiến dịch
    resp_camp_leads = client.get("/campaigns/1/leads", headers=headers)
    assert resp_camp_leads.status_code == 200
    leads = resp_camp_leads.json()
    assert any(l["id"] == lead_id for l in leads)

    # 2. Tạo Cơ hội gắn trực tiếp với chiến dịch ID 1
    opp_payload = {
        "title": "Hợp đồng phần mềm từ Hội thảo 2026",
        "value": 120000000.0,
        "stage": "CLOSED_WON",
        "customer_id": 1,
        "campaign_id": 1,
        "lead_id": lead_id,
    }
    resp_opp = client.post("/opportunities", json=opp_payload, headers=headers)
    assert resp_opp.status_code == 201
    opp_data = resp_opp.json()
    assert opp_data["campaign_id"] == 1
    assert opp_data["lead_id"] == lead_id


def test_convert_lead_inherits_campaign_id_to_opportunity():
    """Khi chuyển đổi Lead sang Khách hàng & Cơ hội, Cơ hội tự động kế thừa campaign_id."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Tạo lead thuộc chiến dịch ID 2
    lead_payload = {
        "name": "Hoàng Kim Ngân",
        "email": "ngan.hoang@vietfintech.com",
        "phone": "0988991122",
        "company_name": "Công ty Cổ phần VietFintech",
        "source": "Facebook Ads",
        "campaign_id": 2,
    }
    resp_lead = client.post("/leads", json=lead_payload, headers=headers)
    assert resp_lead.status_code == 201
    lead_id = resp_lead.json()["id"]

    # Chuyển đổi Lead
    convert_payload = {
        "opportunity_name": "Cơ hội VietFintech từ Facebook Ads",
        "opportunity_value": 70000000.0,
        "opportunity_stage": "PROSPECTING",
    }
    resp_conv = client.post(f"/leads/{lead_id}/convert", json=convert_payload, headers=headers)
    assert resp_conv.status_code == 200
    data = resp_conv.json()
    assert data["success"] is True
    opp = data["opportunity"]
    assert opp["campaign_id"] == 2
    assert opp["lead_id"] == lead_id


# ==============================================================================
# 3. AC S4-03: Xem được số lead, số cơ hội và giá trị đã chốt của từng chiến dịch
# ==============================================================================

def test_campaign_metrics_and_roi_calculation():
    """Xem số lead, số cơ hội, giá trị đã chốt và tính toán ROI chuẩn xác."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Tạo 2 Lead thuộc chiến dịch 1
    for i in range(2):
        client.post("/leads", json={
            "name": f"Lead Test Campaign {i}",
            "email": f"lead.camp{i}@company.vn",
            "phone": f"091200000{i}",
            "source": "Hội thảo",
            "campaign_id": 1,
        }, headers=headers)

    # Tạo 1 Cơ hội WON và 1 Cơ hội OPEN thuộc chiến dịch 1
    client.post("/opportunities", json={
        "title": "Cơ hội Đã Chốt từ Hội Thảo",
        "value": 150000000.0,
        "stage": "CLOSED_WON",
        "customer_id": 1,
        "campaign_id": 1,
    }, headers=headers)

    client.post("/opportunities", json={
        "title": "Cơ hội Đang Đàm Phán",
        "value": 50000000.0,
        "stage": "PROPOSAL",
        "customer_id": 1,
        "campaign_id": 1,
    }, headers=headers)

    # Gọi API metrics của chiến dịch 1
    resp = client.get("/campaigns/1/metrics", headers=headers)
    assert resp.status_code == 200
    metrics = resp.json()

    assert metrics["campaign_id"] == 1
    assert metrics["total_leads"] >= 2
    assert metrics["total_opportunities"] >= 2
    assert metrics["won_opportunities"] >= 1
    assert metrics["closed_won_value"] >= 150000000.0

    # Kiểm tra tính toán ROI: ((closed_won_value - actual_cost) / actual_cost) * 100
    actual_cost = metrics["actual_cost"]  # 45,000,000
    expected_roi = round(((metrics["closed_won_value"] - actual_cost) / actual_cost * 100), 2)
    assert metrics["roi"] == expected_roi


def test_campaign_summary_report():
    """Báo cáo tổng hợp hiệu quả toàn bộ chiến dịch marketing."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/campaigns/metrics/summary", headers=headers)
    assert resp.status_code == 200
    report = resp.json()
    assert report["total_campaigns"] >= 2
    assert report["total_budget"] > 0
    assert isinstance(report["campaign_metrics"], list)
    assert len(report["campaign_metrics"]) == report["total_campaigns"]
